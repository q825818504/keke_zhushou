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
from update_protocol import CHANNEL, atomic_json, download_package, fetch_envelope, safe_extract, version
from public_config import validated_config
from update_client import check_window
import diagnostics


def install_root():
    return Path(os.environ['LOCALAPPDATA'])/'Programs'/'KekeAssistant'


def supported_system():
    if os.name!='nt':raise ValueError('安装器支持 Windows 10 / 11 64 位系统')
    import platform
    if sys.getwindowsversion().major<10 or platform.machine().lower() not in ('amd64','x86_64'):
        raise ValueError('请使用 Windows 10 / 11 x64；目前不提供32位或ARM原生安装包')


def recognized_install(root):
    root=Path(root).resolve()
    try:
        marker=json.loads((root/'installation.json').read_text(encoding='utf-8'))
        return marker.get('product')=='koko-assistant' and marker.get('root')==str(root) and (root/'KekeAssistant.exe').is_file()
    except (OSError,ValueError):
        # v1.0's fixed-root installation predates the ownership marker.
        return root==install_root().resolve() and (root/'active-version.json').is_file() and (root/'KekeAssistant.exe').is_file()


def validate_destination(value):
    if not str(value).strip() or not Path(value).is_absolute():raise ValueError('请选择完整的安装目录')
    root=Path(value).resolve()
    protected=[Path(root.anchor),Path.home(),Path(os.environ.get('WINDIR','C:/Windows')),
               Path(os.environ['LOCALAPPDATA']),Path.home()/'Desktop',Path.home()/'Documents']
    if root in [p.resolve() for p in protected]:raise ValueError('请选择专用子文件夹，例如 D:\\Apps\\KekeAssistant')
    if root.exists() and (not root.is_dir() or (any(root.iterdir()) and not recognized_install(root))):
        raise ValueError('此目录已有其他文件，请选择空文件夹或已有的可可助手安装目录')
    return root


def shortcut(root, desktop=False):
    if os.name!='nt':return
    # Resolve redirected/OneDrive Desktop through the shell's known-folder API.
    buffer=ctypes.create_unicode_buffer(32768)
    ctypes.windll.shell32.SHGetFolderPathW(None,0 if desktop else 0x2,None,0,buffer)
    if not buffer.value:raise OSError('无法获取快捷方式目录')
    target=Path(buffer.value)/'可可助手.lnk'
    script="$ErrorActionPreference='Stop'; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($args[0]); $s.TargetPath=$args[1]; $s.WorkingDirectory=$args[2]; $s.IconLocation=$args[3]; $s.Save()"
    command=root/'create-shortcut.ps1';command.write_text(script,encoding='utf-8-sig')
    environment=dict(os.environ);environment.pop('PSModulePath',None)
    selected=json.loads((root/'active-version.json').read_text(encoding='utf-8'))['directory']
    icon=(root/selected/'KekeAssistantApp.exe').resolve()
    if not icon.is_relative_to((root/'app').resolve()):raise ValueError('快捷方式图标路径无效')
    try:subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(command),str(target),str(root/'KekeAssistant.exe'),str(root),str(icon)+',0'],env=environment,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    finally:command.unlink(missing_ok=True)


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


def install_manifest(public_key):
    manifest=fetch_envelope(CHANNEL+'app-latest.json',public_key)
    if manifest.get('kind')!='app' or manifest.get('platform')!='windows-x64':
        raise ValueError('安装清单产品或平台不匹配')
    version(manifest['version'])
    return manifest

def install(root, public_key, progress):
    root=Path(root).resolve()
    manifest=install_manifest(public_key)
    from install_space import require
    space=require(root,manifest)
    progress('空间检查通过，程序文件约 '+str(round(space['expanded']/1024**2))+' MiB')
    root.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        from prerequisites import ensure
        ensure(manifest,root,progress)
    folder=root/'app'/manifest['version']; root.mkdir(parents=True,exist_ok=True)
    staging=root/'app'/('.stage-'+secrets.token_hex(8)); staging.parent.mkdir(parents=True,exist_ok=True)
    archive=root/('download-'+secrets.token_hex(8)+'.zip')
    try:
        download_package(manifest['package'],archive,progress,cache_dir=root/'part-cache')
        progress('正在解压并校验安装内容…')
        safe_extract(archive,staging)
        info=json.loads((staging/'_internal/release-info.json').read_text())
        if info['version']!=manifest['version'] or info.get('revision',0)!=manifest.get('revision',0) or info['public_key']!=public_key or not (staging/'KekeAssistantApp.exe').is_file():
            raise ValueError('安装内容版本或发行身份不一致')
        validated_config(staging/'_internal/public')
        if folder.exists():
            # Retries never merge partial files or overwrite a running version.
            folder=root/'app'/(manifest['version']+'-'+secrets.token_hex(4))
        os.replace(staging,folder)
        launcher=root/'KekeAssistant.exe'
        if not launcher.exists(): shutil.copyfile(sys.executable,launcher)
        atomic_json(root/'installation.json',{'product':'koko-assistant','root':str(root)})
        atomic_json(root/'active-version.json',{'directory':str(folder.relative_to(root)).replace('\\','/'),'version':manifest['version'],'revision':manifest.get('revision',0)})
        archive.unlink(missing_ok=True)
        trim_cache(root/'part-cache')
        if os.name=='nt':
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Uninstall\KokoAssistant') as key:
                for name,value in {'DisplayName':'可可助手','DisplayVersion':manifest['version'],'InstallLocation':str(root),
                                   'UninstallString':'"'+str(launcher)+'" --uninstall'}.items():
                    winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
            try:shortcut(root)
            except Exception:diagnostics.failure('开始菜单快捷方式创建失败')
        return folder
    except BaseException:
        # 失败重试不得把 GB 级 .stage-/下载包留在安装目录旁；成功路径此时两者都已不存在。
        shutil.rmtree(staging,ignore_errors=True)
        archive.unlink(missing_ok=True)
        raise


def launch(root):
    selected=json.loads((root/'active-version.json').read_text())['directory']
    folder=(root/selected).resolve()
    if not folder.is_relative_to((root/'app').resolve()): raise ValueError('安装记录目录无效')
    subprocess.Popen([str(folder/'KekeAssistantApp.exe')],cwd=str(folder),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def trim_cache(cache, limit=400*1024**2):
    """保留最近用过的分块（约两个版本），避免缓存无限增长。"""
    cache=Path(cache)
    try:
        files=sorted((p for p in cache.iterdir() if p.is_file()),key=lambda p:p.stat().st_mtime,reverse=True)
    except OSError:
        return
    total=0
    for path in files:
        try: total+=path.stat().st_size
        except OSError: continue
        if total>limit:
            try: path.unlink()
            except OSError: pass


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--update',action='store_true'); parser.add_argument('--wait-pid',type=int)
    parser.add_argument('--uninstall',action='store_true'); parser.add_argument('--install-root'); args=parser.parse_args()
    diagnostics.initialize('installer');supported_system()
    executable_root=Path(sys.executable).resolve().parent
    root=Path(args.install_root).resolve() if args.install_root else (executable_root if recognized_install(executable_root) else install_root())
    if args.uninstall:
        from tkinter import messagebox
        if not messagebox.askyesno('卸载可可助手','卸载程序？已保存的背包、截图和个人设置将保留。'): return
        if not recognized_install(root):raise ValueError('安装目录身份验证失败，不能卸载')
        # Defer deletion; both Python and PowerShell verify this dedicated installation.
        script=Path(os.environ['LOCALAPPDATA'])/'KekeAssistant'/'uninstall.ps1'; script.parent.mkdir(parents=True,exist_ok=True)
        script.write_text(UNINSTALL_SCRIPT,encoding='utf-8-sig')
        subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script),str(root)],creationflags=subprocess.CREATE_NO_WINDOW); return
    setup='setup' in Path(sys.executable).stem.lower()
    if not args.update and not setup and (root/'active-version.json').exists():
        launch(root); return
    wait_process(args.wait_pid)
    bundle=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    trust=json.loads((bundle/'update-trust.json').read_text())
    if args.update:
        if not recognized_install(root):raise ValueError('更新目标不是已安装的可可助手')
        result=check_window(lambda progress: install(root,trust['public_key'],progress),'可可助手 · 更新')
        if result is not None: launch(root)
    else:
        from installer_wizard import wizard
        wizard(root,trust['public_key'])


UNINSTALL_SCRIPT=r'''param([string]$target)
Start-Sleep -Seconds 3
$target=[IO.Path]::GetFullPath($target)
if($target -eq [IO.Path]::GetPathRoot($target) -or $target -eq $env:USERPROFILE){exit 1}
$marker=Join-Path $target 'installation.json'
$valid=$false
if(Test-Path -LiteralPath $marker){$m=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json; $valid=($m.product -eq 'koko-assistant' -and $m.root -eq $target)}
else {$valid=($target -eq (Join-Path $env:LOCALAPPDATA 'Programs\KekeAssistant') -and (Test-Path -LiteralPath (Join-Path $target 'active-version.json')))}
if(-not $valid -or -not (Test-Path -LiteralPath (Join-Path $target 'KekeAssistant.exe'))){exit 1}
$w=New-Object -ComObject WScript.Shell
foreach($base in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))){
 $link=Join-Path $base '可可助手.lnk'
 if((Test-Path -LiteralPath $link) -and $w.CreateShortcut($link).TargetPath -eq (Join-Path $target 'KekeAssistant.exe')){Remove-Item -LiteralPath $link -Force}
}
Remove-Item -LiteralPath $target -Recurse -Force
$key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\KokoAssistant'
if((Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue).InstallLocation -eq $target){Remove-Item -LiteralPath $key -ErrorAction SilentlyContinue}
'''

if __name__=='__main__':
    try:main()
    except Exception as error:
        diagnostics.failure('安装器失败')
        ctypes.windll.user32.MessageBoxW(None,str(error)+'\n日志：'+str(diagnostics.ROOT),'可可助手安装失败',0x10)
