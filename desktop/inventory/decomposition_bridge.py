"""Private, authenticated, single-request transport to the opt-in native bridge."""
import ctypes
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

MAGIC = 0x31444b4b
PACKET = struct.Struct('<II32sQQIIIIQ')
REPLY = struct.Struct('<IIIIQII128s')
SESSION = struct.Struct('<IIIIQ32sQ')


class BridgeClient:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.identity_path = Path(__file__).resolve().parents[1]/'native'/'cleanup-identity.json'

    def bundle(self):
        identity = json.loads(self.identity_path.read_text(encoding='utf-8'))
        root = (Path(sys._MEIPASS)/'native-decomposition' if hasattr(sys, '_MEIPASS')
                else Path(__file__).resolve().parents[2]/'build'/'native-decomposition')
        digest = hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
        target = self.directory/'native-decomposition'/digest
        if target.is_symlink() or not target.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError('分解桥接目录无效')
        target.mkdir(parents=True,exist_ok=True)
        for name, expected in identity['files'].items():
            if name not in ('KekeDecompositionBridge.dll','KekeDecompositionLoader.exe'):
                raise ValueError('分解组件清单无效')
            source, output = root/name, target/name
            if output.is_symlink(): raise ValueError('分解组件不能是链接文件')
            if output.is_file() and hashlib.sha256(output.read_bytes()).hexdigest()==expected: continue
            if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
                raise ValueError('分解组件校验失败，请重新打包')
            shutil.copyfile(source,output)
        return target

    def launch(self, pid):
        if os.name!='nt' or type(pid) is not int or pid<=0: raise ValueError('游戏进程无效')
        root=self.bundle()
        executable=str(root/'KekeDecompositionLoader.exe').replace("'","''")
        command=f"Start-Process -FilePath '{executable}' -ArgumentList @('--pid','{pid}') -Verb RunAs -WindowStyle Hidden"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
            capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
        if result.returncode: raise ValueError('加载器启动失败或 UAC 已取消')
        return {'launched':True,'pid':pid,'message':'已启动加载器，请稍候检测桥接状态。加载不会自动分解。'}

    def exchange(self,pid,op=1,request_id=0,revision=0,uid=None,material=0):
        if os.name!='nt': raise ValueError('内存分解仅支持 Windows')
        root=self.bundle()
        raw=(root/f'bridge-session-{pid}.bin').read_bytes()
        if len(raw)!=SESSION.size: raise ValueError('分解会话文件无效')
        magic,version,actual_pid,thread,creation,secret,window=SESSION.unpack(raw)
        if magic!=MAGIC or version!=1 or actual_pid!=pid: raise ValueError('分解会话身份不一致')
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        class Overlapped(ctypes.Structure):
            _fields_=[('Internal',ctypes.c_size_t),('InternalHigh',ctypes.c_size_t),
                      ('Offset',W.DWORD),('OffsetHigh',W.DWORD),('hEvent',W.HANDLE)]
        kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
        kernel.CreateFileW.restype=W.HANDLE
        kernel.WaitNamedPipeW.argtypes=[W.LPCWSTR,W.DWORD]
        kernel.GetNamedPipeServerProcessId.argtypes=[W.HANDLE,ctypes.POINTER(W.ULONG)]
        kernel.CreateEventW.argtypes=[ctypes.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR];kernel.CreateEventW.restype=W.HANDLE
        kernel.CloseHandle.argtypes=[W.HANDLE]
        kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
        kernel.CancelIoEx.argtypes=[W.HANDLE,ctypes.POINTER(Overlapped)]
        kernel.GetOverlappedResult.argtypes=[W.HANDLE,ctypes.POINTER(Overlapped),ctypes.POINTER(W.DWORD),W.BOOL]
        for name in ('ReadFile','WriteFile'):
            getattr(kernel,name).argtypes=[W.HANDLE,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD),ctypes.POINTER(Overlapped)]
        kernel.GetTickCount64.restype=ctypes.c_ulonglong
        pipe=f'\\\\.\\pipe\\KekeDecompose-{pid}'
        if not kernel.WaitNamedPipeW(pipe,1500): raise ValueError('分解桥接尚未连接；请查看加载日志')
        handle=kernel.CreateFileW(pipe,0xc0000000,0,None,3,0x40000000,None)
        if handle==ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
        def transfer(write,data):
            operation=Overlapped();operation.hEvent=kernel.CreateEventW(None,True,False,None)
            if not operation.hEvent: raise ctypes.WinError(ctypes.get_last_error())
            buffer=ctypes.create_string_buffer(data) if write else ctypes.create_string_buffer(data)
            size=len(data) if write else data
            received=W.DWORD()
            try:
                ok=(kernel.WriteFile if write else kernel.ReadFile)(handle,buffer,size,ctypes.byref(received),ctypes.byref(operation))
                if not ok:
                    if ctypes.get_last_error()!=997: raise ctypes.WinError(ctypes.get_last_error())
                    if kernel.WaitForSingleObject(operation.hEvent,18000)!=0:
                        kernel.CancelIoEx(handle,ctypes.byref(operation))
                        kernel.WaitForSingleObject(operation.hEvent,0xffffffff)
                        raise TimeoutError('桥接响应超时，结果不明；禁止重发，请重新读取库存')
                    if not kernel.GetOverlappedResult(handle,ctypes.byref(operation),ctypes.byref(received),False):
                        raise ctypes.WinError(ctypes.get_last_error())
                if received.value!=size: raise ValueError('桥接响应长度无效')
                return buffer.raw[:size]
            finally: kernel.CloseHandle(operation.hEvent)
        try:
            server=W.ULONG()
            if not kernel.GetNamedPipeServerProcessId(handle,ctypes.byref(server)) or server.value!=pid:
                raise ValueError('分解管道不是目标游戏进程提供的')
            pair=uid or (0,0)
            request=PACKET.pack(MAGIC,op,secret,request_id,revision,*pair,material,7 if op==2 else 0,kernel.GetTickCount64()+10000)
            transfer(True,request)
            response=REPLY.unpack(transfer(False,REPLY.size))
            if response[:2]!=(MAGIC,1) or response[4]!=request_id: raise ValueError('分解响应身份无效')
            return {'transport':response[2],'ready':bool(response[3]),'request_id':response[4],
                    'game_thread':response[5],'sender_result':response[6],
                    'message':response[7].split(b'\0')[0].decode('utf-8','replace')}
        finally: kernel.CloseHandle(handle)

    def status(self,pid):
        try: return self.exchange(pid)
        except (OSError,ValueError,TimeoutError) as error:
            root=self.bundle()
            details=[]
            loader_log=root/'loader.log'
            bridge_log=root/f'bridge-{pid}.log'
            try:
                lines=loader_log.read_text(encoding='utf-8',errors='replace').splitlines()
                current=[line for line in lines if line.startswith(f'pid={pid} ')]
                if current: details.append('加载器：'+'；'.join(current[-4:]))
            except OSError:
                pass
            try:
                lines=bridge_log.read_text(encoding='utf-8',errors='replace').splitlines()
                if lines: details.append('桥接：'+'；'.join(lines[-4:]))
            except OSError:
                pass
            message=str(error)
            if details: message+='；诊断：'+'；'.join(details)
            return {'ready':False,'message':message,'log_directory':str(root)}
