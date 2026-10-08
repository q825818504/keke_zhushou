"""Copy and verify public RapidOCR model resources into the independent bundle."""
import hashlib,json,shutil,sys
from pathlib import Path
import rapidocr_onnxruntime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
from vision.upstream.integrations.ocr_model_resources import OCR_MODEL_SPECS,validate_ocr_model_directory
source=Path(rapidocr_onnxruntime.__file__).parent/'models'
target=ROOT/'desktop/vision/resources/models';target.mkdir(parents=True,exist_ok=True)
manifest=[]
for spec in OCR_MODEL_SPECS:
    path=source/spec.filename
    if not path.is_file():raise RuntimeError('Installed RapidOCR lacks '+spec.filename)
    shutil.copy2(path,target/spec.filename)
    manifest.append({'filename':spec.filename,'size':spec.size_bytes,'sha256':spec.sha256,'source':'rapidocr-onnxruntime==1.4.4'})
validate_ocr_model_directory(target)
(target.parent/'model-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Verified three independent OCR models.')
