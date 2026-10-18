"""Bounded independent FName-pool discovery from game writable sections."""
import argparse,json,struct,time
from pathlib import Path
from .process_reader import ProcessReader
from .runtime_profile import EXPECTED_GAME_SHA,EXPECTED_SIZE
from .discover_runtime_objects import pointer
from .runtime_fast_profile import profile_for,resolve_game_sha256
from .pe_section_reader import read_pe_sections

def decode(reader,blocks,index):
    block=index>>16;offset=(index&65535)*2
    if block>=len(blocks):raise ValueError('name block out of range')
    entry=blocks[block]+offset
    header=struct.unpack('<H',reader.read(entry,2))[0]
    size=header>>6;wide=header&1
    if not 0<size<=1023:raise ValueError('name length out of range')
    raw=reader.read(entry+2,size*(2 if wide else 1))
    value=raw.decode('utf-16-le' if wide else 'utf-8',errors='strict')
    if any(ord(c)<32 for c in value):raise ValueError('control character in name')
    return value

def validate_candidate(reader,candidate,header_raw,samples):
    block,cursor,p0,p1=struct.unpack_from('<IIQQ',header_raw,8)
    if not (0<block<8192 and 0<cursor<=131072 and cursor%2==0 and pointer(p0) and pointer(p1)):
        return None
    first=reader.read(p0,8)
    if first[2:6]!=b'None' or struct.unpack_from('<H',first)[0]>>6!=4:return None
    block_raw=reader.read(candidate+16,(block+1)*8)
    blocks=struct.unpack('<'+'Q'*(block+1),block_raw)
    if not all(pointer(p) for p in blocks):return None
    rows=[]
    for sample in samples:
        obj=int(sample['object'],16);head=reader.read(obj,40);cls=struct.unpack_from('<Q',head,16)[0]
        class_head=reader.read(cls,40)
        token=struct.unpack_from('<Q',head,24)[0];class_token=struct.unpack_from('<Q',class_head,24)[0]
        rows.append({'index':sample['index'],'name':decode(reader,blocks,token&0xffffffff),'number':token>>32,'class_name':decode(reader,blocks,class_token&0xffffffff)})
    verified=len(rows)>=4 and sum(r['class_name'] in ['Class','Package'] for r in rows)>=4 and reader.read(candidate+16,(block+1)*8)==block_raw
    return {'address':hex(candidate),'current_block':block,'current_byte_cursor':cursor,
            'first_entry_hex':first.hex(),'samples':rows,'verified':verified}

def try_profiled_name_pool(reader,image_base,profile,samples):
    address=image_base+profile['name_pool_rva']
    row=validate_candidate(reader,address,reader.read(address,32),samples)
    if not row or not row['verified']:return None
    row['rva']=hex(address-image_base)
    row['discovery_method']='sha_pinned_rva'
    return row

def inspect(pid,registry_report,allow_unpinned_version=False):
    start=time.perf_counter();report={'pid':pid,'read_only':True,'uses_author_sdk':False,'game_capture_complete':False,'scan_bytes':0,'preliminary_candidates':0,'candidates':[],'failed_reads':[]}
    with ProcessReader(pid) as reader:
        identity=reader.identity();report['identity']=identity
        if Path(identity['executable']).name.lower()!='htgame.exe':raise ValueError('unexpected executable')
        main=next(m for m in reader.modules() if Path(m['path']).name.lower()=='htgame.exe');report['main_module']=main
        previous=next(r for r in registry_report['processes'] if r['pid']==pid and r['identity']==identity)
        digest,file_state,reused=resolve_game_sha256(identity['executable'],previous)
        report['game_sha256']=digest;report['executable_file_state']=file_state;report['digest_reused_from_registry']=reused
        if not allow_unpinned_version and (digest!=EXPECTED_GAME_SHA or main['size']!=EXPECTED_SIZE):raise ValueError('unverified game version')
        report['version_policy']='bounded_unpinned_scan' if digest!=EXPECTED_GAME_SHA or main['size']!=EXPECTED_SIZE else 'sha_and_image_size_pinned'
        samples=next(r['samples'] for r in previous['candidates'] if r['verified'])
        image_base=int(main['base'],16);seen=set();profile=profile_for(digest,main['size'])
        if profile:
            try:
                profiled=try_profiled_name_pool(reader,image_base,profile,samples)
            except (OSError,ValueError,UnicodeError,RuntimeError) as error:
                profiled=None;report['profile_fast_path_error']=str(error)
            if profiled and profiled['verified']:
                report['candidates']=[profiled]
                report['fast_path_profile']=profile['profile_id']
                report['fast_path_header_bytes']=32
                report['discovery_method']='sha_pinned_rva'
                report['status']='name_pool_verified'
                report['elapsed_ms']=round((time.perf_counter()-start)*1000,2)
                return report
            report['fast_path_profile']=profile['profile_id']
            report['fast_path_status']='rejected; bounded scan follows'
        for section in read_pe_sections(identity['executable']):
            if not section.Characteristics&0x80000000:continue
            size=section.Misc_VirtualSize
            if report['scan_bytes']+size>32*1024*1024:raise ValueError('scan budget exceeded')
            for offset in range(0,size,512*1024):
                address=image_base+section.VirtualAddress+offset;n=min(512*1024+32,size-offset)
                try:data=reader.read(address,n)
                except OSError as e:report['failed_reads'].append({'address':hex(address),'error':str(e)});continue
                report['scan_bytes']+=len(data)
                for i in range(0,len(data)-31,8):
                    block,cursor,p0,p1=struct.unpack_from('<IIQQ',data,i+8)
                    if not (0<block<8192 and 0<cursor<=131072 and cursor%2==0 and pointer(p0) and pointer(p1)):continue
                    candidate=address+i
                    if candidate in seen:continue
                    seen.add(candidate);report['preliminary_candidates']+=1
                    if len(seen)>4096:raise ValueError('candidate read budget exceeded')
                    try:
                        header_raw=data[i:i+32]
                        row=validate_candidate(reader,candidate,header_raw,samples)
                        if row:
                            row['rva']=hex(candidate-image_base)
                            row['discovery_method']='bounded_section_scan'
                            report['candidates'].append(row)
                    except (OSError,ValueError,UnicodeError,RuntimeError):continue
        report['discovery_method']='bounded_section_scan'
        report['status']='name_pool_verified' if any(r['verified'] for r in report['candidates']) else 'name_pool_not_found'
    report['elapsed_ms']=round((time.perf_counter()-start)*1000,2);return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('registry',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    registry=json.loads(args.registry.read_text(encoding='utf-8'));reports=[]
    for previous in registry['processes']:
        try:reports.append(inspect(previous['pid'],registry))
        except Exception as e:reports.append({'pid':previous['pid'],'status':'failed','error':str(e)})
    args.output.write_text(json.dumps({'schema':'keke_name_pool_discovery_v1','processes':reports},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if any(r.get('status')=='name_pool_verified' for r in reports) else 2
if __name__=='__main__':raise SystemExit(main())
