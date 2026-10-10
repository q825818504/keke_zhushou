"""One required application check per startup; optional atomic config refresh."""
from pathlib import Path
import json
import os
import secrets
import subprocess
import sys
from update_protocol import CHANNEL, atomic_json, checked_hash, download_package, fetch_envelope, safe_extract, version
from public_config import validated_config


def refresh_config(app_data, public_key, fallback, progress, fetch=fetch_envelope):
    root=Path(app_data)/'public-config'; root.mkdir(parents=True,exist_ok=True)
    pointer=root/'current.json'; current=None
    try:
        name=json.loads(pointer.read_text())['directory']
        current=(root/name).resolve()
        if not current.is_relative_to(root.resolve()): raise ValueError('配置缓存目录无效')
        validated_config(current)
    except Exception:
        current=None
    try:
        progress('正在检查公共配置…')
        manifest=fetch(CHANNEL+'config-latest.json',public_key)
        if manifest.get('kind')!='config' or type(manifest.get('revision')) is not int or manifest['revision']<1 or manifest.get('config_schema')!=1:
            raise ValueError('配置更新清单无效')
        checked_hash(manifest['package']['sha256'])
        if current and manifest['revision']<json.loads(pointer.read_text())['revision']:
            raise ValueError('拒绝回退到旧版公共配置')
        name=f'r{manifest["revision"]}-{manifest["package"]["sha256"][:16]}'
        candidate=root/name
        if current!=candidate:
            archive=root/(name+'.zip')
            download_package(manifest['package'],archive,progress)
            staging=root/('.stage-'+secrets.token_hex(8))
            safe_extract(archive,staging,config_only=True)
            validated_config(staging)
            if candidate.exists():
                validated_config(candidate)
            else:
                os.replace(staging,candidate)
            atomic_json(pointer,{'directory':name,'revision':manifest['revision']})
        return candidate, None
    except Exception as error:
        selected=current or Path(fallback)
        validated_config(selected)
        return selected, '配置更新未完成，使用本地配置。'+str(error)


def startup_check(current_version, app_data, public_key, fallback, progress, fetch=fetch_envelope):
    progress('正在检查程序版本…')
    manifest=fetch(CHANNEL+'app-latest.json',public_key)
    if manifest.get('kind')!='app' or manifest.get('platform')!='windows-x64':
        raise ValueError('程序更新清单不匹配')
    remote=version(manifest.get('version')); local=version(current_version)
    ledger=Path(app_data)/'highest-version.json'
    if ledger.exists() and remote<version(json.loads(ledger.read_text())['version']):
        raise ValueError('拒绝回退到已发现版本之前的程序')
    atomic_json(ledger,{'version':manifest['version']})
    if local<remote:
        return {'update':manifest}
    if local>remote:
        raise ValueError('本机程序版本不属于当前正式发行，请重新安装官方最新版')
    folder,warning=refresh_config(app_data,public_key,fallback,progress,fetch)
    return {'config':folder,'warning':warning}


def check_window(operation, title='可可助手 · 启动检查'):
    import queue
    import threading
    import tkinter as tk
    from tkinter import ttk
    events=queue.Queue(); result={}; running=False
    window=tk.Tk(); window.title(title); window.geometry('560x270'); window.resizable(False,False)
    window.configure(bg='#f7f7fa')
    tk.Label(window,text='可可助手',font=('Microsoft YaHei UI',21,'bold'),bg='#f7f7fa').pack(pady=(24,12))
    label=tk.Label(window,text='准备检查…',wraplength=500,font=('Microsoft YaHei UI',11),bg='#f7f7fa',fg='#34465f')
    label.pack(padx=25,pady=10)
    spinner=ttk.Progressbar(window,mode='indeterminate',length=450); spinner.pack(pady=10)
    actions=tk.Frame(window,bg='#f7f7fa'); actions.pack(pady=12)
    def start():
        nonlocal running
        if running: return
        running=True; button.configure(state='disabled'); spinner.start(15)
        def work():
            try: events.put(('done',operation(lambda message: events.put(('progress',message)))))
            except Exception as error: events.put(('error',str(error)))
        threading.Thread(target=work,daemon=True).start()
    button=ttk.Button(actions,text='重试',command=start); button.pack(side='left',padx=10)
    ttk.Button(actions,text='退出',command=window.destroy).pack(side='left',padx=10)
    def poll():
        nonlocal running
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='done': result['value']=value; window.destroy(); return
                if kind=='error':
                    running=False; spinner.stop(); button.configure(state='normal')
                    label.configure(text='无法完成更新检查，请检查网络后重试。\n'+value,fg='#a43b43')
                else: label.configure(text=value,fg='#34465f')
        except queue.Empty: pass
        window.after(100,poll)
    window.after(50,start); window.after(100,poll); window.mainloop()
    return result.get('value')


def gate(info, public_root, app_data):
    result=check_window(lambda progress: startup_check(info['version'],app_data,info['public_key'],public_root,progress))
    if result is None: return None
    if 'update' in result:
        install_root=Path(sys.executable).resolve().parents[2]
        helper=Path(getattr(sys,'_MEIPASS',install_root))/'update-helper.exe'
        if not helper.is_file(): raise RuntimeError('联网更新入口缺失，请重新运行安装器')
        subprocess.Popen([str(helper),'--update','--wait-pid',str(os.getpid())],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return None
    return result
