import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from update_protocol import atomic_json
from update_client import startup_check
from release_lifecycle import release_status,acknowledge

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_history_and_acknowledgement_revision(self):
        atomic_json(self.root/'release-notes.json',{'version':'1.3','revision':1,'notes':'当前'})
        atomic_json(self.root/'release-history.json',[{'version':'1.3','notes':'当前'},{'version':'1.2','notes':'过去'}])
        atomic_json(self.root/'release-seen.json',{'version':'1.3'})
        data=release_status(self.root,self.root)
        self.assertTrue(data['show']);self.assertEqual(data['notes'],'当前');self.assertEqual(len(data['history']),2)
        acknowledge(self.root,self.root);self.assertFalse(release_status(self.root,self.root)['show'])
    def test_same_version_new_revision_requires_update(self):
        fetch=lambda *_:{'kind':'app','platform':'windows-x64','version':'1.3','revision':1}
        self.assertIn('update',startup_check('1.3',self.root,'key',self.root,lambda _:None,fetch,current_revision=0))
        with patch('update_client.refresh_config',return_value=(self.root,None)):
            self.assertIn('config',startup_check('1.3',self.root,'key',self.root,lambda _:None,fetch,current_revision=1))
        with self.assertRaisesRegex(ValueError,'修订'):
            startup_check('1.3',self.root,'key',self.root,lambda _:None,lambda *_:{'kind':'app','platform':'windows-x64','version':'1.3','revision':0})
    def test_invalid_revision_rejected(self):
        for value in (-1,True,'1'):
            with self.assertRaises(ValueError):startup_check('1.3',self.root,'key',self.root,lambda _:None,lambda *_:{'kind':'app','platform':'windows-x64','version':'1.3','revision':value})

if __name__=='__main__':unittest.main()
