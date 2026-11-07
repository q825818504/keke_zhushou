"""Verified native lock/discard state changes for selected inventory items."""

from copy import deepcopy
from datetime import datetime, timezone
import secrets
import threading
import time

from .core import CoreRpcError
from .equipment import equipment_state, fingerprint
from .snapshot import require_current_revision


MAX_SELECTED_ITEMS = 2000
PLAN_TTL_SECONDS = 120
OBSERVE_ATTEMPTS = 4
STATE_BATCH_CAPABILITY = 'native_equipment_state_batch_v1'
MAX_STATE_OPERATIONS = 16


class EquipmentStateActions:
    """Freeze explicit state changes, use supported batches, then verify."""

    FIELDS = {
        'locked': ('locked', 'equipment.set_item_locked'),
        'discarded': ('discarded', 'equipment.set_item_discarded'),
    }

    def __init__(self, inventory, now=time.monotonic, sleep=time.sleep):
        self.inventory = inventory
        self.now = now
        self.sleep = sleep
        self.plan = None
        self.stop = threading.Event()
        self.thread = None
        self.job = {
            'running': False,
            'state': 'idle',
            'message': '尚未执行锁定或弃置操作',
            'completed': 0,
            'total': 0,
            'results': [],
        }

    @staticmethod
    def _instance_id(key):
        return f'nte-equipment:{key[0]}:{key[1]}'

    def status(self):
        with self.inventory.lock:
            return deepcopy(self.job)

    def preview(self, account, source, instance_ids, field):
        if not isinstance(account, str) or not account.strip() or len(account) > 80:
            raise ValueError('账号标签无效')
        account = account.strip()
        if source != 'native':
            raise ValueError('原生锁定/弃置只支持 DLL 原生库存；OCR 状态操作尚未接入')
        if field not in self.FIELDS:
            raise ValueError('仅支持锁定或弃置状态')
        if (not isinstance(instance_ids, list) or not 1 <= len(instance_ids) <= MAX_SELECTED_ITEMS
                or any(not isinstance(value, str) or not value for value in instance_ids)
                or len(set(instance_ids)) != len(instance_ids)):
            raise ValueError(f'请选择1–{MAX_SELECTED_ITEMS}件不重复装备')

        with self.inventory.lock:
            if self.inventory.native_busy():
                raise ValueError('请等待当前原生读取或装备操作结束')
            if self.inventory.vision and self.inventory.vision.job.get('running'):
                raise ValueError('请先结束截图扫描，再操作装备状态')

            view = self.inventory.view(account, source)
            if view.get('selected_source') != 'native':
                raise ValueError('当前选中的数据不是 DLL 原生装备库存')
            profile = self.inventory.accounts.get(account)
            stored = self.inventory.load(account)
            if not profile or not profile.get('uid') or stored.get('account_uid') != profile['uid']:
                raise ValueError('账号 UID 与装备快照不一致，请重新读取游戏数据')

            raw = stored.get('domains', {}).get('equipment')
            data = stored.get('inventory', {}).get('equipment', {})
            session = stored.get('native_sessions', {}).get('equipment', {})
            header = raw.get('header', {}) if isinstance(raw, dict) else {}
            if (not isinstance(raw, dict)
                    or not isinstance(data, dict)
                    or data.get('source', {}).get('adapter') != 'nte-native-v1'):
                raise ValueError('缺少 DLL 原生装备快照，请重新读取')
            if data.get('coverage', {}).get('collection_complete') is not True:
                raise ValueError('装备列表不是完整原生快照；请完成 DLL 全量读取后再操作')
            if (not isinstance(session, dict)
                    or type(session.get('pid')) is not int or session['pid'] <= 0
                    or session.get('provider_id') != header.get('providerId')
                    or session.get('domain_key') != header.get('domainKey')
                    or session.get('snapshot_id') != header.get('snapshotId')
                    or session.get('revision') != header.get('revision')):
                raise ValueError('原生装备快照缺少有效游戏会话信息，请重新读取')

            context = (session['pid'], session['provider_id'], session['domain_key'])
            state = equipment_state(raw, context)
            key_by_id = {self._instance_id(key): key for key in state['items']}
            if not set(instance_ids).issubset(key_by_id):
                raise ValueError('选择中包含已过期装备，请刷新背包列表')

            state_field, method = self.FIELDS[field]
            selected_rows = []
            for instance_id in instance_ids:
                key = key_by_id[instance_id]
                row = state['items'][key]
                current = row.get(state_field)
                if type(current) is not bool:
                    raise ValueError('所选装备的锁定/弃置状态未知；请重新读取原生库存')
                selected_rows.append((instance_id, key, row, current))
            target = not all(current for _, _, _, current in selected_rows)
            operations = []
            for instance_id, key, row, current in selected_rows:
                changes = []
                clears = None
                if target:
                    other_field = 'discarded' if state_field == 'locked' else 'locked'
                    other = row.get(other_field)
                    if type(other) is not bool:
                        raise ValueError('所选装备的锁定/弃置状态未知；请重新读取原生库存')
                    if other:
                        other_method = self.FIELDS[other_field][1]
                        changes.append({'field': other_field, 'method': other_method,
                                        'before': True, 'after': False})
                        clears = other_field
                if current is not target:
                    changes.append({'field': state_field, 'method': method,
                                    'before': current, 'after': target})
                operations.append({
                    'instance_id': instance_id,
                    'key': key,
                    'equipment': deepcopy(row['uid']),
                    'name': row.get('names', {}).get('zh_cn') or str(row.get('item_id', '装备')),
                    'category': 'drive' if row.get('kind') == 'module' else 'tape',
                    'field': state_field,
                    'before': current,
                    'after': target,
                    'clears': clears,
                    'changes': changes,
                })
            token = secrets.token_urlsafe(32)
            self.plan = {
                'token': token,
                'created': self.now(),
                'account': account,
                'account_uid': profile['uid'],
                'context': context,
                'session': deepcopy(session),
                'fingerprint': fingerprint(state),
                'state': state,
                'field': state_field,
                'target': target,
                'operations': operations,
            }
            return {
                'token': token,
                'account': account,
                'account_uid': profile['uid'],
                'field': state_field,
                'target': target,
                'total': len(operations),
                'mutation_total': sum(len(op['changes']) for op in operations),
                'expires_in': PLAN_TTL_SECONDS,
                'items': [{key: op[key] for key in ('instance_id', 'name', 'category', 'before', 'after', 'clears')}
                          for op in operations],
            }

    def start(self, token):
        with self.inventory.lock:
            if self.inventory.native_busy():
                raise ValueError('已有原生读取或装备操作，请等待完成')
            if self.inventory.vision and self.inventory.vision.job.get('running'):
                raise ValueError('请先结束截图扫描，再操作装备状态')
            plan = self.plan
            if not isinstance(token, str) or not plan or not secrets.compare_digest(plan['token'], token):
                raise ValueError('状态操作预览无效，请重新生成')
            self.plan = None
            if self.now() - plan['created'] > PLAN_TTL_SECONDS:
                raise ValueError('状态操作预览已过期，请重新生成')
            self.stop.clear()
            self.inventory.native_operation = 'equipment-state'
            action = '锁定' if plan['field'] == 'locked' and plan['target'] else (
                '解锁' if plan['field'] == 'locked' else
                '弃置' if plan['target'] else '取消弃置')
            self.job = {
                'running': True,
                'state': 'running',
                'message': f'正在核对原生装备快照，准备{action}…',
                'operation': plan['field'],
                'account': plan['account'],
                'completed': 0,
                'total': len(plan['operations']),
                'results': [],
            }
            self.thread = threading.Thread(target=self._run, args=(plan,), daemon=True,
                                           name='native-equipment-state')
            self.thread.start()
        return self.status()

    def cancel(self):
        with self.inventory.lock:
            if self.job['running']:
                self.stop.set()
                self.job['message'] = '正在停止后续操作；已派发的当前操作仍会先复核'
            return deepcopy(self.job)

    def _set(self, **fields):
        with self.inventory.lock:
            self.job.update(fields)

    def _run(self, plan):
        equipment = self.inventory.equipment
        adapter = None
        report_path = self.inventory.directory / 'equipment-state-operations' / (secrets.token_hex(12) + '.json')
        audit = {
            'schema_version': 1,
            'account': plan['account'],
            'account_uid': plan['account_uid'],
            'field': plan['field'],
            'operations': [{key: op[key] for key in ('instance_id', 'name', 'category', 'before', 'after', 'clears', 'changes')}
                           for op in plan['operations']],
        }

        def record():
            self.inventory._write(report_path, {**audit, 'job': self.status(),
                'saved_at': datetime.now(timezone.utc).isoformat()})

        try:
            adapter = equipment._open()
            self.inventory.verify_live_account(plan['account'], adapter.pid)
            state, observation = equipment._capture(adapter)
            if (state['context'] != plan['context']
                    or fingerprint(state) != plan['fingerprint']):
                raise ValueError('游戏账号或装备状态与预览不同，未派发操作；请重新读取并预览')
            if (self.inventory.accounts.get(plan['account']) or {}).get('uid') != plan['account_uid']:
                raise ValueError('账号 UID 已变化，未派发操作')
            audit['before'] = observation.raw_snapshot
            expected_control_context = state['control_context']
            record()

            capabilities = adapter.core.hello.get('capabilities', [])
            batch_supported = (isinstance(capabilities, list)
                               and STATE_BATCH_CAPABILITY in capabilities)
            actionable = [operation for operation in plan['operations'] if operation['changes']]
            no_change = [operation for operation in plan['operations'] if not operation['changes']]
            if no_change:
                results = [{key: operation[key] for key in
                    ('instance_id', 'name', 'category', 'before', 'after', 'clears')}
                    | {'verified': True, 'changed': False} for operation in no_change]
                with self.inventory.lock:
                    current_results = list(self.job.get('results', [])) + results
                    self.job.update(completed=len(current_results), results=current_results,
                                    message=f"已核对 {len(current_results)} / {len(plan['operations'])} 件")
                audit.setdefault('verified', []).extend(results)
                record()

            batches = []
            pending, pending_count = [], 0
            for operation in actionable:
                operation_count = len(operation['changes'])
                if batch_supported and pending and pending_count + operation_count > MAX_STATE_OPERATIONS:
                    batches.append(pending)
                    pending, pending_count = [], 0
                if not batch_supported and pending:
                    batches.append(pending)
                    pending = []
                pending.append(operation)
                pending_count += operation_count
            if pending:
                batches.append(pending)

            for batch in batches:
                if self.stop.is_set():
                    self._set(state='stopped', message='已停止后续操作；已完成操作均已复核')
                    break
                self.inventory.verify_live_account(plan['account'], adapter.pid)
                if equipment._identity(adapter) != expected_control_context:
                    raise ValueError('游戏来源已变化，停止后续操作')
                header = observation.raw_snapshot['header']
                if isinstance(header.get('revision'), str):
                    require_current_revision(adapter.core, header, lambda: None)
                else:
                    fresh, fresh_observation = equipment._capture(adapter)
                    if (fresh['control_context'] != expected_control_context
                            or fingerprint(fresh) != fingerprint(state)):
                        raise ValueError('装备状态在执行前发生变化，停止后续操作')
                    state, observation = fresh, fresh_observation

                changes = [change for operation in batch for change in operation['changes']]
                for operation in batch:
                    current = state['items'].get(operation['key'])
                    if not current:
                        raise ValueError('所选装备已不存在，停止后续操作')
                    if any(current.get(change['field']) is not change['before']
                           for change in operation['changes']):
                        raise ValueError('所选装备状态已变化，停止后续操作')
                first = batch[0]
                action = ('锁定' if plan['field'] == 'locked' and plan['target'] else
                          '解锁' if plan['field'] == 'locked' else
                          '弃置' if plan['target'] else '取消弃置')
                batch_item_ids = [operation['instance_id'] for operation in batch]
                self._set(message=f'正在{action} {len(batch)} 件装备（本批包含 {len(changes)} 项状态变更）',
                          in_flight=batch_item_ids)
                audit['in_flight'] = batch_item_ids
                audit['last_request'] = {
                    'method': 'equipment.set_item_states' if batch_supported else first['changes'][0]['method'],
                    'operations': [{
                        'instance_id': operation['instance_id'],
                        'changes': [{key: change[key] for key in ('field', 'before', 'after')}
                                    for change in operation['changes']],
                        'equipment': operation['equipment'],
                    } for operation in batch],
                }
                record()
                dispatch_error = None
                try:
                    if batch_supported:
                        params = {'operations': [
                            {'equipment': operation['equipment'], 'field': change['field'],
                             'value': change['after']}
                            for operation in batch for change in operation['changes']]}
                        audit['last_rpc_response'] = adapter.core.call('equipment.set_item_states', params)
                    else:
                        responses = []
                        for change in first['changes']:
                            self.inventory.verify_live_account(plan['account'], adapter.pid)
                            if equipment._identity(adapter) != expected_control_context:
                                raise ValueError('游戏来源已变化，停止后续操作')
                            params = {'equipment': first['equipment'], change['field']: change['after']}
                            responses.append(adapter.core.call(change['method'], params))
                        audit['last_rpc_response'] = responses
                except Exception as error:
                    dispatch_error = error
                    audit['last_rpc_error'] = str(error)

                verified = False
                after = None
                after_observation = None
                for attempt in range(OBSERVE_ATTEMPTS):
                    self.sleep(.3 if attempt == 0 else .5)
                    try:
                        candidate, candidate_observation = equipment._capture(adapter)
                    except CoreRpcError as error:
                        if error.code == -32001 and str(error) in (
                                'not_ready', 'source_changed', 'control_timeout') and attempt < OBSERVE_ATTEMPTS - 1:
                            continue
                        if attempt < OBSERVE_ATTEMPTS - 1:
                            continue
                        raise
                    audit['last_observation'] = candidate_observation.raw_snapshot
                    after, after_observation = candidate, candidate_observation
                    transition = self._transition_progress(state, candidate, batch)
                    if transition == 'complete':
                        verified = True
                        break

                if not verified:
                    audit['unconfirmed_instances'] = batch_item_ids
                    if dispatch_error:
                        audit['unconfirmed_error'] = str(dispatch_error)
                    if transition in ('partial', 'none'):
                        audit['partially_observed_changes'] = self._observed_changes(after, batch, observed=True)
                        audit['not_observed_changes'] = self._observed_changes(after, batch, observed=False)
                        audit['pending_local_save'] = True
                        audit.pop('in_flight', None)
                        record()
                        try:
                            equipment._save(plan['account'], after_observation, expected_control_context)
                        except Exception as error:
                            audit['local_save_error'] = str(error)
                            self._set(state='partial', message=(
                                '批次结果未完全复核，且无法保存本次观测；已停止后续操作，请重新读取游戏数据'))
                            record()
                            break
                        audit['pending_local_save'] = False
                        state, observation = after, after_observation
                        if transition == 'partial':
                            self._set(state='partial', message=(
                                '本批次只观察到部分状态变更，已保存复读结果并停止后续操作；'
                                '请重新读取检查，程序不会自动重发'))
                        else:
                            self._set(state='unconfirmed', message=(
                                '已读取但未观察到目标状态变更；已停止且不会自动重发，请重新读取检查'))
                    else:
                        self._set(state='unconfirmed', message=(
                            '本批次结果包含预期之外的变化，已停止且不会自动重发；请重新读取检查'))
                    record()
                    break

                results_for_batch = []
                for operation in batch:
                    result = {key: operation[key] for key in
                              ('instance_id', 'name', 'category', 'before', 'after', 'clears')}
                    result['verified'] = True
                    result['changed'] = True
                    results_for_batch.append(result)
                with self.inventory.lock:
                    results = list(self.job.get('results', [])) + results_for_batch
                    self.job.update(completed=len(results), results=results,
                                    message=f"已复核 {len(results)} / {len(plan['operations'])} 件")
                audit.setdefault('verified', []).extend(results_for_batch)
                audit['last_request_verified'] = True
                audit['pending_local_save'] = True
                audit['last_observation'] = after_observation.raw_snapshot
                audit.pop('in_flight', None)
                record()
                try:
                    equipment._save(plan['account'], after_observation, expected_control_context)
                except Exception as error:
                    audit['local_save_error'] = str(error)
                    self._set(state='partial', message=(
                        f"游戏内状态已复核 {self.job['completed']} 件，但本地背包快照保存失败；"
                        '已停止后续操作，请重新读取游戏数据核对'))
                    record()
                    break
                audit['pending_local_save'] = False
                state, observation = after, after_observation
                record()
            else:
                self._set(state='complete', message=f"已完成并复核 {len(plan['operations'])} 件装备状态")
            if self.job.get('state') == 'running':
                self._set(state='complete', message=f"已完成并复核 {self.job['completed']} 件装备状态")
            record()
        except Exception as error:
            diagnostics_message = str(error)
            completed = int(self.job.get('completed', 0))
            in_flight = audit.get('in_flight') is not None
            pending_save = audit.get('pending_local_save') is True
            if in_flight:
                audit['unconfirmed_instances'] = audit['in_flight']
                self._set(state='partial' if completed else 'unconfirmed', message=(
                    f'已复核 {completed} 件；' if completed else ''
                ) + '最新一批操作已派发但结果无法确认，已停止且不会自动重发；请重新读取游戏库存核对')
            elif pending_save:
                self._set(state='partial', message=(
                    f'游戏内状态已复核 {completed} 件，但本地背包快照未能保存；'
                    '已停止后续操作，请重新读取游戏数据核对'))
            else:
                self._set(state='partial' if completed else 'error',
                          message=(f'已复核 {completed} 件；后续操作停止：' if completed else '状态操作未完成：') + diagnostics_message)
            try:
                audit['failure'] = diagnostics_message
                record()
            except Exception:
                pass
        finally:
            if adapter:
                try:
                    adapter.close()
                except Exception:
                    pass
            with self.inventory.lock:
                self.job['running'] = False
                self.inventory.native_operation = None

    @staticmethod
    def _transition_progress(before, after, groups):
        if (before.get('context') != after.get('context')
                or before.get('control_context') != after.get('control_context')
                or before.get('characters') != after.get('characters')
                or before.get('items', {}).keys() != after.get('items', {}).keys()):
            return 'unexpected'
        by_key = {}
        for group in groups:
            by_key.setdefault(group['key'], []).extend(group['changes'])
        expected_count = sum(len(group['changes']) for group in groups)
        observed_count = 0
        for item_key, original in before['items'].items():
            current = after['items'][item_key]
            changes = by_key.get(item_key, [])
            if not changes:
                if original != current:
                    return 'unexpected'
                continue
            fields = {change['field'] for change in changes}
            if ({name: value for name, value in original.items() if name not in fields}
                    != {name: value for name, value in current.items() if name not in fields}):
                return 'unexpected'
            for change in changes:
                field = change['field']
                if original.get(field) is not change['before']:
                    return 'unexpected'
                if current.get(field) is change['after']:
                    observed_count += 1
                elif current.get(field) is not change['before']:
                    return 'unexpected'
        if observed_count == expected_count:
            return 'complete'
        return 'partial' if observed_count else 'none'

    @staticmethod
    def _observed_changes(state, groups, observed):
        result = []
        for group in groups:
            row = state['items'].get(group['key'])
            for change in group['changes']:
                applied = row is not None and row.get(change['field']) is change['after']
                if applied is observed:
                    result.append({'instance_id': group['instance_id'], 'field': change['field'],
                                   'before': change['before'], 'after': change['after']})
        return result
