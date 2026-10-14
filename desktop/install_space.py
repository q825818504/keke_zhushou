"""Signed package sizes and per-volume installation peak-space checks."""
from pathlib import Path
import os
import shutil
import tempfile

MiB=1024**2

def format_size(size):
    return f'{size/1024**3:.2f} GiB' if size>=1024**3 else f'{size/MiB:.0f} MiB'

def package_size(package):
    size=package.get('size')
    if type(size) is not int or not 0<size<=2*1024**3:raise ValueError('发行包大小无效')
    return size

def expanded_size(package):
    size=package.get('expanded_size')
    if size is None:return max(package_size(package)*4,512*MiB),True
    if type(size) is not int or not 0<size<=3*1024**3:raise ValueError('程序解压大小无效')
    return size,False

def existing_parent(path):
    path=Path(path).resolve()
    while not path.exists():path=path.parent
    return path

def inspect(root,manifest,present=None):
    if present is None:
        from prerequisites import present
    root=Path(root).resolve();package=manifest['package']
    expanded,estimated=expanded_size(package)
    required=package_size(package)+expanded+96*MiB
    budgets={}
    def add(path,size):
        ancestor=existing_parent(path);key=os.path.normcase(ancestor.anchor)
        row=budgets.setdefault(key,{'path':str(ancestor),'required':0})
        row['required']+=size
    missing=[]
    # Prerequisites are installed serially before the application download.
    runtime_download=0;runtime_system=0
    for name in ('webview2','vcredist'):
        if present(name):continue
        meta=manifest.get('prerequisites',{}).get(name)
        if not meta:raise ValueError('发行清单缺少必要运行组件：'+name)
        missing.append(name);runtime_download=max(runtime_download,package_size(meta))
        runtime_system+=768*MiB if name=='webview2' else 64*MiB
    add(root,max(required,runtime_download+96*MiB))
    if missing:
        add(Path(os.environ.get('SystemRoot',Path.home().anchor)),runtime_system)
        add(Path(tempfile.gettempdir()),max(runtime_download,128*MiB))
    for row in budgets.values():
        row['free']=shutil.disk_usage(row['path']).free
        row['ok']=row['free']>=row['required']
    return {'expanded':expanded,'download':package_size(package),'estimated':estimated,
            'missing':missing,'volumes':list(budgets.values()),'ok':all(r['ok'] for r in budgets.values())}

def require(root,manifest):
    result=inspect(root,manifest)
    for row in result['volumes']:
        if not row['ok']:
            raise ValueError(f'磁盘空间不足：{Path(row["path"]).anchor}需 {format_size(row["required"])}，可用 {format_size(row["free"])}。请选择其他位置或释放空间。')
    return result
