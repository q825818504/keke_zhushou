"""Native equipment workflow: frozen intent, live identity checks and observed results.

RPC names/UID contract verified against NTE Drive Calculator commit
0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1. No arbitrary RPC is exposed.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import secrets
import threading
import time

from .adapters.nte import NteAdapter
from .core import CoreRpcError
from .snapshot import uid
from .equipment_assembly import assembly_plan, resolve_request, verify_operation
from .equipment_layout import CATALOG, native_position, shape, visual_position
from .snapshot import require_current_revision
from . import equipment_plans

CAPABILITIES = {'equipment', 'native_equipment_v1'}
KINDS = {'drive': 'module', 'tape': 'core'}
STATE_FIELDS = {'equipped', 'equipped_character_id', 'equipped_character_uid', 'equipped_placement'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def equipment_state(raw, context):
    rows = raw['rows']
    characters = raw['pages'][0]['characters']
    owners = {}
    identities = set()
    for character in characters:
        cid = character.get('character_id')
        identity = uid(character.get('uid'))
        if type(cid) is not int or cid <= 0 or cid in owners or identity in identities:
            raise ValueError('角色实例身份不完整或重复，请重新读取')
        owners[cid] = character['uid']
        identities.add(identity)
    items = {}
    for row in rows:
        key = uid(row.get('uid'))
        if key in items or type(row.get('equipped')) is not bool:
            raise ValueError('装备身份重复或装备状态未知，无法执行卸装')
        if row['equipped']:
            cid = row.get('equipped_character_id')
            if type(cid) is not int or cid not in owners or row.get('equipped_character_uid') != owners[cid]:
                raise ValueError('装备所属角色实例未能核实，无法执行卸装')
        items[key] = deepcopy(row)
    return {'context': context, 'characters': owners, 'items': items}


def fingerprint(state):
    return digest({'context': state['context'], 'characters': sorted(state['characters'].items()),
                   'items': [state['items'][key] for key in sorted(state['items'])]})


def _expected_batch_transition(before, observed, final):
    """Allow only planned equipment-state transitions while a one-key request settles."""
    before_context, observed_context = before.get('context'), observed.get('context')
    # equip_one_key can invalidate and rebuild the native inventory projection,
    # rotating its domain key. Keep the process/provider and separate equipment
    # control identity fixed; roster and item checks below validate the new view.
    same_source = (isinstance(before_context, tuple) and isinstance(observed_context, tuple)
                   and len(before_context) == len(observed_context) == 3
                   and before_context[:2] == observed_context[:2])
    if (not same_source or before.get('control_context') != observed.get('control_context')
            or before['characters'] != observed['characters'] or before['items'].keys() != observed['items'].keys()):
        return False
    empty = {'equipped': False, 'equipped_character_id': None,
             'equipped_character_uid': None, 'equipped_placement': None}
    for key, original in before['items'].items():
        current = observed['items'][key]
        target = final['items'][key]
        if ({k: v for k, v in original.items() if k not in STATE_FIELDS}
                != {k: v for k, v in current.items() if k not in STATE_FIELDS}):
            return False
        current_state = {field: current.get(field) for field in STATE_FIELDS}
        original_state = {field: original.get(field) for field in STATE_FIELDS}
        target_state = {field: target.get(field) for field in STATE_FIELDS}
        if current_state not in (original_state, target_state, empty):
            return False
    return True


def _matches_batch_final(before, observed, expected_fingerprint):
    before_context, observed_context = before.get('context'), observed.get('context')
    if (not isinstance(before_context, tuple) or not isinstance(observed_context, tuple)
            or len(before_context) != 3 or len(observed_context) != 3
            or before_context[:2] != observed_context[:2]
            or before.get('control_context') != observed.get('control_context')):
        return False
    # Compare the whole planned gear state under the original account context,
    # while persisting the actual key from the freshly captured snapshot.
    return fingerprint({**observed, 'context': before_context}) == expected_fingerprint


def verify_unequipped(before, after, target):
    if (before['context'] != after['context'] or before.get('control_context') != after.get('control_context')
            or before['characters'] != after['characters']):
        raise ValueError('游戏会话或角色实例已变化，停止后续卸装')
    if before['items'].keys() != after['items'].keys():
        raise ValueError('装备集合已变化，停止后续卸装')
    for key, original in before['items'].items():
        observed = after['items'][key]
        if key != target:
            if original != observed:
                raise ValueError('其他装备发生变化，停止后续卸装，请重新读取')
        elif ({k: v for k, v in original.items() if k not in STATE_FIELDS}
              != {k: v for k, v in observed.items() if k not in STATE_FIELDS}):
            raise ValueError('目标装备资料发生变化，停止后续卸装')
    observed = after['items'][target]
    return (observed.get('equipped') is False and observed.get('equipped_character_id') is None
            and observed.get('equipped_character_uid') is None and observed.get('equipped_placement') is None)


class EquipmentService:
    def __init__(self, inventory, adapter_factory=NteAdapter, now=time.monotonic, sleep=time.sleep):
        self.inventory = inventory
        self.factory, self.now, self.sleep = adapter_factory, now, sleep
        self.plan = None
        self.selection = None
        self.stop = threading.Event()
        self.thread = None
        self.job = {'running': False, 'state': 'idle', 'message': '尚未执行原生卸装',
                    'completed': 0, 'total': 0, 'results': []}

    def status(self):
        with self.inventory.lock:
            return deepcopy(self.job)

    def _reserve(self):
        with self.inventory.lock:
            if self.inventory.job['running'] or self.inventory.native_operation:
                raise ValueError('已有原生读取或装备操作，请等待完成')
            if self.inventory.vision and self.inventory.vision.job.get('running'):
                raise ValueError('请先结束截图扫描，再操作装备')
            self.inventory.native_operation = 'equipment'

    def _release(self):
        with self.inventory.lock:
            self.inventory.native_operation = None

    def _open(self):
        adapter = self.factory()
        try:
            if not self.inventory.components:
                raise ValueError('内置组件尚未准备')
            adapter.prepare(str(self.inventory.components.component_root()))
            adapter.open(lambda: None)
            if not CAPABILITIES.issubset(adapter.core.hello.get('capabilities', [])):
                raise ValueError('当前组件没有原生装备执行能力，请检测组件并重启游戏')
            return adapter
        except Exception:
            try: adapter.close()
            except Exception: pass
            raise

    def _identity(self, adapter):
        if adapter.pid_reader() != adapter.pid:
            raise ValueError('游戏进程已变化，停止装备操作')
        status = adapter.core.call('equipment.status', {})
        if status.get('ready') is not True:
            raise ValueError('游戏装备接口未就绪，请返回可操作场景后重新检测')
        values = tuple(status.get(key) for key in ('providerId', 'domainKey'))
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError('装备接口缺少来源身份')
        return (adapter.pid, *values)

    def _capture(self, adapter):
        context = self._identity(adapter)
        observation = adapter.read('equipment', lambda: None)
        if self._identity(adapter) != context or observation.raw_snapshot['header']['providerId'] != context[1]:
            raise ValueError('读取期间游戏会话发生变化')
        header = observation.raw_snapshot['header']
        # equipment.status uses the control-domain key; inventory.snapshot uses a
        # different domain key. Persist/compare inventory identity with inventory,
        # and independently freeze control identity for the running operation.
        state = equipment_state(observation.raw_snapshot, (context[0], header['providerId'], header['domainKey']))
        state['control_context'] = context
        return state, observation

    def _roster(self, state, raw):
        # Equipment catalog names do not double as character names.
        from .catalog import display_names
        character_names = display_names(self.inventory.components.component_root(), 'characters',
                                        [{'character_id': cid} for cid in state['characters']])
        result = []
        for cid in sorted(state['characters']):
            rows = [row for row in state['items'].values() if row.get('equipped') is True
                    and row.get('equipped_character_id') == cid]
            result.append({'character_id': cid, 'name': character_names.get(str(cid), '角色 ' + str(cid)),
                           'drive': sum(row.get('kind') == 'module' for row in rows),
                           'tape': sum(row.get('kind') == 'core' for row in rows)})
        return result

    def inspect(self, account=None):
        """Prepare reusable opaque gear handles from the account's saved native snapshot."""
        account = account or self.inventory.config.get('account')
        if not isinstance(account, str) or not account.strip() or len(account) > 80:
            raise ValueError('账号标签无效')
        self._ensure_idle()
        self.selection = None
        self.plan = None
        profile = self.inventory.accounts.get(account.strip())
        if not profile or not profile.get('uid'):
            return {'ready': False, 'message': '当前资料尚未绑定游戏 UID；请先读取游戏数据，或在背包数据中确认旧资料归属。',
                    'account': account.strip(), 'account_uid': None, 'characters': [], 'items': [], 'equipment_count': 0}
        stored = self.inventory.load(account.strip())
        stored_uid = stored.get('account_uid')
        if stored_uid is not None and stored_uid != profile['uid']:
            return {'ready': False, 'message': '快照 UID 与账号资料不一致；为避免跨账号读取，请检查账号资料。',
                    'account': account.strip(), 'account_uid': profile['uid'], 'characters': [], 'items': [], 'equipment_count': 0}
        raw = stored.get('domains', {}).get('equipment')
        data = stored.get('inventory', {}).get('equipment', {})
        session = stored.get('native_sessions', {}).get('equipment', {})
        header = raw.get('header', {}) if isinstance(raw, dict) else {}
        if (not isinstance(data, dict) or data.get('source', {}).get('adapter') != 'nte-native-v1'
                or not isinstance(raw, dict)):
            return {'ready': False, 'message': '该 UID 尚无 DLL 原生装备快照；请在当前游戏账号中重新读取所有数据。',
                    'account': account.strip(), 'account_uid': profile['uid'],
                    'characters': [], 'items': [], 'equipment_count': 0}
        if (not isinstance(session, dict) or not isinstance(header, dict)
                or type(session.get('pid')) is not int or session.get('pid') <= 0
                or session.get('provider_id') != header.get('providerId')
                or session.get('domain_key') != header.get('domainKey')
                or session.get('snapshot_id') != header.get('snapshotId')
                or session.get('revision') != header.get('revision')):
            return {'ready': False, 'message': '此快照缺少原生进程来源信息；请在当前游戏账号中重新读取一次。',
                    'account': account.strip(), 'account_uid': profile['uid'],
                    'characters': [], 'items': [], 'equipment_count': len(data.get('records', []))}
        context = (session['pid'], session['provider_id'], session['domain_key'])
        state = equipment_state(raw, context)
        keys, labels, items = {}, {}, []
        for index, key in enumerate(sorted(state['items']), 1):
            row = state['items'][key]
            if row.get('kind') not in ('module', 'core'): continue
            ident = secrets.token_urlsafe(18)
            keys[ident], labels[key] = key, '#' + str(index)
            try: cells = shape(row) if row['kind'] == 'module' else None
            except ValueError: cells = None
            items.append({'id': ident, 'label': labels[key], 'category': 'drive' if row['kind'] == 'module' else 'tape',
                'name': row.get('names', {}).get('zh_cn') or str(row.get('item_id', '装备')),
                'level': row.get('level'), 'rarity': row.get('quality'), 'shape': row.get('geometry'), 'cells': cells,
                'owner': row.get('equipped_character_id') if row['equipped'] else None,
                'placement': visual_position(row, row.get('equipped_placement')) if cells else None,
                'main_stats': row['main_stats'] if isinstance(row.get('main_stats'), list) else [],
                'sub_stats': row['sub_stats'] if isinstance(row.get('sub_stats'), list) else []})
        selection_id = secrets.token_urlsafe(24)
        self.selection = {'id': selection_id, 'account': account.strip(), 'created': self.now(),
                          'fingerprint': fingerprint(state), 'context': context,
                          'session': deepcopy(session), 'state': state, 'raw': raw,
                          'keys': keys, 'labels': labels}
        characters = self._roster(state, raw)
        for row in characters:
            row['board'] = CATALOG['characters'].get(str(row['character_id']), {}).get('cells')
        return {'ready': True, 'account': account.strip(), 'account_uid': profile['uid'], 'saved_at': raw.get('saved_at'),
                'characters': characters, 'items': items, 'selection_id': selection_id,
                'equipment_count': len(state['items']), 'core_version': '0.4.4',
                'saved_plans': equipment_plans.list_plans(self.inventory.directory, account.strip(), state, self.selection)}

    def save_build_plan(self, account, selection_id, character_id, core, modules, exclude_others, complete):
        if not isinstance(account, str): raise ValueError('账号无效')
        with self.inventory.lock:
            if self.inventory.native_busy(): raise ValueError('请等待读取或装备操作结束')
            selection, state = self._selected_state(account.strip())
            if selection_id != selection['id']: raise ValueError('快照已刷新，请重新计算')
            profile = self.inventory.accounts.get(account.strip())
            return equipment_plans.save(self.inventory.directory, account.strip(), state, selection,
                                        character_id, core, modules, exclude_others, complete,
                                        profile.get('uid') if profile else None)

    def delete_build_plan(self, account, character_id):
        if not isinstance(account, str) or not account.strip(): raise ValueError('账号无效')
        with self.inventory.lock:
            if self.inventory.native_busy(): raise ValueError('请等待读取或装备操作结束')
            profile = self.inventory.accounts.get(account.strip())
            if not profile or not profile.get('uid'):
                raise ValueError('账号 UID 未确认，无法删除方案')
            return equipment_plans.delete(self.inventory.directory, account.strip(), character_id)

    def preview_saved(self, account, character_id):
        if not isinstance(account, str): raise ValueError('账号无效')
        selection, state = self._selected_state(account.strip())
        record = equipment_plans.read(self.inventory.directory, account.strip()).get(str(character_id))
        if record is None: raise ValueError('请先在计算配装中保存该角色方案')
        resolved = equipment_plans.resolve(record, state, selection)
        return self.preview_assembly(account, selection['id'], resolved['character_id'], resolved['core'], resolved['modules'], 'manual')

    def _selected_state(self, account):
        selection = self.selection
        if (not selection or selection['account'] != account or self.now() - selection['created'] > 600):
            raise ValueError('请从该账号已保存的 DLL 原生快照载入装备')
        current = self.inventory.load(account)
        raw = current.get('domains', {}).get('equipment')
        sessions = current.get('native_sessions', {})
        if (not isinstance(sessions, dict) or sessions.get('equipment') != selection['session']
                or not isinstance(raw, dict)):
            raise ValueError('账号的原生装备快照已更新，请重新载入方案')
        state = equipment_state(raw, selection['context'])
        if fingerprint(state) != selection['fingerprint']:
            raise ValueError('账号的原生装备快照已变化，请重新载入方案')
        return selection, state

    def _ensure_idle(self):
        if self.inventory.native_busy():
            raise ValueError('请等待读取或装备操作结束后再载入配装快照')
        if self.inventory.vision and self.inventory.vision.job.get('running'):
            raise ValueError('请先结束截图扫描，再载入或预览配装')

    def preview(self, account, character_ids, categories):
        self._ensure_idle()
        if not isinstance(account, str) or not account.strip() or len(account) > 80:
            raise ValueError('请填写80字以内的本机账号标签')
        if (not isinstance(character_ids, list) or not 1 <= len(character_ids) <= 64
                or any(type(cid) is not int or cid <= 0 for cid in character_ids)
                or len(set(character_ids)) != len(character_ids)):
            raise ValueError('请选择需要卸装的角色')
        if (not isinstance(categories, list) or not categories or len(categories) > 2
                or any(not isinstance(c, str) or c not in KINDS for c in categories)
                or len(set(categories)) != len(categories)):
            raise ValueError('请选择驱动块或空幕（卡带）')
        self.plan = None
        selection, state = self._selected_state(account.strip())
        if not set(character_ids).issubset(state['characters']):
            raise ValueError('所选角色不属于当前游戏快照，请重新载入')
        names = {r['character_id']: r['name'] for r in self._roster(state, selection['raw'])}
        operations = []
        for key in sorted(state['items']):
            row = state['items'][key]
            cid = row.get('equipped_character_id')
            if row['equipped'] is not True or cid not in character_ids or row.get('kind') not in {KINDS[c] for c in categories}:
                continue
            operations.append({'character': deepcopy(state['characters'][cid]), 'equipment': deepcopy(row['uid']),
                               'action': 'unequip',
                               'method': 'equipment.unequip_module' if row['kind'] == 'module' else 'equipment.unequip_core',
                               'character_id': cid, 'character_name': names[cid],
                               'category': 'drive' if row['kind'] == 'module' else 'tape',
                               'name': row.get('names', {}).get('zh_cn') or str(row.get('item_id', '装备'))})
        if len(operations) > 2048:
            raise ValueError('单次操作过多，请分角色执行')
        public = {'account': account.strip(), 'characters': [names[cid] for cid in character_ids],
                  'total': len(operations), 'items': [{k: v for k, v in op.items() if k not in ('character', 'equipment', 'method')} for op in operations]}
        if operations:
            token = secrets.token_urlsafe(32)
            self.plan = {'token': token, 'operation': 'unequip', 'created': self.now(), 'fingerprint': fingerprint(state),
                         'context': state['context'], 'session': selection['session'], 'operations': operations, **public}
            public.update(token=token, expires_in=120)
        return public

    def preview_assembly(self, account, selection_id, character_id, core, modules, placement_mode):
        self._ensure_idle()
        if not isinstance(account, str) or not account.strip() or len(account) > 80:
            raise ValueError('请填写80字以内的本机账号标签')
        self.plan = None
        selection, state = self._selected_state(account.strip())
        if not isinstance(selection_id, str) or selection_id != selection['id']:
            raise ValueError('装备选择已失效，请重新载入背包快照')
        core_key, keys, positions = resolve_request(state, selection, character_id, core, modules, placement_mode)
        names = {r['character_id']: r['name'] for r in self._roster(state, selection['raw'])}
        operations, final = assembly_plan(state, character_id, core_key, keys, positions, names, selection['labels'])
        batch = None
        if core_key is not None and keys:
            batch = {'method': 'equipment.equip_one_key',
                     'character': deepcopy(state['characters'][character_id]),
                     'core': deepcopy(state['items'][core_key]['uid']),
                     'placements': [{'equipment': deepcopy(state['items'][key]['uid']),
                                     **native_position(state['items'][key], position)}
                                    for key, position in zip(keys, positions)]}
        public = {'operation': 'assembly', 'account': account.strip(), 'characters': [names[character_id]],
            'total': len(operations), 'items': [{k: v for k, v in op.items() if k not in ('character', 'equipment', 'method', 'native_placement')} for op in operations],
            'transfers': sum(state['items'][key]['equipped'] and state['items'][key]['equipped_character_id'] != character_id
                             for key in keys + ([core_key] if core_key is not None else [])),
            'layout': {'cells': CATALOG['characters'].get(str(character_id), {}).get('cells', []),
                       'pieces': [{'label': selection['labels'][key], 'name': state['items'][key].get('names', {}).get('zh_cn'),
                                   'cells': shape(state['items'][key]), **position} for key, position in zip(keys, positions)]},
            'core_label': selection['labels'].get(core_key), 'drive_count': len(keys),
            'execution_mode': 'one_key' if batch else 'individual'}
        if operations:
            token = secrets.token_urlsafe(32)
            self.plan = {**public, 'token': token, 'created': self.now(), 'fingerprint': fingerprint(state),
                         'session': selection['session'], 'final_fingerprint': fingerprint(final),
                         'context': state['context'], 'operations': operations,
                         'batch': batch, 'final_state': final}
            public.update(token=token, expires_in=120)
        return public

    def start(self, token):
        self._reserve()
        try:
            with self.inventory.lock:
                plan = self.plan
                if not isinstance(token, str) or not plan or not secrets.compare_digest(plan['token'], token):
                    raise ValueError('装备操作预览无效，请重新生成')
                self.plan = None
                if self.now() - plan['created'] > 120:
                    raise ValueError('装备操作预览已过期，请重新生成')
                self.stop.clear()
                self.job = {'running': True, 'state': 'running', 'message': '正在核对游戏与装备操作预览…',
                            'operation': plan.get('operation', 'unequip'),
                            'account': plan['account'], 'completed': 0,
                            'total': 1 if plan.get('batch') else len(plan['operations']),
                            'batch_active': False, 'results': []}
                self.thread = threading.Thread(target=self._run, args=(plan,), daemon=True, name='native-unequip')
                self.thread.start()
            return self.status()
        except Exception:
            self._release()
            raise

    def cancel(self):
        with self.inventory.lock:
            if self.job['running']:
                if self.job.get('batch_active'):
                    self.job['message'] = '一键装配已提交，当前批次无法中断；正在等待结果核验'
                else:
                    self.stop.set()
                    self.job['message'] = '正在停止；已发出的操作会先完成结果核对'
        return self.status()

    def _set(self, **fields):
        with self.inventory.lock:
            self.job.update(fields)

    def _save(self, account, observation, expected_context):
        with self.inventory.lock:
            self.selection = None
            stored = self.inventory.load(account)
            stored.setdefault('domains', {})['equipment'] = observation.raw_snapshot
            stored['inventory']['equipment'] = observation.data
            profile = self.inventory.accounts.get(account)
            if not profile or not profile.get('uid'):
                raise ValueError('当前资料尚未绑定游戏 UID，未保存装备快照')
            stored['account_uid'] = profile['uid']
            header = observation.raw_snapshot.get('header', {})
            stored['native_sessions'] = {**stored.get('native_sessions', {}), 'equipment': {
                'pid': expected_context[0], 'provider_id': header.get('providerId'),
                'domain_key': header.get('domainKey'), 'snapshot_id': header.get('snapshotId'),
                'revision': header.get('revision'), 'saved_at': observation.raw_snapshot.get('saved_at')}}
            path = self.inventory._path(account)
            if path.exists():
                self.inventory._write(path.with_suffix('.previous.json'), json.loads(path.read_text(encoding='utf-8')))
            self.inventory._write(path, stored)
            self.inventory.config['account'] = account
            self.inventory.config['native_account'] = account
            self.inventory._write(self.inventory.directory / 'config.json', self.inventory.config)

    def _batch_status(self, adapter, header):
        current = adapter.core.call('native.snapshot.status', {}, timeout=2)
        domains = [row for row in current.get('domains', [])
                   if isinstance(row, dict) and row.get('domain') == header.get('domain')]
        if current.get('providerId') != header.get('providerId') or len(domains) != 1:
            raise ValueError('游戏背包来源已变化，停止批量装配')
        row = domains[0]
        if row.get('ready') is not True or row.get('dirty') is not False:
            return None
        return row

    def _run_batch(self, adapter, plan, state, observation, audit, record):
        batch = plan['batch']
        header = observation.raw_snapshot['header']
        if self.stop.is_set():
            self._set(state='stopped', message='已停止，批量装备命令尚未派发')
            return
        if self._identity(adapter) != state['control_context']:
            raise ValueError('游戏来源已变化，停止批量装配')
        require_current_revision(adapter.core, header, lambda: None)

        self._set(message='正在一次提交空幕与全部驱动；完成后整体核验',
                  batch_active=True, in_flight=0)
        audit['execution_mode'] = 'equipment.equip_one_key'
        audit['batch_request'] = deepcopy(batch)
        record()
        dispatch_error = None
        try:
            audit['batch_response'] = adapter.core.call(
                batch['method'],
                {'character': batch['character'], 'placements': batch['placements'], 'core': batch['core']},
                timeout=30)
        except Exception as error:
            # A transport timeout can happen after the game accepted the command.
            # Observe the result, but never replay an ambiguous equipment write.
            dispatch_error = error
            audit['batch_error'] = str(error)

        deadline = self.now() + 15
        next_full_read = self.now() + .5
        expected = plan['final_state']
        observed_header = header
        while self.now() < deadline:
            self.sleep(.15)
            status = self._batch_status(adapter, observed_header)
            changed = (status is not None and status.get('revision') != observed_header.get('revision'))
            if not changed and self.now() < next_full_read:
                continue
            try:
                after, current_observation = self._capture(adapter)
            except CoreRpcError as error:
                if error.code == -32001 and str(error) in ('not_ready', 'source_changed', 'control_timeout'):
                    next_full_read = self.now() + .5
                    continue
                raise
            audit['last_observation'] = current_observation.raw_snapshot
            observed_header = current_observation.raw_snapshot['header']
            if _matches_batch_final(state, after, plan['final_fingerprint']):
                self.inventory.verify_live_account(plan['account'], adapter.pid)
                self._save(plan['account'], current_observation, after['context'])
                result = {'character_id': plan['characters'][0], 'action': 'equip_one_key', 'verified': True}
                message = '批量装配完成；最新背包快照整体核验通过，背包数据已更新'
                if dispatch_error:
                    message += '（组件响应异常，但游戏状态已核实）'
                self._set(state='verified', message=message, batch_active=False,
                          in_flight=None, completed=1, total=1, results=[result])
                return
            if not _expected_batch_transition(state, after, expected):
                raise ValueError('批量装配期间检测到预览以外的装备变化，已停止；请重新读取游戏状态')
            next_full_read = self.now() + 1

        detail = ('组件响应：' + str(dispatch_error) + '。') if dispatch_error else ''
        self._set(state='unconfirmed', message=detail +
                  '批量装配结果在等待时间内未能整体核实；未自动重发，请重新读取并检查装备。',
                  batch_active=False, in_flight=0)

    def _run(self, plan):
        adapter = None
        results = []
        report_path = self.inventory.directory / 'equipment-operations' / (secrets.token_hex(12) + '.json')
        audit = {'schema_version': 1, 'account': plan['account'], 'operations': deepcopy(plan['operations'])}

        def record():
            self.inventory._write(report_path, {**audit, 'job': self.status(),
                'saved_at': datetime.now(timezone.utc).isoformat()})

        try:
            adapter = self._open()
            self.inventory.verify_live_account(plan['account'], adapter.pid)
            state, observation = self._capture(adapter)
            if state['context'] != plan['context'] or fingerprint(state) != plan['fingerprint']:
                raise ValueError('游戏账号、装备或角色状态与预览不同，本次未派发，请重新预览')
            session = plan.get('session')
            if session and session.get('pid') != state['context'][0]:
                raise ValueError('预览后的游戏进程已变化，请重新读取后再操作')
            # Refresh/disable/reopen may change snapshot revisions without changing
            # any equipment. The full state above must match; dispatch guards below
            # use the newly captured revision, not the old saved snapshot revision.
            audit['before'] = observation.raw_snapshot
            observed_header = observation.raw_snapshot['header']
            self._set(report=str(report_path), in_flight=None)
            record()
            if plan.get('batch') and plan.get('operation') == 'assembly':
                self._run_batch(adapter, plan, state, observation, audit, record)
                return
            for operation_index, operation in enumerate(plan['operations']):
                if self.stop.is_set():
                    self._set(state='stopped', message='已停止后续装备操作；已发出的操作均已核对')
                    break
                current_identity = self._identity(adapter)
                if current_identity != state['control_context']:
                    raise ValueError('游戏来源已变化，停止后续装备操作')
                if isinstance(observed_header.get('revision'), str):
                    require_current_revision(adapter.core, observed_header, lambda: None)
                else:
                    fresh, fresh_observation = self._capture(adapter)
                    if fingerprint(fresh) != fingerprint(state) or fresh['control_context'] != state['control_context']:
                        raise ValueError('装备状态在执行前发生变化，停止后续装备操作')
                    state, observed_header = fresh, fresh_observation.raw_snapshot['header']
                key = uid(operation['equipment'])
                action = operation.get('action', 'unequip')
                self._set(message=('正在装入：' if action == 'equip' else '正在卸下：') + operation['character_name'] + ' · ' + operation['name'], in_flight=len(results))
                # Persist the original loadout and the pending command before touching game state.
                record()
                dispatch_error = None
                try:
                    # Fixed allowlist generated from a validated live snapshot; never accept web-supplied RPCs or UIDs.
                    params = {'character': operation['character'], 'equipment': operation['equipment']}
                    if action == 'equip' and operation['category'] == 'drive': params.update(operation['native_placement'])
                    audit['last_rpc_response'] = adapter.core.call(operation['method'], params)
                except Exception as error:
                    dispatch_error = error
                verified = False
                for attempt in range(4):
                    self.sleep(.3 if attempt == 0 else .5)
                    try:
                        after, observation = self._capture(adapter)
                    except CoreRpcError as error:
                        if error.code == -32001 and str(error) in ('not_ready', 'source_changed', 'control_timeout') and attempt < 3:
                            continue  # Retry observations only, never equipment commands.
                        raise
                    audit['last_observation'] = observation.raw_snapshot
                    if verify_operation(state, after, operation):
                        state = after
                        observed_header = observation.raw_snapshot['header']
                        verified = True
                        break
                    if fingerprint(after) != fingerprint(state):
                        raise ValueError('目标装备出现未预期变化，停止后续装备操作')
                result = {k: operation[k] for k in ('character_id', 'character_name', 'category', 'name', 'action')}
                result['verified'] = verified
                results.append(result)
                self._set(results=deepcopy(results), completed=sum(r['verified'] for r in results),
                          in_flight=None if verified else len(results)-1)
                if not verified:
                    detail = ('组件返回：' + str(dispatch_error) + '。') if dispatch_error else ''
                    self._set(state='unconfirmed', message=detail + '装备操作结果尚未确认；已停止，请核对游戏并重新读取。不会自动重发。')
                    return
                self._save(plan['account'], observation, state['context'])
                if dispatch_error:
                    self._set(state='stopped', message='本件装备操作已由新快照确认，但组件响应异常；已停止后续操作，请重新预览。')
                    return
            else:
                if plan.get('final_fingerprint') and fingerprint(state) != plan['final_fingerprint']:
                    raise ValueError('最终配装与预览不一致，请重新读取并核对')
                self._set(state='verified', message=('装配完成' if plan.get('operation') == 'assembly' else '卸装完成') + '；全部操作已由新库存快照确认，背包数据已更新')
        except Exception as error:
            self._set(state='error', message=str(error) + '。本次不会自动重发装备操作。')
        finally:
            if adapter:
                try: adapter.close()
                except Exception: pass
            # Keep the operation visible as active until the shared native lock
            # is released. The role-build UI uses the idle status to reload the
            # verified snapshot; publishing completion first creates a race in
            # which that reload is rejected and never retried.
            self._release()
            self._set(running=False, batch_active=False)
            try:
                record()
            except Exception as error:
                self._set(state='error', message=self.job['message'] + '；保存操作记录失败：' + str(error))
