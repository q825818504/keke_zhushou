"""Real CPU OCR on synthetic Chinese equipment screenshots and public templates."""
import sys,json,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from vision.engine import VisionEngine
from vision.service import VisionService
from vision.upstream.integrations.bundled_resources import bundled_config_dir
from vision.upstream.scanner.ocr_engine import OCREngine
from vision.upstream.scanner.shape_recognizer import ShapeRecognizer
from vision.upstream.features.drive_assembly.role_recognition import resolve_role_recognition
import cv2
result={'samples':[]}
with tempfile.TemporaryDirectory() as tmp:
    engine=VisionEngine(Path(tmp)/'parser')
    for kind in ('drive','tape'):
        start=time.monotonic();data=engine.parse(Path('build/ocr-real-fixtures')/(kind+'.png'))
        assert len(data['records'])==1,(kind,data.get('error'))
        row=data['records'][0];assert row['category']==kind,(kind,row)
        assert row['sub_attributes'].get('攻击力')==48,row
        assert row['sub_attributes'].get('暴击率%')==2.4,row
        assert row['main_attributes'] is None,row
        assert data['role']['role_name']=='娜娜莉',data['role']
        result['samples'].append({'kind':kind,'shape':row['shape'],'sub_attributes':row['sub_attributes'],'role':data['role']['role_name'],'seconds':round(time.monotonic()-start,2)})
    recognizer=engine.processor.shape_recognizer
    for name in recognizer.templates:
        img=cv2.imread(str(bundled_config_dir()/'templates'/(name+'.png')),cv2.IMREAD_GRAYSCALE)
        match=recognizer.recognize(img);assert match['shape_id']==name,match
    result['shape_templates']=len(recognizer.templates)
    # Invoke the actual scanner classes in a fail-closed guard, without game input.
    for mode in ('mouse','new','gamepad'):
        service=VisionService(Path(tmp)/mode)
        def deny(capability):raise PermissionError('fixture denies live input')
        service.guard=deny
        scanner=None
        try:
            scanner=service.make_scanner(mode,str(Path(tmp)/('capture-'+mode)))
            (scanner._input.operation_guard if mode=='mouse' else scanner.operation_guard)('interface_input')
            raise AssertionError('scanner bypassed input guard')
        except PermissionError:pass
    result['scan_input_guard']='all modes deny unauthorized input'
Path('build/vision-real-ocr-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
