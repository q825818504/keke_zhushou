"""Export maintained data and referenced images, without source files."""
from pathlib import Path
import json
import re
import shutil
import copy
from update_protocol import atomic_json, digest, load_config


def export_config(root, destination):
    root=Path(root).resolve(); destination=Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    knowledge=root/'data/knowledge'
    read=lambda relative: json.loads((knowledge/relative).read_text(encoding='utf-8-sig'))
    bindings={'characterKnowledge':{p.stem:json.loads(p.read_text(encoding='utf-8-sig')) for p in (knowledge/'characters').glob('*.json')},
              'characterOverrides':read('character_overrides.json'),'arcDriveKnowledge':read('encyclopedia/arc_drives.json'),
              'skyCurtainKnowledge':read('encyclopedia/sky_curtains.json'),'driverBlockKnowledge':read('encyclopedia/driver_blocks.json'),
              'teamTemplateKnowledge':read('team_templates.json'),'teamGuideOverrides':read('team_overrides.json'),
              'esperCycleKnowledge':read('esper_cycles.json')}
    teams=bindings['teamTemplateKnowledge']['teams']; overrides=bindings['teamGuideOverrides']
    merged={team['id']:copy.deepcopy(team) for team in teams}
    for ident,team in overrides.get('edits',{}).items():
        if team.get('id')!=ident: raise ValueError('阵容维护编号不匹配')
        merged[ident]=copy.deepcopy(team)
    bindings['teamTemplateKnowledge']['teams']=[team for ident,team in merged.items() if ident not in overrides.get('removed',[])]
    atomic_json(destination/'config.json',{'schema':1,'bindings':bindings})
    document=load_config(destination)
    assets={}
    def local_asset_paths(value):
        if isinstance(value,dict):
            for item in value.values():
                yield from local_asset_paths(item)
        elif isinstance(value,list):
            for item in value:
                yield from local_asset_paths(item)
        elif isinstance(value,str) and not value.startswith(('http://','https://')):
            yield from re.findall(r'data/[^"\s]+?\.(?:webp|png|jpe?g|gif|svg)',value)
    for relative in sorted(set(local_asset_paths(document))):
        source=(root/relative).resolve()
        if not source.is_relative_to(root/'data') or not source.is_file():
            raise ValueError('公共配置图片缺失：'+relative)
        target=destination/relative; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target); assets[relative]=digest(target)
    document['assets']=assets
    atomic_json(destination/'config.json',document)
    return document


def validated_config(directory):
    document=load_config(directory)
    for relative, expected in document.get('assets',{}).items():
        path=(Path(directory)/relative).resolve()
        if not relative.startswith('data/') or not path.is_relative_to((Path(directory)/'data').resolve()) or digest(path)!=expected:
            raise ValueError('公共配置图片校验失败')
    return document
