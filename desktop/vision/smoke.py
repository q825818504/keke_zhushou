"""Actual packaged model/parser acceptance without game input or player storage."""
import json,tempfile,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from .engine import VisionEngine
from .upstream.integrations.bundled_resources import bundled_config_dir,bundled_ocr_model_dir
from .upstream.integrations.ocr_model_resources import validate_ocr_model_directory

def check_bundle():
    validate_ocr_model_directory(bundled_ocr_model_dir())
    with tempfile.TemporaryDirectory() as tmp:
        engine=VisionEngine(Path(tmp)/'parser');rows=[]
        for kind in ('drive','tape'):
            img=Image.new('RGB',(2560,1440),(24,26,30));draw=ImageDraw.Draw(img)
            font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',30)
            draw.text((100,100),'娜娜莉',font=font,fill='white')
            if kind=='drive':
                with Image.open(bundled_config_dir()/'templates/H_2.png') as icon:img.paste(icon.convert('RGB').resize((250,240)),(1762,350))
                draw.text((2000,330),'驱动块',font=font,fill='white');top=819
            else:
                draw.text((2000,330),'森林萤火之心卡带',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20),fill='white')
                draw.text((1813,660),'攻击力',font=font,fill='white');top=758
            for i,text in enumerate(['攻击力 48','暴击率 2.4%','暴击伤害 4.8%','防御力 25']):draw.text((1811,top+i*55),text,font=font,fill='white')
            path=Path(tmp)/(kind+'.png');img.save(path);start=time.monotonic();result=engine.parse(path)
            record=result['records'][0]
            if record['category']!=kind or record['sub_attributes'].get('攻击力')!=48 or record['sub_attributes'].get('暴击率%')!=2.4 or result['role']['role_name']!='娜娜莉':raise ValueError('打包OCR样例识别不一致')
            rows.append({'category':kind,'shape':record['shape'],'seconds':round(time.monotonic()-start,2)})
        from .upstream.integrations.vision.mouse_scan_runtime import require_mouse_scan_runtime
        runtime=require_mouse_scan_runtime()
        return {'ok':True,'models':3,'templates':len(engine.processor.shape_recognizer.templates),'samples':rows,'mouse_runtime':runtime.ok,'external_nte_components':False}
