"""Development-only preview of a prepared release; never imported by shipped entry points."""
from pathlib import Path
import argparse
import json
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ['LOCALAPPDATA'] = str(ROOT / 'build/v1.4-local-preview-user-data')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-report')
    args = parser.parse_args()
    bundle = ROOT / 'dist/windows/releases/v1.4/program/KekeAssistantApp/_internal'
    info = json.loads((bundle / 'release-info.json').read_text(encoding='utf-8'))
    if info['version'] != '1.4':
        raise ValueError('本地预览需要已构建的 v1.4 文件')
    import runtime
    from inventory.service import InventoryService
    from vision.service import VisionService
    from native.components import ComponentManager
    from user_entry import SMOKE
    title = '可可助手 v1.4 · 本地预览'
    if not args.smoke_report and not runtime.single_instance(title, 'preview-v1.4'):
        return
    runtime.BUNDLE = bundle
    vision = VisionService(runtime.APP_DATA / 'vision-scans')
    components = ComponentManager(runtime.APP_DATA / 'native-components', bundle=bundle / 'native-components')
    inventory = InventoryService(runtime.APP_DATA / 'player-inventory', components=components, vision=vision)
    server = runtime.public_server(bundle / 'public', 0, inventory=inventory, vision=vision)
    (runtime.APP_DATA / 'preview-address.json').parent.mkdir(parents=True, exist_ok=True)
    (runtime.APP_DATA / 'preview-address.json').write_text(json.dumps({'port': server.server_port, 'version': '1.4'}), encoding='utf-8')
    runtime.launch_window(title, 'preview-v1.4', server, report=args.smoke_report, smoke_js=SMOKE)


if __name__ == '__main__':
    from runtime import guarded
    guarded(main)
