import copy, json, tempfile, shutil
from pathlib import Path
from unittest.mock import patch
import admin_server as admin
plans=json.loads(Path('build/terminal-qa/plans.json').read_text(encoding="utf-8"))
for ident,plan in plans.items():
    assert admin._validate_terminal_puzzle(ident,plan)==plan
    invalid=copy.deepcopy(plan)
    invalid['pieces'].append({**invalid['pieces'][0], 'id':'D99'})
    try: admin._validate_terminal_puzzle(ident,invalid)
    except ValueError: pass
    else: raise AssertionError('overlap accepted')
    missing=copy.deepcopy(plan)
    cassette=next(item for item in json.loads((admin.KNOWLEDGE/'encyclopedia/sky_curtains.json').read_text(encoding='utf-8'))['items'] if item['id']==plan['cassette_id'])
    first=cassette['set_requirements']['required_drives'][0]['shape_id']
    missing['pieces']=[piece for piece in missing['pieces'] if piece['shape_id']!=first]
    try: admin._validate_terminal_puzzle(ident,missing)
    except ValueError: pass
    else: raise AssertionError('incomplete set accepted')
with tempfile.TemporaryDirectory(prefix='keke-terminal-') as tmp:
    root=Path(tmp); knowledge=root/'data/knowledge'
    shutil.copytree(admin.KNOWLEDGE,knowledge)
    with patch.multiple(admin,ROOT=root,KNOWLEDGE=knowledge,CHAR_OVERRIDES=knowledge/'character_overrides.json',CHAR_BUNDLE=knowledge/'character_overrides.js'):
        document=admin._load_character_overrides()
        ident='canhong'
        source=json.loads((knowledge/'characters/canhong.json').read_text(encoding="utf-8"))
        source_before=(knowledge/'characters/canhong.json').read_bytes()
        cassette=next(item for item in json.loads((knowledge/'encyclopedia/sky_curtains.json').read_text(encoding='utf-8'))['items'] if item['id']==plans[ident]['cassette_id'])
        rec={**source['recommended'],'cassette':{'id':cassette['id'],'name':cassette['name']},'terminal_puzzle':plans[ident]}
        document['characters'].setdefault(ident,{})['recommended']=admin._validate_recommendations({ident:rec})[ident]
        admin._commit_bundles(character_overrides=document)
        assert json.loads((knowledge/'character_overrides.json').read_text(encoding="utf-8"))['characters'][ident]['recommended']['terminal_puzzle']==plans[ident]
        assert (knowledge/'characters/canhong.json').read_bytes()==source_before
        assert 'terminal_puzzle' in (knowledge/'character_overrides.js').read_text(encoding="utf-8")
print('Terminal storage passed: all JS layouts match server footprints; isolated JSON/bundle write preserved source.')
