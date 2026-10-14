import json,tempfile,unittest
from pathlib import Path
from cloud_notes import refresh,cached,BASE
from release_lifecycle import release_status
from release_publish import initialize_notes
from update_protocol import atomic_json

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def reader(self,url):
        if url==BASE+'index.json':return json.dumps({'schema':1,'versions':['1.3','1.2']})
        return '云端改过的当前说明' if url.endswith('v1.3.md') else '旧版本说明'
    def test_cloud_edit_without_rebuild_and_current_history(self):
        self.assertTrue(refresh(self.root,'1.3',self.reader))
        atomic_json(self.root/'release-notes.json',{'version':'1.3','revision':2,'notes':'内置旧说明'})
        data=release_status(self.root,self.root)
        self.assertEqual(data['notes'],'云端改过的当前说明');self.assertEqual(len(data['history']),2)
        self.assertTrue(refresh(self.root,'1.3',lambda url:self.reader(url).replace('改过','再次改过')))
        self.assertIn('再次改过',release_status(self.root,self.root)['notes'])
    def test_offline_preserves_cache_and_falls_back(self):
        refresh(self.root,'1.3',self.reader);before=(self.root/'release-notes-cache.json').read_bytes()
        def error(_):raise OSError('offline')
        self.assertFalse(refresh(self.root,'1.3',error));self.assertEqual(before,(self.root/'release-notes-cache.json').read_bytes())
        self.assertEqual(cached(self.root,'1.3')[0]['notes'],'云端改过的当前说明')
        self.assertIsNone(cached(self.root,'1.4'))
    def test_bad_paths_and_oversize_never_replace_cache(self):
        refresh(self.root,'1.3',self.reader);before=(self.root/'release-notes-cache.json').read_bytes()
        self.assertFalse(refresh(self.root,'1.3',lambda _:json.dumps({'schema':1,'versions':['../../evil']})))
        self.assertFalse(refresh(self.root,'1.3',lambda url:self.reader(url) if url.endswith('index.json') else 'x'*65537))
        self.assertEqual(before,(self.root/'release-notes-cache.json').read_bytes())
    def test_publish_does_not_overwrite_cloud_edits(self):
        source=self.root/'desktop/releases/user';source.mkdir(parents=True);(source/'v1.3.md').write_text('本地说明',encoding='utf-8')
        store=self.root/'store';(store/'notes').mkdir(parents=True);(store/'notes/v1.3.md').write_text('云端编辑',encoding='utf-8')
        initialize_notes(store,self.root)
        self.assertEqual((store/'notes/v1.3.md').read_text(encoding='utf-8'),'云端编辑')

if __name__=='__main__':unittest.main()
