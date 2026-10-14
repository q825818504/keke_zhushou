"""Editable, bounded plain-text notes; separate from signed program/config data."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from update_protocol import REPOSITORY,open_url,version,atomic_json
import diagnostics

BASE=f'https://gitee.com/{REPOSITORY}/raw/main/notes/'

def read(url):
    with open_url(url) as response:body=response.read(64*1024+1)
    if len(body)>64*1024:raise ValueError('更新说明文件过大')
    return body.decode('utf-8-sig')

def validated(history,current):
    if not isinstance(history,list) or not 1<=len(history)<=100:raise ValueError('更新历史无效')
    seen=set();rows=[]
    for row in history:
        if not isinstance(row,dict):raise ValueError('更新说明无效')
        name=row.get('version');version(name)
        notes=row.get('notes')
        if name in seen or not isinstance(notes,str) or not notes.strip() or len(notes.encode('utf-8'))>64*1024:raise ValueError('更新说明内容无效')
        seen.add(name)
        if version(name)<=version(current):rows.append({'version':name,'notes':notes})
    if current not in {r['version'] for r in rows}:raise ValueError('缺少当前版本更新说明')
    return sorted(rows,key=lambda r:version(r['version']),reverse=True)

def refresh(app_data,current,reader=read):
    try:
        index=json.loads(reader(BASE+'index.json'))
        if not isinstance(index,dict) or index.get('schema')!=1:raise ValueError('说明索引无效')
        names=index.get('versions')
        if not isinstance(names,list) or not 1<=len(names)<=100:raise ValueError('说明版本列表无效')
        for name in names:version(name)
        if len(set(names))!=len(names):raise ValueError('说明版本重复')
        names=[n for n in names if version(n)<=version(current)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows=list(pool.map(lambda name:{'version':name,'notes':reader(BASE+'v'+name+'.md')},names))
        history=validated(rows,current)
        atomic_json(Path(app_data)/'release-notes-cache.json',{'schema':1,'history':history})
        return True
    except Exception as error:
        diagnostics.event('云端更新说明获取未完成，保留离线说明',detail=str(error)[:300]);return False

def cached(app_data,current):
    try:
        value=json.loads((Path(app_data)/'release-notes-cache.json').read_text(encoding='utf-8'))
        if not isinstance(value,dict) or value.get('schema')!=1:return None
        return validated(value['history'],current)
    except (OSError,ValueError,KeyError,TypeError):return None
