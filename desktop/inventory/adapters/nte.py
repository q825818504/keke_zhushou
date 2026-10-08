"""NTE-specific protocol and field mapping; replaceable compatibility adapter."""
from pathlib import Path
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
import subprocess
from . import Observation, SessionChanged
from ..core import Core
from ..catalog import display_names
from ..snapshot import DOMAINS, read_snapshot
from ..contract import CONTRACT_VERSION, validate_domain

def capture_pid():
    if os.name != 'nt':
        raise RuntimeError('游戏同步仅支持Windows桌面版')
    script = "@(Get-Process HTGame -ErrorAction SilentlyContinue | ForEach-Object { @{pid=$_.Id;created=$_.StartTime.ToFileTime()} }) | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('无法核对游戏进程')
    values = json.loads(result.stdout or '[]')
    if isinstance(values,dict):
        values = [values]
    if len(values)!=1:
        raise RuntimeError('请登录游戏并只保留一个游戏进程')
    value = values[0]
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.WaitNamedPipeW.argtypes = [ctypes.c_wchar_p,ctypes.c_uint32]
    kernel.WaitNamedPipeW.restype = ctypes.c_int
    pipe = chr(92)*2 + '.' + chr(92) + 'pipe' + chr(92) + 'nte.capture.v1.' + str(value['pid']) + '.' + str(value['created'])
    if not kernel.WaitNamedPipeW(pipe,1) and ctypes.get_last_error() not in (5,121,231):
        raise RuntimeError('当前游戏的原生组件未就绪。请在账号数据中检测环境并部署配套组件，重新启动游戏并登录后重试')
    return value['pid']


def merge_profiles(previous, observations, timestamp):
    """Accumulated observed fields; raw pages remain separate and unchanged."""
    merged = {row['character_id']:json.loads(json.dumps(row)) for row in previous}
    for row in observations:
        target = merged.setdefault(row['character_id'], {'character_id':row['character_id'], '_field_observed_at':{}})
        for field, value in row.items():
            if field == 'character_id' or (value is None and not (field == 'fork_id' and row.get('fork_observed') is True)):
                continue
            if field.startswith('fork_') and row.get('fork_observed') is not True:
                continue
            if field in ('selected_awaken_effect_ids','awakening_selection_initialized') and row.get('awakening_selection_initialized') is not True:
                continue
            if field == 'skill_levels' and isinstance(value,dict):
                value = {**target.get(field,{}), **{k:v for k,v in value.items() if v is not None}}
            target[field] = value
            target.setdefault('_field_observed_at',{})[field] = timestamp
    return [merged[key] for key in sorted(merged)]


def core_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def normalize_attributes(values):
    if not isinstance(values,list):
        return None
    return [{'id':row.get('property_id'),'name':row.get('names',{}).get('zh_cn'),
             'value':row.get('value'),'is_percent':row.get('percent')} for row in values]


def normalize_snapshot(kind, raw):
    header=raw.get('header',{})
    source={'adapter':'nte-native-v1','session':header.get('providerId'),
            'snapshot':header.get('snapshotId'),'revision':header.get('revision')}
    coverage={'scope':header.get('collectionScope',header.get('domain',kind)),
              'collection_complete':header.get('collectionComplete',header.get('enumerationComplete')),
              'account_complete': True if header.get('complete') is True else None}
    rows=raw.get('observed_profiles',raw.get('rows',[])) if kind=='characters' else raw.get('rows',[])
    names=raw.get('display_names',{})
    records=[]
    for row in rows:
        if kind=='equipment':
            identity=row.get('uid',{})
            if type(identity.get('slot')) is not int or type(identity.get('serial')) is not int:
                raise ValueError('旧装备记录缺少有效实例ID')
            record={'instance_id':f"nte-equipment:{identity['slot']}:{identity['serial']}",
                'definition_id':str(row['item_id']) if row.get('item_id') is not None else None,
                'category':{'module':'drive','core':'tape'}.get(row.get('kind'),'other'),
                'name':row.get('names',{}).get('zh_cn') or names.get(str(row.get('item_id'))) or row.get('name'),
                'shape':row.get('geometry'),'cell_count':row.get('grid'),'level':row.get('level'),
                'max_level':row.get('max_level'),'rarity':row.get('quality'),'set_id':row.get('suit_id'),
                'is_equipped':row.get('equipped'),'is_locked':row.get('locked'),'is_discarded':row.get('discarded'),
                'equipped_character_id':str(row['equipped_character_id']) if row.get('equipped_character_id') else None,
                'placement':row.get('equipped_placement'), 'main_attributes':normalize_attributes(row.get('main_stats')),
                'sub_attributes':normalize_attributes(row.get('sub_stats'))}
        elif kind=='characters':
            record={'character_id':str(row['character_id']),'name':names.get(str(row['character_id'])),
                'level':row.get('character_level'),'breakthrough':row.get('breakthrough_stage'),
                'awakening':row.get('awakening_level'),'awakening_selection_known':row.get('awakening_selection_initialized'),
                'selected_awakening_effects':row.get('selected_awaken_effect_ids'),
                'skills':row.get('skill_levels'),'arc_drive_known':row.get('fork_observed'),
                'arc_drive':{'definition_id':row.get('fork_id'),'level':row.get('fork_level'),
                    'breakthrough':row.get('fork_breakthrough_stage'),'refinement':row.get('fork_refinement_level')},
                'field_observed_at':row.get('_field_observed_at',{})}
        else:
            record={'name':row.get('displayName'),'definition_id':row.get('ItemID'),
                    'quantity':row.get('Amount'),'data':row}
        records.append(record)
    value={'contract_version':CONTRACT_VERSION,'source':source,'coverage':coverage,
           'saved_at':raw.get('saved_at'),'records':records}
    return validate_domain(kind,value)


class NteAdapter:
    adapter_id='nte-native-v1'
    domains=tuple(DOMAINS)

    def __init__(self,core_factory=Core,pid_reader=capture_pid):
        self.factory=core_factory
        self.pid_reader=pid_reader
        self.core=None
        self.provider=None

    def prepare(self,folder):
        selected = Path(folder).expanduser().resolve()
        root = selected
        if not (root/'component-bundle.json').is_file() and (root/'_internal/component-bundle.json').is_file():
            root = (root/'_internal').resolve()
        manifest_file = root/'third_party/native-capture/component-bundle.json'
        if not manifest_file.is_file():
            manifest_file = root/'component-bundle.json'
        if not manifest_file.is_file():
            raise ValueError('内置原生组件清单缺失，请重新准备完整组件包')
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        core_relative = manifest.get('roles',{}).get('core')
        if core_relative not in ('third_party/native-capture/core/nte-core.exe', 'nte-core.exe'):
            raise ValueError('组件目录布局不兼容')
        executable = (root/core_relative).resolve()
        if not executable.is_relative_to(root) or not executable.is_file():
            raise ValueError('目录缺少原生nte-core.exe')
        # User-selected component has to match the public pinned build, not just its local manifest.
        expected = json.loads((Path(__file__).parents[1]/'component-identity.json').read_text(encoding='utf-8'))
        if core_digest(executable)!=expected['core_sha256']:
            raise ValueError('Core不是已适配的公开版本（0.4.4）；请使用说明中的固定版本组件')
        self.root=root
        self.executable=executable

    def open(self,check):
        check()
        self.pid=self.pid_reader()
        self.core=self.factory(self.executable,self.pid,self.root/'data')
        check()

    def read(self,kind,check,previous=None):
        snapshot=read_snapshot(self.core,kind,check)
        provider=snapshot['header']['providerId']
        if self.provider is not None and provider!=self.provider:
            raise SessionChanged('游戏会话已变化，停止本次同步')
        self.provider=provider
        if self.pid_reader()!=self.pid:
            raise SessionChanged('游戏进程已变化，停止本次同步')
        snapshot['saved_at']=datetime.now(timezone.utc).isoformat()
        snapshot['display_names']=display_names(self.root,kind,snapshot['rows'])
        if kind=='characters':
            snapshot['observed_profiles']=merge_profiles((previous or {}).get('observed_profiles',[]),snapshot['rows'],snapshot['saved_at'])
        return Observation(normalize_snapshot(kind,snapshot),snapshot)

    def abort(self):
        if self.core:
            self.core.close()

    def close(self):
        if not self.core:
            return
        core=self.core
        for domain in ('inventory','character','team','environment'):
            if f'{domain}.snapshot.v1' in core.hello.get('capabilities',[]):
                try:core.call('native.snapshot.disable',{'domain':domain},timeout=1.5)
                except Exception:pass
        if 'inventory.all_items.v1' in core.hello.get('capabilities',[]):
            try:core.call('native.snapshot.disable',{'domain':'inventory','scope':'all_items'},timeout=1.5)
            except Exception:pass
        core.close()
        self.core=None
