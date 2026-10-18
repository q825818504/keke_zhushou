"""Native equipment failure-path tests against owned fixtures, with no live writes."""
from copy import deepcopy
import json
from pathlib import Path
import secrets
import shutil
from types import SimpleNamespace
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from native_equipment_fixture import World
from inventory.equipment import equipment_state, verify_unequipped
from runtime import public_server


class NativeEquipmentTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / 'build/test-native-equipment'
        test_path = test_root / secrets.token_hex(10)
        if not test_path.resolve().is_relative_to(test_root.resolve()): raise ValueError('Invalid test directory')
        test_path.mkdir(parents=True)
        self.tmp = SimpleNamespace(name=str(test_path))
        self.addCleanup(shutil.rmtree, test_path, True)
        self.world = World()
        self.inventory = self.world.service(self.tmp.name, '测试账号')
        self.service = self.inventory.equipment
        self.service.inspect('测试账号')

    def recapture(self):
        adapter = self.world.adapter()
        self.service._save('测试账号', adapter.read('equipment', lambda: None),
                           (self.world.pid, self.world.provider, self.world.domain))
        return self.service.inspect('测试账号')

    def preview(self, categories=None, characters=None):
        return self.service.preview('测试账号', characters or [1003], categories or ['drive', 'tape'])

    def assembly_preview(self):
        snapshot = self.service.inspect('测试账号')
        core = next(row for row in snapshot['items'] if row['label'] == '#4')
        drive = next(row for row in snapshot['items'] if row['label'] == '#3')
        return self.service.preview_assembly('测试账号', snapshot['selection_id'], 1003,
            core['id'], [{'id': drive['id'], 'row': 1, 'column': 1}], 'manual')

    def run_plan(self, plan):
        self.service.start(plan['token'])
        self.service.thread.join(5)
        self.assertFalse(self.service.thread.is_alive())
        self.assertIsNone(self.inventory.native_operation)
        return self.service.status()

    def test_inspect_and_preview_never_write(self):
        info = self.service.inspect('测试账号')
        self.assertTrue(info['ready'])
        self.assertEqual(info['equipment_count'], 4)
        plan = self.preview()
        self.assertEqual(plan['total'], 2)
        self.assertNotIn('equipment', plan['items'][0])
        self.assertEqual(self.world.calls, [])

    def test_core_only_selected_owner_and_category(self):
        before = deepcopy(self.world.rows)
        result = self.run_plan(self.preview(['tape']))
        self.assertEqual(result['state'], 'verified')
        self.assertEqual(result['completed'], 1)
        self.assertEqual(self.world.calls[0][0], 'equipment.unequip_core')
        for index in (0, 2, 3): self.assertEqual(before[index], self.world.rows[index])
        self.assertFalse(self.world.rows[1]['equipped'])
        saved = self.inventory.load('测试账号')
        self.assertEqual(len(saved['inventory']['equipment']['records']), 4)
        self.assertEqual(self.inventory.config['account'], '测试账号')

    def test_multi_role_batch_serializes_and_verifies(self):
        result = self.run_plan(self.preview(characters=[1003, 1019]))
        self.assertEqual((result['state'], result['completed']), ('verified', 3))
        self.assertEqual(len(self.world.calls), 3)
        self.assertEqual(sum(r['equipped'] for r in self.world.rows), 0)

    def test_batch_accepts_rotated_inventory_key_after_verified_equip(self):
        self.world.on_write = lambda: setattr(self.world, 'inventory_domain', 'fixture-inventory-after-write')
        result = self.run_plan(self.assembly_preview())
        self.assertEqual(result['state'], 'verified')
        stored = self.inventory.load('测试账号')
        self.assertEqual(stored['domains']['equipment']['header']['domainKey'], 'fixture-inventory-after-write')
        self.assertEqual(stored['native_sessions']['equipment']['domain_key'], 'fixture-inventory-after-write')

    def test_rotated_inventory_key_still_rechecks_live_uid_before_save(self):
        def rotate_scope_and_change_uid():
            self.world.inventory_domain = 'fixture-inventory-after-write'
            self.inventory.uid_reader = lambda pid: '999999999999'
        self.world.on_write = rotate_scope_and_change_uid
        result = self.run_plan(self.assembly_preview())
        self.assertEqual(result['state'], 'error')
        self.assertIn('与选中的账号资料不一致', result['message'])
        stored = self.inventory.load('测试账号')
        self.assertEqual(stored['domains']['equipment']['header']['domainKey'], 'fixture-domain')

    def test_prewrite_backup_and_final_audit(self):
        def audit_exists_before_write():
            files = list((self.inventory.directory / 'equipment-operations').glob('*.json'))
            self.assertEqual(len(files), 1)
            audit = json.loads(files[0].read_text(encoding='utf-8'))
            self.assertIn('before', audit)
            self.assertEqual(audit['job']['in_flight'], 0)
            self.assertNotIn('token', audit)
        self.world.on_write = audit_exists_before_write
        result = self.run_plan(self.preview(['tape']))
        self.assertEqual(result['state'], 'verified')
        audit = json.loads(Path(result['report']).read_text(encoding='utf-8'))
        self.assertFalse(audit['job']['running'])
        self.assertIsNone(audit['job']['in_flight'])
        self.assertTrue(audit['before']['rows'][1]['equipped'])

    def test_completion_is_not_published_before_native_lock_release(self):
        release_entered = threading.Event()
        allow_release = threading.Event()
        original_release = self.service._release

        def delayed_release():
            release_entered.set()
            allow_release.wait(5)
            original_release()

        self.service._release = delayed_release
        try:
            self.service.start(self.preview(['tape'])['token'])
            self.assertTrue(release_entered.wait(3))
            status = self.inventory.status()
            self.assertTrue(status['equipment_job']['running'])
            self.assertEqual(status['native_operation'], 'equipment')
        finally:
            allow_release.set()
            if self.service.thread:
                self.service.thread.join(5)
        status = self.inventory.status()
        self.assertFalse(status['equipment_job']['running'])
        self.assertIsNone(status['native_operation'])

    def test_stale_preview_no_dispatch(self):
        plan = self.preview()
        self.world.rows[0]['level'] = 1
        self.assertEqual(self.run_plan(plan)['state'], 'error')
        self.assertEqual(self.world.calls, [])

    def test_changed_account_or_process_no_dispatch(self):
        plan = self.preview()
        self.world.domain = 'other-account'
        self.assertEqual(self.run_plan(plan)['state'], 'error')
        self.assertEqual(self.world.calls, [])

    def test_unsupported_capability_releases_reservation(self):
        self.world.available = False
        result = self.run_plan(self.preview(['tape']))
        self.assertEqual(result['state'], 'error')
        self.assertIn('没有原生装备执行', result['message'])
        self.assertIsNone(self.inventory.native_operation)

    def test_not_ready_never_writes(self):
        self.world.ready = False
        result = self.run_plan(self.preview())
        self.assertEqual(result['state'], 'error')
        self.assertIn('未就绪', result['message'])
        self.assertEqual(self.world.calls, [])

    def test_close_failure_still_releases_reservation(self):
        factory = self.service.factory
        def fail_close():
            adapter = factory()
            def close(): raise OSError('fixture close error')
            adapter.close = close
            return adapter
        self.world.available = False
        self.service.factory = fail_close
        result = self.run_plan(self.preview(['tape']))
        self.assertEqual(result['state'], 'error')
        self.assertIsNone(self.inventory.native_operation)

    def test_backup_failure_prevents_dispatch(self):
        plan = self.preview()
        def denied(*args): raise OSError('fixture backup unavailable')
        self.inventory._write = denied
        result = self.run_plan(plan)
        self.assertEqual(result['state'], 'error')
        self.assertEqual(self.world.calls, [])

    def test_invalid_owner_uid_never_previews(self):
        self.world.rows[0]['equipped_character_uid'] = {'slot': 101, 'serial': 999}
        with self.assertRaisesRegex(ValueError, '所属角色'): self.recapture()

    def test_duplicate_uid_never_previews(self):
        self.world.rows[1]['uid'] = deepcopy(self.world.rows[0]['uid'])
        with self.assertRaises(ValueError): self.recapture()

    def test_boolean_uid_never_previews(self):
        self.world.characters[0]['uid']['slot'] = True
        with self.assertRaises(ValueError): self.recapture()

    def test_expired_preview_never_writes(self):
        plan = self.preview()
        deadline = self.service.plan['created'] + 121
        self.service.now = lambda: deadline
        with self.assertRaisesRegex(ValueError, '过期'): self.service.start(plan['token'])
        self.assertEqual(self.world.calls, [])
        self.assertIsNone(self.inventory.native_operation)

    def test_token_single_use(self):
        plan = self.preview(['tape'])
        self.run_plan(plan)
        with self.assertRaisesRegex(ValueError, '预览无效'): self.service.start(plan['token'])
        self.assertEqual(len(self.world.calls), 1)

    def test_lost_ack_does_not_repeat_and_can_observe_success(self):
        self.world.error = 'after'
        result = self.run_plan(self.preview())
        self.assertEqual((result['state'], result['completed']), ('stopped', 1))
        self.assertEqual(len(self.world.calls), 1)

    def test_unknown_outcome_never_repeat(self):
        self.world.error = 'before'
        path = self.inventory._path('测试账号')
        previous = path.read_bytes()
        result = self.run_plan(self.preview())
        self.assertEqual((result['state'], result['completed']), ('unconfirmed', 0))
        self.assertEqual(len(self.world.calls), 1)
        self.assertEqual(path.read_bytes(), previous)

    def test_unrelated_equipment_change_stops(self):
        self.world.unrelated = True
        result = self.run_plan(self.preview())
        self.assertEqual(result['state'], 'error')
        self.assertEqual(len(self.world.calls), 1)
        self.assertIn('其他装备', result['message'])

    def test_cancel_finishes_current_verification_only(self):
        self.world.on_write = self.service.cancel
        result = self.run_plan(self.preview())
        self.assertEqual((result['state'], result['completed']), ('stopped', 1))
        self.assertEqual(len(self.world.calls), 1)

    def test_zero_equipped_returns_no_token(self):
        for row in self.world.rows:
            row.update(equipped=False, equipped_character_id=None, equipped_character_uid=None, equipped_placement=None)
        self.recapture()
        plan = self.preview()
        self.assertEqual(plan['total'], 0)
        self.assertNotIn('token', plan)

    def test_unsupported_and_duplicate_inputs(self):
        for characters, categories in [([True], ['drive']), ([1003, 1003], ['drive']), ([1003], ['arc']), ([1003], []), ([1003], [{}])]:
            with self.subTest(characters=characters, categories=categories):
                with self.assertRaises(ValueError): self.service.preview('A', characters, categories)
        self.assertEqual(self.world.calls, [])

    def test_native_and_vision_operation_exclusion(self):
        self.inventory.native_operation = 'equipment'
        with self.assertRaises(ValueError): self.service.inspect()
        with self.assertRaises(ValueError): self.inventory.start(account='A')
        with self.assertRaises(ValueError): self.inventory.delete('A', 'native')
        self.inventory.native_operation = None
        self.inventory.vision = type('Vision', (), {'job': {'running': True}})()
        with self.assertRaises(ValueError): self.preview()

    def test_http_requires_origin_and_token(self):
        root = Path(self.tmp.name) / 'public'
        root.mkdir()
        (root / 'public-manifest.json').write_text(json.dumps({'files': []}), encoding='utf-8')
        server = public_server(root, 0, inventory=self.inventory)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with urlopen(base + '/inventory/status') as response: token = json.load(response)['token']
            def post(headers):
                request = Request(base + '/inventory/equipment/inspect', data=b'{}', method='POST', headers=headers)
                with urlopen(request) as response: return json.load(response)
            with self.assertRaises(HTTPError) as error: post({'Content-Type': 'application/json'})
            self.assertEqual(error.exception.code, 403)
            result = post({'Content-Type': 'application/json', 'Origin': base, 'X-Keke-Inventory': token})
            self.assertTrue(result['ready'])
            self.assertEqual(self.world.calls, [])
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main(verbosity=2)
