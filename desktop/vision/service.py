"""Bounded local OCR jobs. Vision batches never overwrite native inventory."""
import base64
import ctypes
import hashlib
import io
import queue
import json
import os
import secrets
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import CancelledError
from PIL import Image
import diagnostics
from inventory.accounts import validate_uid

MODES=('offline','mouse','new','gamepad','retry')

class VisionService:
    def __init__(self,directory,engine_factory=None,scanner_factory=None):
        self.directory=Path(directory)
        self.engine_factory=engine_factory
        self.scanner_factory=scanner_factory
        self.lock=threading.RLock();self.stop=threading.Event();self.capture_stop=threading.Event();self.thread=None;self.scanner=None
        self.job={'running':False,'message':'尚未开始识别','processed':0,'total':0};self.batch=None
        self.window=None;self.engine=None;self.extra_engine=None

    def status(self):
        with self.lock:
            return json.loads(json.dumps({'job':self.job,'batch':self.batch},ensure_ascii=False))

    def _write(self,path,value):
        # Windows readers can briefly deny rename/delete sharing. Coordinate our
        # own readers and retry external transient locks without truncating JSON.
        with self.lock:
            path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.'+secrets.token_hex(6)+'.tmp')
            try:
                tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8')
                delays=(.01,.025,.05,.1,.2,.35)
                for attempt in range(len(delays)+1):
                    try:
                        os.replace(tmp,path)
                        break
                    except PermissionError:
                        if attempt==len(delays):raise
                        time.sleep(delays[attempt])
            finally:
                try:tmp.unlink(missing_ok=True)
                except OSError:diagnostics.event('批次临时文件暂被占用，保留待清理',file=tmp.name)

    def _base(self,account,batch_id):
        if not isinstance(account,str) or not account.strip() or len(account)>80:raise ValueError('账号标签无效')
        if not isinstance(batch_id,str) or len(batch_id)!=24 or any(c not in '0123456789abcdef' for c in batch_id):raise ValueError('批次ID无效')
        return self.directory/hashlib.sha256(account.encode()).hexdigest()/batch_id

    def load(self,account,batch_id):
        with self.lock:
            base=self._base(account,batch_id)
            batch=json.loads((base/'batch.json').read_text(encoding='utf-8'))
            batch['storage']=self.storage_paths(base)
            return batch

    @staticmethod
    def storage_paths(base):
        return {'directory':str(base.resolve()),'images_directory':str((base/'images').resolve())}

    def open_folder(self,account,batch_id):
        directory=self._base(account,batch_id)/'images'
        if not directory.is_dir():raise ValueError('截图文件夹不存在')
        if os.name!='nt':raise ValueError('打开文件夹仅支持Windows')
        os.startfile(str(directory.resolve()))
        return {'opened':True}

    def history(self,account):
        with self.lock:
            root=self._base(account,'0'*24).parent
            rows=[]
            for file in sorted(root.glob('*/batch.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
                try:
                    b=json.loads(file.read_text(encoding='utf-8'));rows.append({k:b.get(k) for k in ('id','account','account_uid','mode','saved_at','complete','state','expected','processed')})
                except (OSError,ValueError):pass
            return rows

    def delete(self,account,batch_id):
        with self.lock:
            if self.job['running']:
                raise ValueError('请等待识别任务完成后再删除')
            base=self._base(account,batch_id)
            root=self.directory.resolve()
            resolved=base.resolve()
            if not resolved.is_relative_to(root) or resolved.parent.parent != root:
                raise ValueError('批次目录超出保存范围')
            if base.is_symlink() or base.parent.is_symlink():
                raise ValueError('不能删除链接目录')
            if not (base/'batch.json').is_file():
                raise ValueError('此识别批次不存在')
            shutil.rmtree(base)
            if self.batch and self.batch.get('account')==account and self.batch.get('id')==batch_id:
                self.batch=None
                self.job={'running':False,'message':'已删除识别批次','processed':0,'total':0}
        return {'deleted':True,'id':batch_id}

    def image(self,account,batch_id,name):
        if not isinstance(name,str) or Path(name).name!=name or name in ('.','..') or not name.lower().endswith('.png'):raise ValueError('图片名称无效')
        path=self._base(account,batch_id)/'images'/name
        if not path.is_file():raise ValueError('图片不存在')
        return path

    def start(self,mode,account,count=None,files=None,batch_id=None,account_uid=None):
        if mode not in MODES:raise ValueError('识别模式无效')
        self._base(account,'0'*24)
        if mode == 'retry':
            account_uid = validate_uid(account_uid)
        else:
            account_uid = validate_uid(account_uid)
        if mode in ('mouse','gamepad') and (type(count) is not int or not 1<=count<=2000):raise ValueError('请填写1–2000的当前筛选库存数量')
        with self.lock:
            if self.job['running']:raise ValueError('已有识别任务，请等待或取消')
            if mode=='retry':
                batch=self.load(account,batch_id);base=self._base(account,batch_id)
                if not any(row.get('error') for row in batch['images']):raise ValueError('此批次没有失败图片')
                if batch.get('account_uid') not in (None, account_uid):raise ValueError('此批次所属UID与当前账号资料不一致')
                batch['account_uid'] = account_uid
                # Retrying OCR cannot repair a cancelled or incomplete acquisition.
                batch['retry']=True
            else:
                batch_id=secrets.token_hex(12);base=self._base(account,batch_id);(base/'images').mkdir(parents=True)
                batch={'schema_version':1,'id':batch_id,'account':account,'account_uid':account_uid,'mode':mode,'expected':count,
                       'saved_at':datetime.now(timezone.utc).isoformat(),'state':'pending','complete':False,
                       'capture_complete':False,'processed':0,'images':[],'records':[]}
                if mode=='offline':
                    if not isinstance(files,list) or not 1<=len(files)<=2000:raise ValueError('请选择图片文件')
                    size=0
                    for index,file in enumerate(files):
                        encoded=file.get('data') if isinstance(file,dict) else None
                        if not isinstance(encoded,str):raise ValueError('图片数据无效')
                        try:data=base64.b64decode(encoded,validate=True)
                        except Exception:raise ValueError('图片编码无效')
                        size+=len(data)
                        if len(data)>16*1024*1024 or size>64*1024*1024:raise ValueError('单图限制16MB，每批限制64MB；请分批导入')
                        try:
                            with Image.open(io.BytesIO(data)) as image:
                                if image.width*image.height>20_000_000:raise ValueError('图片像素过大')
                                image.convert('RGB').save(base/'images'/f'{index:05d}.png')
                        except (OSError,Image.DecompressionBombError):raise ValueError('图像损坏或无法读取')
                    batch['expected']=len(files);batch['capture_complete']=True
            self.stop.clear();self.capture_stop.clear();self.window=None;self.batch=batch
            batch['storage']=self.storage_paths(base)
            self.job={'running':True,'message':'正在准备OCR；扫描时请在3秒内切回游戏装备背包','processed':0,'total':batch['expected'] or 0,'account':account,'account_uid':account_uid,'id':batch_id,'capture_running':mode in ('mouse','new','gamepad'),'capture_stopping':False}
            self._write(base/'batch.json',batch)
            self.thread=threading.Thread(target=self._run,args=(base,batch,mode),daemon=True);self.thread.start()
        return self.status()

    def check(self):
        if self.stop.is_set():raise CancelledError('已取消；保留本次部分结果和原库存')

    def check_capture(self):
        self.check()
        if self.capture_stop.is_set():raise CancelledError('已停止采集，继续识别已保存截图')

    def guard(self,capability):
        self.check_capture()
        if capability!='interface_input':raise PermissionError('仅允许装备遍历截图')
        if os.name!='nt':raise ValueError('游戏扫描仅支持Windows')
        user=ctypes.windll.user32;user.GetForegroundWindow.restype=ctypes.c_void_p
        window=user.GetForegroundWindow();pid=ctypes.c_ulong();user.GetWindowThreadProcessId(ctypes.c_void_p(window),ctypes.byref(pid))
        kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x1000,False,pid.value)
        if not handle:raise ValueError('无法确认前台游戏进程')
        try:
            buffer=ctypes.create_unicode_buffer(32768);size=ctypes.c_ulong(len(buffer))
            if not kernel.QueryFullProcessImageNameW(ctypes.c_void_p(handle),0,buffer,ctypes.byref(size)) or Path(buffer.value).name.lower()!='htgame.exe':raise ValueError('前台不是异环游戏，扫描已停止')
            if self.window is None:
                from .windows_access import require_matching_input_privilege
                require_matching_input_privilege(ctypes.c_void_p(handle))
        finally:kernel.CloseHandle(ctypes.c_void_p(handle))
        identity=(window,pid.value)
        if self.window is not None and identity!=self.window:raise ValueError('前台游戏窗口已变化，扫描已停止')
        self.window=identity

    def make_scanner(self,mode,directory):
        if self.scanner_factory:return self.scanner_factory(mode,directory,self.guard)
        if mode=='mouse':
            from .upstream.integrations.vision.mouse_scan_runtime import require_mouse_scan_runtime
            require_mouse_scan_runtime()
            from .mouse_scanner import VerifiedMouseScanner
            return VerifiedMouseScanner(directory,operation_guard=self.guard)
        if mode=='new':
            from .upstream.scanner.drone_scanner import DroneScanner
            from .upstream.integrations.bundled_resources import bundled_config_dir
            return DroneScanner(directory,str(bundled_config_dir()/'templates/new_tag.png'),operation_guard=self.guard)
        from .gamepad_scanner import GamepadScanner
        return GamepadScanner(directory,operation_guard=self.guard)

    def _collect_images(self,base):
        images=base/'images'
        for path in list(images.rglob('*.png')):
            if path.parent!=images and not (images/path.name).exists():shutil.copy2(path,images/path.name)

    def _run(self,base,batch,mode):
        hook=None
        # Full gamepad scans queue paths to screenshots already on disk (at most 2000).
        # A slow OCR worker must not stop controller navigation after 32 captures.
        work=queue.Queue(maxsize=0 if mode=='gamepad' else 32)
        seen=set()
        worker_errors=[]
        existing={row['file']:row for row in batch['images']}
        last_checkpoint=time.monotonic()
        checkpoint_error=None

        def update_progress(persist=True):
            nonlocal last_checkpoint,checkpoint_error
            batch['images']=sorted(existing.values(),key=lambda row:row['file'])
            batch['records']=[record for image in batch['images'] for record in image.get('records',[])]
            processed=sum(not row.get('pending') and row.get('error')!='采集或识别未完成' for row in batch['images'])
            batch['processed']=processed
            self.job.update(processed=processed,captured=len(existing),queued=work.qsize())
            if mode=='new' or not self.job.get('capture_running'):self.job['total']=len(existing)
            phase='采集与识别并行' if self.job.get('capture_running') and not self.capture_stop.is_set() else '正在识别已保存截图'
            self.job['message']=f"已截图{len(existing)}张，已识别{processed}张；{phase}"
            # Screenshots are already durable. Coalesce metadata checkpoints so
            # two workers do not rewrite the growing batch for every image.
            if persist and time.monotonic()-last_checkpoint>=.5:
                try:
                    self._write(base/'batch.json',batch)
                    checkpoint_error=None
                except PermissionError:
                    if checkpoint_error is None:diagnostics.event('批次记录暂被占用，继续采集并稍后重试')
                    checkpoint_error=True
                finally:last_checkpoint=time.monotonic()
            if checkpoint_error:self.job['message']+='；批次记录暂被占用，截图继续保存'

        def enqueue(source,*unused):
            self.check()
            if worker_errors:raise RuntimeError('识别线程失败：'+str(worker_errors[0]))
            source=Path(source);path=base/'images'/source.name
            if path.name in seen:return
            old=existing.get(path.name)
            if mode=='retry' and old and not old.get('error'):return
            if source!=path:shutil.copy2(source,path)
            seen.add(path.name)
            with self.lock:
                existing[path.name]={'file':path.name,'records':[],'lines':[],'pending':True,'error':'等待识别'}
                update_progress()
            while True:
                self.check()
                if worker_errors:raise RuntimeError('识别线程失败：'+str(worker_errors[0]))
                try:work.put(path,timeout=.1);break
                except queue.Full:continue

        # Never call one RapidOCR instance concurrently: its detector and
        # recognizer mutate buffers. Two independent engines have bounded CPU
        # sessions; smaller machines and injected engines retain one worker.
        worker_count=2 if self.engine_factory is None and (os.cpu_count() or 1)>=4 else 1
        capture_finished=threading.Event()
        if mode not in ('mouse','new','gamepad'):capture_finished.set()
        def recognize(slot):
            try:
                # Keep the previous single OCR lane while input is active. A
                # second model initialization/inference must not delay releasing
                # a held stick and turn one grid step into an auto-repeat.
                if slot:
                    capture_finished.wait()
                while True:
                    path=work.get()
                    if path is None:break
                    if self.stop.is_set():continue
                    engine=self.engine if slot==0 else self.extra_engine
                    if engine is None:
                        if self.engine_factory:engine=self.engine_factory(base/'parser')
                        else:
                            from .engine import VisionEngine
                            engine=VisionEngine(base/'parser')
                        if slot==0:self.engine=engine
                        else:self.extra_engine=engine
                    try:result=engine.parse(path)
                    except Exception as error:
                        diagnostics.failure('截图识别失败');result={'records':[],'error':str(error),'lines':[]}
                    result={**result,'file':path.name}
                    for index,row in enumerate(result.get('records',[])):
                        row['instance_id']=f"vision:{batch['id']}:{path.stem}:{index}"
                        row['image']=path.name
                    with self.lock:
                        existing[path.name]=result;update_progress()
            except Exception as error:
                diagnostics.failure('OCR工作线程失败');worker_errors.append(error)

        consumers=[threading.Thread(target=recognize,args=(slot,),name=f'vision-ocr-{slot}',daemon=True) for slot in range(worker_count)]
        for consumer in consumers:consumer.start()
        problem=None
        try:
            if mode in ('mouse','new','gamepad'):
                import keyboard
                hook=keyboard.add_hotkey('f8',self.stop_capture)
                try:
                    # Initialize before the focus countdown, not immediately
                    # after the first capture while the next stick is held.
                    if self.engine is None and self.engine_factory is None:
                        from .engine import VisionEngine
                        self.job['message']='正在加载识别模型，加载完成后倒计时3秒开始扫描'
                        self.engine=VisionEngine(base/'parser')
                    self.job['message']='请在3秒内切回游戏装备背包；即将从第一件开始扫描'
                    for _ in range(30):self.check_capture();time.sleep(.1)
                    self.guard('interface_input')
                    self.scanner=self.make_scanner(mode,str(base/'images'))
                    if mode=='new':self.scanner.start_scan(on_capture=enqueue)
                    else:
                        captured=self.scanner.start_scan(batch['expected'],on_capture=enqueue,commit_on_complete=False)
                        self.check_capture()
                        if captured!=batch['expected']:raise ValueError('采集未覆盖预期数量，保留部分截图')
                    self.check_capture();batch['capture_complete']=True
                except Exception as error:
                    diagnostics.failure('截图采集停止或失败')
                    batch['capture_complete']=False;batch['capture_error']=str(error)
                    batch['capture_stopped']=self.capture_stop.is_set()
                    if self.stop.is_set():raise
                    self._collect_images(base)
                    if not any((base/'images').glob('*.png')) and not self.capture_stop.is_set():raise
                finally:
                    with self.lock:self.job['capture_running']=False
                    if self.scanner and hasattr(self.scanner,'close'):
                        try:self.scanner.close()
                        except Exception:pass
                    self.scanner=None
                    capture_finished.set()
            self._collect_images(base)
            for path in sorted((base/'images').glob('*.png')):enqueue(path)
        except Exception as error:
            diagnostics.failure('扫描批次失败');problem=error
        finally:
            capture_finished.set()
            # Drain saved work on acquisition failure; cancellation skips queued
            # OCR while preserving pending evidence. Never let the next job race
            # this job's inference workers.
            for consumer in consumers:
                while consumer.is_alive():
                    try:work.put(None,timeout=.1);break
                    except queue.Full:continue
            for consumer in consumers:consumer.join()
            if hook is not None:
                import keyboard
                keyboard.remove_hotkey(hook)
            if worker_errors and problem is None:problem=worker_errors[0]
            with self.lock:
                self._collect_images(base)
                for path in sorted((base/'images').glob('*.png')):
                    if path.name not in existing:
                        existing[path.name]={'file':path.name,'records':[],'lines':[],'error':'尚未识别（任务已停止）','pending':True}
                update_progress(persist=False)
                failures=sum(bool(row.get('error')) and not row.get('pending') for row in batch['images'])
                batch['complete']=bool(batch['mode'] in ('mouse','gamepad') and batch['capture_complete']
                    and not problem and not self.stop.is_set() and not failures
                    and len(batch['images'])==batch['expected'] and len(batch['records'])==batch['expected'])
                batch['state']='cancelled' if self.stop.is_set() else ('error' if problem else
                    ('partial' if failures or batch.get('capture_error') else 'parsed'))
                self.job['message']=str(problem) if problem else f"识别{len(batch['records'])}件，失败{failures}张；已保存独立视觉批次"
                if not problem and mode=='new' and not batch['images'] and not batch.get('capture_error'):self.job['message']='未发现新增装备（NEW），本批次未保存装备截图'
                if not problem and batch.get('capture_error'):self.job['message']+='；采集未完成：'+batch['capture_error']
                try:self._write(base/'batch.json',batch)
                except Exception as error:
                    batch['complete']=False;batch['state']='error'
                    self.job['message']='截图已保留，但批次记录保存失败：'+str(error)
                finally:self.job['running']=False

    def correct(self,account,batch_id,index,record):
        with self.lock:
            if self.job['running']:raise ValueError('任务运行期间不能修改记录')
            batch=self.load(account,batch_id)
            if type(index) is not int or not 0<=index<len(batch['records']) or not isinstance(record,dict) or record.get('category') not in ('drive','tape'):raise ValueError('记录无效')
            previous=batch['records'][index]
            record={**record,'instance_id':previous['instance_id'],'image':previous['image'],'manually_corrected':True}
            image=next(image for image in batch['images'] if image['file']==previous['image'])
            position=next(i for i,r in enumerate(image['records']) if r['instance_id']==previous['instance_id'])
            image['records'][position]=record;batch['records'][index]=record
            self._write(self._base(account,batch_id)/'batch.json',batch)
            if self.batch and self.batch['id']==batch_id:self.batch=batch
            return batch

    def _stop_scanner(self):
        scanner=self.scanner
        if scanner:
            scanner._stopped=True
            if hasattr(scanner,'emergency_stop'):
                try:scanner.emergency_stop()
                except Exception:pass

    def stop_capture(self):
        with self.lock:
            if not self.job.get('running') or not self.job.get('capture_running'):return self.status()
            self.capture_stop.set()
            self.job['capture_stopping']=True
            self.job['message']='正在停止采集；已截图的装备将继续识别'
        self._stop_scanner()
        return self.status()

    def cancel(self):
        self.stop.set();self.capture_stop.set()
        self._stop_scanner()
        return self.status()

    def close(self):
        self.cancel()
        if self.thread:self.thread.join(timeout=3)
