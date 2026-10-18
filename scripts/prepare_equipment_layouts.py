"""Export only native placement geometry from a read-only public static catalog."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def export(database, destination):
    database = Path(database).resolve()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        shapes, origins = {}, {}
        for name, count in connection.execute('SELECT shape_id,cell_count FROM equipment_shape ORDER BY shape_id'):
            cells = connection.execute('SELECT x,y FROM equipment_shape_cell WHERE shape_id=? ORDER BY ordinal', (name,)).fetchall()
            top, left = min(r for r, c in cells), min(c for r, c in cells)
            normalized = sorted([r-top, c-left] for r, c in cells)
            if len(normalized) != count or len({tuple(p) for p in normalized}) != count:
                raise ValueError('Invalid shape: ' + name)
            shapes[name.removeprefix('EquipmentGeometry_')] = normalized
            origins[name.removeprefix('EquipmentGeometry_')] = [top, left]
        characters = {}
        for cid, name in connection.execute('SELECT character_id,name_zh FROM character ORDER BY character_id'):
            cells = [list(row) for row in connection.execute('SELECT row,column FROM equipment_plan_cell WHERE character_id=? ORDER BY row,column', (cid,))]
            if not cells:
                continue
            if len(cells) != 20 or any(not 1 <= v <= 5 for p in cells for v in p):
                raise ValueError('Invalid character board: ' + str(cid))
            characters[str(cid)] = {'name': name, 'cells': cells}
    value = {'schema': 1, 'source': {'project': 'hxwd94666/NTE-Drive-Calculator',
             'database_sha256': hashlib.sha256(database.read_bytes()).hexdigest(),
             'tables': ['equipment_shape', 'equipment_shape_cell', 'equipment_plan_cell', 'character'],
             'coordinates': 'UI: 1-based bounding-box top-left. RPC/snapshot: original shape origin. RPC = UI - origins; x=row, y=column.'},
             'shapes': shapes, 'origins': origins, 'characters': characters}
    Path(destination).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {len(shapes)} shapes and {len(characters)} character boards')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('database')
    parser.add_argument('--output', default=str(Path(__file__).resolve().parents[1]/'desktop/inventory/equipment-layouts.json'))
    args = parser.parse_args()
    export(args.database, args.output)
