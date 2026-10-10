"""Standalone online installer/installed launcher; no source or publishing credentials."""
from pathlib import Path
import argparse
import ctypes
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from update_protocol import CHANNEL, atomic_json, download_package, fetch_envelope, safe_extract, version
from public_config import validated_config
from update_client import check_window


def install_root():
    return Path(os.environ['LOCALAPPDATA'])/'Programs'/'KekeAssistant'


def wait_process(pid):
    if not pid: return
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    handle=kernel.OpenProcess(0x100000,False,pid)
    if not handle: return
    try:
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        if kernel.WaitForSingleObject(handle,60000)!=0:
            raise RuntimeError('助手仍在运行，请关闭后重试更新')
    finally:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]; kernel.CloseHandle(handle)


def install(root, public_key, progress):
    root=Path(root).resolve()
    manifest=fetch_envelope(CHANNEL+'app-latest.json',public_key)
    if manifest.get('kind')!='app' or manifest.get('platform')!='windows-x64':
        raise ValueError('安装清单产品或平台不匹配')
    version(manifest['version'])
    if os.name=='nt':
        from prerequisites import ensure
        ensure(manifest,root,progress)
    folder=root/'app'/manifest['version']; root.mkdir(parents=True,exist_ok=True)
    staging=root/'app'/('.stage-'+secrets.token_hex(8)); staging.parent.mkdir(parents=True,exist_ok=True)
    archive=root/('download-'+secrets.token_hex(8)+'.zip')
    download_package(manifest['package'],archive,progress)
    progress('正在解压并校验安装内容…')
    safe_extract(archive,staging)
    info=json.loads((staging/'_internal/release-info.json').read_text())
    if info['version']!=manifest['version'] or info['public_key']!=public_key or not (staging/'KekeAssistantApp.exe').is_file():
        raise ValueError('安装内容版本或发行身份不一致')
    validated_config(staging/'_internal/public')
    if folder.exists():
        # Retries never merge partial files or overwrite a running version.
        folder=root/'app'/(manifest['version']+'-'+secrets.token_hex(4))
    os.replace(staging,folder)
    launcher=root/'KekeAssistant.exe'
    if not launcher.exists(): shutil.copyfile(sys.executable,launcher)
    atomic_json(root/'active-version.json',{'directory':str(folder.relative_to(root)).replace('\\','/'),'version':manifest['version']})
    archive.unlink(missing_ok=True)
    if os.name=='nt':
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\KokoAssistant') as key:
            for name,value in {'DisplayName':'可可助手','DisplayVersion':manifest['version'],'InstallLocation':str(root),
                               'UninstallString':'"'+str(launcher)+'" --uninstall'}.items():
                winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
        # Paths are parameters to a static PowerShell program; never build shell code from them.
        script="$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($args[0]); $s.TargetPath=$args[1]; $s.WorkingDirectory=$args[2]; $s.Save()"
        shortcut=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/可可助手.lnk'
        command=root/'create-shortcut.ps1'; command.write_text(script,encoding='utf-8-sig')
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(command),str(shortcut),str(launcher),str(root)],creationflags=subprocess.CREATE_NO_WINDOW)
        command.unlink(missing_ok=True)
    return folder


def launch(root):
    selected=json.loads((root/'active-version.json').read_text())['directory']
    folder=(root/selected).resolve()
    if not folder.is_relative_to((root/'app').resolve()): raise ValueError('安装记录目录无效')
    subprocess.Popen([str(folder/'KekeAssistantApp.exe')],cwd=str(folder),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--update',action='store_true'); parser.add_argument('--wait-pid',type=int)
    parser.add_argument('--uninstall',action='store_true'); args=parser.parse_args()
    root=install_root()
    if args.uninstall:
        from tkinter import messagebox
        if not messagebox.askyesno('卸载可可助手','卸载程序？已保存的背包、截图和个人设置将保留。'): return
        # Defer deletion of the running launcher. LiteralPath operations stay in the fixed install root.
        script=Path(os.environ['LOCALAPPDATA'])/'KekeAssistant'/'uninstall.ps1'; script.parent.mkdir(parents=True,exist_ok=True)
        script.write_text("param([string]$target)\nStart-Sleep -Seconds 3\n$expected=Join-Path $env:LOCALAPPDATA 'Programs\\KekeAssistant'\nif([IO.Path]::GetFullPath($target) -ne [IO.Path]::GetFullPath($expected)){exit 1}\nRemove-Item -LiteralPath $target -Recurse -Force\nRemove-Item -LiteralPath 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\KokoAssistant' -ErrorAction SilentlyContinue\nRemove-Item -LiteralPath (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\可可助手.lnk') -ErrorAction SilentlyContinue\n",encoding='utf-8-sig')
        subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(root)],creationflags=subprocess.CREATE_NO_WINDOW); return
    setup='setup' in Path(sys.executable).stem.lower()
    if not args.update and not setup and (root/'active-version.json').exists():
        launch(root); return
    wait_process(args.wait_pid)
    bundle=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    trust=json.loads((bundle/'update-trust.json').read_text())
    result=check_window(lambda progress: install(root,trust['public_key'],progress),'可可助手 · 联网安装')
    if result is not None: launch(root)


if __name__=='__main__': main()
