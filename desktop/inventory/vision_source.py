"""OCR observations in the shared account view, without native identity synthesis."""
from vision.stat_validation import validate_record

def vision_domain(batch):
    records=[]
    for index,item in enumerate(batch.get('records',[])):
        if not isinstance(item,dict) or item.get('category') not in ('drive','tape'):continue
        row=validate_record(item)
        # An OCR identity belongs only to this batch. Identical stat rolls can be distinct items.
        row['instance_id']='ocr:'+batch['id']+':'+str(item.get('instance_id',index))
        row['native_instance_id']=None
        row['definition_id']=None
        for key in ('is_equipped','is_locked','is_discarded'):
            row[key]=item.get(key) if type(item.get(key)) is bool else None
        row.setdefault('provenance',{})['instance_identity']='scan-local'
        row['evidence']={'batch_id':batch['id'],'image':item.get('image'),'account':batch['account'],
                         'account_uid':batch.get('account_uid')}
        records.append(row)
    return {'contract_version':1,'source':{'adapter':'ocr-scan-v1','snapshot':batch['id'],'mode':batch['mode']},
            'coverage':{'scope':'selected_inventory_list' if batch.get('complete') is True else 'recognized_images',
                        'collection_complete':batch.get('complete') is True,'account_complete':None,
                        'identity_scope':'scan-local','equipment_states_complete':all(type(r.get('is_equipped')) is bool for r in records) if records else False},
            'saved_at':batch.get('saved_at'),'records':records}
