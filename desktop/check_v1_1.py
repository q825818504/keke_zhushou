"""Regression checks for Tcl isolation, installer ownership and diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
import diagnostics
import installer_entry as installer
import update_client
from update_protocol import atomic_json

class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build')
        self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_startup_tk_is_in_child_and_custom_update_root_passed(self):
        data=self.root/'data';data.mkdir()
        exe=self.root/'custom 中文 path/app/1.0/KekeAssistantApp.exe';exe.parent.mkdir(parents=True)
        bundle=self.root/'bundle';bundle.mkdir();(bundle/'update-helper.exe').write_bytes(b'x')
        def child(command,**kwargs):
            self.assertIn('--startup-check',command)
            atomic_json(command[-1],{'update':{'version':'1.1'}})
            return Mock(returncode=0)
        with patch.object(sys,'executable',str(exe)),patch.object(sys,'_MEIPASS',str(bundle),create=True),patch.object(sys,'frozen',True,create=True),patch('update_client.subprocess.run',side_effect=child),patch('update_client.subprocess.Popen') as launch,patch.object(update_client,'check_window',side_effect=AssertionError('Tk in parent')):
            self.assertIsNone(update_client.gate({},self.root,data))
            command=launch.call_args.args[0]
            self.assertEqual(command[command.index('--install-root')+1],str(exe.parents[2]))
        self.assertFalse(list(data.glob('startup-*.json')))
    def test_cancelled_or_failed_startup_does_not_open_ui(self):
        with patch('update_client.subprocess.run',return_value=Mock(returncode=0)):
            self.assertIsNone(update_client.gate({},self.root,self.root))
        with patch('update_client.subprocess.run',return_value=Mock(returncode=9)):
            with self.assertRaisesRegex(RuntimeError,'异常退出'):update_client.gate({},self.root,self.root)
    def test_custom_directory_ownership_and_launch(self):
        root=self.root/'中文 路径/KekeAssistant'
        self.assertEqual(installer.validate_destination(root),root.resolve())
        root.mkdir(parents=True);(root/'KekeAssistant.exe').write_bytes(b'launcher')
        atomic_json(root/'installation.json',{'product':'koko-assistant','root':str(root.resolve())})
        atomic_json(root/'active-version.json',{'directory':'app/1.1','version':'1.1'})
        self.assertTrue(installer.recognized_install(root))
        self.assertEqual(installer.validate_destination(root),root.resolve())
        with patch('installer_entry.subprocess.Popen') as launch:
            installer.launch(root)
            self.assertEqual(launch.call_args.args[0],[str(root/'app/1.1/KekeAssistantApp.exe')])
        atomic_json(root/'active-version.json',{'directory':'../../unrelated','version':'1.1'})
        with self.assertRaises(ValueError):installer.launch(root)
    def test_existing_unrelated_directory_refused(self):
        (self.root/'unrelated.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError,'其他文件'):installer.validate_destination(self.root)
        with self.assertRaises(ValueError):installer.validate_destination(Path(self.root.anchor))
        with self.assertRaises(ValueError):installer.validate_destination('relative/path')
        self.assertTrue((self.root/'unrelated.txt').exists())
    def test_diagnostics_redact_and_exclude_personal_data(self):
        logs=self.root/'logs';logs.mkdir()
        (logs/'user.log').write_text('access_token=not-real-token UID=219001221086 C:/Users/Alime/private\n',encoding='utf-8')
        (logs/'inventory.json').write_text('private inventory')
        with patch.object(diagnostics,'ROOT',logs),patch.object(diagnostics,'refresh_windows_events'):
            exported=diagnostics.export()
        import zipfile
        with zipfile.ZipFile(exported) as archive:
            self.assertNotIn('inventory.json',archive.namelist())
            text=archive.read('user.log').decode()
            for secret in ('not-real-token','219001221086','Alime'):self.assertNotIn(secret,text)
    def test_windows_crash_parser_real_event_properties(self):
        rows=[{'time':'test','application':'KekeAssistantApp.exe','module':'tcl86t.dll','code':'80000003'}]
        xml='<Events xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><Event><System><TimeCreated SystemTime="test"/></System><EventData><Data Name="AppName">KekeAssistantApp.exe</Data><Data Name="ModuleName">tcl86t.dll</Data><Data Name="ExceptionCode">80000003</Data></EventData></Event></Events>'
        with patch('diagnostics.subprocess.run',return_value=Mock(returncode=0,stdout=xml.encode('utf-16'))):
            self.assertEqual(diagnostics.refresh_windows_events(),rows)
        legacy='<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event"><System><TimeCreated SystemTime="test"/></System><EventData>'+''.join('<Data>'+v+'</Data>' for v in ['KekeAssistantApp.exe','0','0','tcl86t.dll','0','0','80000003'])+'</EventData></Event>'
        with patch('diagnostics.subprocess.run',return_value=Mock(returncode=0,stdout=legacy.encode('utf-16'))):
            self.assertEqual(diagnostics.refresh_windows_events(),rows)
    def test_fresh_release_requires_upgrade_notes(self):
        from build_release import prepare
        atomic_json(self.root/'desktop/release-state.json',{'last_published':'1.0','config_revision':2})
        with self.assertRaisesRegex(ValueError,'升级内容'):prepare(self.root)

    def test_actual_wizard_waits_for_location_and_honors_finish_choices(self):
        import tkinter as tk
        from tkinter import ttk
        import installer_wizard
        original=tk.Tk.mainloop;errors=[];calls=[]
        def widgets(root):
            for child in root.winfo_children():
                yield child;yield from widgets(child)
        def mainloop(window,*args):
            def first():
                try:
                    self.assertEqual(calls,[])
                    next(w for w in widgets(window) if isinstance(w,ttk.Button) and w.cget('text')=='开始安装').invoke()
                except Exception as error:errors.append(error);window.destroy()
            def finish():
                try:
                    checks=[w for w in widgets(window) if isinstance(w,ttk.Checkbutton)]
                    self.assertEqual(len(checks),2)
                    for check in checks:check.invoke()
                    next(w for w in widgets(window) if isinstance(w,ttk.Button) and w.cget('text')=='完成').invoke()
                except Exception as error:errors.append(error);window.destroy()
            window.after(200,first);window.after(1000,finish);window.after(5000,window.destroy)
            original(window,*args)
        def fake_install(root,key,progress):calls.append(root);progress('测试安装完成');return root
        with patch.object(tk.Tk,'mainloop',mainloop),patch.object(installer,'launch') as launch,patch.object(installer,'shortcut') as shortcut:
            installer_wizard.wizard(self.root/'KekeAssistant','test-key',fake_install)
            launch.assert_not_called();shortcut.assert_not_called()
        self.assertEqual(len(calls),1)
        if errors:raise errors[0]

if __name__=='__main__':unittest.main(verbosity=2)
