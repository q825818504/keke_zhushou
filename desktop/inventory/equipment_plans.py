"""Account-local persistent build intent; never store transient UI handles or issue RPCs."""
from datetime import datetime, timezone
import hashlib
import json
import os
import secrets
from .equipment_assembly import resolve_request, STATE_FIELDS


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def reference(row):
    return digest([row['kind'], row['uid']])


def signature(row):
    return digest({key: value for key, value in row.items() if key not in STATE_FIELDS})


def path_for(directory, account):
    root = (directory / 'build-plans').resolve()
    path = root / (digest(account) + '.json')
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError('方案保存路径无效')
    return path


def read(directory, account):
    path = path_for(directory, account)
    if not path.exists(): return {}
    if path.stat().st_size > 2*1024*1024: raise ValueError('方案文件过大')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if value.get('schema') != 1 or not isinstance(value.get('plans'), dict): raise ValueError()
        return value['plans']
    except (ValueError, AttributeError):
        raise ValueError('保存的配装方案文件损坏，请检查本机数据')


def resolve(record, state, selection):
    cid = record['character_id']
    if cid not in state['characters'] or digest(state['characters'][cid]) != record['character_ref']:
        raise ValueError('方案角色实例已变化，请重新计算并保存')
    by_ref = {reference(row): key for key, row in state['items'].items()}
    handles = {key: ident for ident, key in selection['keys'].items()}
    def item_ref(entry):
        key = by_ref.get(entry['ref'])
        if key not in state['items'] or signature(state['items'][key]) != entry['signature']:
            raise ValueError('方案中的装备已消失或属性已变化，请重新计算')
        row = state['items'][key]
        if record['exclude_others'] and row['equipped'] and row['equipped_character_id'] != cid:
            raise ValueError('方案装备已被其他角色占用，请重新计算或调整限制后保存')
        return handles[key]
    core = item_ref(record['core']) if record['core'] else 'none'
    modules = [{'id': item_ref(entry), 'row': entry['row'], 'column': entry['column']} for entry in record['modules']]
    resolve_request(state, selection, cid, core, modules, 'manual')
    return {'character_id': cid, 'core': core, 'modules': modules, 'exclude_others': record['exclude_others'],
            'saved_at': record['saved_at'], 'complete': record.get('complete', False), 'valid': True}


def list_plans(directory, account, state, selection):
    result = {}
    for cid, record in read(directory, account).items():
        try:
            result[cid] = resolve(record, state, selection)
        except (ValueError, KeyError, TypeError) as error:
            result[cid] = {'valid': False, 'reason': str(error), 'saved_at': record.get('saved_at', '') if isinstance(record, dict) else ''}
    return result


def save(directory, account, state, selection, character_id, core, modules, exclude_others, complete, account_uid=None):
    if type(exclude_others) is not bool or type(complete) is not bool:
        raise ValueError('方案限制或搜索状态无效')
    core_key, keys, positions = resolve_request(state, selection, character_id, core, modules, 'manual')
    chosen = keys + ([core_key] if core_key is not None else [])
    if exclude_others and any(state['items'][key]['equipped'] and state['items'][key]['equipped_character_id'] != character_id for key in chosen):
        raise ValueError('已开启不占用其他角色装备，所选装备不满足限制')
    def item_ref(key):
        return {'ref': reference(state['items'][key]), 'signature': signature(state['items'][key])}
    record = {'character_id': character_id, 'character_ref': digest(state['characters'][character_id]),
              'core': item_ref(core_key) if core_key is not None else None,
              'modules': [{**item_ref(key), **position} for key, position in zip(keys, positions)],
              'exclude_others': exclude_others, 'complete': complete, 'saved_at': datetime.now(timezone.utc).isoformat()}
    plans = read(directory, account)
    plans[str(character_id)] = record
    path = path_for(directory, account)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.'+secrets.token_hex(8)+'.tmp')
    try:
        temporary.write_text(json.dumps({'schema': 1, 'account': account, 'account_uid': account_uid,
                                         'plans': plans}, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return resolve(record, state, selection)


def delete(directory, account, character_id):
    """Delete one character's saved plan from the account-scoped plan file."""
    if not isinstance(account, str) or not account.strip():
        raise ValueError('账号无效')
    if type(character_id) is not int or character_id <= 0:
        raise ValueError('角色无效')
    account = account.strip()
    path = path_for(directory, account)
    if not path.is_file():
        raise ValueError('该账号没有已保存方案')
    plans = read(directory, account)
    key = str(character_id)
    if key not in plans:
        raise ValueError('该角色没有已保存方案')
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('account') not in (None, account):
        raise ValueError('保存方案所属账号不匹配')
    del plans[key]
    if not plans:
        path.unlink(missing_ok=True)
        return {'deleted': True, 'character_id': character_id, 'remaining': 0}
    payload['plans'] = plans
    temporary = path.with_suffix('.' + secrets.token_hex(8) + '.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {'deleted': True, 'character_id': character_id, 'remaining': len(plans)}
