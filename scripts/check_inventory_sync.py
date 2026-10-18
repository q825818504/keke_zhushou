"""Protocol and local service regressions; no game or capture binary is executed."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import subprocess
from unittest.mock import patch
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from inventory.core import Core
from inventory.snapshot import read_snapshot, DOMAINS
from inventory.service import InventoryService, Cancelled
from inventory.adapters.nte import NteAdapter, merge_profiles, normalize_snapshot
from inventory.adapters import Observation
from inventory.contract import migrate_document, validate_domain
from inventory.catalog import display_names
import sqlite3
from contextlib import closing
from runtime import public_server

class FakeCore:
    def __init__(self,*args, fail=None, mutate=None):
        self.hello = {'protocol_version':1,'capabilities':sorted({c for _,_,cs in DOMAINS.values() for c in cs})}
        self.fail = fail
        self.mutate = mutate
        self.current = None
        self.closed = False
        self.calls = []

    def call(self, method, params, check=lambda:None, timeout=15):
        check(); self.calls.append((method,params))
        if method.endswith('disable'):
            return {}
        if method.endswith('status'):
            result = {'providerId':'p','domains':[{'domain':self.current['domain'],'domainKey':'d','revision':'1','ready':True,'dirty':False}]}
            if self.mutate == 'revision': result['domains'][0]['revision']='2'
            return result
        if method.endswith('refresh'):
            domain = params['domain']
            self.kind = 'items' if params.get('scope') else next(k for k,v in DOMAINS.items() if v[0]==domain)
            if self.kind==self.fail: raise ValueError('fixture unavailable')
            rows = ([{'uid':{'slot':1,'serial':i+1},'item_id':100,'kind':'module' if i<30 else 'core','equipped':i<12,'sub_stats':{'atk':3}} for i in range(65)] if self.kind=='equipment'
                else [{'character_id':1003,'character_level':60,'skill_levels':{'skill-a':3}}] if self.kind=='characters'
                else [{'HTItem':{'ItemID':42,'Amount':5}}] if self.kind=='items' else [{'observed':True}])
            self.rows = rows
            self.current = {'providerId':'p','domain':domain,'snapshotId':'s','generation':'1','domainKey':'d','observedUnixUs':'1','observedMonotonicMs':'1',
                'enabled':True,'ready':True,'state':'ready','recordCount':len(rows),'sourceRecordCount':len(rows),'enumerationComplete':True,
                'complete':False,'sourceCoverage':'unknown','changeCoverage':'unknown','missing':[],'failed':False,'truncated':False,'revision':'1','dirty':False}
            if self.kind=='equipment': self.current.update(collectionComplete=True,collectionScope='EQUIP',characterRefsComplete=True)
            if self.kind=='items': self.current.update(collectionComplete=True,collectionScope='all_observed_InventoryContainerMap_containers')
            return copy.deepcopy(self.current)
        offset = params['offset']; end=min(offset+64,len(self.rows))
        field = DOMAINS[self.kind][1]
        value = {**self.current,field:copy.deepcopy(self.rows[offset:end]),'nextOffset':end if end<len(self.rows) else None}
        if self.kind=='equipment': value.update(projectionComplete=True,characters=[{'character_id':1003}],referencedItemUids=[],statProvenance='fixture')
        if self.mutate=='identity' and offset: value['snapshotId']='different'
        if self.mutate=='count': value[field].pop()
        if self.mutate=='bool_uid' and self.kind=='equipment': value[field][0]['uid']['slot']=True
        if self.mutate=='duplicate' and offset: value[field][0]['uid']={'slot':1,'serial':1}
        if self.mutate=='refs' and self.kind=='equipment': value['referencedItemUids']=[{'slot':9,'serial':9}]
        return value

    def close(self): self.closed=True

class InventoryTests(unittest.TestCase):
    def test_real_stdio_transport_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Path(tmp)/'rpc.py'
            fixture.write_text("import sys,json\nfor line in sys.stdin:\n r=json.loads(line)\n print(json.dumps({'jsonrpc':'2.0','method':'observation','params':{}}),flush=True)\n print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':{'protocol_version':1,'echo':r['params']}}),flush=True)\n",encoding='utf-8')
            popen=subprocess.Popen
            def launch(args,**kwargs):
                return popen([sys.executable,str(fixture)],**kwargs)
            with patch('inventory.core.subprocess.Popen',side_effect=launch):
                core=Core(Path(tmp)/'fixture-not-a-game-core',123)
                self.assertEqual(core.call('test.echo',{'value':7})['echo'],{'value':7})
                core.close()
                self.assertIsNotNone(core.process.poll())

    def test_optional_display_names_dont_modify_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            db=root/'data/game_static.sqlite3'
            with closing(sqlite3.connect(db)) as connection:
                connection.execute('CREATE TABLE character (character_id INTEGER,name_zh TEXT)')
                connection.execute('INSERT INTO character VALUES (1003,?)',('Example',))
                connection.commit()
            original=db.read_bytes()
            self.assertEqual(display_names(root,'characters',[{'character_id':1003}]),{'1003':'Example'})
            self.assertEqual(db.read_bytes(),original)

    def test_domains_pages_and_fields(self):
        for kind in DOMAINS:
            result=read_snapshot(FakeCore(),kind,lambda:None)
            self.assertTrue(result['rows']);self.assertTrue(result['pages'])
        self.assertEqual(len(read_snapshot(FakeCore(),'equipment',lambda:None)['rows']),65)
        self.assertEqual(read_snapshot(FakeCore(),'items',lambda:None)['rows'][0]['HTItem']['Amount'],5)

    def test_bad_pages_never_accepted(self):
        for failure in ('identity','count','bool_uid','duplicate','refs','revision'):
            with self.subTest(failure=failure),self.assertRaises(ValueError):
                read_snapshot(FakeCore(mutate=failure),'equipment',lambda:None)

    def test_missing_capability(self):
        core=FakeCore();core.hello['capabilities']=[]
        with self.assertRaises(ValueError):read_snapshot(core,'items',lambda:None)

    def test_sparse_profile_keeps_unknown_and_accepts_explicit_clear(self):
        first=[{'character_id':1003,'character_level':60,'fork_id':'old','selected_awaken_effect_ids':[1],'skill_levels':{'a':3,'b':4}}]
        next=[{'character_id':1003,'character_level':None,'fork_observed':False,'fork_id':None,'awakening_selection_initialized':False,'selected_awaken_effect_ids':[],'skill_levels':{'a':5}}]
        merged=merge_profiles(first,next,'t')[0]
        self.assertEqual(merged['character_level'],60);self.assertEqual(merged['fork_id'],'old');self.assertEqual(merged['selected_awaken_effect_ids'],[1]);self.assertEqual(merged['skill_levels'],{'a':5,'b':4})
        cleared=merge_profiles([merged],[{'character_id':1003,'fork_observed':True,'fork_id':None,'awakening_selection_initialized':True,'selected_awaken_effect_ids':[]}],'u')[0]
        self.assertEqual(cleared['selected_awaken_effect_ids'],[]);self.assertIsNone(cleared['fork_id'])

    def test_atomic_retention_and_account_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            account='uid:123456789012'
            service=InventoryService(tmp,uid_reader=lambda pid:'123456789012')
            adapter=NteAdapter(core_factory=lambda *args:FakeCore(fail='items'),pid_reader=lambda:123)
            adapter.root=Path(tmp); adapter.executable=Path('not-executed')
            before={'schema_version':1,'account':account,'account_uid':'123456789012','domains':{'items':{'rows':[{'old':7}]}}}
            service._write(service._path(account),before)
            service.job={'running':True,'domains':{}}
            service._run(adapter,'A')
            saved=service.load(account)
            self.assertEqual(saved['domains']['items'],before['domains']['items'])
            self.assertEqual(len(saved['domains']['equipment']['rows']),65)
            self.assertEqual(service.load('B')['domains'],{})
            self.assertFalse(service.status()['job']['running'])
            self.assertTrue(service._path(account).with_suffix('.previous.json').is_file())
            service.stop.set()
            with self.assertRaises(Cancelled):service.check()

    def test_native_read_without_uid_reader_saves_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter=NteAdapter(core_factory=lambda *args:FakeCore(),pid_reader=lambda:123)
            adapter.root=Path(tmp);adapter.executable=Path('not-executed')
            service=InventoryService(tmp);service.job={'running':True,'domains':{}}
            service._run(adapter,'旧标签')
            self.assertIn('UID',service.status()['job']['message'])
            self.assertEqual(list(Path(tmp).glob('account-*.json')),[])

    def test_v1_migration_is_read_only_and_maps_owned_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=read_snapshot(FakeCore(),'equipment',lambda:None)
            raw['rows'][0]['main_stats']=[{'property_id':'attack','value':3.5,'percent':True,'names':{'zh_cn':'攻击'}}]
            value={'schema_version':1,'account':'A','domains':{'equipment':raw}}
            service=InventoryService(tmp);service._write(service._path('A'),value)
            original=service._path('A').read_bytes()
            loaded=service.load('A'); records=loaded['inventory']['equipment']['records']
            self.assertEqual(loaded['schema_version'],2)
            self.assertEqual(sum(row['category']=='drive' for row in records),30)
            self.assertEqual(records[0]['main_attributes'][0],{'id':'attack','name':'攻击','value':3.5,'is_percent':True})
            self.assertIsNone(records[0]['is_locked'])
            self.assertEqual(loaded['domains'],value['domains'])
            self.assertEqual(service._path('A').read_bytes(),original)
            with self.assertRaises(ValueError):migrate_document({'schema_version':99})
            poisoned=copy.deepcopy(loaded['inventory']['equipment'])
            poisoned['records'][1]['instance_id']=poisoned['records'][0]['instance_id']
            with self.assertRaises(ValueError):validate_domain('equipment',poisoned)

    def test_alternative_adapter_needs_no_nte_fields_or_raw_snapshot(self):
        class OwnAdapter:
            adapter_id='fixture-independent'
            domains=('equipment','characters')
            closed=False
            def prepare(self,folder): pass
            def open(self,check): check()
            def read(self,kind,check,previous=None):
                check()
                if kind=='equipment':
                    rows=[{'instance_id':'our:1','category':'drive','is_equipped':True},
                          {'instance_id':'our:2','category':'tape','is_equipped':False}]
                else: rows=[{'character_id':'our-character','level':60}]
                return Observation({'contract_version':1,'source':{'adapter':self.adapter_id},
                    'coverage':{'collection_complete':True,'account_complete':None},'records':rows})
            def close(self):self.closed=True
        with tempfile.TemporaryDirectory() as tmp:
            adapter=OwnAdapter();service=InventoryService(tmp,adapter_factory=lambda name:adapter,uid_reader=lambda pid:'123456789012')
            service.start(tmp,'A');service.thread.join(timeout=3)
            self.assertFalse(service.status()['job']['running'])
            saved=service.load('uid:123456789012')
            self.assertEqual(saved['domains'],{})
            self.assertEqual([r['category'] for r in saved['inventory']['equipment']['records']],['drive','tape'])
            self.assertEqual(saved['inventory']['characters']['records'][0]['character_id'],'our-character')
            self.assertTrue(adapter.closed)
            self.assertEqual(service.load('B')['inventory'],{})

    def test_changed_game_session_stops_remaining_domains(self):
        with tempfile.TemporaryDirectory() as tmp:
            pids=iter([123,456]);adapter=NteAdapter(core_factory=FakeCore,pid_reader=lambda:next(pids))
            adapter.root=Path(tmp);adapter.executable=Path('not-executed')
            service=InventoryService(tmp,uid_reader=lambda pid:'123456789012');service.job={'running':True,'domains':{}}
            service._run(adapter,'A')
            self.assertEqual(service.load('A')['inventory'],{})
            self.assertIn('进程已变化',service.status()['job']['message'])
            self.assertNotIn('characters',service.status()['job']['domains'])

    def test_http_origin_token_and_no_admin_endpoints(self):
        root=Path(__file__).resolve().parents[1]/'build/desktop/public'
        with tempfile.TemporaryDirectory() as tmp:
            service=InventoryService(tmp)
            server=public_server(root,0,inventory=service)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                status=json.load(urlopen(base+'/inventory/status'))
                self.assertIn('token',status)
                for headers in ({},{'Origin':'http://evil.test','X-Keke-Inventory':status['token']},{'Origin':base,'X-Keke-Inventory':'wrong'}):
                    with self.assertRaises(HTTPError) as error:urlopen(Request(base+'/inventory/cancel',data=b'{}',headers={'Content-Type':'application/json',**headers}))
                    self.assertEqual(error.exception.code,403)
                result=json.load(urlopen(Request(base+'/inventory/cancel',data=b'{}',headers={'Content-Type':'application/json','Origin':base,'X-Keke-Inventory':status['token']})))
                self.assertFalse(result['job']['running'])
                for path in ('/api/git/status','/desktop/inventory/service.py','/../.git/config'):
                    with self.assertRaises(HTTPError):urlopen(base+path)
            finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main(verbosity=2)
