"""Signed release data, restricted downloads and transactional extraction."""
from pathlib import Path, PurePosixPath
import base64
import hashlib
import json
import os
import re
import secrets
import stat
import urllib.request
from urllib.parse import urlsplit
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PRODUCT = 'koko-assistant'
REPOSITORY = 'Alime17/koko-assistant-update'
CHANNEL = f'https://gitee.com/{REPOSITORY}/raw/main/channels/'
HOSTS = {'gitee.com', 'foruda.gitee.com', 'api.gitee.com', 'raw.giteeusercontent.com'}
BINDINGS = {'characterKnowledge', 'characterOverrides', 'arcDriveKnowledge', 'skyCurtainKnowledge',
            'driverBlockKnowledge', 'teamTemplateKnowledge', 'teamGuideOverrides', 'esperCycleKnowledge'}


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?', value):
        raise ValueError('版本号格式无效')
    values = tuple(map(int, value.split('.')))
    return values + (0,) * (3-len(values))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked_hash(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value):
        raise ValueError('下载校验码格式无效')
    return value


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(8) + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def checked_url(url):
    value = urlsplit(url)
    if value.scheme != 'https' or value.hostname not in HOSTS or value.username or value.password or value.port not in (None, 443):
        raise ValueError('更新下载地址不受信任')
    return url


class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url):
    request = urllib.request.Request(checked_url(url), headers={'User-Agent':'KokoAssistant/1.0', 'Cache-Control':'no-cache'})
    return urllib.request.build_opener(RestrictedRedirect()).open(request, timeout=25)


def fetch_envelope(url, public_key):
    with open_url(url) as response:
        data = response.read(2*1024*1024+1)
    if len(data) > 2*1024*1024:
        raise ValueError('更新清单过大')
    return verify_envelope(json.loads(data), public_key)


def verify_envelope(envelope, public_key):
    payload = base64.b64decode(envelope['payload'], validate=True)
    signature = base64.b64decode(envelope['signature'], validate=True)
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True)).verify(signature, payload)
    document = json.loads(payload)
    if document.get('product') != PRODUCT or document.get('schema') != 1:
        raise ValueError('更新清单产品或格式不匹配')
    return document


def download_package(description, destination, progress=lambda message: None):
    destination = Path(destination)
    temporary = destination.with_suffix('.partial')
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = description['size']
    checked_hash(description['sha256'])
    if type(expected) is not int or not 0 < expected <= 2*1024**3:
        raise ValueError('更新包大小无效')
    if not isinstance(description['parts'],list) or not 1<=len(description['parts'])<=32:
        raise ValueError('更新分块数量无效')
    total = 0
    try:
        with temporary.open('wb') as output:
            for index, part in enumerate(description['parts']):
                count = 0; checksum = hashlib.sha256()
                checked_hash(part['sha256'])
                if type(part['size']) is not int or not 0 < part['size'] <= 100_000_000:
                    raise ValueError('更新分块大小无效')
                with open_url(part['url']) as stream:
                    while chunk := stream.read(1024*1024):
                        count += len(chunk); total += len(chunk)
                        if count > part['size'] or total > expected:
                            raise ValueError('下载大小超过清单声明')
                        checksum.update(chunk); output.write(chunk)
                        progress(f'正在下载 {index+1}/{len(description["parts"])}：{total//1024**2}/{expected//1024**2} MB')
                if count != part['size'] or checksum.hexdigest() != part['sha256']:
                    raise ValueError('下载分块不完整或校验失败')
        if total != expected or digest(temporary) != description['sha256']:
            raise ValueError('更新包校验失败')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def safe_extract(archive, directory, config_only=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as source:
        names = set(); expanded = 0
        for item in source.infolist():
            relative = PurePosixPath(item.filename)
            parts = tuple(item.filename.rstrip('/').split('/'))
            if not parts or '\\' in item.orig_filename or relative.is_absolute() or any(
                p in {'.','..'} or re.search(r'[<>:"|?*\x00-\x1f]', p) or p.endswith(('.', ' '))
                or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts):
                raise ValueError('更新包路径无效')
            name = str(relative).casefold()
            if name in names or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('更新包含重复路径或符号链接')
            names.add(name); expanded += item.file_size
            if len(names)>15000 or expanded > 3*1024**3:
                raise ValueError('更新包解压大小超出限制')
            target = directory.joinpath(*parts)
            if not target.resolve().is_relative_to(directory):
                raise ValueError('更新包路径越界')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True); continue
            if config_only and (target.suffix.lower() not in {'.json','.png','.webp','.jpg','.jpeg','.gif','.svg','.txt'}
                                or not (item.filename=='config.json' or item.filename.startswith('data/'))):
                raise ValueError('公共配置包含非数据文件')
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(item) as data, target.open('wb') as output:
                import shutil
                shutil.copyfileobj(data, output)


def load_config(directory):
    document = json.loads((Path(directory)/'config.json').read_text(encoding='utf-8'))
    bindings = document.get('bindings')
    if document.get('schema') != 1 or not isinstance(bindings, dict) or set(bindings)!=BINDINGS:
        raise ValueError('公共配置格式无效')
    if not isinstance(bindings.get('characterKnowledge'),dict) or not bindings['characterKnowledge']:
        raise ValueError('公共角色配置缺失')
    if any(not isinstance(v,(dict,list)) for v in bindings.values()):
        raise ValueError('公共配置数据类型无效')
    return document
