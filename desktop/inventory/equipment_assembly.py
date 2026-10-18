"""Build explicit reversible native equip/unequip steps from a live inventory."""
from copy import deepcopy
from .equipment_layout import arrange, native_position
from .snapshot import uid

STATE_FIELDS = {'equipped', 'equipped_character_id', 'equipped_character_uid', 'equipped_placement'}


def verify_operation(before, after, operation):
    if (before['context'] != after['context'] or before.get('control_context') != after.get('control_context')
            or before['characters'] != after['characters']):
        raise ValueError('游戏会话或角色实例已变化，停止装备操作')
    if before['items'].keys() != after['items'].keys():
        raise ValueError('装备集合已变化，停止装备操作')
    key = uid(operation['equipment'])
    for identity, original in before['items'].items():
        observed = after['items'][identity]
        if identity != key and observed != original:
            raise ValueError('其他装备发生变化，停止装备操作，请重新读取')
        if identity == key and ({k: v for k, v in original.items() if k not in STATE_FIELDS}
                                != {k: v for k, v in observed.items() if k not in STATE_FIELDS}):
            raise ValueError('目标装备资料发生变化，停止装备操作')
    return all(after['items'][key].get(field) == value for field, value in expected_fields(operation).items())


def expected_fields(operation):
    equip = operation['action'] == 'equip'
    return {'equipped': equip,
            'equipped_character_id': operation['character_id'] if equip else None,
            'equipped_character_uid': operation['character'] if equip else None,
            'equipped_placement': operation.get('native_placement') if equip else None}


def assembly_plan(state, character_id, core_key, module_keys, positions, names, labels):
    """Full target loadout; explicit source unloads prevent implicit collateral changes."""
    visual = {key: position for key, position in zip(module_keys, positions)}
    desired = {key: native_position(state['items'][key], position) for key, position in zip(module_keys, positions)}
    if core_key is not None: desired[core_key] = None
    operations = []
    simulated = deepcopy(state)

    def command(key, action, target, placement=None):
        item = state['items'][key]
        op = {'action': action, 'method': 'equipment.' + action + ('_module' if item['kind'] == 'module' else '_core'),
              'character': deepcopy(state['characters'][target]), 'equipment': deepcopy(item['uid']),
              'character_id': target, 'character_name': names[target],
              'category': 'drive' if item['kind'] == 'module' else 'tape',
              'name': item.get('names', {}).get('zh_cn') or str(item.get('item_id', '装备')),
              'label': labels[key], 'placement': placement,
              'native_placement': native_position(item, placement) if action == 'equip' and item['kind'] == 'module' else None}
        operations.append(op)
        simulated['items'][key].update(expected_fields(op))

    for key in sorted(state['items']):
        item = state['items'][key]
        if not item['equipped'] or item.get('kind') not in ('module', 'core'): continue
        owner = item['equipped_character_id']
        unchanged = (key in desired and owner == character_id and item.get('equipped_placement') == desired[key])
        if not unchanged and (owner == character_id or key in desired): command(key, 'unequip', owner)
    # Core first, then modules; each independent command is re-observed before the next.
    for key in ([core_key] if core_key is not None else []) + module_keys:
        item = simulated['items'][key]
        if item['equipped'] and item['equipped_character_id'] == character_id and item.get('equipped_placement') == desired[key]:
            continue
        command(key, 'equip', character_id, visual.get(key))
    return operations, simulated


def resolve_request(state, selection, character_id, core, modules, placement_mode):
    if type(character_id) is not int or character_id not in state['characters']:
        raise ValueError('请选择当前游戏中持有的目标角色')
    if not isinstance(core, str): raise ValueError('请选择空幕或保留当前空幕')
    if core == 'keep':
        current = [key for key, item in state['items'].items() if item['kind'] == 'core'
                   and item['equipped'] and item['equipped_character_id'] == character_id]
        if len(current) > 1: raise ValueError('角色空幕状态异常，请重新读取')
        core_key = current[0] if current else None
    elif core == 'none': core_key = None
    else:
        core_key = selection['keys'].get(core)
        if core_key not in state['items'] or state['items'][core_key]['kind'] != 'core':
            raise ValueError('所选空幕不属于本次读取结果')
    if not isinstance(modules, list) or len(modules) > 10 or any(not isinstance(m, dict) for m in modules):
        raise ValueError('驱动清单无效，单角色最多选择10块')
    keys, manual = [], []
    for item in modules:
        ident = item.get('id')
        if not isinstance(ident, str): raise ValueError('驱动选择无效')
        key = selection['keys'].get(ident)
        if key not in state['items'] or state['items'][key]['kind'] != 'module' or key in keys:
            raise ValueError('驱动实例未知或重复选择；同一件物品不能占据两个位置')
        keys.append(key)
        manual.append({'row': item.get('row'), 'column': item.get('column')})
    if placement_mode != 'manual': raise ValueError('请先在装配页使用已有驱动块计算器生成位置')
    positions = arrange(character_id, [state['items'][key] for key in keys], manual) if keys else []
    return core_key, keys, positions
