"""Redistributable runtime detection and signed-release prerequisite installation."""
from pathlib import Path
import os
import subprocess
from update_protocol import download_package

DOWNLOADS={
    'webview2':('MicrosoftEdgeWebView2RuntimeInstallerX64.exe','https://go.microsoft.com/fwlink/p/?LinkId=2124701'),
    'vcredist':('VC_redist.x64.exe','https://aka.ms/vc14/vc_redist.x64.exe')}


def present(name):
    if os.name!='nt': return False
    import winreg
    locations={
        'webview2':[(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}','pv'),
                    (winreg.HKEY_CURRENT_USER,r'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}','pv')],
        'vcredist':[(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64','Installed')]}
    for hive,path,value in locations[name]:
        try:
            with winreg.OpenKey(hive,path,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                result=winreg.QueryValueEx(key,value)[0]
                if result and result!='0.0.0.0':
                    if name=='vcredist':
                        system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
                        if not all((system/n).is_file() for n in ('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll')):continue
                    return True
        except OSError: pass
    return False


def ensure(manifest,root,progress):
    for name in DOWNLOADS:
        if present(name): continue
        meta=manifest.get('prerequisites',{}).get(name)
        if not meta: raise RuntimeError('发行清单缺少必要运行组件：'+name)
        progress('正在准备运行组件：'+name)
        installer=Path(root)/DOWNLOADS[name][0]
        download_package(meta,installer,progress)
        args=['/silent','/install'] if name=='webview2' else ['/install','/passive','/norestart']
        result=subprocess.run([str(installer),*args],timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode not in (0,3010,1638) or not present(name):
            raise RuntimeError('运行组件安装未完成，请处理系统安装提示后重试：'+name)
        installer.unlink(missing_ok=True)
