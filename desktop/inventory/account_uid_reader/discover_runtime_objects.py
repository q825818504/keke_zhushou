"""Own bounded object-registry discovery; read-only, no author IPC/SDK."""
import argparse,json,struct,time
from pathlib import Path
from .process_reader import ProcessReader,find_process_ids_by_image_name
from .runtime_profile import EXPECTED_GAME_SHA,EXPECTED_SIZE
from .runtime_fast_profile import profile_for,resolve_game_sha256
from .pe_section_reader import read_pe_sections

def pointer(p):return 0x10000<=p<0x800000000000

def candidates(data,base):
    for offset in range(0,len(data)-31,8):
        maximum,count,max_chunks,num_chunks=struct.unpack_from('<iiii',data,offset+16)
        if not (128<count<=8000000 and count<=maximum<=67108864 and 0<num_chunks<=max_chunks<=1024):continue
        if maximum%65536 or maximum!=max_chunks*65536 or count>num_chunks*65536:continue
        chunks,preallocated=struct.unpack_from('<QQ',data,offset)
        if pointer(chunks) and (preallocated==0 or pointer(preallocated)):
            yield base+offset,(chunks,preallocated,maximum,count,max_chunks,num_chunks)

def validate(reader,address,header):
    chunks,preallocated,maximum,count,max_chunks,num_chunks=header
    row={'address':hex(address),'header':{'chunks':hex(chunks),'preallocated':hex(preallocated),'max_elements':maximum,'num_elements':count,'max_chunks':max_chunks,'num_chunks':num_chunks},'samples':[],'verified':False}
    try:
        chunk_bytes=reader.read(chunks,num_chunks*8)
        chunk_addresses=struct.unpack('<'+'Q'*num_chunks,chunk_bytes)
        if not all(pointer(p) for p in chunk_addresses):return row
        for index in sorted(set([0,1,2,16,64,128,256,count//2,count-1])):
            if index>=count:continue
            entry=reader.read(chunk_addresses[index//65536]+index%65536*24,24)
            obj=struct.unpack_from('<Q',entry)[0]
            if not obj:continue
            if not pointer(obj):return row
            object_header=reader.read(obj,40)
            object_index=struct.unpack_from('<i',object_header,12)[0]
            cls=struct.unpack_from('<Q',object_header,16)[0]
            sample={'index':index,'object':hex(obj),'object_index':object_index,'class':hex(cls),'name_token':hex(struct.unpack_from('<Q',object_header,24)[0]),'entry_hex':entry.hex(),'header_hex':object_header.hex()}
            row['samples'].append(sample)
            if object_index!=index or not pointer(cls):return row
            class_header=reader.read(cls,40)
            class_index=struct.unpack_from('<i',class_header,12)[0]
            if not 0<=class_index<count:return row
            class_slot=reader.read(chunk_addresses[class_index//65536]+class_index%65536*24,8)
            if struct.unpack('<Q',class_slot)[0]!=cls:return row
        if len(row['samples'])<4:return row
        row['verified']=reader.read(address,32)==struct.pack('<QQiiii',*header) and reader.read(chunks,num_chunks*8)==chunk_bytes
    except (OSError,ValueError,RuntimeError) as e:row['error']=str(e)
    return row

def try_profiled_registry(reader,image_base,profile):
    """Read the SHA-pinned candidate and pass it through the regular validator."""
    address=image_base+profile['object_registry_rva']
    data=reader.read(address,32)
    rows=list(candidates(data,address))
    if len(rows)!=1 or rows[0][0]!=address:return None
    row=validate(reader,address,rows[0][1])
    if not row.get('verified'):return None
    row['rva']=hex(address-image_base)
    row['discovery_method']='sha_pinned_rva'
    return row

def inspect(pid,allow_unpinned_version=False):
    start=time.perf_counter();report={'pid':pid,'read_only':True,'uses_author_sdk':False,'game_capture_complete':False,'scan_bytes':0,'failed_reads':[],'candidates':[]}
    with ProcessReader(pid) as reader:
        identity=reader.identity();report['identity']=identity
        if Path(identity['executable']).name.lower()!='htgame.exe':raise ValueError('unexpected executable')
        digest,file_state,_=resolve_game_sha256(identity['executable']);report['game_sha256']=digest;report['executable_file_state']=file_state
        main=next(m for m in reader.modules() if Path(m['path']).name.lower()=='htgame.exe')
        report['main_module']=main
        if not allow_unpinned_version and (digest!=EXPECTED_GAME_SHA or main['size']!=EXPECTED_SIZE):raise ValueError('unverified game version')
        report['version_policy']='bounded_unpinned_scan' if digest!=EXPECTED_GAME_SHA or main['size']!=EXPECTED_SIZE else 'sha_and_image_size_pinned'
        image_base=int(main['base'],16);seen=set()
        profile=profile_for(digest,main['size'])
        if profile:
            try:
                profiled=try_profiled_registry(reader,image_base,profile)
            except (OSError,ValueError,RuntimeError) as error:
                profiled=None;report['profile_fast_path_error']=str(error)
            if profiled:
                report['candidates']=[profiled]
                report['fast_path_profile']=profile['profile_id']
                report['fast_path_header_bytes']=32
                report['discovery_method']='sha_pinned_rva'
                report['status']='registry_candidates_verified'
                report['elapsed_ms']=round((time.perf_counter()-start)*1000,2)
                return report
            report['fast_path_profile']=profile['profile_id']
            report['fast_path_status']='rejected; bounded scan follows'
        else:
            report['fast_path_status']='no exact SHA/size profile; bounded scan follows'
        for section in read_pe_sections(identity['executable']):
            if not section.Characteristics&0x80000000:continue
            size=section.Misc_VirtualSize
            if report['scan_bytes']+size>32*1024*1024:raise ValueError('writable scan exceeds budget')
            for offset in range(0,size,512*1024):
                n=min(512*1024+32,size-offset)
                address=image_base+section.VirtualAddress+offset
                try:data=reader.read(address,n)
                except OSError as e:
                    report['failed_reads'].append({'address':hex(address),'bytes':n,'error':str(e)});continue
                report['scan_bytes']+=len(data)
                for candidate,header in candidates(data,address):
                    if candidate in seen:continue
                    seen.add(candidate)
                    if len(seen)>256:raise ValueError('candidate budget exceeded')
                    item=validate(reader,candidate,header);item['rva']=hex(candidate-image_base);report['candidates'].append(item)
        report['discovery_method']='bounded_section_scan'
        report['status']='registry_candidates_verified' if any(x['verified'] for x in report['candidates']) else 'registry_not_found'
    report['elapsed_ms']=round((time.perf_counter()-start)*1000,2)
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args();args.output.parent.mkdir(parents=True,exist_ok=True)
    pids=find_process_ids_by_image_name('HTGame.exe')
    reports=[]
    for pid in pids:
        try:reports.append(inspect(pid))
        except Exception as e:reports.append({'pid':pid,'status':'failed','error':str(e)})
    args.output.write_text(json.dumps({'schema':'keke_registry_discovery_v1','processes':reports},ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if any(r.get('status')=='registry_candidates_verified' for r in reports) else 2
if __name__=='__main__':raise SystemExit(main())
