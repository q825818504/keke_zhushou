"""Bounded local diagnostics; excludes inventory, screenshots and publishing secrets."""
from pathlib import Path
import atexit
import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import re
import secrets
import subprocess
import sys
import threading
import traceback
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'KekeAssistant'/'logs'
LOGGER=logging.getLogger('keke')
_fault=None
_events=[]
_lock=threading.Lock()
_session_started=False

def redact(value):
    text=str(value)
    text=re.sub(r'(?i)(authorization|access_token|gitee_token|token|password|secret)([\s"\x27:=]+)[^\s,;"\x27]+',r'\1\2[已隐藏]',text)
    text=re.sub(r'(?i)\b(?:bearer|basic)\s+\S+','[凭据已隐藏]',text)
    text=re.sub(r'(?i)([A-Z]:[\\/]Users[\\/])[^\\/\s]+',r'\1[用户]',text)
    text=re.sub(r'(?i)(uid\s*[:=]?\s*)\d+',r'\1[已隐藏]',text)
    text=re.sub(r'(https?://[^\s?#]+)[?#][^\s]+',r'\1[参数已隐藏]',text)
    return text[:16000]

class SafeFormatter(logging.Formatter):
    def format(self,record): return redact(super().format(record))

def event(message,**fields):
    LOGGER.info('%s %s',message,json.dumps(fields,ensure_ascii=False,default=str))

def failure(message): LOGGER.error('%s\n%s',message,traceback.format_exc())

def initialize(mode='user'):
    global _fault
    if LOGGER.handlers:return
    ROOT.mkdir(parents=True,exist_ok=True)
    handler=RotatingFileHandler(ROOT/(mode+'.log'),maxBytes=2*1024**2,backupCount=4,encoding='utf-8')
    handler.setFormatter(SafeFormatter('%(asctime)s %(levelname)s %(threadName)s %(message)s'))
    LOGGER.addHandler(handler);LOGGER.setLevel(logging.INFO)
    path=ROOT/(mode+'-fault.log')
    if path.exists() and path.stat().st_size>2*1024**2:
        path.replace(path.with_suffix('.previous.log'))
    _fault=path.open('a',encoding='utf-8')
    faulthandler.enable(_fault,all_threads=True)
    def thread_error(args):
        LOGGER.error('后台线程未处理异常\n%s',''.join(traceback.format_exception(args.exc_type,args.exc_value,args.exc_traceback)))
    threading.excepthook=thread_error
    event('进程启动',mode=mode,pid=os.getpid(),system=platform.platform(),python=platform.python_version())
    threading.Thread(target=refresh_windows_events,name='diagnostics-system',daemon=True).start()

def begin_session():
    """Only the process holding the user's single-instance mutex owns this marker."""
    global _session_started
    if _session_started:return
    _session_started=True
    marker=ROOT/'session.json'
    if marker.exists():event('上次主界面未正常退出；请结合系统崩溃记录确认原因')
    identity=secrets.token_hex(8)
    marker.write_text(json.dumps({'pid':os.getpid(),'session':identity}),encoding='utf-8')
    def finished():
        try:
            if json.loads(marker.read_text())['session']==identity:marker.unlink()
        except (OSError,ValueError,KeyError):pass
        event('主界面正常退出')
    atexit.register(finished)

def refresh_windows_events():
    global _events
    if os.name!='nt':return []
    # Only confirmed Windows application crashes for our executable/core/game;
    # ordinary game exits are not reported as crashes. Never export raw WER dumps.
    try:
        query='*[System[(EventID=1000) and TimeCreated[timediff(@SystemTime)<=604800000]]]'
        result=subprocess.run(['wevtutil.exe','qe','Application','/q:'+query,'/f:xml','/c:400','/rd:true','/uni:true'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:raise OSError('Windows 事件记录暂不可用')
        xml=result.stdout.decode('utf-16').strip()
        if not xml.startswith('<Events'):xml='<Events>'+xml+'</Events>'
        tree=ET.fromstring(xml);ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'}
        rows=[]
        for item in tree.findall('e:Event',ns):
            values=item.findall('e:EventData/e:Data',ns)
            fields={d.attrib.get('Name'):d.text for d in values if d.attrib.get('Name')}
            # Older Win10 event-provider schema contains positional, unnamed Data.
            if not fields and len(values)>=7:
                fields={'AppName':values[0].text,'ModuleName':values[3].text,'ExceptionCode':values[6].text}
            if not re.fullmatch(r'(?i)(KekeAssistant(App)?|nte-core|HTGame)\.exe',fields.get('AppName','')):continue
            timestamp=item.find('e:System/e:TimeCreated',ns).attrib.get('SystemTime','')
            rows.append({'time':timestamp,'application':fields['AppName'],'module':fields.get('ModuleName','未知'),'code':fields.get('ExceptionCode','未知')})
        with _lock:_events=rows[:50]
        return _events
    except Exception:
        failure('系统崩溃记录查询失败');return _events

def recent():
    lines=[]
    try:lines=(ROOT/'user.log').read_text(encoding='utf-8',errors='replace').splitlines()[-100:]
    except OSError:pass
    with _lock:events=list(_events)
    return {'logs':redact('\n'.join(lines)),'crashes':events,'directory':str(ROOT),'hint':'仅记录系统确认的崩溃；没有记录不代表没有出错。'}

def trim_exports(directory,keep=5):
    """Keep only the newest diagnostic packages; the folder otherwise grows without bound."""
    try:files=sorted((path for path in Path(directory).glob('可可助手诊断-*.zip') if path.is_file()),key=lambda path:path.stat().st_mtime_ns,reverse=True)
    except OSError:return
    for path in files[keep:]:
        try:path.unlink()
        except OSError:pass

def export():
    refresh_windows_events()
    destination=ROOT/'exports';destination.mkdir(exist_ok=True)
    path=destination/('可可助手诊断-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.zip')
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for source in ROOT.glob('*.log*'):
            if source.is_file() and source.stat().st_size<=3*1024**2:
                archive.writestr(source.name,redact(source.read_text(encoding='utf-8',errors='replace')))
        archive.writestr('system.json',json.dumps({'system':platform.platform(),'architecture':platform.machine(),'events':recent()['crashes'],'generated':datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2))
    trim_exports(destination,keep=5)
    return path
