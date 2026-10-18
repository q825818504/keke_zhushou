"""Independent native placement validation; solving belongs to DriveLayoutSolver."""
import json
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('equipment-layouts.json').read_text(encoding='utf-8'))


def board(character_id):
    value = CATALOG['characters'].get(str(character_id))
    if not value or len(value['cells']) != 20:
        raise ValueError('当前角色缺少已核实的原生终端盘面，暂不能装配驱动块')
    return {tuple(cell) for cell in value['cells']}


def shape(item):
    name = str(item.get('geometry') or '').removeprefix('EquipmentGeometry_')
    cells = CATALOG['shapes'].get(name)
    if not cells or type(item.get('grid')) is not int or len(cells) != item['grid']:
        raise ValueError('驱动形状或格数未知，无法安全计算摆放位置')
    return cells


def occupied(item, placement):
    if (not isinstance(placement, dict) or any(type(placement.get(k)) is not int or not 1 <= placement[k] <= 5
                                             for k in ('row', 'column'))):
        raise ValueError('驱动位置必须是1至5的整数行列')
    return {(placement['row']+r, placement['column']+c) for r, c in shape(item)}


def native_position(item, placement):
    """Convert UI bounding-box coordinates to the game's original shape pivot."""
    occupied(item, placement)
    name = str(item.get('geometry') or '').removeprefix('EquipmentGeometry_')
    dr, dc = CATALOG['origins'][name]
    position = {'row': placement['row']-dr, 'column': placement['column']-dc}
    if any(not 1 <= v <= 5 for v in position.values()):
        raise ValueError('驱动原生锚点超出接口支持范围')
    return position


def visual_position(item, placement):
    if placement is None: return None
    shape(item)
    if not isinstance(placement, dict) or any(type(placement.get(k)) is not int for k in ('row', 'column')):
        raise ValueError('驱动原生位置无效，请重新读取')
    name = str(item.get('geometry') or '').removeprefix('EquipmentGeometry_')
    dr, dc = CATALOG['origins'][name]
    return {'row': placement['row']+dr, 'column': placement['column']+dc}


def arrange(character_id, items, manual):
    available = board(character_id)
    if len(items) > 10 or sum(len(shape(item)) for item in items) > len(available):
        raise ValueError('所选驱动超过角色终端容量，请减少装备')
    if not isinstance(manual, list) or len(manual) != len(items):
        raise ValueError('请先使用驱动块计算器生成完整摆法')
    used = set()
    for item, position in zip(items, manual):
        cells = occupied(item, position)
        if not cells.issubset(available) or cells & used:
            raise ValueError('驱动块重叠或越出角色可用格，请调整行列或使用自动摆放')
        used |= cells
    return manual
