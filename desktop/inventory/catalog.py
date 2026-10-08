"""Optional read-only display names from the selected Core's static catalog."""
import sqlite3
import json
from pathlib import Path
from contextlib import closing

def display_names(root, kind, rows):
    fields = {'equipment':('equipment_item','item_id'), 'characters':('character','character_id')}
    if kind not in fields:
        return {}
    database = root/'data/game_static.sqlite3'
    if not database.is_file():
        if kind=='characters':
            try:
                catalog=json.loads((Path(__file__).parents[1]/'vision/resources/catalog.json').read_text(encoding='utf-8'))
                return {str(row['character_id']):row['name_zh'] for row in catalog['characters']}
            except (OSError,ValueError,KeyError):pass
        return {}
    table, field = fields[kind]
    identities = sorted({str(row[field]) for row in rows if type(row.get(field)) is int or (isinstance(row.get(field),str) and len(row[field])<=128)})
    names = {}
    try:
        with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as connection:
            connection.execute('PRAGMA query_only=ON')
            for offset in range(0,len(identities),256):
                batch=identities[offset:offset+256]
                parameters=','.join('?' for _ in batch)
                for identity, name in connection.execute(f'SELECT {field},name_zh FROM {table} WHERE {field} IN ({parameters})',batch):
                    if name:
                        names[str(identity)] = name
    except sqlite3.Error:
        return {}
    return names
