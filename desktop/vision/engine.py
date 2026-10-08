"""Shared OCR and screenshot parsing, with honest inferred-field provenance."""
import json
import re
from pathlib import Path
import cv2
from .upstream.scanner.batch_processor import BatchProcessor
from .upstream.integrations.bundled_resources import bundled_config_dir, bundled_root
from .upstream.integrations.vision.equipment_state_detection import right_panel_button_state_from_image
from .upstream.features.drive_assembly.role_recognition import resolve_role_recognition

class VisionEngine:
    def __init__(self, directory):
        self.processor=BatchProcessor(str(directory),config_dir=bundled_config_dir(),ocr_backend_preference='cpu')
        self.ocr=self.processor.ocr_engine
        self.roles=[r['name_zh'] for r in json.loads((bundled_root()/'catalog.json').read_text(encoding='utf-8'))['characters']]

    def parse(self,path):
        from .upstream.utils.image_io import imread_unicode
        image=imread_unicode(str(path))
        if image is None:raise ValueError('图片无法读取')
        lines=self.ocr.extract_lines(image)
        role=resolve_role_recognition([line['text'] for line in lines],self.roles)
        try:
            items=[self.processor._process_single_image(str(path))]
        except Exception as primary:
            try:items=self.processor.parse_identify_items(str(path))
            except Exception:items=[]
            if not items:
                return {'lines':lines,'role':vars(role),'state_candidate':right_panel_button_state_from_image(image),
                        'records':[],'error':str(primary)}
        records=[self.normalize(item) for item in items]
        if len(records)==1:
            main,level=read_visible_panel_fields(lines,image.shape[1])
            records[0]['main_attributes']=main
            records[0]['level']=level
            records[0]['provenance']['main_attributes']='ocr' if main else 'unknown'
            records[0]['provenance']['level']='ocr' if level is not None else 'unknown'
        return {'lines':lines,'role':vars(role),'state_candidate':right_panel_button_state_from_image(image),
                'records':records}

    @staticmethod
    def normalize(item):
        raw=item.model_dump() if hasattr(item,'model_dump') else dict(item)
        for field in ('role_scores','max_score','is_mvp','pick_order'):raw.pop(field,None)
        return {'category':raw['item_type'],'name':raw.get('set_name') or raw.get('shape_id'),
                'shape':raw.get('shape_id'),'cell_count':raw.get('area'),'rarity_candidate':raw.get('quality'),
                'level':None,'is_locked':None,'is_discarded':None,'is_equipped':None,
                'main_attributes':None,'sub_attributes':raw.get('sub_stats',{}),
                'inferred_main_attributes':raw.get('main_stats'),
                'provenance':{'instance_identity':'scan-local','main_attributes':'upstream parser inference or label only',
                              'rarity':'upstream candidate','sub_attributes':'ocr'},'parser_result':raw}


def read_visible_panel_fields(lines, width):
    """Pair visible main-stat labels and values only inside the right panel.

    Separate OCR boxes are matched by their row. Never substitute the source
    parser's maximum-level values for the values visible in the screenshot.
    """
    panel=[line for line in lines if line.get('box') and line['box'][0]>=width*.67]
    mains=[line for line in panel if line['text'].strip()=='主属性']
    subs=[line for line in panel if line['text'].strip()=='副属性']
    if len(mains)!=1 or len(subs)!=1:return None,None
    top,bottom=mains[0]['box'][3],subs[0]['box'][1]
    if top>=bottom:return None,None
    rows=[line for line in panel if top<=line['box'][1] and line['box'][3]<=bottom]
    from .upstream.domain.stat_catalog import StatCatalog
    catalog=StatCatalog.from_config_dir(bundled_config_dir())
    attributes={}
    numeric=re.compile(r'\d+(?:\.\d+)?%?')
    for line in rows:
        text=line['text'].strip()
        if numeric.fullmatch(text):continue
        label=catalog.normalize_stat_name(text,cutoff=1.0)
        if label is None:continue
        box=line['box'];center=(box[1]+box[3])/2
        values=[other for other in rows if other['box'][0]>=box[2]
                and abs((other['box'][1]+other['box'][3])/2-center)<=max(5,(box[3]-box[1])/2)
                and numeric.fullmatch(other['text'].strip())]
        if len(values)!=1:continue
        value=values[0]['text'].strip()
        key=catalog.normalize_stat_name(text,is_percent=value.endswith('%'),cutoff=1.0)
        if key:attributes[key]=float(value.rstrip('%'))
    levels=[int(line['text'].strip()[1:]) for line in panel
            if line['box'][3]<mains[0]['box'][1] and re.fullmatch(r'\+\d{1,2}',line['text'].strip())]
    level=levels[0] if len(levels)==1 and 0<=levels[0]<=20 else None
    return attributes or None,level
