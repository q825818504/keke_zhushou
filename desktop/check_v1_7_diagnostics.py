"""Focused regression checks for the V1.7 native-environment diagnostics."""
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

import diagnostics
from native.components import ComponentManager


class NativeDiagnosticsChecks(unittest.TestCase):
    def setUp(self):
        self.base = Path(__file__).resolve().parents[1]/'build'/'diagnostics-fixture'
        self.app_data = self.base/'app-data'
        self.bundle = self.base/'bundle'
        self.game = self.base/'game'
        files = {'d3d12.dll':b'host','plugins/NTE_PluginCombat.dll':b'capture'}
        expected = {}
        for name,content in files.items():
            expected[name] = hashlib.sha256(content).hexdigest()
        self.identity = {'layout':'test','core_version':'test','roles':{
            'host':'d3d12.dll','capture_plugin':'plugins/NTE_PluginCombat.dll'},
            'files':expected,'deployment':list(files)}
        self.processes = [{'pid':4321,'created':638974224000000000,'path':str(self.game/'HTGame.exe')}]
        self.events = []
        self.fake_files={str(self.game/'HTGame.exe').casefold()}
        for name in files:
            self.fake_files.add(str(self.bundle/name).casefold())
            self.fake_files.add(str(self.game/name).casefold())
        self.fake_directories={str(self.bundle).casefold(),str(self.game).casefold()}

    def inspect(self, manager):
        with patch.object(Path,'is_dir',autospec=True,side_effect=lambda path:str(path).casefold() in self.fake_directories), \
             patch.object(Path,'is_file',autospec=True,side_effect=lambda path:str(path).casefold() in self.fake_files), \
             patch('native.components.digest',side_effect=self.digest), \
             patch('native.components.atomic_json'), \
             patch.object(diagnostics,'event',side_effect=lambda name,**fields:self.events.append((name,fields))):
            return manager.inspect(str(self.game))

    def digest(self,path):
        name=str(path).casefold()
        for file,expected in self.identity['files'].items():
            if name.endswith(str(Path(file)).casefold()):return expected
        raise AssertionError('Unexpected file hash request: '+str(path))

    def manager(self, pipe_reader, module_reader=None):
        loaded = module_reader or (lambda pid:[
            {'name':'d3d12.dll','path':str(self.game/'d3d12.dll')},
            {'name':'NTE_PluginCombat.dll','path':str(self.game/'plugins/NTE_PluginCombat.dll')}])
        return ComponentManager(self.app_data,self.bundle,lambda:self.processes,self.identity,
            pipe_reader,loaded)

    def test_records_matching_endpoint_and_loaded_modules(self):
        pipe = f"nte.capture.v1.{self.processes[0]['pid']}.{self.processes[0]['created']}"
        result = self.inspect(self.manager(lambda:[pipe]))
        self.assertEqual(result['endpoint_scan_state'],'found')
        self.assertEqual(result['modules']['host_state'],'loaded')
        self.assertEqual(result['modules']['capture_state'],'loaded')
        self.assertTrue(result['game_path_matches_process'])
        self.assertTrue(all(row.get('observed_sha256')==row['expected_sha256'] for row in result['files']))
        self.assertEqual(self.events[-1][0],'原生环境检测')
        self.assertEqual(self.events[-1][1]['endpoint_enumeration']['state'],'ok')

    def test_distinguishes_pipe_enumeration_failure(self):
        def fail():
            raise OSError(5,'Access is denied')
        result = self.inspect(self.manager(fail))
        self.assertEqual(result['endpoint_scan_state'],'error')
        self.assertFalse(result['endpoint_present'])
        self.assertIn('无法枚举原生端点',result['issues'][0])
        self.assertEqual(self.events[-1][1]['endpoint_enumeration']['state'],'error')

    def test_rejects_stale_pid_reuse_pipe(self):
        stale = f"nte.capture.v1.{self.processes[0]['pid']}.1"
        result = self.inspect(self.manager(lambda:[stale]))
        self.assertEqual(result['endpoint_scan_state'],'not_found')
        self.assertFalse(result['endpoint_present'])
        self.assertFalse(result['endpoint_enumeration']['process_matches'][0]['start_time_match'])

    def test_reports_module_inspection_failure_without_claiming_not_loaded(self):
        def fail(pid):
            raise OSError(5,'Access is denied')
        result = self.inspect(self.manager(lambda:[],fail))
        self.assertEqual(result['modules']['scan_state'],'error')
        self.assertEqual(result['modules']['host_state'],'unknown')
        self.assertEqual(result['modules']['capture_state'],'unknown')
        self.assertEqual(result['endpoint_scan_state'],'not_found')


if __name__ == '__main__':
    unittest.main(verbosity=2)
