"""Offline failure-path acceptance for release/install protocols."""
import base64
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import update_protocol as protocol
from update_client import startup_check, refresh_config
from release_publish import signed, audit_files
from release_publish import configure, API
import requests
from build_release import candidate_version
from public_config import export_config, validated_config
import installer_entry


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build')
        self.root=Path(self.temporary.name)
        self.config=self.root/'bundled'
        protocol.atomic_json(self.config/'config.json',{'schema':1,'bindings':{name:({'role':{}} if name=='characterKnowledge' else {}) for name in protocol.BINDINGS},'assets':{}})
    def tearDown(self): self.temporary.cleanup()
    def test_signature_and_tampering(self):
        key=Ed25519PrivateKey.generate(); public=base64.b64encode(key.public_key().public_bytes_raw()).decode()
        envelope=signed({'schema':1,'product':protocol.PRODUCT,'version':'1.0'},key)
        self.assertEqual(protocol.verify_envelope(envelope,public)['version'],'1.0')
        envelope['payload']=base64.b64encode(b'{}').decode()
        with self.assertRaises(Exception): protocol.verify_envelope(envelope,public)
    def test_numeric_version_and_failed_release_not_incremented(self):
        self.assertGreater(protocol.version('1.10'),protocol.version('1.9'))
        state={'last_published':None}
        self.assertEqual(candidate_version(state),candidate_version(state))
        self.assertEqual(candidate_version({'last_published':'1.9'}),'1.10')
    def test_version_unavailable_blocks_before_configuration(self):
        calls=[]
        def offline(url,key): calls.append(url); raise OSError('offline')
        with self.assertRaises(OSError): startup_check('1.0',self.root/'profile','key',self.config,lambda _:None,offline)
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0].endswith('app-latest.json'))
    def test_config_failure_uses_bundled_then_cache(self):
        def fetch(url,key):
            if url.endswith('app-latest.json'): return {'kind':'app','platform':'windows-x64','version':'1.0'}
            raise OSError('offline')
        data=self.root/'profile'
        result=startup_check('1.0',data,'key',self.config,lambda _:None,fetch)
        self.assertEqual(result['config'],self.config)
        self.assertTrue(result['warning'])
        cached=data/'public-config/r1-good'; cached.mkdir(parents=True)
        (cached/'config.json').write_bytes((self.config/'config.json').read_bytes())
        protocol.atomic_json(data/'public-config/current.json',{'directory':'r1-good','revision':1})
        result=startup_check('1.0',data,'key',self.config,lambda _:None,fetch)
        self.assertEqual(result['config'],cached)
    def test_mandatory_update_and_replay_rejection(self):
        def fetch(url,key): return {'kind':'app','platform':'windows-x64','version':'1.1'}
        result=startup_check('1.0',self.root/'profile','key',self.config,lambda _:None,fetch)
        self.assertIn('update',result)
        with self.assertRaises(ValueError):
            startup_check('1.0',self.root/'profile','key',self.config,lambda _:None,lambda *_:{'kind':'app','platform':'windows-x64','version':'1.0'})
    def test_zip_unsafe_paths_and_source_in_config(self):
        for i,name in enumerate(('../escape','/absolute','data/./x','data//x','data/NUL.txt','data/x.exe','data/x.py','data/a\\b.json')):
            archive=self.root/f'{i}.zip'
            info=zipfile.ZipInfo(name); info.filename=name
            with zipfile.ZipFile(archive,'w') as z:z.writestr(info,b'bad')
            with self.subTest(name=name),self.assertRaises(ValueError):protocol.safe_extract(archive,self.root/f'extract{i}',True)
        archive=self.root/'link.zip'
        info=zipfile.ZipInfo('data/link.json'); info.create_system=3; info.external_attr=(stat.S_IFLNK|0o777)<<16
        with zipfile.ZipFile(archive,'w') as z:z.writestr(info,'../escape')
        with self.assertRaises(ValueError):protocol.safe_extract(archive,self.root/'link',True)
        archive=self.root/'duplicate.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('data/A.json','{}');z.writestr('data/a.json','{}')
        with self.assertRaises(ValueError):protocol.safe_extract(archive,self.root/'duplicate',True)
    def test_corrupt_download_preserves_existing_file(self):
        target=self.root/'download.zip';target.write_bytes(b'old-valid')
        data=b'new-valid'; checksum=hashlib.sha256(data).hexdigest()
        description={'size':len(data),'sha256':checksum,'parts':[{'size':len(data),'sha256':checksum,'url':'https://gitee.com/example'}]}
        with patch.object(protocol,'open_url',return_value=io.BytesIO(b'damaged')):
            with self.assertRaises(ValueError):protocol.download_package(description,target)
        self.assertEqual(target.read_bytes(),b'old-valid')
        self.assertFalse(target.with_suffix('.partial').exists())
        with patch.object(protocol,'open_url',return_value=io.BytesIO(data)):protocol.download_package(description,target)
        self.assertEqual(target.read_bytes(),data)
    def test_invalid_config_hash_cannot_escape_cache(self):
        data=self.root/'profile'
        result=refresh_config(data,'key',self.config,lambda _:None,lambda *_:{'kind':'config','config_schema':1,'revision':1,'package':{'sha256':'../../evil'}})
        self.assertEqual(result[0],self.config)
        self.assertFalse((self.root/'evil').exists())
    def test_export_matches_bindings_and_images(self):
        document=export_config(Path(__file__).resolve().parents[1],self.root/'export')
        self.assertEqual(set(document['bindings']),protocol.BINDINGS)
        self.assertGreater(len(document['assets']),100)
        validated_config(self.root/'export')
        self.assertFalse(any(p.suffix in {'.js','.py','.exe'} for p in (self.root/'export').rglob('*')))
    def test_release_whitelist_rejects_source_and_path_escape(self):
        source=self.root/'app.py';source.write_text('source')
        package={'parts':[{'name':'app.py','size':source.stat().st_size,'sha256':protocol.digest(source)}]}
        with self.assertRaises(ValueError):audit_files(self.root,{'config_package':package})
    def test_download_host_restrictions(self):
        for url in ('http://gitee.com/a','https://evil.example/a','https://gitee.com.evil.example/a','https://user:password@gitee.com/a'):
            with self.assertRaises(ValueError):protocol.checked_url(url)
    def test_failed_install_preserves_active_version(self):
        root=self.root/'install'
        protocol.atomic_json(root/'active-version.json',{'directory':'app/1.0','version':'1.0'})
        with patch.object(installer_entry,'fetch_envelope',return_value={'kind':'app','platform':'windows-x64','version':'1.1','package':{}}),patch('prerequisites.ensure'),patch.object(installer_entry,'download_package',side_effect=ValueError('corrupt package')):
            with self.assertRaises(ValueError):installer_entry.install(root,'key',lambda _:None)
        self.assertEqual(json.loads((root/'active-version.json').read_text())['version'],'1.0')
    def test_gitee_owner_without_permissions_can_save(self):
        repo={'full_name':protocol.REPOSITORY}
        def response(value,status=200):
            from unittest.mock import Mock
            return Mock(status_code=status,json=lambda:value)
        with patch('release_publish.requests.get',side_effect=[response(repo),response([repo])]) as get,patch('release_publish.read_secrets',return_value={'private_key':'test-existing'}),patch('release_publish.save_secrets') as save:
            self.assertTrue(configure('test-token-not-a-real-secret')['configured'])
            self.assertEqual(save.call_args.args[0]['private_key'],'test-existing')
            self.assertEqual(get.call_args.kwargs['params']['type'],'owner')
    def test_gitee_invalid_token_and_wrong_owner_not_saved(self):
        from unittest.mock import Mock
        for responses,expected in (([Mock(status_code=401)],'无效'),([Mock(status_code=200,json=lambda:{'full_name':protocol.REPOSITORY}),Mock(status_code=200,json=lambda:[])],'所有者')):
            with patch('release_publish.requests.get',side_effect=responses),patch('release_publish.save_secrets') as save:
                with self.assertRaisesRegex(RuntimeError,expected):configure('test-token-not-a-real-secret')
                save.assert_not_called()
    def test_gitee_network_error_has_clear_message_and_does_not_save(self):
        with patch('release_publish.requests.get',side_effect=requests.Timeout('test timeout')),patch('release_publish.save_secrets') as save:
            with self.assertRaisesRegex(RuntimeError,'连接Gitee失败'):configure('test-token-not-a-real-secret')
            save.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
