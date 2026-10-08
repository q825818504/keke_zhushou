"""Components are tested in fake game folders; never deploy into the user's game."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from native.components import ComponentManager
from inventory.service import InventoryService
from vision.service import VisionService
from runtime import public_server

class AccountSourcesTests(unittest.TestCase):
    def manager(self, root, running=lambda:[]):
        bundle=root/'bundle';bundle.mkdir()
        names=['nte-core.exe','d3d12.dll','plugins/NTE_PluginUser.dll','plugins/NTE_PluginUser.dll.sig']
        files={}
        for name in names:
            path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('fixture:'+name).encode())
            files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        identity={'files':files,'roles':{'core':'nte-core.exe'},'layout':'native-plugins-v3','core_version':'0.4.4','deployment':names[1:]}
        game=root/'game';game.mkdir();(game/'HTGame.exe').write_bytes(b'fixture never executed')
        return ComponentManager(root/'manager',bundle=bundle,process_reader=running,identity=identity),game

    def test_pinned_bundle_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp));self.assertTrue(manager.inspect(str(game))['bundle_ready'])
            (manager.bundle/'nte-core.exe').write_bytes(b'changed')
            with self.assertRaises(ValueError):manager.component_root()
            with self.assertRaises(ValueError):manager.deploy(str(game))
            self.assertFalse((game/'d3d12.dll').exists())

    def test_opt_in_deployment_and_remove_only_added_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp))
            (game/'d3d12.dll').write_bytes((manager.bundle/'d3d12.dll').read_bytes())
            self.assertFalse(manager.inspect(str(game))['deployment_ready'])
            self.assertTrue(manager.deploy(str(game))['deployment_ready'])
            manager.deploy(str(game));manager.remove(str(game))
            self.assertTrue((game/'d3d12.dll').exists())
            self.assertFalse((game/'plugins/NTE_PluginUser.dll').exists())
            self.assertTrue((game/'HTGame.exe').exists())

    def test_conflict_and_running_game_never_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp))
            (game/'d3d12.dll').write_bytes(b'other-mod')
            with self.assertRaises(ValueError):manager.deploy(str(game))
            self.assertEqual((game/'d3d12.dll').read_bytes(),b'other-mod')
            manager.process_reader=lambda:[{'pid':123}]
            with self.assertRaises(ValueError):manager.deploy(str(game))
            with self.assertRaises(ValueError):manager.remove(str(game))

    def test_failed_file_transaction_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp))
            import shutil
            original=shutil.copyfile
            def copy(source,target):
                if source.name=='NTE_PluginUser.dll':raise OSError('fixture failure')
                return original(source,target)
            with patch('native.components.shutil.copyfile',side_effect=copy):
                with self.assertRaises(OSError):manager.deploy(str(game))
            self.assertFalse((game/'d3d12.dll').exists())
            self.assertEqual(json.loads(manager._ledger(game).read_text())['created'],{})

    def test_remove_rejects_modified_managed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp));manager.deploy(str(game))
            target=game/'plugins/NTE_PluginUser.dll';target.write_bytes(b'updated-by-elsewhere')
            with self.assertRaises(ValueError):manager.remove(str(game))
            self.assertEqual(target.read_bytes(),b'updated-by-elsewhere')
            self.assertTrue((game/'d3d12.dll').exists())

    def batch(self, vision, account, batch_id, complete=False, mode='mouse', count=2):
        rows=[{'instance_id':'local-'+str(i),'category':'drive' if i%2==0 else 'tape','name':'fixture','image':str(i)+'.png','is_equipped':None} for i in range(count)]
        batch={'schema_version':1,'id':batch_id,'account':account,'mode':mode,'complete':complete,'capture_complete':complete,'state':'parsed' if complete else 'partial',
               'saved_at':'2026-10-08T10:00:00+00:00','processed':count,'expected':100,'images':[],'records':rows}
        vision._write(vision._base(account,batch_id)/'batch.json',batch)
        return batch

    def test_ocr_visible_without_native_data_and_account_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            vision=VisionService(Path(tmp)/'vision');service=InventoryService(Path(tmp)/'inventory',vision=vision)
            self.batch(vision,'A','1'*24)
            view=service.view('A');domain=view['inventory']['equipment']
            self.assertEqual(view['selected_source'],'ocr:'+'1'*24)
            self.assertFalse(domain['coverage']['collection_complete'])
            self.assertEqual(len(domain['records']),2)
            self.assertTrue(all(row['is_equipped'] is None for row in domain['records']))
            self.assertEqual(service.view('B')['sources'],[])
            with self.assertRaises(ValueError):service.view('B','ocr:'+'1'*24)
            self.assertEqual(service.load('A')['inventory'],{})

    def test_native_and_ocr_never_double_count_or_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);vision=VisionService(root/'vision');service=InventoryService(root/'inventory',vision=vision)
            native={'contract_version':1,'source':{'adapter':'nte-native-v1'},'coverage':{'collection_complete':True,'account_complete':None},'records':[{'instance_id':'native:1','category':'drive','is_equipped':True}]}
            service._write(service._path('A'),{'schema_version':2,'account':'A','domains':{},'inventory':{'equipment':native}})
            before=service._path('A').read_bytes();self.batch(vision,'A','2'*24,True)
            self.assertEqual(len(service.view('A')['inventory']['equipment']['records']),1)
            ocr=service.view('A','ocr:'+'2'*24)['inventory']['equipment']
            self.assertEqual(len(ocr['records']),2)
            self.assertTrue(ocr['coverage']['collection_complete'])
            self.assertIsNone(ocr['coverage']['account_complete'])
            self.assertEqual(service._path('A').read_bytes(),before)
            batch=vision.load('A','2'*24);batch['records'][0]['name']='corrected'
            vision._write(vision._base('A','2'*24)/'batch.json',batch)
            self.assertEqual(service.view('A','ocr:'+'2'*24)['inventory']['equipment']['records'][0]['name'],'corrected')

    def test_embedded_components_used_instead_of_legacy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp))
            class Adapter:
                adapter_id='fixture';domains=()
                def prepare(self,folder):self.folder=folder
                def open(self,check):check()
                def close(self):pass
            adapter=Adapter();service=InventoryService(Path(tmp)/'inventory',adapter_factory=lambda _:adapter,components=manager)
            service.config['folder']='does-not-exist'
            service.start(account='A');service.thread.join(2)
            self.assertEqual(adapter.folder,str(manager.bundle))
            self.assertNotIn('folder',service.status()['config'])

    def test_environment_http_requires_origin_and_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager,game=self.manager(Path(tmp));service=InventoryService(Path(tmp)/'inventory',components=manager)
            server=public_server(Path(__file__).resolve().parents[1]/'build/desktop/public',0,inventory=service)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                token=json.load(urlopen(base+'/inventory/status'))['token'];data=json.dumps({'game_directory':str(game)}).encode()
                with self.assertRaises(HTTPError) as caught:urlopen(Request(base+'/inventory/components/deploy',data=data,headers={'Content-Type':'application/json'}))
                self.assertEqual(caught.exception.code,403);self.assertFalse((game/'d3d12.dll').exists())
                headers={'Content-Type':'application/json','Origin':base,'X-Keke-Inventory':token}
                result=json.load(urlopen(Request(base+'/inventory/components/check',data=data,headers=headers)))
                self.assertTrue(result['bundle_ready']);self.assertFalse(result['deployment_ready'])
                result=json.load(urlopen(Request(base+'/inventory/components/deploy',data=data,headers=headers)))
                self.assertTrue(result['deployment_ready'])
                result=json.load(urlopen(Request(base+'/inventory/components/remove',data=data,headers=headers)))
                self.assertFalse(result['deployment_ready'])
            finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main(verbosity=2)
