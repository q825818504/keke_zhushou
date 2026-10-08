"""Saved-source deletion and native replacement; only temporary fixtures."""
import json
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from inventory.service import InventoryService
from inventory.adapters.nte import NteAdapter
from vision.service import VisionService
from check_inventory_sync import FakeCore

class SavedDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.vision=VisionService(self.root/'vision')
        self.service=InventoryService(self.root/'inventory',vision=self.vision)
    def seed(self,account,id):
        base=self.vision._base(account,id);(base/'images').mkdir(parents=True)
        (base/'images'/'1.png').write_bytes(b'fixture')
        self.vision._write(base/'batch.json',{'id':id,'account':account,'mode':'mouse','records':[],'images':[],'processed':0})
        return base
    def test_ocr_deletion_keeps_other_batches_accounts_and_native(self):
        first=self.seed('A','1'*24);second=self.seed('A','2'*24);other=self.seed('B','1'*24)
        self.service._write(self.service._path('A'),{'schema_version':2,'account':'A','inventory':{},'domains':{}})
        native=self.service._path('A').read_bytes()
        self.vision.batch=self.vision.load('A','1'*24)
        self.service.delete('A','ocr:'+'1'*24)
        self.assertFalse(first.exists());self.assertTrue(second.exists());self.assertTrue(other.exists())
        self.assertEqual(native,self.service._path('A').read_bytes());self.assertIsNone(self.vision.batch)
        self.assertEqual(len(self.vision.history('A')),1)
    def test_native_delete_includes_backup_only_for_selected_account(self):
        for account in ('A','B'):
            self.service._write(self.service._path(account),{'schema_version':2,'account':account,'inventory':{},'domains':{}})
            self.service._path(account).with_suffix('.previous.json').write_text('{}')
        batch=self.seed('A','1'*24)
        self.service.delete('A','native')
        self.assertFalse(self.service._path('A').exists());self.assertFalse(self.service._path('A').with_suffix('.previous.json').exists())
        self.assertTrue(self.service._path('B').exists());self.assertTrue(batch.exists())
    def test_running_jobs_and_invalid_sources_are_rejected(self):
        base=self.seed('A','1'*24)
        self.vision.job['running']=True
        with self.assertRaises(ValueError):self.service.delete('A','ocr:'+'1'*24)
        self.vision.job['running']=False;self.service.job['running']=True
        with self.assertRaises(ValueError):self.service.delete('A','native')
        self.service.job['running']=False
        for source in ('auto','ocr:../../anything',None):
            with self.assertRaises(ValueError):self.service.delete('A',source)
        self.assertTrue(base.exists())
    def test_native_reread_replaces_same_label_keeps_ocr(self):
        batch=self.seed('A','1'*24)
        for marker in ('first','second'):
            class MarkedCore(FakeCore):
                def call(inner,method,params,check=lambda:None,timeout=15):
                    value=super().call(method,params,check,timeout)
                    if method.endswith('refresh') and inner.kind=='equipment':inner.rows[0]['name']=marker
                    return value
            adapter=NteAdapter(core_factory=lambda *args:MarkedCore(),pid_reader=lambda:123)
            adapter.root=self.root;adapter.executable=Path('not-executed')
            self.service.job={'running':True,'domains':{}}
            self.service._run(adapter,'A')
        self.assertEqual(self.service.load('A')['domains']['equipment']['rows'][0]['name'],'second')
        self.assertEqual(len(list((self.root/'inventory').glob('account-*.json'))),2)
        self.assertTrue(batch.exists());self.assertEqual(len(self.vision.history('A')),1)
        self.assertEqual(self.service.load('B')['inventory'],{})

if __name__=='__main__':unittest.main(verbosity=2)
