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
from .accounts import AccountProfiles, validate_uid

class Cancelled(RuntimeError):
    pass


class InventoryService:
    def __init__(self, directory, adapter_factory=create_adapter, components=None, vision=None, uid_reader=None):
        self.directory = Path(directory)
        self.adapter_factory = adapter_factory
        self.components = components
        self.vision = vision
        self.uid_reader = uid_reader
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.active_adapter = None
        self.native_operation = None
        self.job = {'running':False, 'message':'尚未开始同步', 'domains':{}}
        from .equipment import EquipmentService
        self.equipment = EquipmentService(self)
        from .management import BackpackManagement
        self.management = BackpackManagement(self)
        from .state_actions import EquipmentStateActions
        self.state_actions = EquipmentStateActions(self)
        from .decomposition import DecompositionService
        self.decomposition = DecompositionService(self)
        from .ui_assembly import UIAssemblyService
        self.ui_assembly = UIAssemblyService(self)
        self.config = {'account':'默认账号', 'adapter':'nte-native-v1'}
        try:
            self.config.update(json.loads((self.directory/'config.json').read_text(encoding='utf-8')))
        except (OSError,ValueError):
            pass
        self.accounts = AccountProfiles(self.directory, getattr(vision, 'directory', None))
        self.accounts.discover_legacy(self.config.get('account'))
        native_account = self.config.get('native_account')
        native_profile = self.accounts.get(native_account) if isinstance(native_account, str) and native_account.strip() else None
        if not native_profile or not native_profile.get('uid'):
            native_account = None
            previous_account = self.config.get('account')
            previous_profile = self.accounts.get(previous_account) if isinstance(previous_account, str) and previous_account.strip() else None
            if previous_profile and previous_profile.get('uid'):
                previous_snapshot = self.load(previous_account)
                equipment = previous_snapshot.get('inventory', {}).get('equipment', {})
                raw = previous_snapshot.get('domains', {}).get('equipment')
                session = previous_snapshot.get('native_sessions', {}).get('equipment', {})
                if (previous_snapshot.get('account_uid') in (None, previous_profile['uid'])
                        and isinstance(raw, dict) and equipment.get('source', {}).get('adapter') == 'nte-native-v1'
                        and isinstance(session, dict) and type(session.get('pid')) is int and session.get('pid') > 0):
                    native_account = previous_account
        self.config['native_account'] = native_account
        if native_account:
            self.config['account'] = native_account

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
            result['ocr_batch']={key:batch.get(key) for key in ('id','mode','state','storage','capture_error','expected','processed','account_uid')}
        elif selected not in ('native','none'):
            raise ValueError('数据来源无效')
        return result

    def delete(self, account, source):
        if not isinstance(account,str) or not account.strip() or len(account)>80:
            raise ValueError('账号标签无效')
        with self.lock:
            if self.native_busy():
                raise ValueError('请等待原生读取完成后再删除')
            if source == 'native':
                path=self._path(account)
                path.unlink(missing_ok=True)
                path.with_suffix('.previous.json').unlink(missing_ok=True)
            elif isinstance(source,str) and source.startswith('ocr:') and self.vision:
                self.vision.delete(account,source[4:])
            else:
                raise ValueError('请选择要删除的已保存数据')
            self.management.delete_source(account, source)
        return {'deleted':True,'source':source}

    def delete_account(self, account, uid):
        """Remove one selected profile and its local data, including backups and plans."""
        import shutil
        from contextlib import nullcontext
        from .equipment_plans import path_for
        with self.lock, self.vision.lock if self.vision else nullcontext():
            if self.native_busy() or (self.vision and self.vision.job.get('running')):
                raise ValueError('请等待读取、扫描或装备操作结束后再删除账号')
            profile = self.accounts.get(account)
            if not profile or profile.get('uid') != uid:
                raise ValueError('账号资料已变化，请刷新后重新确认删除')
            native = self._path(account)
            files = [native, native.with_suffix('.previous.json'), path_for(self.directory, account),
                     self.management.path_for(account)]
            root = self.directory.resolve()
            for file in files:
                if file.is_symlink() or not file.resolve().is_relative_to(root):
                    raise ValueError('账号文件路径无效，已停止删除')
            vision_root = self.vision._base(account, '0'*24).parent if self.vision else None
            if vision_root is not None:
                boundary = self.vision.directory.resolve()
                if vision_root.is_symlink() or vision_root.resolve().parent != boundary:
                    raise ValueError('账号截图目录无效，已停止删除')
                if vision_root.exists():shutil.rmtree(vision_root)
            for file in files:file.unlink(missing_ok=True)
            self.accounts.remove(account)
            if self.config.get('native_account') == account:self.config['native_account'] = None
            remaining = self.accounts.list_profiles(self.config.get('native_account'))
            if self.config.get('account') == account:
                self.config['account'] = self.config.get('native_account') or (remaining[0]['account'] if remaining else '默认账号')
            self._save_config()
            if self.equipment.selection and self.equipment.selection.get('account') == account:
                self.equipment.selection = None
                self.equipment.plan = None
            if self.job.get('account') == account:self.job = {'running':False,'message':'已删除账号数据','domains':{}}
            if self.vision and self.vision.batch and self.vision.batch.get('account') == account:
                self.vision.batch = None
                self.vision.job = {'running':False,'message':'已删除账号截图与识别数据','processed':0,'total':0}
            return {'deleted':True,'account':account,'account_profiles':remaining,'config':dict(self.config)}

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
            profiles = self.accounts.list_profiles(config.get('native_account'))
            selected = self.accounts.get(config.get('account'))
            return json.loads(json.dumps({'config':config, 'job':self.job, 'native_operation':self.native_operation,
                'account_profiles':profiles, 'account_uid':selected.get('uid') if selected else None,
                'equipment_job':self.equipment.status(), 'ui_assembly_job':self.ui_assembly.status(),
                'state_action_job':self.state_actions.status(),
                'decomposition_job':self.decomposition.status(),
                'components':self.components.status() if self.components else None, 'vision_job':dict(self.vision.job) if self.vision else None}))

    def _save_config(self):
        self._write(self.directory/'config.json',self.config)

    def select_account(self, account):
        """Validate a profile for browsing without changing the last native-read account."""
        with self.lock:
            profile = self.accounts.select(account)
            return {'selected':self.accounts.summary(profile), 'account_profiles':self.accounts.list_profiles(profile['account'])}

    def set_account_note(self, account, note):
        with self.lock:
            profile = self.accounts.set_note(account, note)
            return {'profile':self.accounts.summary(profile), 'account_profiles':self.accounts.list_profiles(self.config.get('account'))}

    def bind_account_uid(self, account, uid, replace_existing=False):
        with self.lock:
            self.accounts.discover_legacy()
            result = self.accounts.bind(account, uid, replace_existing)
            from . import equipment_plans
            for field in ('source', 'target', 'displaced'):
                profile = result.get(field)
                if not profile:
                    continue
                key = profile['account']
                profile['data'] = self.accounts.data_counts(
                    key, self.vision, self._path(key), equipment_plans.path_for(self.directory, key))
            result['account_profiles'] = self.accounts.list_profiles(self.config.get('account'))
            return result

    def verify_live_account(self, account, pid):
        """Fail closed before equipment RPCs if the selected UID is not live."""
        if self.uid_reader is None:
            return None
        profile = self.accounts.get(account)
        if not profile or not profile.get('uid'):
            raise ValueError('此账号资料尚未绑定游戏UID；先读取游戏数据或手动绑定后再装配')
        actual = validate_uid(self.uid_reader(pid))
        if actual != profile['uid']:
            raise ValueError('当前游戏UID与选中的账号资料不一致，未派发装备操作')
        return actual

    def native_busy(self):
        with self.lock:
            return self.job['running'] or self.native_operation is not None

    def start(self, folder=None, account=None):
        if account is not None and (not isinstance(account,str) or not account.strip() or len(account)>80):
            raise ValueError('账号资料无效')
        if self.components is not None:
            folder = str(self.components.component_root())
        elif not isinstance(folder,str) or len(folder)>1024:
            raise ValueError('内置原生组件尚未准备')
        with self.lock:
            if self.native_busy():
                raise ValueError('已有同步任务，请等待完成或取消')
            if self.vision and self.vision.job.get('running'):
                raise ValueError('请先结束截图扫描，再读取原生数据')
            adapter = self.adapter_factory(self.config.get('adapter','nte-native-v1'))
            adapter.prepare(folder)
            self.stop.clear()
            requested_account = account.strip() if account else self.config.get('account', '默认账号')
            self.job = {'running':True,'message':'连接游戏采集组件并确认UID…','domains':{},'account':requested_account}
            self.thread = threading.Thread(target=self._run,args=(adapter,requested_account),daemon=True)
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
            if self.uid_reader is None:
                raise ValueError('无法确认当前游戏 UID，本次未保存数据。请检查内置 UID 读取组件。')
            account_uid = validate_uid(self.uid_reader(getattr(adapter, 'pid', None)))
            profile = self.accounts.resolve_uid(account_uid)
            account = profile['account']
            with self.lock:
                self.config['account'] = account
                self.config['native_account'] = account
                self.config['adapter'] = adapter.adapter_id
                self._save_config()
                self.job['account'] = account
                self.job['account_uid'] = account_uid
                self.job['message'] = '已确认当前游戏 UID，正在读取账号数据…'
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
                    candidate['account_uid'] = account_uid
                    if observation.raw_snapshot is not None:
                        candidate['domains'][kind] = observation.raw_snapshot
                        if kind == 'equipment' and adapter.adapter_id == 'nte-native-v1':
                            header = observation.raw_snapshot.get('header', {})
                            pid = getattr(adapter, 'pid', None)
                            if type(pid) is int and pid > 0:
                                candidate['native_sessions'] = {**stored.get('native_sessions', {}), 'equipment': {
                                    'pid': pid, 'provider_id': header.get('providerId'),
                                    'domain_key': header.get('domainKey'), 'snapshot_id': header.get('snapshotId'),
                                    'revision': header.get('revision'), 'saved_at': observation.raw_snapshot.get('saved_at')}}
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
        self.equipment.cancel()
        if self.equipment.thread:
            self.equipment.thread.join(timeout=20)
        with self.lock:
            adapter = self.active_adapter
        if adapter:
            try:
                adapter.abort()
            except Exception:
                pass
        if self.thread:
            self.thread.join(timeout=3)
