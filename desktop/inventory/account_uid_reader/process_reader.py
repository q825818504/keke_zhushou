"""Independent, read-only Windows process access. No injection, hooks or writes."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import json,os,sys

PROCESS_QUERY_LIMITED_INFORMATION=0x1000
MAX_ENUMERATED_PROCESSES=32768

def enumerate_process_ids():
 """List process IDs with PSAPI; does not request access to process memory."""
 if os.name!='nt':raise RuntimeError('requires Windows process enumeration')
 api=C.WinDLL('psapi',use_last_error=True);api.EnumProcesses.argtypes=[C.POINTER(W.DWORD),W.DWORD,C.POINTER(W.DWORD)];api.EnumProcesses.restype=W.BOOL
 capacity=1024
 while capacity<=MAX_ENUMERATED_PROCESSES:
  rows=(W.DWORD*capacity)();needed=W.DWORD()
  if not api.EnumProcesses(rows,C.sizeof(rows),C.byref(needed)):raise C.WinError(C.get_last_error())
  if needed.value<C.sizeof(rows):return [int(pid) for pid in rows[:needed.value//C.sizeof(W.DWORD)] if pid]
  capacity*=2
 raise RuntimeError('process list exceeds enumeration bound')

def process_image_path(pid):
 """Resolve one process image using query-limited-information only."""
 if type(pid)is not int or pid<=0:raise ValueError('invalid process ID')
 kernel=C.WinDLL('kernel32',use_last_error=True)
 kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
 kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)];kernel.QueryFullProcessImageNameW.restype=W.BOOL
 kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
 handle=kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
 if not handle:raise C.WinError(C.get_last_error())
 try:
  path=C.create_unicode_buffer(32768);length=W.DWORD(len(path))
  if not kernel.QueryFullProcessImageNameW(handle,0,path,C.byref(length)):raise C.WinError(C.get_last_error())
  return path.value
 finally:kernel.CloseHandle(handle)

def find_process_ids_by_image_name(image_names):
 """Find exact image basenames without spawning tasklist or touching memory."""
 if isinstance(image_names,(str,Path)):image_names=(image_names,)
 names={Path(str(name)).name.casefold() for name in image_names if str(name).strip()}
 if not names:raise ValueError('at least one process image name is required')
 found=[]
 for pid in enumerate_process_ids():
  try:path=process_image_path(pid)
  except OSError:continue
  if Path(path).name.casefold() in names:found.append(pid)
 return found

class MODULEINFO(C.Structure):
 _fields_=[('base',C.c_void_p),('size',W.DWORD),('entry',C.c_void_p)]

class ProcessReader:
 def __init__(self,pid):
  if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('requires Windows x64 Python')
  self.pid=pid;self.handle=None
  self.k=C.WinDLL('kernel32',use_last_error=True);self.p=C.WinDLL('psapi',use_last_error=True)
  specs={'OpenProcess':([W.DWORD,W.BOOL,W.DWORD],W.HANDLE),'CloseHandle':([W.HANDLE],W.BOOL),'ReadProcessMemory':([W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL),'GetProcessTimes':([W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)],W.BOOL),'QueryFullProcessImageNameW':([W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)],W.BOOL)}
  for name,(args,result) in specs.items():f=getattr(self.k,name);f.argtypes=args;f.restype=result
  self.p.EnumProcessModulesEx.argtypes=[W.HANDLE,C.POINTER(W.HMODULE),W.DWORD,C.POINTER(W.DWORD),W.DWORD];self.p.EnumProcessModulesEx.restype=W.BOOL
  self.p.GetModuleInformation.argtypes=[W.HANDLE,W.HMODULE,C.POINTER(MODULEINFO),W.DWORD];self.p.GetModuleInformation.restype=W.BOOL
  self.p.GetModuleFileNameExW.argtypes=[W.HANDLE,W.HMODULE,W.LPWSTR,W.DWORD];self.p.GetModuleFileNameExW.restype=W.DWORD
  # Explicit read/query only; no debug privilege or access-right workaround.
  self.handle=self.k.OpenProcess(0x410,False,pid)
  if not self.handle:raise C.WinError(C.get_last_error())
 def read(self,address,size):
  if type(address) is not int or not 0x10000<=address<=0x7fffffffffff:raise ValueError('invalid user-space address')
  if type(size) is not int or not 1<=size<=1024*1024 or address+size>0x800000000000:raise ValueError('invalid bounded read')
  if not self.handle:raise RuntimeError('process reader closed')
  data=C.create_string_buffer(size);got=C.c_size_t()
  if not self.k.ReadProcessMemory(self.handle,C.c_void_p(address),data,size,C.byref(got)):raise C.WinError(C.get_last_error())
  if got.value!=size:raise RuntimeError('partial memory read')
  return data.raw
 def identity(self):
  buf=C.create_unicode_buffer(32768);n=W.DWORD(len(buf))
  if not self.k.QueryFullProcessImageNameW(self.handle,0,buf,C.byref(n)):raise C.WinError(C.get_last_error())
  times=[W.FILETIME() for _ in range(4)]
  if not self.k.GetProcessTimes(self.handle,*[C.byref(x) for x in times]):raise C.WinError(C.get_last_error())
  return {'pid':self.pid,'executable':buf.value,'creation_filetime':str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)}
 def modules(self):
  needed=W.DWORD();capacity=256
  for _ in range(5):
   arr=(W.HMODULE*capacity)()
   if not self.p.EnumProcessModulesEx(self.handle,arr,C.sizeof(arr),C.byref(needed),3):raise C.WinError(C.get_last_error())
   if needed.value<=C.sizeof(arr):break
   capacity=needed.value//C.sizeof(W.HMODULE)+32
   if capacity>8192:raise RuntimeError('module list exceeds bound')
  else:raise RuntimeError('module list changed repeatedly')
  rows=[]
  for h in arr[:needed.value//C.sizeof(W.HMODULE)]:
   mi=MODULEINFO();buf=C.create_unicode_buffer(32768)
   if not self.p.GetModuleInformation(self.handle,h,C.byref(mi),C.sizeof(mi)):raise C.WinError(C.get_last_error())
   if not self.p.GetModuleFileNameExW(self.handle,h,buf,len(buf)):raise C.WinError(C.get_last_error())
   rows.append({'path':buf.value,'base':hex(mi.base),'size':mi.size})
  return rows
 def close(self):
  if self.handle:self.k.CloseHandle(self.handle);self.handle=None
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

def diagnose(pid):
 report={'schema':'keke_readonly_process_probe_v1','pid':pid,'independent_game_reader':False,'access':'PROCESS_QUERY_INFORMATION | PROCESS_VM_READ','writes':False,'injection':False}
 try:
  with ProcessReader(pid) as p:
   identity=p.identity();report['identity']=identity
   if Path(identity['executable']).name.lower()!='htgame.exe':raise ValueError('target is not HTGame.exe')
   modules=p.modules();report['module_count']=len(modules)
   main=next((m for m in modules if Path(m['path']).name.lower()=='htgame.exe'),None)
   report['native_components']=[m for m in modules if Path(m['path']).name.lower() in ['d3d12.dll','nte_pluginuser.dll','nte_plugincombat.dll','nte_capture.dll']]
   if not main:raise RuntimeError('game main module not enumerated')
   report['game_module']=main;header=p.read(int(main['base'],16),64)
   report['game_header_read']={'bytes':len(header),'mz':header[:2]==b'MZ'}
   if header[:2]!=b'MZ':raise RuntimeError('invalid game DOS header')
   report['status']='read_access_verified'
 except (OSError,RuntimeError,ValueError) as e:
  report['status']='unavailable';report['error']=str(e);report['windows_error']=getattr(e,'winerror',None)
 return report

if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('usage: process_reader.py GAME_PID OUTPUT_JSON')
 result=diagnose(int(sys.argv[1]));Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=True,indent=2))
 raise SystemExit(0 if result['status']=='read_access_verified' else 2)
