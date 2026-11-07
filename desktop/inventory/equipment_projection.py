"""Project the pinned Core's raw EQUIP records using the static game catalog."""
import json
import math
from pathlib import Path

from .equipment_layout import occupied, visual_position
from .snapshot import uid


def raw_uid(value):
    result = {'slot': value['solt'], 'serial': value['serial']}
    uid(result)
    return result


def curve_value(points, level):
    for index, (right, value) in enumerate(points):
        if level <= right:
            if index == 0:
                return value
            left, previous = points[index - 1]
            return previous + (value - previous) * (level - left) / (right - left)
    return points[-1][1]


def project_equipment(records, references):
    catalog = json.loads(Path(__file__).with_name('equipment-projection-catalog.json').read_text(encoding='utf-8'))

    def stat(prop, value):
        name, percent = catalog['attributes'][prop]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('装备词条数值无效')
        return {'property_id': prop, 'value': value, 'percent': bool(percent), 'names': {'zh_cn': name}}

    items = {}
    for record in records:
        if (record.get('kind') != 'HTEquipmentItem' or record.get('mapUidMatchesItem') is not True
                or record.get('duplicateMapUidObserved') is not False):
            raise ValueError('装备原始记录身份无法核实')
        identity = raw_uid(record['UniqueID'])
        key = uid(identity)
        if key in items:
            raise ValueError('装备实例重复')
        item_id = record['ItemID']
        kind, quality, name, geometry, grid, suit, max_level = catalog['items'][item_id]
        level = record['StrengthenLevel']
        if type(level) is not int or not 0 <= level <= max_level:
            raise ValueError('装备等级无效')
        suffix = f"{'Core' if kind == 'core' else grid}_ITEM_QUALITY_{quality}"
        items[key] = {
            'uid': identity, 'item_id': item_id, 'kind': kind, 'quality': quality.lower(),
            'names': {'zh_cn': name}, 'geometry': geometry.rsplit('EquipmentGeometry_', 1)[-1],
            'grid': grid, 'suit_id': suit, 'suit_names': {}, 'max_level': max_level, 'level': level,
            'locked': record['IsLocked'] == 1, 'discarded': record['IsDiscarded'] == 1,
            'equipped': False, 'equipped_character_id': None, 'equipped_character_uid': None,
            'equipped_placement': None,
            'main_stats': [stat(prop, curve_value(catalog['curves'][f'{prop}_{suffix}'], level))
                           for prop in record['RandomBaseModifyData']],
            'sub_stats': [stat(row['PropName'], row['PropValue']) for row in record['RandomModifyData']],
        }

    characters, owners, equipped = [], set(), set()
    for ref in references:
        character = int(ref['ItemID'])
        identity = raw_uid(ref['UniqueID'])
        if character <= 0 or character in owners or ref.get('bIsTemporary') is not False:
            raise ValueError('装备角色身份无法核实')
        owners.add(character)
        characters.append({'character_id': character, 'uid': identity})
        groups = {}
        for kind, slots in (
            ('core', ref['EquipCoreSlots']),
            ('module', [slot for group in ref['EquipmentSlots'] for slot in group['SlotList']]),
        ):
            for slot in slots:
                key = uid(raw_uid(slot['EquipNetID']))
                item = items[key]
                if slot['State'] != 1 or slot['EquipmentID'] != item['item_id'] or item['kind'] != kind:
                    raise ValueError('装备格位引用与库存不一致')
                groups.setdefault(key, []).append(slot)
        for key, slots in groups.items():
            if key in equipped:
                raise ValueError('同一装备被多个角色引用')
            equipped.add(key)
            item = items[key]
            placement = None
            if item['kind'] == 'module':
                anchors = [slot for slot in slots if slot['bFirstStep'] == 1]
                if len(anchors) != 1:
                    raise ValueError('驱动块缺少唯一原生锚点')
                placement = {'row': anchors[0]['Row'], 'column': anchors[0]['Column']}
                actual = {(slot['Row'], slot['Column']) for slot in slots}
                if len(actual) != len(slots) or occupied(item, visual_position(item, placement)) != actual:
                    raise ValueError('驱动形状与实际占用格不一致')
            elif len(slots) != 1:
                raise ValueError('空幕格位引用重复')
            item.update(equipped=True, equipped_character_id=character,
                        equipped_character_uid=identity, equipped_placement=placement)

    return list(items.values()), characters, [items[key]['uid'] for key in sorted(equipped)]
