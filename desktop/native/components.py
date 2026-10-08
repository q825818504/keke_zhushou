"""Pinned bundle verification and opt-in, reversible game-directory deployment."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import threading

IDENTITY = json.loads((Path(__file__).parent / 'component-identity.json').read_text(encoding='utf-8'))

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def atomic_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def game_processes():
    if os.name != 'nt': return []
    command = "@(Get-Process HTGame -ErrorAction SilentlyContinue | ForEach-Object { @{pid=$_.Id;path=$_.Path} }) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=6,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode: raise ValueError('无法检查游戏进程，请以管理员身份运行助手后重试')
    values = json.loads(result.stdout or '[]')
    values=[values] if isinstance(values,dict) else values
    # Query limited information also works when .NET Process.Path cannot inspect elevated modules.
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
    kernel.QueryFullProcessImageNameW.restype=ctypes.c_int
    kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle.restype=ctypes.c_int
    for value in values:
        if value.get('path'):continue
        handle=kernel.OpenProcess(0x1000,False,value['pid'])
        if not handle:continue
        try:
            size=ctypes.c_uint32(32768);buffer=ctypes.create_unicode_buffer(size.value)
            if kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):value['path']=buffer.value
        finally:kernel.CloseHandle(handle)
    return values

class ComponentManager:
    def __init__(self, directory, bundle=None, process_reader=game_processes, identity=None):
        self.directory = Path(directory)
        self.identity = identity or IDENTITY
        self.bundle = Path(bundle) if bundle else (Path(sys._MEIPASS)/'native-components' if hasattr(sys,'_MEIPASS') else Path(__file__).resolve().parents[2]/'build/native-components')
        self.process_reader = process_reader
        self.lock = threading.RLock()
        self.last = None
        self.config = {'game_directory':''}
        try:self.config.update(json.loads((self.directory/'settings.json').read_text(encoding='utf-8')))
        except (OSError,ValueError):pass

    def verify_bundle(self):
        issues=[]
        for name, expected in self.identity['files'].items():
            path=self.bundle/name
            try:
                if not path.is_file() or digest(path)!=expected:issues.append('内置组件缺失或校验失败：'+name)
            except OSError:issues.append('无法读取内置组件：'+name)
        return issues

    def component_root(self):
        issues=self.verify_bundle()
        if issues:raise ValueError('；'.join(issues[:3]))
        return self.bundle

    def _target(self, directory, name):
        root=Path(directory).resolve();path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('组件目标路径越界：'+name)
        return path

    def _game_directory(self, value):
        if not isinstance(value,str) or not value.strip() or len(value)>1024:raise ValueError('请选择HTGame.exe所在文件夹')
        root=Path(value.strip().strip(chr(34))).expanduser().resolve()
        if root.name.lower()=='htgame.exe':root=root.parent
        if not root.is_dir() or not (root/'HTGame.exe').is_file():raise ValueError('此文件夹没有HTGame.exe，请选择游戏实际程序目录')
        return root

    def _files(self, root):
        rows=[]
        for name in self.identity['deployment']:
            target=self._target(root,name)
            present=target.is_file()
            rows.append({'file':name,'state':'current' if present and digest(target)==self.identity['files'][name] else 'conflict' if target.exists() else 'missing'})
        return rows

    def inspect(self, game_directory=None):
        with self.lock:
            issues=self.verify_bundle()
            processes=self.process_reader()
            selected=game_directory or self.config.get('game_directory') or next((str(Path(p['path']).parent) for p in processes if p.get('path')), '')
            files=[];root=None
            if selected:
                try:root=self._game_directory(selected);files=self._files(root)
                except (ValueError,OSError) as error:issues.append(str(error))
            if processes and not selected:
                issues.append('当前权限无法获取游戏路径，请手动选择HTGame.exe目录或以管理员身份运行助手')
            if root:
                self.config['game_directory']=str(root)
                atomic_json(self.directory/'settings.json',self.config)
            endpoints=[]
            if os.name=='nt':
                try:
                    names=os.listdir('\\\\.\\pipe\\')
                    for p in processes:
                        for name in names:
                            if name.startswith('nte.capture.v1.'+str(p['pid'])+'.'):endpoints.append({'pid':p['pid'],'name':name})
                except OSError:pass
            # Required CRT presence is separate from the runtime plugin handshake.
            crt=[]
            if os.name=='nt':
                system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'
                crt=[{'file':n,'present':(system/n).is_file()} for n in ('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll')]
            for row in crt:
                if not row['present']:issues.append('缺少Microsoft VC++ x64运行库：'+row['file'])
            result={'bundle_ready':not any(issue.startswith(('内置组件','无法读取内置组件')) for issue in issues),'layout':self.identity['layout'],'core_version':self.identity['core_version'],
                'platform_supported':os.name=='nt' and platform.machine().lower() in ('amd64','x86_64'),
                'game_directory':str(root) if root else selected,'game_running':bool(processes),'processes':processes,
                'files':files,'deployment_ready':bool(files) and all(r['state']=='current' for r in files),
                'endpoint_present':bool(endpoints),'endpoints':endpoints,'runtime_libraries':crt,'issues':issues,
                'message':'原生端点已出现；同步时还会核对协议与快照' if endpoints else '退出游戏后部署组件，再重新启动游戏并登录',
                'sdk_note':'开发SDK不需要单独安装；运行能力由插件提供。当前端点出现不代表协议握手或数据读取成功。'}
            self.last=result
            return result

    def status(self):
        with self.lock:return self.last or {'game_directory':self.config.get('game_directory',''),'message':'点击检测环境，检查内置组件、游戏部署及运行连接'}

    def _ledger(self, root):
        return self.directory/'deployments'/(hashlib.sha256(str(root).casefold().encode()).hexdigest()+'.json')

    def deploy(self, game_directory):
        with self.lock:
            self.component_root()
            root=self._game_directory(game_directory)
            if self.process_reader():raise ValueError('请完全退出游戏后部署组件，再重新启动游戏')
            rows=self._files(root)
            conflicts=[r['file'] for r in rows if r['state']=='conflict']
            if conflicts:raise ValueError('已有不同版本组件或其他模组，未覆盖：'+', '.join(conflicts))
            ledger=self._ledger(root)
            try:record=json.loads(ledger.read_text(encoding='utf-8'))
            except FileNotFoundError:record={'directory':str(root),'created':{},'layout':self.identity['layout']}
            written=[]
            try:
                for row in sorted(rows,key=lambda row:row['file']=='d3d12.dll'):
                    if row['state']=='current':continue
                    if self.process_reader():raise ValueError('游戏在部署期间启动，已停止部署')
                    name=row['file'];target=self._target(root,name);target.parent.mkdir(parents=True,exist_ok=True)
                    temporary=target.with_name(target.name+'.keke-'+secrets.token_hex(6)+'.tmp')
                    try:
                        shutil.copyfile(self.bundle/name,temporary)
                        if digest(temporary)!=self.identity['files'][name]:raise ValueError('组件写入校验失败：'+name)
                        # Windows rename fails if another file appeared; never overwrite an unreviewed file.
                        if target.exists():raise ValueError('目标文件在部署时发生变化：'+name)
                        temporary.rename(target)
                        written.append((name,target));record['created'][name]=self.identity['files'][name]
                        atomic_json(ledger,record)
                    finally:temporary.unlink(missing_ok=True)
            except Exception:
                if self.process_reader():
                    atomic_json(ledger,record)
                    raise ValueError('部署未完成，游戏已经启动；已保存新增文件记录，请退出游戏后移除或重新部署')
                for name,target in reversed(written):
                    if target.is_file() and digest(target)==self.identity['files'][name]:
                        target.unlink();record['created'].pop(name,None)
                atomic_json(ledger,record)
                raise
            result=self.inspect(str(root));result['message']='组件已准备。请通过原游戏启动器启动游戏并登录，再进行原生同步。'
            self.last=result
            return result

    def remove(self, game_directory):
        with self.lock:
            root=self._game_directory(game_directory)
            if self.process_reader():raise ValueError('请完全退出游戏后移除组件')
            ledger=self._ledger(root)
            if not ledger.is_file():raise ValueError('没有可可助手的部署记录，未改动原有组件')
            record=json.loads(ledger.read_text(encoding='utf-8'))
            for name, expected in list(record.get('created',{}).items()):
                if name not in self.identity['deployment'] or expected!=self.identity['files'][name]:raise ValueError('部署记录不匹配，已停止移除')
                target=self._target(root,name)
                if target.exists() and (not target.is_file() or digest(target)!=expected):raise ValueError('组件已被其他程序修改，未删除：'+name)
            for name in sorted(record.get('created',{}),key=lambda name:name!='d3d12.dll'):
                if self.process_reader():raise ValueError('游戏在移除期间启动，已停止；剩余记录保留')
                self._target(root,name).unlink(missing_ok=True);record['created'].pop(name)
                atomic_json(ledger,record)
            result=self.inspect(str(root));result['message']='已移除可可助手本次新增的组件；原先存在的组件保留。'
            self.last=result
            return result
