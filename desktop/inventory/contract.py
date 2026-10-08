"""Source-independent Keke inventory contract. None always means unobserved."""
from copy import deepcopy

SCHEMA_VERSION = 2
CONTRACT_VERSION = 1
DOMAIN_NAMES = ('equipment','characters','items','team','environment')

def validate_domain(kind, value):
    if kind not in DOMAIN_NAMES or not isinstance(value,dict) or value.get('contract_version')!=CONTRACT_VERSION:
        raise ValueError('库存契约或类别版本无效')
    rows=value.get('records')
    if not isinstance(rows,list) or len(rows)>32768 or any(not isinstance(row,dict) for row in rows):
        raise ValueError('库存记录列表无效')
    if not isinstance(value.get('source'),dict) or not isinstance(value['source'].get('adapter'),str):
        raise ValueError('库存缺少采集来源')
    coverage=value.get('coverage')
    if not isinstance(coverage,dict) or any(coverage.get(k) is not None and type(coverage.get(k)) is not bool for k in ('collection_complete','account_complete')):
        raise ValueError('库存覆盖证明无效')
    if kind=='equipment':
        if coverage.get('collection_complete') is not True:
            raise ValueError('装备全集尚未采集完成，不替换旧库存')
        ids=[]
        for row in rows:
            identity=row.get('instance_id')
            if not isinstance(identity,str) or not identity or len(identity)>256:
                raise ValueError('装备缺少稳定实例ID')
            if row.get('category') not in ('drive','tape','other'):
                raise ValueError('装备分类无效')
            for field in ('is_equipped','is_locked','is_discarded'):
                if row.get(field) is not None and type(row[field]) is not bool:
                    raise ValueError('装备状态必须为已观测布尔值或未知')
            ids.append(identity)
        if len(ids)!=len(set(ids)):
            raise ValueError('装备实例ID重复')
    if kind=='characters':
        ids=[row.get('character_id') for row in rows]
        if any(not isinstance(key,str) or not key for key in ids) or len(ids)!=len(set(ids)):
            raise ValueError('角色身份无效或重复')
    return value


def migrate_document(document):
    """Read-time v1 compatibility. Never rewrites an existing user file."""
    version=document.get('schema_version')
    if type(version) is not int or version not in (1,SCHEMA_VERSION):
        raise ValueError('库存文件来自不支持的版本，原文件已保留')
    result=deepcopy(document)
    if version==SCHEMA_VERSION:
        if not isinstance(result.get('inventory'),dict):
            raise ValueError('库存文件缺少自有契约数据')
        for kind,domain in result['inventory'].items():
            validate_domain(kind,domain)
        return result
    from .adapters.nte import normalize_snapshot
    result['schema_version']=SCHEMA_VERSION
    result['inventory']={kind:normalize_snapshot(kind,raw) for kind,raw in result.get('domains',{}).items()}
    return result
