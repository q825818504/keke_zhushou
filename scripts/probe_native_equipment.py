"""Read-only native equipment probe by default; exact reviewed intent for live tests.

Execution is deliberately separate: --execute-approved points to a previously
reviewed preview. A changed source or inventory aborts before any command.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop'))
from inventory.service import InventoryService
from native.components import ComponentManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--character-id', type=int, action='append')
    parser.add_argument('--category', choices=['drive', 'tape'], action='append')
    parser.add_argument('--account', default='原生卸装联调')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--execute-approved', type=Path)
    args = parser.parse_args()
    directory = ROOT / 'build/native-equipment-lab-data'
    components = ComponentManager(directory / 'components', bundle=ROOT / 'build/native-components')
    inventory = InventoryService(directory / 'player-inventory', components=components)
    service = inventory.equipment
    try:
        if args.execute_approved:
            approved = json.loads(args.execute_approved.read_text(encoding='utf-8'))
            if approved.get('schema_version') != 1 or not approved.get('total'):
                raise ValueError('缺少可执行的已审核卸装预览')
            preview = service.preview(approved['account'], approved['character_ids'], approved['categories'])
            if (not service.plan or service.plan['fingerprint'] != approved['fingerprint']
                    or list(service.plan['context']) != approved['context'] or preview['total'] != approved['total']):
                raise ValueError('当前游戏或装备已不符合已审核预览，本次未派发')
            service.start(preview['token'])
            try:
                while service.thread.is_alive(): service.thread.join(.5)
            except KeyboardInterrupt:
                service.cancel()
                service.thread.join()
            result = service.status()
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result['state'] == 'verified' else 1
        inspection = service.inspect()
        result = {'schema_version': 1, 'inspection': inspection}
        if args.character_id:
            categories = args.category or ['drive', 'tape']
            preview = service.preview(args.account, args.character_id, categories)
            preview.pop('token', None)
            result.update(preview, character_ids=args.character_id, categories=categories,
                          fingerprint=service.plan['fingerprint'] if service.plan else None,
                          context=list(service.plan['context']) if service.plan else None)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        inventory.close()


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True))
        raise SystemExit(1)
