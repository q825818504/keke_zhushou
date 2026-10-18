"""Isolated browser fixture for unequip controls. No game connection is possible."""
from pathlib import Path
import json
import secrets
import shutil

from native_equipment_fixture import World
from runtime import public_server
from vision.service import VisionService

root = Path(__file__).resolve().parents[1]
temporary_root = root / 'build/test-native-equipment-browser'
directory = temporary_root / secrets.token_hex(10)
if not directory.resolve().is_relative_to(temporary_root.resolve()): raise ValueError('Invalid fixture path')
directory.mkdir(parents=True)
world = World()
world.rows[1]['names']['zh_cn'] = '<script>fixture</script>'
inventory = world.service(directory)
vision = VisionService(directory / 'vision')
inventory.vision = vision
base_status = inventory.status
inventory.status = lambda: {**base_status(), 'fixture_dispatch_count': len(world.calls)}
server = public_server(root / 'build/desktop/public', 0, inventory=inventory, vision=vision)
print(json.dumps({'port': server.server_port}), flush=True)
try: server.serve_forever()
finally:
    server.server_close()
    inventory.close()
    shutil.rmtree(directory)
