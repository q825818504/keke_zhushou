"""Ephemeral inventory UI fixture server, never uses real player data."""
from pathlib import Path
import json
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from runtime import public_server
from inventory.service import InventoryService
from native.components import ComponentManager
from vision.service import VisionService
from inventory.snapshot import read_snapshot, DOMAINS
from check_inventory_sync import FakeCore

with tempfile.TemporaryDirectory() as tmp:
    vision=VisionService(Path(tmp)/'vision')
    game=Path(tmp)/'fixture-game';game.mkdir();(game/'HTGame.exe').write_bytes(b'fixture-not-executable')
    components=ComponentManager(Path(tmp)/'components',process_reader=lambda:[])
    components.inspect(str(game))
    class UnavailableAdapter:
        def prepare(self,folder):raise ValueError('测试环境不运行原生采集')
    service=InventoryService(Path(tmp)/'inventory',adapter_factory=lambda _:UnavailableAdapter(),components=components,vision=vision)
    for account in ('默认账号','OCR账号'):
        for batch_id,complete,count,mode in [('1'*24,True,2,'mouse'),('2'*24,False,1,'new')]:
            records=[{'instance_id':'scan-local-'+str(i),'image':str(i)+'.png','category':'drive' if i==0 else 'tape','name':'OCR装备','is_equipped':None} for i in range(count)]
            vision._write(vision._base(account,batch_id)/'batch.json',{'schema_version':1,'id':batch_id,'account':account,'mode':mode,'complete':complete,'capture_complete':complete,'state':'parsed',
                'saved_at':'2026-10-08T10:00:00+00:00','processed':count,'images':[],'records':records})
    value={'schema_version':1,'account':'默认账号','domains':{}}
    for kind in DOMAINS:
        data=read_snapshot(FakeCore(),kind,lambda:None)
        data['saved_at']='2026-10-07T10:00:00+00:00'
        value['domains'][kind]=data
    value['domains']['equipment']['rows'][0]['name']='<script>bad</script>'
    service._write(service._path('默认账号'),value)
    own={'contract_version':1,'source':{'adapter':'independent-fixture'},'coverage':{'collection_complete':True,'account_complete':None},'saved_at':'2026-10-07T10:00:00+00:00'}
    service._write(service._path('自主格式测试'),{'schema_version':2,'account':'自主格式测试','domains':{},'inventory':{
        'equipment':{**own,'records':[{'instance_id':'own-drive','category':'drive','is_equipped':True,'name':'自有驱动'}, {'instance_id':'own-tape','category':'tape','is_equipped':False}]},
        'characters':{**own,'records':[{'character_id':'own-character'}]}}})
    server=public_server(Path(__file__).resolve().parents[1]/'build/desktop/public',0,inventory=service,vision=vision)
    print(json.dumps({'port':server.server_port}),flush=True)
    try: server.serve_forever()
    finally: server.server_close()
