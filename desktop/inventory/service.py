"""Source-independent sync jobs and atomic Keke inventory storage."""
from pathlib import Path
import hashlib
import json
import os
import secrets
import threading
import diagnostics
from .adapters import create_adapter, SessionChanged
from .contract import SCHEMA_VERSION, DOMAIN_NAMES, migrate_document, validate_domain

class Cancelled(RuntimeError):
    pass


class InventoryService:
    def __init__(self, directory, adapter_factory=create_adapter, components=None, vision=None):
        self.directory = Path(directory)
        self.adapter_factory = adapter_factory
        self.components = components
        self.vision = vision
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.active_adapter = None
        self.job = {'running':False, 'message':'尚未开始同步', 'domains':{}}
        self.config = {'account':'默认账号', 'adapter':'nte-native-v1'}
        try:
            self.config.update(json.loads((self.directory/'config.json').read_text(encoding='utf-8')))
        except (OSError,ValueError):
            pass

    def _path(self, account):
        return self.directory / ('account-' + hashlib.sha256(account.encode()).hexdigest() + '.json')

    def load(self, account):
        try:
            return migrate_document(json.loads(self._path(account).read_text(encoding='utf-8')))
        except FileNotFoundError:
            return {'schema_version':SCHEMA_VERSION,'account':account,'domains':{},'inventory':{}}

    def view(self, account, source='auto'):
        """Compose account data from native snapshots and immutable OCR evidence.

        The selected source is a view, never a destructive merge or UID guess.
        """
        from .vision_source import vision_domain
        stored=self.load(account)
        sources=[]
        if stored.get('inventory'):
            data=stored['inventory'].get('equipment',{'records':[],'coverage':{}})
            sources.append({'id':'native','label':'原生装备库存','count':len(data['records']),
                            'complete':data['coverage'].get('collection_complete') is True,'saved_at':data.get('saved_at')})
        history=self.vision.history(account) if self.vision else []
        for row in history:
            sources.append({'id':'ocr:'+row['id'],'label':'OCR · '+str(row.get('mode')),
                            'complete':row.get('complete') is True,'saved_at':row.get('saved_at'),'state':row.get('state'),'count':row.get('processed',0),'mode':row.get('mode')})
        selected=source
        if source=='auto':
            selected='native' if any(s['id']=='native' for s in sources) else next((s['id'] for s in sources if s['complete']),next((s['id'] for s in sources if s.get('count',0)>0),sources[0]['id'] if sources else 'none'))
        result={**stored,'inventory':dict(stored.get('inventory',{})),'sources':sources,'selected_source':selected}
        if selected.startswith('ocr:'):
            if selected not in {s['id'] for s in sources}:raise ValueError('当前账号没有此识别批次')
            batch=self.vision.load(account,selected[4:])
            result['inventory']['equipment']=vision_domain(batch)
            result['ocr_batch']={key:batch.get(key) for key in ('id','mode','state','storage','capture_error','expected','processed')}
        elif selected not in ('native','none'):
            raise ValueError('数据来源无效')
        return result

    def delete(self, account, source):
        if not isinstance(account,str) or not account.strip() or len(account)>80:
            raise ValueError('账号标签无效')
        with self.lock:
            if self.job['running']:
                raise ValueError('请等待原生读取完成后再删除')
            if source == 'native':
                path=self._path(account)
                path.unlink(missing_ok=True)
                path.with_suffix('.previous.json').unlink(missing_ok=True)
            elif isinstance(source,str) and source.startswith('ocr:') and self.vision:
                self.vision.delete(account,source[4:])
            else:
                raise ValueError('请选择要删除的已保存数据')
        return {'deleted':True,'source':source}

    def _write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.' + secrets.token_hex(6) + '.tmp')
        try:
            temporary.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8')
            os.replace(temporary,path)
        finally:
            temporary.unlink(missing_ok=True)

    def status(self):
        with self.lock:
            config = {key:value for key,value in self.config.items() if key!='folder'}
            return json.loads(json.dumps({'config':config, 'job':self.job, 'components':self.components.status() if self.components else None, 'vision_job':dict(self.vision.job) if self.vision else None}))

    def start(self, folder=None, account=None):
        if not isinstance(account,str) or not account.strip() or len(account)>80:
            raise ValueError('请填写80字以内的本机账号标签')
        if self.components is not None:
            folder = str(self.components.component_root())
        elif not isinstance(folder,str) or len(folder)>1024:
            raise ValueError('内置原生组件尚未准备')
        with self.lock:
            if self.job['running']:
                raise ValueError('已有同步任务，请等待完成或取消')
            adapter = self.adapter_factory(self.config.get('adapter','nte-native-v1'))
            adapter.prepare(folder)
            self.config = {'account':account.strip(), 'adapter':adapter.adapter_id}
            self._write(self.directory/'config.json',self.config)
            self.stop.clear()
            self.job = {'running':True,'message':'连接游戏采集组件…','domains':{},'account':account.strip()}
            self.thread = threading.Thread(target=self._run,args=(adapter,account.strip()),daemon=True)
            self.thread.start()
            diagnostics.event('原生读取开始')
        return self.status()

    def check(self):
        if self.stop.is_set():
            raise Cancelled('同步已取消，上次成功数据仍保留')

    def cancel(self):
        with self.lock:
            self.stop.set()
        return self.status()

    def _run(self, adapter, account):
        try:
            self.check()
            with self.lock:
                self.active_adapter = adapter
            adapter.open(self.check)
            stored = self.load(account)
            for kind in adapter.domains:
                self.check()
                if kind not in DOMAIN_NAMES:
                    raise ValueError('采集器返回未知类别')
                with self.lock:
                    self.job['message'] = '正在读取：' + kind
                    self.job['domains'][kind] = {'state':'reading'}
                try:
                    previous = stored.get('domains',{}).get(kind)
                    if stored.get('inventory',{}).get(kind,{}).get('source',{}).get('adapter') != adapter.adapter_id:
                        previous = None
                    observation = adapter.read(kind,self.check,previous)
                    data = validate_domain(kind,observation.data)
                    if data['source']['adapter'] != adapter.adapter_id:
                        raise ValueError('采集来源与适配器不一致')
                    candidate = {**stored,'inventory':{**stored.get('inventory',{}),kind:data},
                                 'domains':{**stored.get('domains',{})}}
                    if observation.raw_snapshot is not None:
                        candidate['domains'][kind] = observation.raw_snapshot
                    else:
                        candidate['domains'].pop(kind,None)
                    with self.lock:
                        self.check()
                        path = self._path(account)
                        if path.exists():
                            self._write(path.with_suffix('.previous.json'),json.loads(path.read_text(encoding='utf-8')))
                        self._write(path,candidate)
                        stored = candidate
                        self.job['domains'][kind] = {'state':'saved','count':len(data['records'])}
                except (Cancelled,SessionChanged):
                    raise
                except Exception as error:
                    diagnostics.failure('原生类别读取失败：'+kind)
                    with self.lock:
                        self.job['domains'][kind] = {'state':'error','error':str(error)}
            with self.lock:
                successes = sum(v['state']=='saved' for v in self.job['domains'].values())
                self.job['message'] = f'已保存{successes}类数据；未成功的类别保留上次快照'
        except Exception as error:
            diagnostics.failure('原生读取任务结束异常')
            with self.lock:
                self.job['message'] = str(error)
        finally:
            try:
                adapter.close()
            except Exception:
                pass
            with self.lock:
                self.active_adapter = None
                self.job['running'] = False
            diagnostics.event('原生读取结束',domains={k:v['state'] for k,v in self.job['domains'].items()})

    def close(self):
        self.cancel()
        with self.lock:
            adapter = self.active_adapter
        if adapter:
            try:
                adapter.abort()
            except Exception:
                pass
        if self.thread:
            self.thread.join(timeout=3)
