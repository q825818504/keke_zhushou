"""Bounded snapshot reader: page identity, source revision and UID validation."""
import json

from .core import CoreRpcError

META = ('providerId','domain','snapshotId','generation','domainKey','observedUnixUs','observedMonotonicMs',
        'enabled','ready','state','recordCount','sourceRecordCount','enumerationComplete','complete',
        'sourceCoverage','changeCoverage','missing','failed','truncated')
DOMAINS = {
 'equipment': ('inventory', 'items', ('inventory.snapshot.v1','native_inventory_dto_v1')),
 'characters': ('character', 'profiles', ('character.snapshot.v1','native_character_profile_v1')),
 'items': ('inventory', 'records', ('inventory.all_items.v1',)),
 'team': ('team', 'records', ('team.snapshot.v1',)),
 'environment': ('environment', 'records', ('environment.snapshot.v1',)),
}

def require_current_revision(core, header, check):
    """Cheap pre-write guard; full records are still read and verified after each write."""
    current = core.call('native.snapshot.status', {}, check)
    matches = [row for row in current.get('domains', [])
               if isinstance(row, dict) and row.get('domain') == header.get('domain')]
    if (current.get('providerId') != header.get('providerId') or len(matches) != 1
            or matches[0].get('ready') is not True or matches[0].get('dirty') is not False
            or matches[0].get('domainKey') != header.get('domainKey')
            or matches[0].get('revision') != header.get('revision')):
        raise ValueError('原生装备快照修订已变化，停止后续操作；请重新读取并生成方案')
    return True

def uid(value):
    if not isinstance(value, dict) or any(type(value.get(k)) is not int or not 0 < value[k] < 4294967295 for k in ('slot','serial')):
        raise ValueError('装备UID无效')
    return value['slot'], value['serial']

def read_snapshot(core, kind, check):
    domain, field, required = DOMAINS[kind]
    if not set(required).issubset(core.hello.get('capabilities', [])):
        raise ValueError('当前组件未提供此类数据能力')
    scope = {'scope':'all_items'} if kind == 'items' else {}
    header = core.call('native.snapshot.refresh', {'domain':domain, **scope}, check)
    check()
    fields = META if field != 'records' else tuple(k for k in META if k not in ('state','sourceRecordCount')) + ('revision','dirty')
    if any(k not in header for k in fields) or header['domain'] != domain:
        raise ValueError('快照元数据不完整')
    for k in ('enabled','ready','enumerationComplete'):
        if header[k] is not True:
            raise ValueError('游戏数据尚未就绪，保留上次数据')
    if header['failed'] is not False or header['truncated'] is not False:
        raise ValueError('快照读取失败或被截断')
    count = header['recordCount']
    if type(count) is not int or not 0 <= count <= 32768:
        raise ValueError('快照数量无效')
    for k in ('providerId','snapshotId','generation','domainKey','observedUnixUs','observedMonotonicMs'):
        if not isinstance(header[k], str) or not header[k] or len(header[k]) > 1024:
            raise ValueError('快照身份无效')
    identity = list(fields)
    if 'revision' in header:
        revision = header['revision']
        if not isinstance(revision,str) or not revision.isascii() or not revision.isdecimal() or len(revision)>20 or int(revision)>18446744073709551615 or header.get('dirty') is not False:
            raise ValueError('来源修订无效')
        identity += ['revision','dirty']
    if kind == 'equipment':
        expected = {'collectionComplete':True,'collectionScope':'EQUIP','characterRefsComplete':True}
        if any(type(header.get(k)) is not type(v) or header.get(k) != v for k,v in expected.items()):
            raise ValueError('完整装备集合或角色关联尚未就绪')
        identity += list(expected)
    if kind == 'items':
        expected = {'collectionComplete':True,'collectionScope':'all_observed_InventoryContainerMap_containers',
                    'sourceRecordCount':count,'complete':False,'sourceCoverage':'unknown','changeCoverage':'unknown'}
        if any(type(header.get(k)) is not type(v) or header.get(k)!=v for k,v in expected.items()) or 'revision' not in header:
            raise ValueError('全部物品观测范围或来源证明无效')
        identity += ['collectionComplete','collectionScope','sourceRecordCount']
    rows, pages, offset, size = [], [], 0, 0
    method = 'native.' + domain + '.page' if field != 'records' else 'native.snapshot.page'
    raw_equipment = False
    while True:
        params = {'snapshotId':header['snapshotId'],'offset':offset,'limit':64, **scope}
        if field == 'records':
            params['domain'] = domain
        try:
            page = core.call(method, params, check)
        except CoreRpcError as error:
            if (kind != 'equipment' or pages or error.domain_code != 'NATIVE_MAPPING_UNSUPPORTED'
                    or error.data.get('detail') != 'native_projection_unavailable'):
                raise
            raw_equipment = True
            method, field = 'native.snapshot.page', 'records'
            identity.append('characterRefs')
            page = core.call(method, {**params, 'domain': domain}, check)
        if any(type(page.get(k)) is not type(header[k]) or page.get(k)!=header[k] for k in identity):
            raise ValueError('分页来源发生变化，本次数据已丢弃')
        part = page.get(field)
        next_offset = page.get('nextOffset')
        end = count if next_offset is None else next_offset
        if ('nextOffset' not in page or not isinstance(part,list) or any(not isinstance(row,dict) for row in part)
            or type(end) is not int or not offset <= end <= min(count,offset+64)
            or (len(part) != end-offset if kind != 'characters' else len(part)>end-offset)
            or (next_offset is not None and (end <= offset or end >= count))):
            raise ValueError('分页数量或游标无效')
        size += len(json.dumps(page,ensure_ascii=False).encode())
        if size > 64*1024*1024:
            raise ValueError('数据超过64MB限制')
        if kind == 'equipment' and not raw_equipment and page.get('projectionComplete') is not True:
            raise ValueError('装备字段映射尚未完成')
        rows.extend(part)
        # Keep every returned field, including sparse-profile diagnostics and equipped references.
        pages.append(page)
        offset = end
        if next_offset is None:
            break
    if raw_equipment:
        from .equipment_projection import project_equipment
        rows, characters, references = project_equipment(rows, header['characterRefs'])
        for page in pages:
            page.update(characters=characters, referencedItemUids=references, projectionComplete=True,
                        statProvenance={'main': 'static_catalog_curve', 'percent': 'static_catalog',
                                        'sub': 'raw_save_struct_float'})
    if kind == 'equipment':
        keys = [uid(row.get('uid')) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError('存在重复装备UID')
        chars, refs, provenance = pages[0].get('characters'), pages[0].get('referencedItemUids'), pages[0].get('statProvenance')
        if not isinstance(chars,list) or not isinstance(refs,list) or (not rows and not chars):
            raise ValueError('尚未观测到装备或角色')
        if any(page.get('characters')!=chars or page.get('referencedItemUids')!=refs or page.get('statProvenance')!=provenance for page in pages):
            raise ValueError('装备分页角色或属性来源不一致')
        refkeys = [uid(ref) for ref in refs]
        if refkeys != sorted(set(refkeys)) or not set(refkeys).issubset(keys):
            raise ValueError('已装备引用未被库存覆盖')
    if kind == 'characters':
        ids = [row.get('character_id') for row in rows]
        if any(type(cid) is not int or cid<=0 for cid in ids) or len(ids)!=len(set(ids)):
            raise ValueError('角色身份重复或无效')
    if 'revision' in header:
        current = core.call('native.snapshot.status', {}, check)
        matches = [row for row in current.get('domains',[]) if isinstance(row,dict) and row.get('domain')==domain]
        if len(matches)!=1 or current.get('providerId')!=header['providerId'] or matches[0].get('ready') is not True or matches[0].get('dirty') is not False or any(matches[0].get(k)!=header[k] for k in ('domainKey','revision')):
            raise ValueError('读取期间游戏数据发生变化，请重试')
    check()
    return {'header':header, 'rows':rows, 'pages':pages}
