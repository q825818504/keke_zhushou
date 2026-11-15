"""Read-only assembly preview; execute only the exact separately approved intent."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'desktop'))
from inventory.service import InventoryService
from inventory.equipment import digest
from inventory.snapshot import uid
from native.components import ComponentManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-audit', type=Path)
    parser.add_argument('--character-id', type=int)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--execute-approved', type=Path)
    args = parser.parse_args()
    directory = ROOT/'build/native-equipment-lab-data'
    inventory = InventoryService(directory/'player-inventory', components=ComponentManager(directory/'components', bundle=ROOT/'build/native-components'))
    service = inventory.equipment
    try:
        info = service.inspect()
        handles = {key: ident for ident, key in service.selection['keys'].items()}
        if args.execute_approved:
            approved = json.loads(args.execute_approved.read_text(encoding='utf-8'))
            if approved.get('schema') != 1 or not approved.get('total'):
                raise ValueError('缺少已审核的具体装配清单')
            intent = approved['intent']
            character_id = intent['character_id']
            core = handles[tuple(intent['core'])] if intent['core'] is not None else 'none'
            modules = [{'id': handles[tuple(row['uid'])], 'row': row['row'], 'column': row['column']} for row in intent['modules']]
            preview = service.preview_assembly(approved['account'], info['selection_id'], character_id, core, modules, 'manual')
            if (not service.plan or service.plan['fingerprint'] != approved['fingerprint']
                    or list(service.plan['context']) != approved['context']
                    or digest(service.plan['operations']) != approved['operations_digest']):
                raise ValueError('游戏或具体装配步骤与已审核清单不同，本次未派发')
            service.start(preview['token'])
            try:
                while service.thread.is_alive(): service.thread.join(.5)
            except KeyboardInterrupt:
                service.cancel(); service.thread.join()
            result = service.status()
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result['state'] == 'verified' else 1
        if not args.from_audit or not args.character_id or not args.out:
            raise ValueError('只读预览需提供from-audit、character-id与out')
        raw = json.loads(args.from_audit.read_text(encoding='utf-8'))['before']
        original = [row for row in raw['rows'] if row.get('equipped') is True and row.get('equipped_character_id') == args.character_id]
        cores = [row for row in original if row['kind'] == 'core']
        if len(cores) != 1: raise ValueError('原始审核快照必须包含该角色的一件空幕')
        core_key = uid(cores[0]['uid'])
        drive_keys = [uid(row['uid']) for row in original if row['kind'] == 'module']
        selected = [handles[key] for key in drive_keys]
        program = "const fs=require('node:fs'),p=require('./native_assembly_planner.js'),v=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(p.plan(v.info,v.character_id,v.items)));"
        calculated = subprocess.run(['node','-e',program], input=json.dumps({'info':info,'character_id':args.character_id,'items':selected}),
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if calculated.returncode: raise ValueError(calculated.stderr)
        modules = json.loads(calculated.stdout)
        preview = service.preview_assembly('原生装配联调', info['selection_id'], args.character_id, handles[core_key], modules, 'manual')
        if service.plan:
            if service.plan['context'][1] != raw['header']['providerId']:
                raise ValueError('当前游戏来源与原始备份不同，请人工核对账号')
            original_owner = cores[0]['equipped_character_uid']
            if any(op['character'] != original_owner for op in service.plan['operations'] if op['character_id'] == args.character_id):
                raise ValueError('角色实例与原始快照不同，本次只读预览停止')
        preview.pop('token', None)
        result = {'schema':1, **preview, 'intent':{'character_id':args.character_id, 'core':core_key,
            'modules':[{'uid':service.selection['keys'][row['id']], 'row':row['row'],'column':row['column']} for row in modules]},
            'fingerprint':service.plan['fingerprint'] if service.plan else None,
            'context':list(service.plan['context']) if service.plan else None,
            'operations_digest':digest(service.plan['operations']) if service.plan else None}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
        print(json.dumps(preview,ensure_ascii=False))
        return 0
    finally: inventory.close()


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False))
        raise SystemExit(1)
