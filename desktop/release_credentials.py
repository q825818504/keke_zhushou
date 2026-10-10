"""Local Windows DPAPI storage. Secret material never enters a release."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import json
import os
import base64


class Blob(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('发布凭据只支持Windows本机保护')
    buffer = (ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer); output = Blob()
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    if decrypt:
        ok = api.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        ok = api.CryptProtectData(ctypes.byref(source), 'KokoAssistant publishing', None, None, None, 1, ctypes.byref(output))
    if not ok: raise ctypes.WinError(ctypes.get_last_error())
    try: return ctypes.string_at(output.data, output.length)
    finally:
        kernel=ctypes.WinDLL('kernel32'); kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree(output.data)


def secret_path():
    return Path(os.environ['LOCALAPPDATA'])/'KekeAssistant'/'publishing'/'credentials.dpapi'


def read_secrets():
    path=secret_path()
    return json.loads(protect(path.read_bytes(), True)) if path.is_file() else {}


def save_secrets(values):
    from update_protocol import atomic_json
    path=secret_path(); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_bytes(protect(json.dumps(values).encode()))
    os.replace(temporary,path)


def signing_identity(trust):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from update_protocol import atomic_json
    values=read_secrets()
    if 'private_key' not in values:
        if Path(trust).exists():
            raise RuntimeError('本机缺少此发行公钥对应的私钥，请从原维护电脑恢复发布身份')
        key=Ed25519PrivateKey.generate()
        values['private_key']=base64.b64encode(key.private_bytes_raw()).decode()
        save_secrets(values)
    key=Ed25519PrivateKey.from_private_bytes(base64.b64decode(values['private_key']))
    public=base64.b64encode(key.public_key().public_bytes_raw()).decode()
    if Path(trust).exists() and json.loads(Path(trust).read_text())['public_key']!=public:
        raise RuntimeError('本机发布身份与发行公钥不一致')
    atomic_json(trust,{'schema':1,'public_key':public})
    return key
