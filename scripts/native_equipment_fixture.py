"""Owned in-memory game stand-in. Never launches a game or native component."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from inventory.adapters import Observation
from inventory.adapters.nte import normalize_snapshot
from inventory.equipment import EquipmentService
from inventory.service import InventoryService
from inventory.equipment_layout import board, occupied


class World:
    def __init__(self):
        self.pid = 123
        self.provider = 'fixture-provider'
        self.domain = 'fixture-domain'
        self.inventory_domain = None
        self.available = True
        self.ready = True
        self.revision = 1
        self.calls = []
        self.error = None
        self.unrelated = False
        self.wrong_placement = False
        self.on_write = lambda: None
        self.clock = [0.0]
        self.characters = [{'character_id': 1003, 'uid': {'slot': 101, 'serial': 1}},
                           {'character_id': 1019, 'uid': {'slot': 102, 'serial': 2}}]
        self.rows = []
        for number, kind, cid in [(1, 'module', 1003), (2, 'core', 1003), (3, 'module', 1019), (4, 'core', None)]:
            owner = next((c['uid'] for c in self.characters if c['character_id'] == cid), None)
            self.rows.append({'uid': {'slot': 200 + number, 'serial': number}, 'item_id': str(number),
                'kind': kind, 'level': 0, 'names': {'zh_cn': '测试装备 ' + str(number)},
                'equipped': cid is not None, 'equipped_character_id': cid,
                'equipped_character_uid': deepcopy(owner),
                'equipped_placement': {'row': 1, 'column': number} if cid and kind == 'module' else None,
                'locked': True, 'discarded': False})
            if kind == 'module':
                row = self.rows[-1]
                row.update(geometry='Hen2', grid=2)
                if cid:
                    row['equipped_placement'] = next({'row': r, 'column': c} for r in range(1, 6) for c in range(1, 6)
                        if occupied(row, {'row': r, 'column': c}).issubset(board(cid)))

    def adapter(self):
        world = self

        class Adapter:
            def __init__(self):
                self.pid = world.pid
                self.core = SimpleNamespace(hello={'core_version': '0.4.4', 'capabilities':
                    ['equipment', 'native_equipment_v1'] if world.available else []}, call=self.call)

            def prepare(self, folder): pass
            def open(self, check): check()
            def close(self): pass
            def pid_reader(self): return world.pid

            def call(self, method, params, timeout=None):
                if method == 'native.snapshot.status':
                    return {'providerId': world.provider, 'domains': [{'domain': 'inventory',
                            'domainKey': world.inventory_domain or world.domain, 'revision': world.revision,
                            'ready': world.ready, 'dirty': False}]}
                if method == 'equipment.status':
                    return {'providerId': world.provider, 'domainKey': world.domain, 'ready': world.ready}
                if method == 'equipment.equip_one_key':
                    world.calls.append((method, deepcopy(params)))
                    if world.error == 'before': raise TimeoutError('fixture lost response')
                    character_uid = params['character']
                    character = next(c for c in world.characters if c['uid'] == character_uid)
                    selected = [params['core'], *(placement['equipment'] for placement in params['placements'])]
                    for current in world.rows:
                        if current['equipped'] and (current['equipped_character_uid'] == character_uid or current['uid'] in selected):
                            current.update(equipped=False, equipped_character_uid=None,
                                           equipped_character_id=None, equipped_placement=None)
                    core = next(row for row in world.rows if row['uid'] == params['core'])
                    assert core['kind'] == 'core'
                    core.update(equipped=True, equipped_character_uid=deepcopy(character_uid),
                                equipped_character_id=character['character_id'], equipped_placement=None)
                    for placement in params['placements']:
                        row = next(item for item in world.rows if item['uid'] == placement['equipment'])
                        assert row['kind'] == 'module'
                        position = {'row': placement['row'], 'column': placement['column']}
                        if world.wrong_placement: position['row'] = 99
                        row.update(equipped=True, equipped_character_uid=deepcopy(character_uid),
                                   equipped_character_id=character['character_id'], equipped_placement=position)
                    if world.unrelated: world.rows[2]['level'] += 1
                    world.on_write()
                    world.revision += 1
                    if world.error == 'after': raise TimeoutError('fixture lost response')
                    return {'accepted': True}
                if method not in ('equipment.unequip_module', 'equipment.unequip_core', 'equipment.equip_module', 'equipment.equip_core'):
                    raise AssertionError('Unexpected RPC ' + method)
                world.calls.append((method, deepcopy(params)))
                if world.error == 'before': raise TimeoutError('fixture lost response')
                row = next(r for r in world.rows if r['uid'] == params['equipment'])
                assert method.endswith('module') == (row['kind'] == 'module')
                if method.startswith('equipment.unequip_'):
                    assert row['equipped_character_uid'] == params['character']
                    row.update(equipped=False, equipped_character_uid=None, equipped_character_id=None, equipped_placement=None)
                else:
                    assert not row['equipped']
                    character = next(c for c in world.characters if c['uid'] == params['character'])
                    position = {'row': params['row'], 'column': params['column']} if row['kind'] == 'module' else None
                    if position and world.wrong_placement: position['row'] = 99
                    row.update(equipped=True, equipped_character_uid=deepcopy(params['character']),
                               equipped_character_id=character['character_id'], equipped_placement=position)
                if world.unrelated: world.rows[2]['level'] += 1
                world.on_write()
                if world.error == 'after': raise TimeoutError('fixture lost response')
                return {'accepted': True}

            def read(self, kind, check):
                assert kind == 'equipment'
                check()
                raw = {'header': {'providerId': world.provider, 'domain': 'inventory',
                                  'domainKey': world.inventory_domain or world.domain,
                                  'snapshotId': 'fixture', 'revision': world.revision,
                                  'collectionComplete': True, 'collectionScope': 'EQUIP'},
                       'rows': deepcopy(world.rows), 'pages': [{'characters': deepcopy(world.characters)}],
                       'saved_at': '2026-10-16T00:00:00+00:00'}
                return Observation(normalize_snapshot(kind, raw), raw)

        return Adapter()

    def service(self, directory, account='装配测试'):
        uid = '123456789012'
        inventory = InventoryService(Path(directory) / 'inventory', components=SimpleNamespace(
            component_root=lambda: Path(directory), status=lambda: {}), uid_reader=lambda pid: uid)
        inventory.accounts._ensure_unbound(account)
        inventory.accounts.bind(account, uid)
        inventory.config['account'] = account
        inventory.config['native_account'] = account
        inventory.equipment = EquipmentService(inventory, adapter_factory=self.adapter,
                                               now=lambda: self.clock[0],
                                               sleep=lambda seconds: self.clock.__setitem__(0, self.clock[0] + seconds))
        adapter = self.adapter()
        inventory.equipment._save(account, adapter.read('equipment', lambda: None),
                                  (self.pid, self.provider, self.domain))
        return inventory
