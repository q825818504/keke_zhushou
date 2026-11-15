"""Bounded, structurally validated metadata discovery; no injection, RPCs or game writes."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
from inventory.account_uid_reader.process_reader import ProcessReader, find_process_ids_by_image_name
from inventory.account_uid_reader.discover_runtime_objects import inspect as inspect_registry
from inventory.account_uid_reader.discover_runtime_names import inspect as inspect_names

PATTERN=re.compile(r'decompos|dismant|recycl|salvag|disassembl|breakdown',re.I)

def discover(output):
    result={'read_only':True,'game_calls':False,'writes_game_memory':False,'processes':[]}
    pids=find_process_ids_by_image_name('HTGame.exe')
    if len(pids)!=1:raise RuntimeError('Require exactly one HTGame.exe process')
    # Unsupported builds use only the existing bounded section discovery,
    # with independently validated registry/name-pool candidates. No offsets
    # from a different build are accepted and no game functions are called.
    registry=inspect_registry(pids[0],allow_unpinned_version=True)
    (output/'object-registry.json').write_text(json.dumps({'processes':[registry]},indent=2),encoding='utf-8')
    names=inspect_names(pids[0],{'processes':[registry]},allow_unpinned_version=True)
    (output/'name-pool.json').write_text(json.dumps({'processes':[names]},indent=2),encoding='utf-8')
    candidates=[r for r in names.get('candidates',[]) if r.get('verified')]
    if len(candidates)!=1:raise RuntimeError('Require one verified name pool')
    candidate=candidates[0];matches=[];scanned=0;decoded=0
    with ProcessReader(pids[0]) as reader:
        if reader.identity()!=registry['identity']:raise RuntimeError('Game identity changed')
        base=int(candidate['address'],16)
        current,cursor=struct.unpack('<II',reader.read(base+8,8))
        if current!=candidate['current_block'] or not 0<cursor<=131072:raise RuntimeError('Name pool changed')
        if (current+1)*131072>64*1024*1024:raise RuntimeError('Name pool exceeds 64MiB research budget')
        blocks=struct.unpack('<'+'Q'*(current+1),reader.read(base+16,(current+1)*8))
        for index,address in enumerate(blocks):
            size=cursor if index==current else 131072
            raw=reader.read(address,size);scanned+=len(raw);offset=0
            while offset+2<=len(raw):
                header=struct.unpack_from('<H',raw,offset)[0];length=header>>6;wide=header&1
                end=offset+2+length*(2 if wide else 1)
                if not 0<length<=1023 or end>len(raw):break
                try:value=raw[offset+2:end].decode('utf-16-le' if wide else 'utf-8')
                except UnicodeError:value=''
                decoded+=1
                if PATTERN.search(value):
                    if len(matches)>=2000:raise RuntimeError('Name match budget exceeded')
                    matches.append({'name':value,'name_index':(index<<16)|(offset//2)})
                offset=(end+1)&~1
        if reader.identity()!=registry['identity']:raise RuntimeError('Game identity changed')
    result.update(status='metadata_only',game_sha256=registry['game_sha256'],scanned_bytes=scanned,
                  decoded_names=decoded,matches=matches,
                  limitations=['Names do not establish callable addresses, parameter layout or a verified decomposition protocol'])
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'build/cleanup-research')
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):raise ValueError('Output must remain in workspace build')
    output.mkdir(parents=True,exist_ok=True)
    try:result=discover(output)
    except Exception as error:result={'status':'failed','read_only':True,'error':str(error)}
    (output/'runtime-cleanup-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['status']=='metadata_only' else 1

if __name__=='__main__':raise SystemExit(main())
