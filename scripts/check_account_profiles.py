"""UID account identity, migration, and native snapshot attribution tests."""
import json
from pathlib import Path
import secrets
import shutil
import sys
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop'))
sys.path.insert(0, str(ROOT / 'scripts'))

from inventory.accounts import validate_uid
from inventory.equipment_plans import path_for
from inventory.service import InventoryService
from native_equipment_fixture import World
from vision.service import VisionService


class AccountProfileTests(unittest.TestCase):
    def setUp(self):
        test_root = ROOT / 'build/test-account-profiles'
        self.root = test_root / secrets.token_hex(10)
        if not self.root.resolve().is_relative_to(test_root.resolve()):
            raise ValueError('Invalid account fixture path')
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.vision = VisionService(self.root / 'vision')
        self.inventory = InventoryService(self.root / 'inventory', vision=self.vision)

    def add_legacy_data(self, account, batch_id):
        self.inventory._write(self.inventory._path(account), {
            'schema_version': 2, 'account': account, 'domains': {}, 'inventory': {'items': {'records': []}}
        })
        self.vision._write(self.vision._base(account, batch_id) / 'batch.json', {
            'schema_version': 1, 'id': batch_id, 'account': account, 'account_uid': None,
            'mode': 'offline', 'complete': True, 'state': 'parsed', 'saved_at': '2026-10-17T00:00:00+00:00',
            'processed': 1, 'expected': 1, 'images': [], 'records': []
        })
        plan_path = path_for(self.inventory.directory, account)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps({'schema': 1, 'account': account, 'account_uid': None, 'plans': {}}), encoding='utf-8')
        return [self.inventory._path(account), self.vision._base(account, batch_id) / 'batch.json', plan_path]

    def test_empty_default_label_is_not_an_unbound_account(self):
        self.assertIsNone(self.inventory.accounts.get('默认账号'))
        self.inventory.accounts._ensure_unbound('默认账号')
        self.inventory.accounts._write()
        self.inventory.accounts.discover_legacy()
        self.assertIsNone(self.inventory.accounts.get('默认账号'))
        self.assertEqual(self.inventory.accounts.list_profiles(), [])

    def test_delete_uid_removes_all_local_data_and_preserves_other_accounts(self):
        first = self.inventory.accounts.resolve_uid('123456789012')['account']
        other = self.inventory.accounts.resolve_uid('987654321098')['account']
        paths = self.add_legacy_data(first, 'a'*24)
        other_paths = self.add_legacy_data(other, 'b'*24)
        for file, key in [(paths[0], first), (other_paths[0], other)]:
            self.inventory._write(file, {'schema_version':2,'account':key,'domains':{},'inventory':{}})
        backup = paths[0].with_suffix('.previous.json');backup.write_bytes(paths[0].read_bytes())
        images = paths[1].parent/'images';images.mkdir();(images/'fixture.png').write_bytes(b'fixture')
        self.inventory.config.update(account=first, native_account=first)
        self.vision.batch = {'account':first,'id':'a'*24}
        with self.assertRaisesRegex(ValueError, '变化'):
            self.inventory.delete_account(first, 'wrong-uid')
        self.assertTrue(all(file.exists() for file in paths))
        self.vision.job['running'] = True
        with self.assertRaisesRegex(ValueError, '等待'):
            self.inventory.delete_account(first, '123456789012')
        self.vision.job['running'] = False
        result = self.inventory.delete_account(first, '123456789012')
        self.assertTrue(result['deleted'])
        self.assertTrue(all(not file.exists() for file in paths))
        self.assertFalse(backup.exists());self.assertFalse(images.parent.exists())
        self.assertTrue(all(file.exists() for file in other_paths))
        self.assertIsNone(self.inventory.accounts.get(first));self.assertIsNone(self.vision.batch)
        self.assertEqual(self.inventory.config['account'], other)
        self.assertIsNone(self.inventory.config['native_account'])
        restarted = InventoryService(self.inventory.directory, vision=self.vision)
        self.assertIsNone(restarted.accounts.get(first))
        self.assertEqual(len(restarted.accounts.list_profiles()), 1)
        restarted.delete_account(other, '987654321098')
        self.assertEqual(restarted.accounts.list_profiles(), [])
        self.assertEqual(restarted.config['account'], '默认账号')

    def test_legacy_discovery_stays_unbound_and_conflict_requires_explicit_replace(self):
        uid = '123456789012'
        source_paths = self.add_legacy_data('旧资料', '1' * 24)
        target_paths = self.add_legacy_data('UID已有资料', '2' * 24)
        source_before = [path.read_bytes() for path in source_paths]
        target_before = [path.read_bytes() for path in target_paths]

        self.inventory.accounts.discover_legacy()
        self.assertIsNone(self.inventory.accounts.get('旧资料')['uid'])
        self.assertIsNone(self.inventory.accounts.get('UID已有资料')['uid'])

        bound = self.inventory.bind_account_uid('UID已有资料', uid)
        self.assertEqual(bound['source']['uid'], uid)
        conflict = self.inventory.bind_account_uid('旧资料', uid)
        self.assertTrue(conflict['conflict'])
        self.assertEqual(conflict['target']['account'], 'UID已有资料')
        self.assertEqual(conflict['target']['data'], {'native_snapshot': True, 'ocr_batches': 1, 'saved_plans': True})
        self.assertIsNone(self.inventory.accounts.get('旧资料')['uid'])
        self.assertEqual(self.inventory.accounts.get('UID已有资料')['uid'], uid)

        replaced = self.inventory.bind_account_uid('旧资料', uid, replace_existing=True)
        self.assertFalse(replaced['conflict'])
        self.assertEqual(replaced['source']['uid'], uid)
        self.assertEqual(replaced['displaced']['account'], 'UID已有资料')
        self.assertIsNone(self.inventory.accounts.get('UID已有资料')['uid'])
        self.assertEqual([path.read_bytes() for path in source_paths], source_before)
        self.assertEqual([path.read_bytes() for path in target_paths], target_before)
        self.assertEqual(self.inventory.accounts.resolve_uid(uid)['account'], '旧资料')

    def test_account_notes_are_editable_and_uid_validation_is_exact(self):
        profile = self.inventory.accounts.resolve_uid('123456789012')
        self.inventory.select_account(profile['account'])
        result = self.inventory.set_account_note(profile['account'], '小号 · 日常')
        self.assertEqual(result['profile']['note'], '小号 · 日常')
        self.assertNotEqual(self.inventory.status()['config']['account'], profile['account'])
        self.assertIsNone(self.inventory.status()['config']['native_account'])
        self.assertEqual(self.inventory.accounts.get(profile['account'])['uid'], '123456789012')
        self.assertEqual(self.inventory.accounts.list_profiles()[0]['display_name'], '小号 · 日常 · UID 123456789012')
        for value in ('1234567', '123456789012345678901', '12x456789', '18446744073709551616', 123456789012):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_uid(value)

    def test_uid_recorded_data_cannot_be_rebound_and_rejection_keeps_selection(self):
        account = '带UID历史的资料'
        uid_a, uid_b = '123456789012', '223456789012'
        paths = self.add_legacy_data(account, '3' * 24)
        for path in paths:
            value = json.loads(path.read_text(encoding='utf-8'))
            value['account_uid'] = uid_a
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        before = [path.read_bytes() for path in paths]

        other = self.inventory.accounts.resolve_uid('323456789012')
        self.inventory.select_account(other['account'])
        selected_before = self.inventory.status()['config']['account']
        result = self.inventory.bind_account_uid(account, uid_b)

        self.assertTrue(result['uid_mismatch'])
        self.assertEqual(result['existing_uids'], [uid_a])
        self.assertIsNone(self.inventory.accounts.get(account)['uid'])
        self.assertEqual(self.inventory.status()['config']['account'], selected_before)
        self.assertEqual([path.read_bytes() for path in paths], before)

    def test_uid_bound_profile_cannot_be_rebound(self):
        profile = self.inventory.accounts.resolve_uid('123456789012')
        result = self.inventory.bind_account_uid(profile['account'], '223456789012')
        self.assertTrue(result['uid_mismatch'])
        self.assertEqual(result['existing_uids'], ['123456789012'])
        self.assertEqual(self.inventory.accounts.get(profile['account'])['uid'], '123456789012')

    def test_native_read_resolves_live_uid_and_tags_snapshot_without_claiming_legacy_data(self):
        uid = '123456789012'
        self.inventory._write(self.inventory._path('旧标签'), {
            'schema_version': 2, 'account': '旧标签', 'domains': {}, 'inventory': {'items': {'records': []}}
        })
        old_bytes = self.inventory._path('旧标签').read_bytes()
        self.inventory.accounts.discover_legacy()

        world = World()
        self.inventory.components = SimpleNamespace(component_root=lambda: self.root, status=lambda: {})
        adapter = world.adapter()
        adapter.adapter_id = 'nte-native-v1'
        adapter.domains = ('equipment',)
        read = adapter.read
        adapter.read = lambda kind, check, previous=None: read(kind, check)
        self.inventory.adapter_factory = lambda _adapter_id: adapter
        self.inventory.uid_reader = lambda pid: uid

        self.inventory.start(account='旧标签')
        self.inventory.thread.join(3)
        self.assertFalse(self.inventory.thread.is_alive())
        self.assertFalse(self.inventory.status()['job']['running'])
        profile = self.inventory.accounts.resolve_uid(uid)
        saved = self.inventory.load(profile['account'])
        self.assertEqual(saved['account_uid'], uid)
        self.assertIn('equipment', saved['inventory'])
        self.assertEqual(self.inventory._path('旧标签').read_bytes(), old_bytes)
        self.assertEqual(self.inventory.status()['config']['account'], profile['account'])
        self.assertEqual(self.inventory.status()['config']['native_account'], profile['account'])

    def test_equipment_is_blocked_when_live_uid_differs_from_selected_profile(self):
        profile = self.inventory.accounts.resolve_uid('123456789012')
        self.inventory.uid_reader = lambda pid: '123456789013'
        with self.assertRaisesRegex(ValueError, 'UID与选中的账号资料不一致'):
            self.inventory.verify_live_account(profile['account'], 123)


if __name__ == '__main__':
    unittest.main(verbosity=2)
