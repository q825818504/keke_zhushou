"""Read-only matching of discovered decomposition names to validated UObject entries."""
from pathlib import Path
import json
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
from inventory.account_uid_reader.process_reader import ProcessReader
from inventory.account_uid_reader.discover_runtime_objects import validate, pointer
from inventory.account_uid_reader.discover_runtime_names import decode
from inventory.account_uid_reader.runtime_fast_profile import executable_file_state

def inspect(directory):
    registry=json.loads((directory/'object-registry.json').read_text(encoding='utf-8'))['processes'][0]
    pool=json.loads((directory/'name-pool.json').read_text(encoding='utf-8'))['processes'][0]
    names=json.loads((directory/'runtime-cleanup-metadata.json').read_text(encoding='utf-8'))
    targets={row['name_index'] for row in names['matches'] if any(s in row['name'].lower() for s in ('decompos','decompose')) and '/' not in row['name']}
    previous_file=directory/'runtime-cleanup-objects.json'
    previous=json.loads(previous_file.read_text(encoding='utf-8')) if previous_file.exists() else {}
    owners={int(row['address'],16) for row in previous.get('matches',[])
            if (row['class']=='Class' and row['name'].startswith('HTUI_EquipDecompose'))
            or (row['class']=='ScriptStruct' and row['name']=='DecomposeSelectData')}
    reg=next(row for row in registry['candidates'] if row['verified'])
    np=next(row for row in pool['candidates'] if row['verified'])
    found=[];failures=0;start=time.monotonic()
    with ProcessReader(registry['pid']) as reader:
        if reader.identity()!=registry['identity']:raise RuntimeError('Process identity changed')
        if executable_file_state(registry['identity']['executable'])!=registry['executable_file_state']:
            raise RuntimeError('Executable changed')
        base=int(reg['address'],16);header=reader.read(base,32)
        values=struct.unpack('<QQiiii',header)
        verified=validate(reader,base,values)
        if not verified['verified']:raise RuntimeError('Registry validation failed')
        chunks,_,_,count,_,chunk_count=values
        if count>1000000:raise RuntimeError('Object count exceeds one million metadata budget')
        table=reader.read(chunks,chunk_count*8)
        chunk_pointers=struct.unpack('<'+'Q'*chunk_count,table)
        name_base=int(np['address'],16);block,cursor=struct.unpack('<II',reader.read(name_base+8,8))
        if block>8191:raise RuntimeError('Name pool bound exceeded')
        blocks=struct.unpack('<'+'Q'*(block+1),reader.read(name_base+16,(block+1)*8))
        cache={}
        def name(token):
            index=token&0xffffffff
            if index not in cache:cache[index]=decode(reader,blocks,index)
            return cache[index]
        def describe(address):
            head=reader.read(address,40)
            token=struct.unpack_from('<Q',head,24)[0]
            cls=struct.unpack_from('<Q',head,16)[0]
            class_name=name(struct.unpack_from('<Q',reader.read(cls,40),24)[0])
            return {'address':hex(address),'name':name(token),'class':class_name,
                    'outer':struct.unpack_from('<Q',head,32)[0]}
        for chunk_index,address in enumerate(chunk_pointers):
            if time.monotonic()-start>90:raise RuntimeError('Metadata discovery exceeded 90 seconds')
            rows=min(65536,count-chunk_index*65536)
            if rows<=0:break
            # ProcessReader caps every individual read at one MiB.
            raw=b''.join(reader.read(address+start*24,min(4096,rows-start)*24)
                         for start in range(0,rows,4096))
            for offset in range(rows):
                obj=struct.unpack_from('<Q',raw,offset*24)[0]
                if not pointer(obj):continue
                try:head=reader.read(obj,40)
                except OSError:
                    failures+=1
                    if failures>1000:raise RuntimeError('Too many unreadable objects')
                    continue
                index=chunk_index*65536+offset
                if struct.unpack_from('<i',head,12)[0]!=index:continue
                token=struct.unpack_from('<Q',head,24)[0]
                if token&0xffffffff not in targets and struct.unpack_from('<Q',head,32)[0] not in owners:continue
                row=describe(obj);outer=row.pop('outer');row['object_index']=index;row['parents']=[]
                for _ in range(4):
                    if not pointer(outer):break
                    parent=describe(outer);outer=parent.pop('outer');row['parents'].append(parent)
                row['header_hex']=reader.read(obj,256).hex()
                if reader.read(obj,40)!=head:raise RuntimeError('Matched object changed during read')
                found.append(row)
                if len(found)>512:raise RuntimeError('Match budget exceeded')
        if reader.read(chunks,chunk_count*8)!=table or reader.identity()!=registry['identity']:
            raise RuntimeError('Object table identity changed')
    return {'status':'metadata_only','read_only':True,'game_calls':False,'writes_game_memory':False,
            'game_sha256':registry['game_sha256'],'objects_observed':count,'unreadable_objects':failures,
            'elapsed_seconds':round(time.monotonic()-start,3),'matches':found,
            'limitations':['UFunction parameter layout and network result still unverified; no function was called']}

def main():
    directory=ROOT/'build/cleanup-research-current'
    try:result=inspect(directory)
    except Exception as error:result={'status':'failed','read_only':True,'error':str(error)}
    (directory/'runtime-cleanup-objects.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['status']=='metadata_only' else 1

if __name__=='__main__':raise SystemExit(main())
