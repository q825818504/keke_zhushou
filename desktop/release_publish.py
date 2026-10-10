"""Publish audited artifacts to a dedicated Gitee release repository."""
from pathlib import Path
import argparse
import base64
import hashlib
import json
import os
import subprocess
import threading
from datetime import datetime, timezone
import requests
from release_credentials import read_secrets, save_secrets, signing_identity
from update_protocol import PRODUCT, REPOSITORY, atomic_json, checked_url, digest, open_url

LOCK=threading.Lock()
API=f'https://gitee.com/api/v5/repos/{REPOSITORY}'
REMOTE=f'https://gitee.com/{REPOSITORY}.git'


def configure(token):
    if not isinstance(token,str) or not 10<=len(token.strip())<=512 or any(c.isspace() for c in token.strip()):
        raise ValueError('请输入Gitee个人访问令牌，仅保存在这台电脑')
    token=token.strip()
    def get(url,**kwargs):
        try:
            response=requests.get(url,headers={'Authorization':'Bearer '+token},timeout=(8,15),**kwargs)
        except requests.RequestException:
            raise RuntimeError('连接Gitee失败，令牌未保存。请检查网络后重试。') from None
        if response.status_code==401:
            raise RuntimeError('Gitee令牌无效或已过期，令牌未保存。请重新生成私人令牌。')
        if response.status_code==403:
            raise RuntimeError('Gitee拒绝授权，令牌未保存。请确认勾选了 projects 权限。')
        if response.status_code!=200:
            raise RuntimeError('Gitee授权检查失败，令牌未保存：HTTP '+str(response.status_code))
        try:return response.json()
        except ValueError:raise RuntimeError('Gitee返回的内容无效，令牌未保存。请稍后重试。') from None
    repository=get(API)
    if not isinstance(repository,dict) or repository.get('full_name','').casefold()!=REPOSITORY.casefold():
        raise RuntimeError('Gitee返回的发布仓库不匹配，令牌未保存。')
    permissions=repository.get('permissions') or {}
    writable=permissions.get('push') or permissions.get('admin')
    if not writable:
        # Gitee may omit GitHub-style permissions. Authenticated owner-only listing
        # proves ownership and projects scope without requiring user_info access.
        for page in range(1,11):
            owned=get('https://gitee.com/api/v5/user/repos',params={'type':'owner','per_page':100,'page':page})
            if not isinstance(owned,list):raise RuntimeError('Gitee仓库授权响应无效，令牌未保存。')
            writable=any(isinstance(repo,dict) and repo.get('full_name','').casefold()==REPOSITORY.casefold() for repo in owned)
            if writable or len(owned)<100:break
    if not writable:
        raise RuntimeError('当前令牌不属于发布仓库的所有者或没有写入权限，令牌未保存。')
    values=read_secrets(); values['gitee_token']=token.strip(); save_secrets(values)
    return {'ok':True,'configured':True,'message':'发布令牌已保存，Gitee仓库权限验证通过。尚未上传发行文件。'}


class Gitee:
    def __init__(self,token): self.headers={'Authorization':'Bearer '+token,'Accept':'application/json'}
    def request(self,method,path,**kwargs):
        timeout=kwargs.pop('timeout',(20,300))
        response=requests.request(method,API+path,headers=self.headers,timeout=timeout,**kwargs)
        if response.status_code not in (200,201):
            raise RuntimeError('Gitee发布操作失败：HTTP '+str(response.status_code))
        return response.json()
    def upload(self,release_id,path):
        with path.open('rb') as stream:
            # urllib3 uses the connect timeout during a non-streaming multipart write.
            # Large release parts need a longer write deadline than a metadata request.
            result=self.request('POST',f'/releases/{release_id}/attach_files',timeout=(300,300),files={'file':(path.name,stream,'application/octet-stream')})
        if isinstance(result,list): result=result[0]
        url=result.get('browser_download_url') or result.get('download_url') or result.get('url')
        if not url: raise RuntimeError('Gitee未返回可用的附件下载地址')
        return checked_url(url)


def signed(document,key):
    payload=json.dumps(document,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()
    return {'payload':base64.b64encode(payload).decode(),'signature':base64.b64encode(key.sign(payload)).decode()}


def verify_download(url,path):
    count=0; checksum=hashlib.sha256()
    with open_url(url) as stream:
        while chunk:=stream.read(1024*1024):
            count+=len(chunk)
            if count>path.stat().st_size: raise RuntimeError('匿名附件下载返回了错误内容')
            checksum.update(chunk)
    if count!=path.stat().st_size or checksum.hexdigest()!=digest(path):
        raise RuntimeError('附件不能匿名完整下载，未切换线上版本')


def git(workspace,*args,token=None):
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
    env={name:value for name,value in env.items() if not name.startswith('GIT_TRACE')}
    if token:
        env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.https://gitee.com/.extraheader',
                   GIT_CONFIG_VALUE_0='Authorization: Basic '+base64.b64encode(('oauth2:'+token).encode()).decode())
    result=subprocess.run(['git','-c','safe.directory='+Path(workspace).resolve().as_posix(),*args],cwd=workspace,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
    if result.returncode:
        error=result.stderr[-500:]
        if token:
            error=error.replace(token,'[redacted]').replace(env['GIT_CONFIG_VALUE_0'],'[redacted]')
        raise RuntimeError('Git发布操作失败：'+error)
    return result.stdout.strip()


def audit_files(output,artifacts):
    selected=[]
    for package in (artifacts['config_package'],artifacts.get('app_package'),*artifacts.get('prerequisites',{}).values()):
        if package:
            for part in package['parts']:
                path=output/part['name']
                if path.parent!=output or not path.name.endswith('.part') or path.stat().st_size!=part['size'] or digest(path)!=part['sha256']:
                    raise ValueError('发行分块清单校验失败')
                selected.append(path)
    if 'installer' in artifacts:
        meta=artifacts['installer']; path=output/meta['name']
        if path.parent!=output or not path.name.startswith('KokoAssistantSetup-v') or path.suffix!='.exe' or digest(path)!=meta['sha256'] or path.stat().st_size!=meta['size']:
            raise ValueError('联网安装器清单校验失败')
        selected.append(path)
    if any(p.stat().st_size>100_000_000 for p in selected): raise ValueError('发行附件超过Gitee限制')
    return selected


def publish(root,output):
    root=Path(root).resolve(); output=Path(output).resolve()
    if not output.is_relative_to(root/'dist/windows/releases'): raise ValueError('只允许发布专用发行产物目录')
    if not LOCK.acquire(blocking=False): raise RuntimeError('另一项发布任务正在运行')
    try:
        values=read_secrets(); token=values.get('gitee_token')
        if not token: raise RuntimeError('请先设置本机Gitee发布凭据')
        artifacts=json.loads((output/'release-artifacts.json').read_text(encoding='utf-8'))
        files=audit_files(output,artifacts); key=signing_identity(root/'desktop/update-trust.json')
        store=root/'build/gitee-publish'; store.parent.mkdir(parents=True,exist_ok=True)
        if not (store/'.git').exists():
            store.mkdir(exist_ok=True); git(store,'init','-b','main'); git(store,'remote','add','origin',REMOTE)
        if git(store,'remote','get-url','origin')!=REMOTE: raise RuntimeError('发布仓库远端不匹配')
        refs=git(store,'ls-remote','origin','refs/heads/main',token=token)
        if refs:
            git(store,'pull','--ff-only','origin','main',token=token)
        state=json.loads((root/'desktop/release-state.json').read_text(encoding='utf-8'))
        from update_protocol import verify_envelope, fetch_envelope, CHANNEL
        public_key=base64.b64encode(key.public_key().public_bytes_raw()).decode()
        remote_app=remote_config=None
        # Read fetched remote history, not a local commit left by an interrupted push.
        if refs:
            names=git(store,'ls-tree','-r','--name-only','origin/main').splitlines()
            for name in ('app','config'):
                path=f'channels/{name}-latest.json'
                if path in names:
                    remote=verify_envelope(json.loads(git(store,'show','origin/main:'+path)),public_key)
                    if name=='app':remote_app=remote
                    else:remote_config=remote
        already=bool(remote_config and remote_config['revision']==artifacts['config_revision'] and remote_config['package']['sha256']==artifacts['config_package']['sha256'])
        if 'app_package' in artifacts:
            already=already and bool(remote_app and remote_app['version']==artifacts['version'] and remote_app['package']['sha256']==artifacts['app_package']['sha256'])
        if already:
            for name,expected in (('config',remote_config),('app',remote_app)):
                if expected:
                    actual=fetch_envelope(CHANNEL+name+'-latest.json',public_key)
                    if actual['package']['sha256']!=expected['package']['sha256']:raise RuntimeError('线上清单尚未可用，请重试')
            if 'app_package' in artifacts:state['last_published']=artifacts['version']
            state['config_revision']=artifacts['config_revision'];state['config_hash']=artifacts['config_package']['sha256'];atomic_json(root/'desktop/release-state.json',state)
            return {'ok':True,'message':'已确认先前完成的发行，恢复本地发行记录'}
        if remote_app and state['last_published']!=remote_app['version']:
            raise RuntimeError('远端正式版本已变化，请先同步发行记录')
        if remote_config and artifacts['config_revision']<=remote_config['revision']:
            raise RuntimeError('配置发行编号已使用，请同步发行记录后重新准备')
        (store/'README.md').write_text('# 可可助手更新服务\n\n只发布安装器、程序更新包、公共配置和签名清单；源码维护在GitHub。\n',encoding='utf-8')
        tracked=git(store,'ls-files').splitlines()
        if any(not (p=='README.md' or (p.startswith(('channels/','metadata/')) and Path(p).suffix=='.json') or (p.startswith('licenses/') and Path(p).suffix in {'.txt','.md'})) for p in tracked):
            raise RuntimeError('Gitee发布仓库包含白名单之外的文件，请人工核对')
        if not refs:
            git(store,'add','README.md'); git(store,'-c','user.name=Koko Assistant Publisher','-c','user.email=release@koko.local','commit','-m','Initialize release-only repository')
            git(store,'push','origin','main',token=token)
        api=Gitee(token)
        tag='v'+artifacts['version'] if 'app_package' in artifacts else 'config-r'+str(artifacts['config_revision'])
        releases=api.request('GET','/releases',params={'per_page':100})
        release=next((r for r in releases if r['tag_name']==tag),None)
        if release is None:
            release=api.request('POST','/releases',json={'tag_name':tag,'target_commitish':'main','name':'可可助手 '+tag,'body':'官方程序与公共配置发行产物。','prerelease':False})
        # Existing valid attachments are reused on retries; never update latest before anonymous checks pass.
        detail=api.request('GET',f'/releases/{release["id"]}')
        raw_assets=detail.get('assets',[])
        assets=raw_assets.get('links',[]) if isinstance(raw_assets,dict) else raw_assets if isinstance(raw_assets,list) else []
        index_file=store/'metadata/downloads.json'
        download_index=json.loads(index_file.read_text(encoding='utf-8')) if index_file.exists() else {}
        receipt_file=output/'upload-receipts.json'
        receipts=json.loads(receipt_file.read_text(encoding='utf-8')) if receipt_file.exists() else {}
        urls={}
        for path in files:
            matched=next((a for a in assets if a.get('name')==path.name),None)
            checksum=digest(path)
            url=download_index.get(checksum,{}).get('url') or receipts.get(path.name,{}).get('url')
            if not url and matched:url=matched.get('browser_download_url') or matched.get('url')
            if not url: url=api.upload(release['id'],path)
            verify_download(url,path); urls[path.name]=url
            receipts[path.name]={'url':url,'sha256':checksum};atomic_json(receipt_file,receipts)
            download_index[checksum]={'url':url,'size':path.stat().st_size,'name':path.name}
            atomic_json(index_file,download_index)
        now=datetime.now(timezone.utc).isoformat()
        base={'product':PRODUCT,'schema':1,'published_at':now}
        def package(meta):
            return {**meta,'parts':[{**part,'url':urls[part['name']]} for part in meta['parts']]}
        config={**base,'kind':'config','config_schema':1,'revision':artifacts['config_revision'],'package':package(artifacts['config_package'])}
        atomic_json(store/'channels/config-latest.json',signed(config,key))
        atomic_json(store/f'metadata/config/r{config["revision"]}.json',signed(config,key))
        if 'app_package' in artifacts:
            app={**base,'kind':'app','platform':'windows-x64','version':artifacts['version'],
                 'package':package(artifacts['app_package']),'installer':{**artifacts['installer'],'url':urls[artifacts['installer']['name']]},
                 'prerequisites':{name:package(meta) for name,meta in artifacts.get('prerequisites',{}).items()}}
            atomic_json(store/'channels/app-latest.json',signed(app,key))
            atomic_json(store/f'metadata/app/v{app["version"]}.json',signed(app,key))
        git(store,'add','--','README.md','channels','metadata')
        if git(store,'diff','--cached','--name-only'):
            git(store,'-c','user.name=Koko Assistant Publisher','-c','user.email=release@koko.local','commit','-m','Publish '+tag)
        git(store,'push','origin','main',token=token)
        # A remotely available manifest is the commit point for the official version record.
        from update_protocol import fetch_envelope, CHANNEL
        published=fetch_envelope(CHANNEL+('app-latest.json' if 'app_package' in artifacts else 'config-latest.json'),base64.b64encode(key.public_key().public_bytes_raw()).decode())
        if 'app_package' in artifacts and published['version']!=artifacts['version']: raise RuntimeError('远端版本验证失败')
        configuration=fetch_envelope(CHANNEL+'config-latest.json',base64.b64encode(key.public_key().public_bytes_raw()).decode())
        if configuration['revision']!=config['revision'] or configuration['package']['sha256']!=artifacts['config_package']['sha256']:
            raise RuntimeError('远端配置清单验证失败，发行记录未更新')
        if 'app_package' in artifacts: state['last_published']=artifacts['version']
        state['config_revision']=config['revision'];state['config_hash']=artifacts['config_package']['sha256']; atomic_json(root/'desktop/release-state.json',state)
        return {'ok':True,'message':'已发布 '+tag+'，所有下载内容已通过匿名校验'}
    finally: LOCK.release()


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('directory'); args=parser.parse_args()
    print(json.dumps(publish(Path(__file__).resolve().parents[1],args.directory),ensure_ascii=False))
