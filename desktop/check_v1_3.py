import tempfile,json
from pathlib import Path
from unittest.mock import patch,Mock
import unittest
import install_space
import installer_entry

class SpaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build');self.root=Path(self.tmp.name)
        self.manifest={'kind':'app','platform':'windows-x64','version':'1.3','package':{'size':200*1024**2,'expanded_size':360*1024**2}}
    def tearDown(self):self.tmp.cleanup()
    def test_budget_not_fixed_two_gigabytes(self):
        with patch('install_space.shutil.disk_usage',return_value=Mock(free=700*1024**2)):
            result=install_space.inspect(self.root,self.manifest,present=lambda _:True)
        self.assertTrue(result['ok']);self.assertEqual(result['volumes'][0]['required'],656*1024**2)
    def test_insufficient_blocks_before_any_download(self):
        with patch('installer_entry.fetch_envelope',return_value=self.manifest),patch('prerequisites.present',return_value=True),patch('install_space.shutil.disk_usage',return_value=Mock(free=500*1024**2)),patch('installer_entry.download_package') as download,patch('prerequisites.ensure') as ensure:
            with self.assertRaisesRegex(ValueError,'空间不足'):installer_entry.install(self.root,'key',lambda _:None)
        download.assert_not_called();ensure.assert_not_called()
    def test_future_nonexistent_folder_uses_parent_volume(self):
        with patch('install_space.shutil.disk_usage',return_value=Mock(free=2*1024**3)) as disk:
            result=install_space.inspect(self.root/'nested/KekeAssistant',self.manifest,present=lambda _:True)
        self.assertTrue(result['ok']);disk.assert_called_once_with(str(self.root.resolve()))
    def test_runtime_requirements_merge_on_same_volume(self):
        self.manifest['prerequisites']={'webview2':{'size':220*1024**2},'vcredist':{'size':20*1024**2}}
        with patch.dict('os.environ',{'SystemRoot':str(self.root)}),patch('install_space.tempfile.gettempdir',return_value=str(self.root)),patch('install_space.shutil.disk_usage',return_value=Mock(free=4*1024**3)):
            result=install_space.inspect(self.root,self.manifest,present=lambda _:False)
        self.assertEqual(len(result['volumes']),1)
        self.assertEqual(result['volumes'][0]['required'],(656+768+64+220)*1024**2)
    def test_legacy_manifest_uses_explicit_estimate(self):
        del self.manifest['package']['expanded_size']
        with patch('install_space.shutil.disk_usage',return_value=Mock(free=4*1024**3)):
            result=install_space.inspect(self.root,self.manifest,present=lambda _:True)
        self.assertTrue(result['estimated']);self.assertEqual(result['expanded'],800*1024**2)
    def test_malformed_size_rejected(self):
        for value in (-1,False,'360',4*1024**3):
            self.manifest['package']['expanded_size']=value
            with self.assertRaises(ValueError):install_space.inspect(self.root,self.manifest,present=lambda _:True)

    def test_wizard_disables_install_until_enough_space(self):
        import tkinter as tk
        from tkinter import ttk
        import installer_wizard
        original=tk.Tk.mainloop;errors=[];calls=[];free=[100*1024**2]
        def widgets(window):
            for child in window.winfo_children():
                yield child;yield from widgets(child)
        def mainloop(window,*args):
            def check():
                try:
                    button=next(w for w in widgets(window) if isinstance(w,ttk.Button) and w.cget('text')=='开始安装')
                    self.assertTrue(button.instate(['disabled']));self.assertTrue(any('空间不足' in str(w.cget('text')) for w in widgets(window) if isinstance(w,ttk.Label)))
                    button.invoke();self.assertEqual(calls,[])
                    free[0]=2*1024**3
                    entry=next(w for w in widgets(window) if isinstance(w,ttk.Entry));entry.insert('end','-other')
                    self.assertFalse(button.instate(['disabled']))
                except Exception as error:errors.append(error)
                finally:window.destroy()
            window.after(500,check);original(window,*args)
        with patch.object(tk.Tk,'mainloop',mainloop),patch('prerequisites.present',return_value=True),patch('install_space.shutil.disk_usage',side_effect=lambda _:Mock(free=free[0])):
            installer_wizard.wizard(self.root/'KekeAssistant','key',lambda *args:calls.append(args),lambda _:self.manifest)
        if errors:raise errors[0]

if __name__=='__main__':unittest.main()
