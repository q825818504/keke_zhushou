"""Assembly identities, transfers, geometry and uncertain outcomes; no real game."""
from copy import deepcopy
import json
from pathlib import Path
import secrets
import shutil
import unittest
from native_equipment_fixture import World
from inventory.equipment_layout import board, occupied, native_position, visual_position, CATALOG


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parents[1]/'build/test-native-assembly'/secrets.token_hex(10)
        self.directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.directory, True)
        self.world = World()
        self.inventory = self.world.service(self.directory)
        self.service = self.inventory.equipment

    def inspect(self):
        adapter=self.world.adapter()
        self.service._save('装配测试',adapter.read('equipment',lambda:None),
                           (self.world.pid,self.world.provider,self.world.domain))
        self.info = self.service.inspect()
        self.ids = {r['label']: r['id'] for r in self.info['items']}

    def positions(self, labels, cid=1003):
        used, result = set(), []
        for label in labels:
            row = self.world.rows[int(label[1:])-1]
            for r in range(1, 6):
                for c in range(1, 6):
                    position = {'row': r, 'column': c}
                    cells = occupied(row, position)
                    if cells.issubset(board(cid)) and not cells & used:
                        result.append({'id': self.ids[label], **position}); used |= cells; break
                else: continue
                break
        return result

    def preview(self, labels=('#3',), core='#4', cid=1003):
        return self.service.preview_assembly('装配测试', self.info['selection_id'], cid,
            self.ids.get(core, core), self.positions(labels, cid), 'manual')

    def execute(self, preview):
        self.service.start(preview['token']); self.service.thread.join(5)
        self.assertFalse(self.service.thread.is_alive())
        self.assertIsNone(self.inventory.native_operation)
        return self.service.status()

    def empty(self):
        for row in self.world.rows:
            row.update(equipped=False, equipped_character_id=None, equipped_character_uid=None, equipped_placement=None)

    def test_inspection_opaque_instances_and_preview_are_read_only(self):
        self.inspect(); preview = self.preview()
        self.assertEqual(self.world.calls, [])
        self.assertTrue(all('uid' not in row for row in self.info['items']))
        self.assertEqual(len(self.info['characters'][0]['board']), 20)
        self.assertEqual(preview['total'], 5)
        self.assertEqual(preview['transfers'], 1)

    def test_full_loadout_and_cross_role_transfer(self):
        self.inspect(); result = self.execute(self.preview())
        self.assertEqual((result['state'], result['completed']), ('verified', 1))
        self.assertEqual([m for m,p in self.world.calls], ['equipment.equip_one_key'])
        self.assertEqual([r['equipped_character_id'] for r in self.world.rows], [None,None,1003,1003])
        self.assertTrue(all(r['locked'] for r in self.world.rows))
        audit = json.loads(Path(result['report']).read_text(encoding='utf-8'))
        self.assertEqual(len(audit['operations']), 5)
        self.assertNotIn('token', audit)
        self.assertEqual(self.inventory.load('装配测试')['inventory']['equipment']['records'][2]['equipped_character_id'], '1003')

    def test_noop_exact_current_layout_has_no_write_token(self):
        self.inspect()
        row = self.world.rows[0]
        p = self.service.preview_assembly('装配测试', self.info['selection_id'],1003,'keep',
            [{'id':self.ids['#1'],**row['equipped_placement']}],'manual')
        self.assertEqual(p['total'], 0); self.assertNotIn('token', p)

    def test_tape_replace_keeps_selected_existing_drive(self):
        self.inspect(); before=deepcopy(self.world.rows[0])
        p=self.service.preview_assembly('装配测试',self.info['selection_id'],1003,self.ids['#4'],
            [{'id':self.ids['#1'],**before['equipped_placement']}],'manual')
        result=self.execute(p)
        self.assertEqual(result['state'],'verified');self.assertEqual(p['total'],2)
        self.assertEqual(before,self.world.rows[0])

    def test_tape_transfer_preserves_source_drives(self):
        self.empty();self.world.rows[1].update(equipped=True,equipped_character_id=1019,equipped_character_uid=self.world.characters[1]['uid'])
        self.inspect();p=self.preview(labels=(),core='#2')
        self.assertEqual(p['transfers'],1)
        self.assertEqual(self.execute(p)['state'],'verified')
        self.assertEqual(self.world.rows[1]['equipped_character_id'],1003)

    def test_duplicate_foreign_and_non_module_handles_rejected(self):
        self.inspect();positions=self.positions(('#1',))
        for modules in (positions+positions,[{'id':'forged','row':1,'column':1}],[{'id':self.ids['#2'],'row':1,'column':1}]):
            with self.subTest(modules=modules),self.assertRaises(ValueError):
                self.service.preview_assembly('装配测试',self.info['selection_id'],1003,'keep',modules,'manual')
        self.assertEqual(self.world.calls,[])

    def test_overlaps_and_outside_cells_rejected(self):
        self.inspect();p=self.positions(('#1',))[0]
        for modules in ([p,dict(p,id=self.ids['#3'])],[dict(p,row=5,column=5)],[dict(p,row=True)]):
            with self.subTest(modules=modules),self.assertRaises(ValueError):
                self.service.preview_assembly('装配测试',self.info['selection_id'],1003,'keep',modules,'manual')

    def test_stale_inspection_rejected_without_dispatch(self):
        self.inspect();self.world.rows[0]['level']+=1
        adapter=self.world.adapter()
        observation=adapter.read('equipment',lambda:None)
        stored=self.inventory.load('装配测试')
        stored['domains']['equipment']=observation.raw_snapshot
        stored['inventory']['equipment']=observation.data
        self.inventory._write(self.inventory._path('装配测试'),stored)
        with self.assertRaisesRegex(ValueError,'快照已变化'):self.preview()
        self.assertIsNone(self.inventory.native_operation)

    def test_expired_inspection_rejected(self):
        self.inspect();self.service.now=lambda:self.service.selection['created']+601
        with self.assertRaisesRegex(ValueError,'请从该账号已保存'):self.preview()

    def test_changed_state_after_preview_never_writes(self):
        self.inspect();p=self.preview();self.world.domain='new-game'
        self.assertEqual(self.execute(p)['state'],'error');self.assertEqual(self.world.calls,[])

    def test_lost_equip_response_confirmed_once_then_stops(self):
        self.empty();self.inspect();self.world.error='after'
        result=self.execute(self.preview(labels=(),core='#4'))
        self.assertEqual((result['state'],result['completed']),('stopped',1))
        self.assertEqual(len(self.world.calls),1)

    def test_unconfirmed_equip_never_retries(self):
        self.empty();self.inspect();self.world.error='before'
        result=self.execute(self.preview(labels=(),core='#4'))
        self.assertEqual((result['state'],result['completed']),('unconfirmed',0))
        self.assertEqual(len(self.world.calls),1)

    def test_wrong_placement_stops_following_commands(self):
        self.empty();self.inspect();self.world.wrong_placement=True
        result=self.execute(self.preview(labels=('#1','#3'),core='none'))
        self.assertEqual(result['state'],'error');self.assertEqual(len(self.world.calls),1)

    def test_cancel_verifies_current_equip_only(self):
        self.empty();self.inspect();self.world.on_write=self.service.cancel
        result=self.execute(self.preview())
        self.assertEqual((result['state'],result['completed']),('verified',1));self.assertEqual(len(self.world.calls),1)

    def test_backup_failure_blocks_equip(self):
        self.empty();self.inspect();p=self.preview()
        def fail(*args):raise OSError('backup failed')
        self.inventory._write=fail
        self.assertEqual(self.execute(p)['state'],'error');self.assertEqual(self.world.calls,[])

    def test_unrelated_changes_stop_equip(self):
        self.empty();self.inspect();self.world.unrelated=True
        self.assertEqual(self.execute(self.preview(labels=(),core='#4'))['state'],'error')
        self.assertEqual(len(self.world.calls),1)

    def test_unsupported_geometry_blocks_plan(self):
        self.world.rows[2]['geometry']='unknown';self.inspect()
        with self.assertRaises(ValueError):self.preview()

    def test_exported_boards_and_shapes_are_bounded(self):
        self.assertEqual(len(CATALOG['shapes']),12)
        for entry in CATALOG['characters'].values():
            self.assertEqual(len(set(map(tuple,entry['cells']))),20)
            self.assertTrue(all(1<=v<=5 for p in entry['cells'] for v in p))

    def test_long_drive_uses_native_pivot_not_visual_top_left(self):
        self.empty();self.world.characters[0]['character_id']=1051
        self.world.rows[0].update(geometry='Shu4',grid=4)
        self.inspect()
        preview=self.service.preview_assembly('装配测试',self.info['selection_id'],1051,'none',
            [{'id':self.ids['#1'],'row':2,'column':2}],'manual')
        self.assertEqual(preview['layout']['pieces'][0]['row'],2)
        self.assertEqual(self.execute(preview)['state'],'verified')
        self.assertEqual(self.world.calls[0][1]['row'],3)
        self.assertEqual(self.world.rows[0]['equipped_placement'],{'row':3,'column':2})
        info=self.service.inspect()
        self.assertEqual(info['items'][0]['placement'],{'row':2,'column':2})

    def test_original_native_four_piece_fixture_has_no_overlap(self):
        used=set()
        for geometry,grid,position in [('Hen2',2,{'row':5,'column':2}),('ZhiJiao1',3,{'row':4,'column':4}),
                ('ZhiJiao3',3,{'row':1,'column':3}),('Shu4',4,{'row':2,'column':2})]:
            item={'geometry':geometry,'grid':grid}
            visual=visual_position(item,position)
            self.assertEqual(native_position(item,visual),position)
            cells=occupied(item,visual)
            self.assertTrue(cells.issubset(board(1051)));self.assertFalse(cells&used);used|=cells
        self.assertEqual(len(used),12)

    def test_all_shape_origins_roundtrip_and_physical_cells(self):
        for geometry,cells in CATALOG['shapes'].items():
            item={'geometry':geometry,'grid':len(cells)}
            visual={'row':1,'column':1};native=native_position(item,visual)
            self.assertEqual(visual_position(item,native),visual)
            dr,dc=CATALOG['origins'][geometry]
            raw={(native['row']+r+dr,native['column']+c+dc) for r,c in cells}
            self.assertEqual(raw,occupied(item,visual))


if __name__=='__main__':unittest.main(verbosity=2)
