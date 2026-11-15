"""Post-render housekeeping; only verified, owned release directories are removed."""
from pathlib import Path
import json
import re
import shutil
import os
import diagnostics
from update_protocol import atomic_json

def cleanup_versions(executable, frozen=False):
    if not frozen:
        return
    current=Path(executable).resolve().parent
    app=current.parent; root=app.parent
    if app.name!='app' or current.name.startswith('.'):
        return
    from installer_entry import recognized_install
    if not recognized_install(root):
        return
    pointer=json.loads((root/'active-version.json').read_text(encoding='utf-8'))
    if (root/pointer['directory']).resolve()!=current:
        return
    helper=current/'_internal/update-helper.exe'
    if helper.is_file():
        try:
            temporary=root/'launcher-next.exe'
            shutil.copyfile(helper,temporary);os.replace(temporary,root/'KekeAssistant.exe')
            from installer_entry import shortcut
            shortcut(root)
            import ctypes
            buffer=ctypes.create_unicode_buffer(32768)
            ctypes.windll.shell32.SHGetFolderPathW(None,0,None,0,buffer)
            if buffer.value and (Path(buffer.value)/'可可助手.lnk').is_file():shortcut(root,desktop=True)
        except OSError:diagnostics.failure('启动入口图标更新未完成，下次启动重试')
    for folder in app.iterdir():
        if folder==current or not re.fullmatch(r'\d+\.\d+(?:\.\d+)?(?:-[0-9a-f]{8})?',folder.name):
            continue
        if folder.is_symlink() or folder.is_junction() or not folder.is_dir():
            continue
        if not (folder/'KekeAssistantApp.exe').is_file() or not (folder/'_internal/release-info.json').is_file():
            continue
        try:
            info=json.loads((folder/'_internal/release-info.json').read_text(encoding='utf-8'))
            if not folder.name.startswith(str(info['version'])):
                continue
            # Reject nested links too; never follow a junction into personal data.
            if any(p.is_symlink() or p.is_junction() for p in folder.rglob('*')):
                continue
            shutil.rmtree(folder)
            diagnostics.event('清理旧程序版本',version=info['version'])
        except (OSError,ValueError,KeyError):
            diagnostics.failure('旧程序目录清理未完成，将在下次启动重试')

def cleanup_config(root, current):
    root=Path(root).resolve(); current=Path(current).resolve()
    if current.parent!=root:
        return
    for entry in root.iterdir():
        if entry==current or entry.name=='current.json' or entry.is_symlink() or entry.is_junction():
            continue
        if not re.fullmatch(r'r\d+-[0-9a-f]{16}(?:-[0-9a-f]{8})?(?:\.zip)?',entry.name):
            continue
        try:
            if entry.is_file():entry.unlink()
            elif entry.is_dir() and not any(p.is_symlink() or p.is_junction() for p in entry.rglob('*')):shutil.rmtree(entry)
        except OSError:diagnostics.failure('旧配置缓存清理未完成')


def cleanup_assets(root, keep):
    """保留当前图片缓存，删除更早的 assets 目录与残留临时包。"""
    root=Path(root).resolve(); keep=Path(keep).resolve()
    if keep.parent!=root:
        return
    for entry in root.iterdir():
        if entry==keep or entry.is_symlink() or entry.is_junction():
            continue
        if not re.fullmatch(r'[0-9a-f]{16}|\.(?:stage|assets)-[0-9a-f]+(?:\.zip)?',entry.name):
            continue
        try:
            if entry.is_file():entry.unlink()
            elif entry.is_dir() and not any(p.is_symlink() or p.is_junction() for p in entry.rglob('*')):shutil.rmtree(entry)
        except OSError:diagnostics.failure('旧配置图片缓存清理未完成')

def release_status(public_root, app_data):
    try:
        notes=json.loads((Path(public_root)/'release-notes.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {'version':None,'notes':'','show':False}
    try:seen=json.loads((Path(app_data)/'release-seen.json').read_text(encoding='utf-8'))['version']
    except (OSError,ValueError,KeyError):seen=None
    try:seen_revision=json.loads((Path(app_data)/'release-seen.json').read_text(encoding='utf-8')).get('revision',0)
    except (OSError,ValueError):seen_revision=0
    try:history=json.loads((Path(public_root)/'release-history.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):history=[{'version':notes['version'],'notes':notes['notes']}]
    from cloud_notes import cached
    cloud=cached(app_data,notes['version'])
    if cloud:
        history=cloud
        notes['notes']=next(row['notes'] for row in cloud if row['version']==notes['version'])
    return {**notes,'history':history,'show':seen!=notes['version'] or seen_revision!=notes.get('revision',0)}

def acknowledge(public_root, app_data):
    notes=release_status(public_root,app_data)
    if notes['version']:atomic_json(Path(app_data)/'release-seen.json',{'version':notes['version'],'revision':notes.get('revision',0)})
