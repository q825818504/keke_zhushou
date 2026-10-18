"""Browser fixture for role-build refresh after one-key auto equipment."""
from pathlib import Path
from copy import deepcopy
import json
import secrets
import shutil
import time

from native_equipment_fixture import World
from inventory.equipment_layout import board
from native_equipment_fixture import occupied
from runtime import public_server
from vision.service import VisionService


root = Path(__file__).resolve().parents[1]
temporary_root = root / 'build/test-role-build-refresh-browser'
directory = temporary_root / secrets.token_hex(10)
if not directory.resolve().is_relative_to(temporary_root.resolve()):
    raise ValueError('Invalid fixture path')
directory.mkdir(parents=True)

world = World()
# Zero's saved scheme has six drives. Expand only this browser fixture so the
# test exercises the same one-key payload size without changing shared fixtures.
for number in range(5, 10):
    item = deepcopy(world.rows[2])
    item.update(uid={'slot': 200 + number, 'serial': number}, item_id=str(number),
                equipped=False, equipped_character_id=None, equipped_character_uid=None,
                equipped_placement=None, names={'zh_cn': '测试装备 ' + str(number)})
    world.rows.append(item)
account = '配装刷新测试'
inventory = world.service(directory, account)
world.on_write = lambda: setattr(world, 'inventory_domain', 'fixture-inventory-after-write')
vision = VisionService(directory / 'vision')
inventory.vision = vision

# Seed a saved scheme that transfers #3 and #4 onto the first character.
selection = inventory.equipment.inspect(account)
core = next(item for item in selection['items'] if item['label'] == '#4')
drives = [item for item in selection['items'] if item['category'] == 'drive'
          and item['label'] in {'#3', '#5', '#6', '#7', '#8', '#9'}]
if len(drives) != 6:
    raise RuntimeError('Could not prepare six drive blocks')
used = set()
active = board(1003)
modules = []
for drive in drives:
    position = None
    for row in range(1, 6):
        for column in range(1, 6):
            cells = occupied(world.rows[2], {'row': row, 'column': column})
            if cells.issubset(active) and not cells.intersection(used):
                position = {'row': row, 'column': column}
                used.update(cells)
                break
        if position:
            break
    if not position:
        raise RuntimeError('Could not place six drives on the fixture board')
    modules.append({'id': drive['id'], **position})
saved = inventory.equipment.save_build_plan(account, selection['selection_id'], 1003,
                                             core['id'], modules, False, True)
if not saved.get('valid'):
    raise RuntimeError('Could not seed the saved role build')

# Recreate the former narrow race: the UI can observe a completed operation
# while the native lock is still held. The UI must wait and then load the saved
# post-operation equipment snapshot instead of dropping the refresh.
release = inventory.equipment._release
def delayed_release():
    if inventory.equipment.job.get('state') == 'verified':
        time.sleep(1.6)
    release()
inventory.equipment._release = delayed_release

base_status = inventory.status
fixture = {'locked_completion_seen': False}
def fixture_status():
    value = base_status()
    if value['equipment_job'].get('state') == 'verified' and value.get('native_operation') == 'equipment':
        fixture['locked_completion_seen'] = True
        # Simulate the old backend ordering so the browser test specifically
        # exercises the front-end's retry/wait behavior.
        value['equipment_job']['running'] = False
    value['fixture_locked_completion_seen'] = fixture['locked_completion_seen']
    return value
inventory.status = fixture_status

server = public_server(root / 'build/desktop/public', 0, inventory=inventory, vision=vision)
print(json.dumps({'port': server.server_port}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
    inventory.close()
    shutil.rmtree(directory)
