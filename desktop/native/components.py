"""Pinned bundle verification and opt-in, reversible game-directory deployment."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import threading
import diagnostics

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
    command = "@(Get-Process HTGame -ErrorAction SilentlyContinue | ForEach-Object { $created=$null; try{$created=$_.StartTime.ToFileTime()}catch{}; @{pid=$_.Id;path=$_.Path;created=$created} }) | ConvertTo-Json -Compress"
    environment=dict(os.environ);environment.pop('PSModulePath',None)
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',"[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "+command],env=environment,capture_output=True,encoding='utf-8',timeout=6,creationflags=subprocess.CREATE_NO_WINDOW)
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

class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize',wintypes.DWORD),('th32ModuleID',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
        ('GlblcntUsage',wintypes.DWORD),('ProccntUsage',wintypes.DWORD),('modBaseAddr',ctypes.POINTER(ctypes.c_ubyte)),
        ('modBaseSize',wintypes.DWORD),('hModule',wintypes.HMODULE),('szModule',ctypes.c_wchar*256),
        ('szExePath',ctypes.c_wchar*260)]

def relevant_loaded_modules(pid):
    """Read-only module snapshot, limited to the deployed host and capture plugin."""
    if os.name != 'nt':raise OSError('Windows module inspection is unavailable')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Module32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MODULEENTRY32W)]
    kernel.Module32FirstW.restype=wintypes.BOOL
    kernel.Module32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MODULEENTRY32W)]
    kernel.Module32NextW.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
    snapshot=kernel.CreateToolhelp32Snapshot(0x00000008|0x00000010,int(pid))
    invalid=ctypes.c_void_p(-1).value
    if snapshot in (None,invalid):raise ctypes.WinError(ctypes.get_last_error())
    rows=[]
    try:
        entry=MODULEENTRY32W();entry.dwSize=ctypes.sizeof(MODULEENTRY32W)
        ctypes.set_last_error(0)
        if not kernel.Module32FirstW(snapshot,ctypes.byref(entry)):
            error=ctypes.get_last_error()
            if error==18:return rows
            raise ctypes.WinError(error)
        while True:
            if entry.szModule.casefold() in ('d3d12.dll','nte_plugincombat.dll'):
                rows.append({'name':entry.szModule,'path':entry.szExePath})
            ctypes.set_last_error(0)
            if not kernel.Module32NextW(snapshot,ctypes.byref(entry)):
                error=ctypes.get_last_error()
                if error not in (0,18):raise ctypes.WinError(error)
                break
        return rows
    finally:
        kernel.CloseHandle(snapshot)

def same_path(left,right):
    try:return os.path.normcase(os.path.realpath(str(left)))==os.path.normcase(os.path.realpath(str(right)))
    except (OSError,TypeError,ValueError):return False

def pipe_names():
    return os.listdir('\\\\.\\pipe\\')

def error_summary(error):
    return {'type':type(error).__name__,'message':str(error)[:800],
        'winerror':getattr(error,'winerror',None),'errno':getattr(error,'errno',None)}

class ComponentManager:
    def __init__(self, directory, bundle=None, process_reader=game_processes, identity=None,
                 pipe_reader=pipe_names, module_reader=relevant_loaded_modules):
        self.directory = Path(directory)
        self.identity = identity or IDENTITY
        self.bundle = Path(bundle) if bundle else (Path(sys._MEIPASS)/'native-components' if hasattr(sys,'_MEIPASS') else Path(__file__).resolve().parents[2]/'build/native-components')
        self.process_reader = process_reader
        self.pipe_reader = pipe_reader
        self.module_reader = module_reader
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
            observed=digest(target) if present else None
            expected=self.identity['files'][name]
            rows.append({'file':name,'state':'current' if present and observed==expected else 'conflict' if target.exists() else 'missing',
                'expected_sha256':expected,'observed_sha256':observed})
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
            process_directories=sorted({str(Path(p['path']).resolve().parent) for p in processes if p.get('path')})
            game_path_matches_process=(any(same_path(root,path) for path in process_directories) if root and process_directories else None)
            if game_path_matches_process is False:
                issues.append('当前核对目录与正在运行的游戏目录不一致')
            module_checks=[]
            roles=self.identity.get('roles',{})
            host_path=(root/roles.get('host','d3d12.dll')) if root else None
            capture_path=(root/roles.get('capture_plugin','plugins/NTE_PluginCombat.dll')) if root else None
            for process in processes:
                pid=process.get('pid')
                check={'pid':pid,'scan_state':'not_checked','host_state':'unknown','capture_state':'unknown','modules':[]}
                if os.name=='nt' and isinstance(pid,int):
                    try:
                        modules=self.module_reader(pid)
                        check['scan_state']='ok'
                        check['modules']=modules[:12]
                        if host_path and capture_path:
                            check['host_state']='loaded' if any(m.get('name','').casefold()=='d3d12.dll' and same_path(m.get('path',''),host_path) for m in modules) else 'not_loaded'
                            check['capture_state']='loaded' if any(m.get('name','').casefold()=='nte_plugincombat.dll' and same_path(m.get('path',''),capture_path) for m in modules) else 'not_loaded'
                    except Exception as error:
                        check['scan_state']='error';check['error']=error_summary(error)
                module_checks.append(check)
                if check['scan_state']=='error':
                    issues.append(f"无法核对游戏进程 {pid} 的组件模块：{check['error']['message']}")
            successful_module_checks=[row for row in module_checks if row['scan_state']=='ok']
            modules={'scan_state':'ok' if successful_module_checks and len(successful_module_checks)==len(module_checks) else 'partial' if successful_module_checks else 'error' if module_checks else 'not_running',
                'host_state':'loaded' if any(row['host_state']=='loaded' for row in module_checks) else 'not_loaded' if root and successful_module_checks else 'unknown',
                'capture_state':'loaded' if any(row['capture_state']=='loaded' for row in module_checks) else 'not_loaded' if root and successful_module_checks else 'unknown',
                'processes':module_checks}
            endpoints=[];pipe_matches=[];capture_pipes=[];pipe_error=None
            pipe_enumeration='not_supported'
            if os.name=='nt':
                try:
                    names=self.pipe_reader();pipe_enumeration='ok'
                    capture_pipes=sorted(name for name in names if name.startswith('nte.capture.v1.'))[:32]
                    for process in processes:
                        pid=process.get('pid')
                        if not isinstance(pid,int):continue
                        prefix='nte.capture.v1.'+str(pid)+'.'
                        candidates=[name for name in capture_pipes if name.startswith(prefix)]
                        expected=prefix+str(process['created']) if process.get('created') is not None else None
                        exact=[name for name in candidates if expected and name==expected]
                        matched=exact or (candidates if expected is None else [])
                        pipe_matches.append({'pid':pid,'created':process.get('created'),'expected':expected,
                            'pid_candidates':candidates,'matches':matched,'start_time_match':bool(exact) if expected else None})
                        endpoints.extend({'pid':pid,'name':name} for name in matched)
                except Exception as error:
                    pipe_enumeration='error';pipe_error=error_summary(error)
                    issues.append('无法枚举原生端点：'+pipe_error['message'])
            # Required CRT presence is separate from the runtime plugin handshake.
            crt=[]
            if os.name=='nt':
                system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32'
                crt=[{'file':n,'present':(system/n).is_file()} for n in ('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll')]
            for row in crt:
                if not row['present']:issues.append('缺少Microsoft VC++ x64运行库：'+row['file'])
            endpoint_scan_state='error' if pipe_enumeration=='error' else 'unsupported' if pipe_enumeration=='not_supported' else 'found' if endpoints else 'not_found'
            if endpoint_scan_state=='error':message='原生端点枚举失败；详细错误已记录到诊断日志'
            elif endpoints:message='原生端点已出现；同步时还会核对协议与快照'
            elif not processes:message='未发现正在运行的游戏进程；登录游戏后重新检测'
            elif game_path_matches_process is False:message='核对目录与正在运行的游戏目录不一致；请确认游戏路径'
            elif modules['host_state']=='not_loaded':message='游戏未从当前核对目录加载 d3d12 组件宿主；请确认目录并从原启动器重启游戏'
            elif modules['host_state']=='loaded' and modules['capture_state']=='not_loaded':message='组件宿主已加载，但采集插件未从当前核对目录加载；请检查插件文件及安全软件记录'
            elif modules['host_state']=='loaded' and modules['capture_state']=='loaded':message='宿主和采集插件已加载，但未发现对应端点；详细环境状态已记录到诊断日志'
            else:message='未发现原生端点；请核对组件文件并在部署后从原启动器重启游戏，详细状态已记录到诊断日志'
            result={'bundle_ready':not any(issue.startswith(('内置组件','无法读取内置组件')) for issue in issues),'layout':self.identity['layout'],'core_version':self.identity['core_version'],
                'platform_supported':os.name=='nt' and platform.machine().lower() in ('amd64','x86_64'),
                'game_directory':str(root) if root else selected,'game_running':bool(processes),'processes':processes,
                'running_game_directories':process_directories,'game_path_matches_process':game_path_matches_process,
                'files':files,'deployment_ready':bool(files) and all(r['state']=='current' for r in files),
                'modules':modules,'endpoint_present':bool(endpoints),'endpoint_scan_state':endpoint_scan_state,
                'endpoint_enumeration':{'state':pipe_enumeration,'error':pipe_error,'capture_pipe_names':capture_pipes,'process_matches':pipe_matches},
                'endpoints':endpoints,'runtime_libraries':crt,'issues':issues,'message':message,
                'sdk_note':'开发SDK不需要单独安装；运行能力由插件提供。当前端点出现不代表协议握手或数据读取成功。'}
            diagnostics.event('原生环境检测',layout=result['layout'],core_version=result['core_version'],platform_supported=result['platform_supported'],
                bundle_ready=result['bundle_ready'],deployment_ready=result['deployment_ready'],game_directory=result['game_directory'],
                running_game_directories=process_directories,game_path_matches_process=game_path_matches_process,processes=processes,
                files=files,modules=modules,endpoint_enumeration=result['endpoint_enumeration'],runtime_libraries=crt,issues=issues)
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
