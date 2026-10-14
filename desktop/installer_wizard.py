"""Location -> installation progress -> explicit completion choices."""
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

def wizard(default,public_key,install_operation=None,manifest_loader=None):
    from installer_entry import install, launch, shortcut, validate_destination,install_manifest
    from install_space import inspect,require,format_size
    import diagnostics
    import ctypes
    try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError,OSError):pass
    operation=install_operation or install
    window=tk.Tk();window.title('可可助手 · 安装向导')
    scale=max(1,window.winfo_fpixels('1i')/96)
    window.geometry(f'{int(700*scale)}x{int(550*scale)}');window.resizable(False,False)
    from window_brand import apply,BG
    apply(window)
    steps=ttk.Label(window,text='安装位置  →  下载与安装  →  完成',foreground='#53596e');steps.pack(anchor='w',padx=32,pady=(18,0))
    title=ttk.Label(window,text='安装可可助手',font=('Microsoft YaHei UI',21,'bold'));title.pack(anchor='w',padx=32,pady=(16,8))
    content=tk.Frame(window,bg=BG);content.pack(fill='both',expand=True,padx=32)
    actions=tk.Frame(window,bg=BG);actions.pack(fill='x',padx=32,pady=22)
    events=queue.Queue();running=False;root=None
    metadata_events=queue.Queue();metadata=None;metadata_error=None;metadata_loading=False
    space_label=None;start_button=None
    path=tk.StringVar(value=str(default));desktop=tk.BooleanVar(value=True);run=tk.BooleanVar(value=True)
    def clear():
        for frame in (content,actions):
            for child in frame.winfo_children():child.destroy()
    def close():
        if running:
            messagebox.showinfo('正在安装','请等待本次安装完成或失败后再关闭。',parent=window);return
        window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    def refresh_space(*unused):
        if running or space_label is None or not space_label.winfo_exists():return
        start_button.configure(state='disabled')
        try:
            selected=validate_destination(path.get())
            if metadata is None or metadata_loading:
                space_label.configure(text=metadata_error or '正在读取最新安装信息并检查磁盘空间…',foreground='#53596e');return
            report=inspect(selected,metadata)
            rows='\n'.join(f'{Path(row["path"]).anchor} 可用 {format_size(row["free"])} · 安装预留 {format_size(row["required"])}'+(' · 空间充足' if row['ok'] else ' · 空间不足') for row in report['volumes'])
            space_label.configure(text=f'程序文件约 {format_size(report["expanded"])}'+('（旧发行包估算）' if report['estimated'] else '')+'；预留包含下载、解压和临时空间。\n'+rows,foreground='#25633d' if report['ok'] else '#a43b43')
            start_button.configure(state='normal' if report['ok'] else 'disabled')
        except (ValueError,OSError) as error:space_label.configure(text=str(error),foreground='#a43b43')
    def load_metadata():
        nonlocal metadata_loading,metadata_error
        if metadata_loading:return
        metadata_loading=True;metadata_error=None
        def work():
            try:metadata_events.put((True,(manifest_loader or install_manifest)(public_key)))
            except Exception as error:metadata_events.put((False,'安装信息检查失败，请检查网络后点击“重新检查”。'+str(error)))
        threading.Thread(target=work,daemon=True,name='installer-space-check').start()
        refresh_space()
    def poll_metadata():
        nonlocal metadata,metadata_error,metadata_loading
        try:
            while True:
                ok,value=metadata_events.get_nowait();metadata_loading=False
                if ok:metadata=value;metadata_error=None
                else:metadata=None;metadata_error=value
                refresh_space()
        except queue.Empty:pass
        window.after(200,poll_metadata)
    path.trace_add('write',refresh_space)
    def location():
        nonlocal space_label,start_button
        clear();title.configure(text='选择安装位置');steps.configure(text='安装位置  →  下载与安装  →  完成')
        ttk.Label(content,text='先检查最新版本及磁盘空间，点击“开始安装”后下载程序。').pack(anchor='w',pady=8)
        ttk.Label(content,text='安装文件夹').pack(anchor='w',pady=(20,8))
        row=tk.Frame(content,bg=BG);row.pack(fill='x')
        ttk.Entry(row,textvariable=path).pack(side='left',fill='x',expand=True)
        def browse():
            selected=filedialog.askdirectory(parent=window,initialdir=str(Path(path.get()).parent),mustexist=False)
            if selected:path.set(str(Path(selected)/'KekeAssistant') if Path(selected).name.lower()!='kekeassistant' else selected)
        ttk.Button(row,text='浏览…',command=browse).pack(side='right',padx=(10,0))
        space_label=ttk.Label(content,text='正在检查磁盘空间…',wraplength=620);space_label.pack(anchor='w',pady=(14,8))
        ttk.Label(content,text='背包、截图和个人设置单独保存在用户数据目录。',wraplength=620).pack(anchor='w')
        ttk.Button(actions,text='取消',command=close).pack(side='left')
        start_button=ttk.Button(actions,text='开始安装',command=start,state='disabled');start_button.pack(side='right')
        ttk.Button(actions,text='重新检查',command=load_metadata).pack(side='right',padx=10)
        refresh_space()
    def start():
        nonlocal root,running
        try:
            if metadata is None:raise ValueError('请先完成安装信息检查')
            root=validate_destination(path.get());require(root,metadata);root.mkdir(parents=True,exist_ok=True)
            probe=root/'.write-test';probe.write_bytes(b'');probe.unlink()
        except (ValueError,OSError) as error:messagebox.showerror('无法安装到此位置',str(error)+'\n请选择可写的专用安装文件夹。',parent=window);return
        running=True;clear();title.configure(text='正在下载并安装');steps.configure(text='安装位置  →  下载与安装（进行中）  →  完成')
        ttk.Label(content,text='安装位置：'+str(root),wraplength=570).pack(anchor='w',pady=12)
        status=ttk.Label(content,text='准备下载…',wraplength=570);status.pack(anchor='w',pady=16)
        progress=ttk.Progressbar(content,mode='indeterminate');progress.pack(fill='x',pady=12);progress.start(15)
        def work():
            try:events.put(('done',operation(root,public_key,lambda text:events.put(('progress',text)))))
            except Exception as error:
                diagnostics.failure('安装任务失败');events.put(('error',str(error)))
        threading.Thread(target=work,name='installer-download',daemon=True).start()
        def poll():
            nonlocal running
            try:
                while True:
                    kind,value=events.get_nowait()
                    if kind=='progress':status.configure(text=value)
                    elif kind=='done':running=False;progress.stop();complete();return
                    else:
                        running=False;progress.stop();title.configure(text='安装未完成');status.configure(text=str(value))
                        ttk.Button(actions,text='返回修改位置',command=location).pack(side='left')
                        ttk.Button(actions,text='重试',command=start).pack(side='right');return
            except queue.Empty:pass
            window.after(100,poll)
        window.after(100,poll)
    def complete():
        clear();title.configure(text='安装完成，可以开始使用');steps.configure(text='安装位置  →  下载与安装  →  完成')
        ttk.Label(content,text='可可助手已安装到：\n'+str(root),wraplength=570).pack(anchor='w',pady=18)
        ttk.Checkbutton(content,text='创建桌面快捷方式',variable=desktop).pack(anchor='w',pady=10)
        ttk.Checkbutton(content,text='立即运行可可助手',variable=run).pack(anchor='w',pady=10)
        def finish():
            try:
                if desktop.get():shortcut(root,desktop=True)
                if run.get():launch(root)
            except Exception as error:
                diagnostics.failure('安装完成操作失败');messagebox.showerror('操作未完成',str(error),parent=window);return
            window.destroy()
        ttk.Button(actions,text='完成',command=finish).pack(side='right')
    location();load_metadata();window.after(50,poll_metadata);window.mainloop()
