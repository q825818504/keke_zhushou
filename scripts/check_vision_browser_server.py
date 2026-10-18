import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from vision.service import VisionService
from inventory.service import InventoryService
from runtime import public_server
from check_vision import Engine,image_payload
with tempfile.TemporaryDirectory() as tmp:
    import base64
    Path('build/vision-upload-fixture.png').write_bytes(base64.b64decode(image_payload()['data']))
    service=VisionService(tmp,engine_factory=Engine)
    inventory=InventoryService(Path(tmp)/'inventory',vision=service)
    profile=inventory.accounts.resolve_uid('123456789012')
    inventory.select_account(profile['account'])
    inventory.config['account']=profile['account']
    empty_profile=inventory.accounts.resolve_uid('987654321098')
    inventory.set_account_note(empty_profile['account'],'测试小号')
    service.start('offline',profile['account'],files=[image_payload(),image_payload()],account_uid='123456789012');service.thread.join()
    server=public_server(Path('build/desktop/public'),0,vision=service,inventory=inventory)
    print(json.dumps({'port':server.server_port}),flush=True)
    try:server.serve_forever()
    finally:server.server_close();service.close()
