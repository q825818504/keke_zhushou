"""Lifecycle regressions protect active releases, offline fallback and user data."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from update_protocol import atomic_json
from release_lifecycle import cleanup_versions,cleanup_config,release_status,acknowledge

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build')
        self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def release(self,name):
        path=self.root/'app'/name;(path/'_internal').mkdir(parents=True)
        (path/'KekeAssistantApp.exe').write_bytes(b'app')
        atomic_json(path/'_internal/release-info.json',{'version':name})
        return path
    def test_clean_old_after_success_only(self):
        old=self.release('1.0');current=self.release('1.2')
        (self.root/'KekeAssistant.exe').write_bytes(b'launcher')
        atomic_json(self.root/'installation.json',{'product':'koko-assistant','root':str(self.root)})
        atomic_json(self.root/'active-version.json',{'directory':'app/1.2'})
        unrelated=self.root/'app/custom';unrelated.mkdir();(unrelated/'keep').write_bytes(b'keep')
        user=self.root/'player-inventory';user.mkdir();(user/'keep.json').write_text('private')
        cleanup_versions(current/'KekeAssistantApp.exe',False);self.assertTrue(old.exists())
        cleanup_versions(old/'KekeAssistantApp.exe',True);self.assertTrue(old.exists())
        cleanup_versions(current/'KekeAssistantApp.exe',True)
        self.assertFalse(old.exists());self.assertTrue(current.exists());self.assertTrue(unrelated.exists());self.assertTrue((user/'keep.json').exists())
    def test_unowned_root_is_never_deleted(self):
        old=self.release('1.0');current=self.release('1.2')
        cleanup_versions(current/'KekeAssistantApp.exe',True);self.assertTrue(old.exists())
    def test_locked_old_release_kept_for_retry(self):
        old=self.release('1.0');current=self.release('1.2')
        (self.root/'KekeAssistant.exe').write_bytes(b'x')
        atomic_json(self.root/'installation.json',{'product':'koko-assistant','root':str(self.root)})
        atomic_json(self.root/'active-version.json',{'directory':'app/1.2'})
        with patch('release_lifecycle.shutil.rmtree',side_effect=PermissionError('locked')):
            cleanup_versions(current/'KekeAssistantApp.exe',True)
        self.assertTrue(old.exists());self.assertTrue(current.exists())
    def test_config_removes_old_but_not_unknown(self):
        old=self.root/('r2-'+'a'*16);old.mkdir()
        current=self.root/('r3-'+'b'*16);current.mkdir()
        archive=self.root/(current.name+'.zip');archive.write_bytes(b'zip')
        unrelated=self.root/'keep.json';unrelated.write_text('private')
        cleanup_config(self.root,current)
        self.assertFalse(old.exists());self.assertFalse(archive.exists());self.assertTrue(current.exists());self.assertTrue(unrelated.exists())
    def test_changelog_explicit_ack_and_new_version(self):
        public=self.root/'public';public.mkdir();data=self.root/'data';data.mkdir()
        atomic_json(public/'release-notes.json',{'version':'1.2','notes':'用户说明'})
        self.assertTrue(release_status(public,data)['show'])
        acknowledge(public,data);self.assertFalse(release_status(public,data)['show'])
        atomic_json(public/'release-notes.json',{'version':'1.3','notes':'下一版'})
        self.assertTrue(release_status(public,data)['show'])
    def test_no_changelog_no_popup(self):
        self.assertFalse(release_status(self.root,self.root)['show'])

if __name__=='__main__':unittest.main()
