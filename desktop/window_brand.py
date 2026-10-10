"""Shared installer/startup branding, called only in isolated Tk processes."""
from pathlib import Path
import sys

BG='#f7f8fb'
INK='#242536'
SECONDARY='#53596e'
ACCENT='#5947ce'

def apply(window):
    from tkinter import ttk
    import tkinter as tk
    assets=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'assets'
    window.configure(bg=BG)
    if (assets/'mint-avatar.ico').is_file():window.iconbitmap(str(assets/'mint-avatar.ico'))
    style=ttk.Style();style.theme_use('vista')
    for name in ('TLabel','TCheckbutton'):
        style.configure(name,background=BG,foreground=INK,font=('Microsoft YaHei UI',10))
    style.configure('TButton',padding=(18,9),font=('Microsoft YaHei UI',10))
    header=tk.Frame(window,bg=BG);header.pack(fill='x',padx=32,pady=(24,0))
    if (assets/'mint-avatar.png').is_file():
        picture=tk.PhotoImage(file=str(assets/'mint-avatar.png'))
        picture=picture.subsample(max(1,picture.width()//64))
        window._brand_image=picture
        tk.Label(header,image=picture,bg=BG).pack(side='left',padx=(0,14))
    words=tk.Frame(header,bg=BG);words.pack(side='left')
    tk.Label(words,text='可可助手',bg=BG,fg=INK,font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
    tk.Label(words,text='配队、养成与背包管理',bg=BG,fg=SECONDARY,font=('Microsoft YaHei UI',10)).pack(anchor='w',pady=(3,0))
    return style
