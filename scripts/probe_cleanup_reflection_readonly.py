"""Read bounded Unreal reflection metadata for cleanup UI signatures.

This diagnostic reads only already-discovered UObject/FField metadata. It does
not invoke a game function, write process memory, or send RPCs.
"""
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

OBJECT_HEADER=40
UFIELD_NEXT=0x28
FIELD_CLASS=0x08
FIELD_OWNER=0x10
FIELD_NEXT=0x18
FIELD_NAME=0x20
FIELD_FLAGS=0x28
PROPERTY_ARRAY_DIM=0x30
PROPERTY_ELEMENT_SIZE=0x34
PROPERTY_FLAGS=0x38
PROPERTY_OFFSET=0x48

def inspect(directory):
    registry_doc=json.loads((directory/'object-registry.json').read_text(encoding='utf-8'))['processes'][0]
    pool_doc=json.loads((directory/'name-pool.json').read_text(encoding='utf-8'))['processes'][0]
    previous=json.loads((directory/'runtime-cleanup-objects.json').read_text(encoding='utf-8'))
    if previous.get('status')!='metadata_only' or previous.get('game_sha256')!=registry_doc.get('game_sha256'):
        raise RuntimeError('Previous bounded object report does not match the registry profile')
    registry=next(row for row in registry_doc['candidates'] if row['verified'])
    pool=next(row for row in pool_doc['candidates'] if row['verified'])
    targets=[row for row in previous['matches'] if row['class'] in ('Class','Function','DelegateFunction','ScriptStruct')
             and (row['name'].startswith('HTUI_EquipDecompose') or row['name']=='DecomposeSelectData'
                  or any(parent['name']=='HTUI_EquipDecompose' for parent in row.get('parents',[])))]
    start=time.monotonic(); failures=[]; parsed=[]
    with ProcessReader(registry_doc['pid']) as reader:
        if reader.identity()!=registry_doc['identity']:
            raise RuntimeError('Game process identity changed; no memory was read')
        if executable_file_state(registry_doc['identity']['executable'])!=registry_doc['executable_file_state']:
            raise RuntimeError('Game executable changed; no memory was read')
        base=int(registry['address'],16)
        values=struct.unpack('<QQiiii',reader.read(base,32))
        if not validate(reader,base,values).get('verified'):
            raise RuntimeError('Object registry validation failed')
        chunks,_,_,count,_,chunk_count=values
        if count>1000000 or chunk_count>1024:
            raise RuntimeError('Object registry exceeds the read budget')
        chunk_raw=reader.read(chunks,chunk_count*8)
        chunk_ptrs=struct.unpack('<'+'Q'*chunk_count,chunk_raw)
        pool_address=int(pool['address'],16)
        block,cursor=struct.unpack('<II',reader.read(pool_address+8,8))
        if block>8191:
            raise RuntimeError('Name pool exceeds the read budget')
        block_ptrs=struct.unpack('<'+'Q'*(block+1),reader.read(pool_address+16,(block+1)*8))
        name_cache={}
        def name(index):
            index=int(index)&0xffffffff
            if index not in name_cache:
                name_cache[index]=decode(reader,block_ptrs,index)
            return name_cache[index]
        def describe_object(address):
            if not pointer(address):raise ValueError('invalid UObject pointer')
            head=reader.read(address,OBJECT_HEADER)
            cls=struct.unpack_from('<Q',head,16)[0]
            if not pointer(cls):raise ValueError('invalid UObject class pointer')
            token=struct.unpack_from('<Q',head,24)[0]
            return {'address':address,'name':name(token),'class':name(struct.unpack('<Q',reader.read(cls+24,8))[0]),
                    'outer':struct.unpack_from('<Q',head,32)[0],
                    'index':struct.unpack_from('<i',head,12)[0]}
        def checked_target(row):
            item=describe_object(int(row['address'],16))
            if item['name']!=row['name'] or item['class']!=row['class'] or item['index']!=row['object_index']:
                raise RuntimeError('Discovered UObject no longer matches its saved identity')
            if item['index']<0 or item['index']>=count:raise RuntimeError('Object index is outside registry')
            table_obj=chunk_ptrs[item['index']//65536]+(item['index']%65536)*24
            slot=struct.unpack('<Q',reader.read(table_obj,8))[0]
            if slot!=int(row['address'],16):raise RuntimeError('Object index no longer points to discovered UObject')
            return item
        items={row['name']:checked_target(row) for row in targets}
        type_cache={}
        def field_class_name(address):
            if address not in type_cache:
                if not pointer(address):raise ValueError('invalid FFieldClass pointer')
                token=struct.unpack('<Q',reader.read(address,8))[0]
                type_cache[address]=name(token)
            return type_cache[address]
        def field_chain(first,owner):
            rows=[];seen=set();address=first
            while pointer(address):
                if address in seen or len(rows)>=128:raise ValueError('FField chain loop/limit')
                seen.add(address)
                raw=reader.read(address,0x50)
                cls=struct.unpack_from('<Q',raw,FIELD_CLASS)[0]
                own=struct.unpack_from('<Q',raw,FIELD_OWNER)[0]
                nxt=struct.unpack_from('<Q',raw,FIELD_NEXT)[0]
                label=name(struct.unpack_from('<Q',raw,FIELD_NAME)[0])
                typ=field_class_name(cls)
                if own!=owner:raise ValueError('FField owner does not match its reflected owner')
                dim=struct.unpack_from('<i',raw,PROPERTY_ARRAY_DIM)[0]
                size=struct.unpack_from('<i',raw,PROPERTY_ELEMENT_SIZE)[0]
                pflags=struct.unpack_from('<Q',raw,PROPERTY_FLAGS)[0]
                offset=struct.unpack_from('<i',raw,PROPERTY_OFFSET)[0]
                if not label or not typ.endswith('Property') or not 1<=dim<=1024 or not 1<=size<=0x100000 or not 0<=offset<=0x100000:
                    raise ValueError('FProperty layout failed structural bounds')
                rows.append({'name':label,'type':typ,'array_dim':dim,'element_size':size,
                             'property_flags_hex':hex(pflags),'offset':offset,'max_end':offset+size*dim})
                if nxt and not pointer(nxt):raise ValueError('invalid FField next pointer')
                address=nxt
            return rows
        def discover_field_chain(owner,limits):
            found=[]
            for offset in limits:
                try:
                    first=struct.unpack('<Q',reader.read(owner+offset,8))[0]
                    if not pointer(first):continue
                    fields=field_chain(first,owner)
                    if fields:found.append({'offset_hex':hex(offset),'properties':fields})
                except (OSError,ValueError,struct.error):continue
            return found

        # Find the class's linked UFunction list through its runtime layout. A
        # candidate must reproduce the previously validated function objects.
        classes=[row for row in targets if row['class']=='Class' and row['name'].startswith('HTUI_EquipDecompose')]
        class_reports=[]
        known_functions={int(row['address'],16):row for row in targets if row['class']=='Function'}
        for class_row in classes:
            class_address=int(class_row['address'],16)
            linked=[]
            for children_offset in range(0x28,0x81,8):
                try:
                    node=struct.unpack('<Q',reader.read(class_address+children_offset,8))[0]
                    chain=[];seen=set()
                    while pointer(node) and node not in seen and len(chain)<128:
                        seen.add(node);obj=describe_object(node)
                        if obj['class']=='Function' and obj['outer']==class_address:
                            chain.append(obj)
                        node=struct.unpack('<Q',reader.read(node+UFIELD_NEXT,8))[0]
                    addresses={item['address'] for item in chain}
                    expected={address for address,row in known_functions.items()
                              if any(parent['name']==class_row['name'] for parent in row.get('parents',[]))}
                    if expected and expected.issubset(addresses):
                        linked.append({'children_offset_hex':hex(children_offset),'functions':[{'name':r['name'],'address':hex(r['address'])} for r in chain]})
                except (OSError,ValueError,struct.error):continue
            class_reports.append({'name':class_row['name'],'address':class_row['address'],'validated_child_lists':linked,
                                  'declared_properties':discover_field_chain(class_address,range(0x28,0xc1,8))})

        function_reports=[]
        for row in targets:
            if row['class']!='Function':continue
            address=int(row['address'],16);owner=items[row['name']]['outer']
            signatures=discover_field_chain(address,range(0x28,0xc1,8))
            function_reports.append({'name':row['name'],'address':row['address'],'owner':hex(owner),
                                     'candidate_parameter_lists':signatures})
        struct_reports=[]
        for row in targets:
            if row['class']!='ScriptStruct' or row['name']!='DecomposeSelectData':continue
            struct_reports.append({'name':row['name'],'address':row['address'],
                                   'candidate_fields':discover_field_chain(int(row['address'],16),range(0x28,0xc1,8))})
        if reader.read(chunks,chunk_count*8)!=chunk_raw or reader.identity()!=registry_doc['identity']:
            raise RuntimeError('Object registry/process identity changed during read')
    return {'status':'metadata_only','read_only':True,'game_calls':False,'writes_game_memory':False,
            'game_sha256':registry_doc['game_sha256'],'elapsed_seconds':round(time.monotonic()-start,3),
            'class_reports':class_reports,'function_reports':function_reports,'struct_reports':struct_reports,
            'limitations':['Only structurally validated UObject/FField metadata is reported; no UFunction was invoked and this does not establish a server request or successful decomposition receipt.']}

def main():
    directory=ROOT/'build/cleanup-research-current'
    output=directory/'runtime-cleanup-reflection.json'
    try:
        result=inspect(directory)
    except Exception as error:
        result={'status':'failed','read_only':True,'error':str(error)}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result.get('status'),'output':str(output),
                      'functions':len(result.get('function_reports',[])),
                      'classes':len(result.get('class_reports',[]))},ensure_ascii=False))
    return 0 if result['status']=='metadata_only' else 1

if __name__=='__main__':raise SystemExit(main())
