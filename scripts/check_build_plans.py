"""Persistent build identities and real service execution against a simulated Core only."""
from copy import deepcopy
from pathlib import Path
import secrets
import shutil
import unittest
from native_equipment_fixture import World
from inventory.equipment import EquipmentService
from inventory.equipment_layout import board, occupied


class PlanWorld(World):
    revision = 1
    separate_control_domain = False
    refresh_changes_revision = False
    string_revision = False
    dirty = False

    def adapter(self):
        adapter = super().adapter()
        old_call, old_read = adapter.core.call, adapter.read
        def call(method, params, check=None, **kwargs):
            if method == 'native.snapshot.status':
                return {'providerId': self.provider, 'domains': [{'domain': 'inventory', 'ready': True, 'dirty': self.dirty,
                        'domainKey': self.domain, 'revision': str(self.revision) if self.string_revision else self.revision}]}
            result = old_call(method, params)
            if method == 'equipment.status' and self.separate_control_domain:
                result['domainKey'] = 'different-control-domain'
            if method.startswith(('equipment.equip_', 'equipment.unequip_')): self.revision += 1
            return result
        def read(kind, check):
            if self.refresh_changes_revision:self.revision+=1
            result = old_read(kind, check)
            result.raw_snapshot['header'].update(domain='inventory', revision=str(self.revision) if self.string_revision else self.revision)
            return result
        adapter.core.call, adapter.read = call, read
        return adapter


class BuildPlanTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]/'build/test-build-plans'/secrets.token_hex(8)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.world = PlanWorld()
        self.inventory = self.world.service(self.root, 'A')
        self.service = self.inventory.equipment
        self.capture()

    def capture(self, account='A'):
        adapter = self.world.adapter()
        self.service._save(account, adapter.read('equipment', lambda: None), (self.world.pid,self.world.provider,self.world.domain))
        self.info = self.service.inspect(account)
        self.ids = {row['label']: row['id'] for row in self.info['items']}

    def modules(self, label='#3'):
        row = self.world.rows[int(label[1:])-1]
        position = next({'row':r,'column':c} for r in range(1,6) for c in range(1,6)
                        if occupied(row,{'row':r,'column':c}).issubset(board(1003)))
        return [{'id':self.ids[label], **position}]

    def save(self, exclude=False):
        return self.service.save_build_plan('A',self.info['selection_id'],1003,self.ids['#4'],self.modules(),exclude,True)

    def execute(self, preview):
        self.service.start(preview['token']); self.service.thread.join(5)
        self.assertFalse(self.service.thread.is_alive())
        self.assertEqual(self.service.status()['state'],'verified',self.service.status())

    def test_handles_refresh_and_service_restart(self):
        old=self.save();self.assertEqual(self.world.calls,[])
        self.service=EquipmentService(self.inventory,adapter_factory=self.world.adapter,
                                      now=lambda:self.world.clock[0],
                                      sleep=lambda seconds:self.world.clock.__setitem__(0,self.world.clock[0]+seconds))
        info=self.service.inspect('A');saved=info['saved_plans']['1003']
        self.assertTrue(saved['valid']);self.assertNotEqual(saved['core'],old['core'])
        self.assertNotEqual(saved['modules'][0]['id'],old['modules'][0]['id'])
        self.assertNotIn('1003',self.service.inspect('B').get('saved_plans',{}))

    def test_saved_plan_records_bound_uid(self):
        import json
        from inventory.equipment_plans import path_for
        self.inventory.bind_account_uid('A','123456789012')
        self.save()
        payload=json.loads(path_for(self.inventory.directory,'A').read_text(encoding='utf-8'))
        self.assertEqual(payload['account_uid'],'123456789012')
        self.assertEqual(payload['account'],'A')

    def test_delete_saved_plan_removes_only_target_and_keeps_account_scope(self):
        import json
        from inventory.equipment_plans import path_for, delete
        self.inventory.bind_account_uid('A','123456789012')
        self.save()
        path=path_for(self.inventory.directory,'A')
        payload=json.loads(path.read_text(encoding='utf-8'))
        payload['plans']['9999']=deepcopy(payload['plans']['1003'])
        path.write_text(json.dumps(payload),encoding='utf-8')
        self.assertEqual(self.service.delete_build_plan('A',1003),{'deleted':True,'character_id':1003,'remaining':1})
        stored=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(stored['account_uid'],'123456789012')
        self.assertNotIn('1003',stored['plans'])
        self.assertIn('9999',stored['plans'])
        self.assertNotIn('1003',self.service.inspect('A')['saved_plans'])
        with self.assertRaisesRegex(ValueError,'没有已保存方案'):
            delete(self.inventory.directory,'B',1003)
        self.assertEqual(self.service.delete_build_plan('A',9999)['remaining'],0)
        self.assertFalse(path.exists(),'the account plan file is removed when its last scheme is deleted')

    def test_full_saved_assembly_transfer_and_target_only_dismantle(self):
        self.save();self.info=self.service.inspect('A')
        preview=self.service.preview_saved('A',1003)
        self.assertEqual(preview['transfers'],1)
        self.execute(preview)
        self.assertEqual([row['equipped_character_id'] for row in self.world.rows],[None,None,1003,1003])
        self.assertTrue(self.service.inspect('A')['saved_plans']['1003']['valid'])
        self.execute(self.service.preview('A',[1003],['drive','tape']))
        self.assertTrue(all(not row['equipped'] for row in self.world.rows))
        self.assertTrue(self.service.inspect('A')['saved_plans']['1003']['valid'])
        self.execute(self.service.preview_saved('A',1003))

    def test_protected_foreign_items_and_own_items(self):
        with self.assertRaisesRegex(ValueError,'其他角色'):self.save(True)
        own=[{'id':self.ids['#1'],**self.info['items'][0]['placement']}]
        saved=self.service.save_build_plan('A',self.info['selection_id'],1003,'keep',own,True,True)
        self.assertTrue(saved['valid'])
        self.world.rows[0].update(equipped_character_id=1019,equipped_character_uid=deepcopy(self.world.characters[1]['uid']))
        self.capture()
        self.assertFalse(self.info['saved_plans']['1003']['valid'])
        with self.assertRaisesRegex(ValueError,'其他角色'):self.service.preview_saved('A',1003)

    def test_changed_item_or_character_invalidates(self):
        self.save();self.world.rows[2]['level']=1;self.capture()
        self.assertFalse(self.info['saved_plans']['1003']['valid'])
        self.save();self.world.characters[0]['uid']['serial']+=1
        for row in self.world.rows:
            if row['equipped_character_id']==1003:row['equipped_character_uid']=deepcopy(self.world.characters[0]['uid'])
        self.capture();self.assertFalse(self.info['saved_plans']['1003']['valid'])

    def test_invalid_layout_stale_handle_and_preview_expiry(self):
        with self.assertRaises(ValueError):self.service.save_build_plan('A',self.info['selection_id'],1003,'none',[{'id':self.ids['#3'],'row':99,'column':1}],False,True)
        old=self.info['selection_id'];self.info=self.service.inspect('A')
        with self.assertRaises(ValueError):self.service.save_build_plan('A',old,1003,'none',[],False,True)
        self.ids={row['label']:row['id'] for row in self.info['items']};self.save()
        preview=self.service.preview_saved('A',1003)
        created=self.service.plan['created'];self.service.now=lambda:created+121
        with self.assertRaises(ValueError):self.service.start(preview['token'])
        self.assertEqual(self.world.calls,[])

    def test_http_save_reload_and_saved_preview(self):
        import json
        import threading
        from urllib.request import Request, urlopen
        from runtime import public_server
        root=Path(__file__).resolve().parents[1]/'build/desktop/public'
        server=public_server(root,0,inventory=self.inventory)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urlopen(base+'/inventory/status') as response:token=json.load(response)['token']
            def post(action, body):
                request=Request(base+'/inventory/equipment/'+action,data=json.dumps(body).encode(),headers={
                    'Content-Type':'application/json','Origin':base,'X-Keke-Inventory':token})
                with urlopen(request) as response:return json.load(response)
            saved=post('save-build',{'account':'A','selection_id':self.info['selection_id'],'character_id':1003,
                 'core':self.ids['#4'],'modules':self.modules(),'exclude_others':False,'complete':True})
            self.assertTrue(saved['valid'])
            info=post('inspect',{'account':'A'})
            self.assertTrue(info['saved_plans']['1003']['valid'])
            self.assertGreater(post('saved-preview',{'account':'A','character_id':1003})['total'],0)
            deleted=post('delete-build',{'account':'A','character_id':1003})
            self.assertEqual(deleted,{'deleted':True,'character_id':1003,'remaining':0})
            self.assertNotIn('1003',post('inspect',{'account':'A'})['saved_plans'])
            self.assertEqual(self.world.calls,[])
        finally:server.shutdown();server.server_close();thread.join()

    def test_live_revision_change_prevents_dispatch_and_cancel_waits_for_atomic_batch(self):
        self.save();preview=self.service.preview_saved('A',1003)
        self.world.rows[0]['level']+=1
        self.service.start(preview['token']);self.service.thread.join(5)
        self.assertEqual(self.service.status()['state'],'error')
        self.assertEqual(self.world.calls,[])
        self.capture();preview=self.service.preview_saved('A',1003)
        self.world.on_write=lambda:self.service.cancel()
        self.service.start(preview['token']);self.service.thread.join(5)
        self.assertEqual(self.service.status()['state'],'verified')
        self.assertEqual(self.service.status()['completed'],1)
        self.assertFalse(self.service.status()['batch_active'])
        self.assertEqual(len(self.world.calls),1)

    def test_independent_control_domain_and_refresh_revision_allow_unchanged_state(self):
        self.world.separate_control_domain=True
        self.world.refresh_changes_revision=True
        self.world.string_revision=True
        self.capture();self.save()
        self.execute(self.service.preview_saved('A',1003))
        self.assertGreater(len(self.world.calls),0)

    def test_fresh_revision_dirty_guard_still_blocks_first_command(self):
        self.world.string_revision=True
        self.capture();self.save();preview=self.service.preview_saved('A',1003)
        self.world.dirty=True
        self.service.start(preview['token']);self.service.thread.join(5)
        self.assertEqual(self.service.status()['state'],'error')
        self.assertEqual(self.world.calls,[])


if __name__=='__main__':unittest.main()
