"""Shared OCR and screenshot parsing, with honest inferred-field provenance."""
import json
import re
import time
import diagnostics
from pathlib import Path
import cv2
from .upstream.scanner.batch_processor import BatchProcessor
from .upstream.integrations.bundled_resources import bundled_config_dir, bundled_root
from .upstream.integrations.vision.equipment_state_detection import right_panel_button_state_from_image
from .upstream.features.drive_assembly.role_recognition import resolve_role_recognition
from .upstream.scanner.window_capture import crop_window_border_from_image
from .upstream.integrations.vision.screenshot_parser import process_single_image

class VisionEngine:
    def __init__(self, directory):
        self.processor=BatchProcessor(str(directory),config_dir=bundled_config_dir(),ocr_backend_preference='cpu')
        self.ocr=self.processor.ocr_engine
        self.roles=[r['name_zh'] for r in json.loads((bundled_root()/'catalog.json').read_text(encoding='utf-8'))['characters']]

    def parse(self,path):
        started=time.perf_counter();fallback=False
        detector=self.ocr.ocr.text_det
        original=detector.limit_type
        try:
            result=self._parse(path)
            # Sparse/uncertain recognition gets the original enlarged detector.
            # Each worker owns its engine, so this setting is never shared.
            if not result.get('records') or any(len(row.get('sub_attributes') or {})<4 for row in result['records']):
                fallback=True;detector.limit_type='min'
                retry=self._parse(path)
                score=lambda value:sum(len(row.get('sub_attributes') or {}) for row in value.get('records',[]))
                if score(retry)>=score(result):result=retry
            return result
        finally:
            detector.limit_type=original
            diagnostics.event('OCR单图完成',elapsed_ms=round((time.perf_counter()-started)*1000),detail_retry=fallback)

    def _parse(self,path):
        from .upstream.utils.image_io import imread_unicode
        image=imread_unicode(str(path))
        if image is None:raise ValueError('图片无法读取')
        image=crop_window_border_from_image(image)
        full_lines=None
        def get_full_lines():
            nonlocal full_lines
            if full_lines is None:full_lines=self.ocr.extract_lines(image)
            return full_lines
        primary_error=None
        try:
            items=[process_single_image(self.processor,str(path),image=image,full_lines=get_full_lines)]
        except Exception as primary:
            try:items=self.processor.parse_identify_items(str(path))
            except Exception:items=[]
            if not items:primary_error=str(primary)
        # Normal inventory captures need only the equipment panel. Keep the
        # full-scene path for unusual/offline images and reward parsing.
        if full_lines is not None or primary_error:
            lines=get_full_lines()
        else:
            left=int(image.shape[1]*.67)
            lines=self.ocr.extract_lines(image[:,left:])
            lines=[{**line,'box':(line['box'][0]+left,line['box'][1],line['box'][2]+left,line['box'][3])} for line in lines]
            # A missing panel anchor means this may be a nonstandard layout.
            texts={line['text'].strip() for line in lines}
            if not {'主属性','副属性'}.issubset(texts):lines=get_full_lines()
        role=resolve_role_recognition([line['text'] for line in lines],self.roles)
        if primary_error:
            return {'lines':lines,'role':vars(role),'state_candidate':right_panel_button_state_from_image(image),
                    'records':[],'error':primary_error}
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
