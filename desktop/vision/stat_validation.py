"""Check OCR percentage points against the bundled equipment stat catalog.

Only unambiguous misplaced-decimal corrections are applied. Evidence remains
in parser_result/lines; uncertain values are flagged rather than clamped.
"""
from copy import deepcopy
from functools import lru_cache
import json
import math
from .upstream.integrations.bundled_resources import bundled_config_dir


@lru_cache(maxsize=1)
def catalog():
    return json.loads((bundled_config_dir()/'stats.json').read_text(encoding='utf-8'))


def validate_record(record):
    row=deepcopy(record)
    config=catalog()
    corrections=list((row.get('stat_validation') or {}).get('corrections',[]))
    issues=[]
    area=row.get('cell_count')
    if row.get('category')=='drive' and not area:
        try:
            from .upstream.domain.drive_layout import SHAPE_FOOTPRINTS
            from .upstream.services.sqlite_allocation_inventory import legacy_shape_id
            area=len(SHAPE_FOOTPRINTS[legacy_shape_id(row.get('shape'))])
        except (ValueError,KeyError,RuntimeError):pass
    aliases=config.get('stat_alias_mapping',{})
    for field in ('sub_attributes','main_attributes'):
        values=row.get(field)
        if not isinstance(values,dict):continue
        for name,raw in list(values.items()):
            key=aliases.get(name,name)
            if '%' not in key or not isinstance(raw,(int,float)) or isinstance(raw,bool):continue
            allowed=[]
            if field=='sub_attributes':
                base=config.get('gold_base_values',{}).get(key,0)*10 if row.get('category')=='tape' else (
                    config.get('gold_base_values',{}).get(key,0)*area if isinstance(area,int) and 2<=area<=4 else None)
                if base:allowed=[round(base*scale,4) for scale in (1,.8,.6)]
            elif row.get('category')=='tape':
                maximum=config.get('tape_main_stat_values',{}).get(key)
                if maximum:
                    if math.isfinite(raw) and 0<=raw<=maximum+.03:continue
                    if row.get('level')==20:allowed=[maximum]
                    else:
                        issues.append({'field':field,'stat':name,'value':raw,'reason':'outside_catalog_range'})
                        continue
            if not allowed:continue
            if math.isfinite(raw) and any(abs(raw-value)<=.03 for value in allowed):continue
            candidates={round(raw/divisor,4) for divisor in (10,100,1000)
                        if math.isfinite(raw) and raw>max(allowed)+.03
                        and any(abs(raw/divisor-value)<=.03 for value in allowed)}
            if len(candidates)==1:
                corrected=candidates.pop();values[name]=corrected
                corrections.append({'field':field,'stat':name,'from':raw,'to':corrected})
            else:issues.append({'field':field,'stat':name,'value':raw,'reason':'not_in_catalog_values'})
    row['stat_validation']={'catalog':'bundled-equipment-stats','corrections':corrections,'issues':issues,'valid':not issues}
    row['usable_for_calculation']=not issues
    return row
