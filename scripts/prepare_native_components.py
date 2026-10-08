"""Build-time import of an exact, pinned native bundle for local previews."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
def prepare(source):
    identity=json.loads((ROOT/'desktop/native/component-identity.json').read_text(encoding='utf-8'))
    source=Path(source).resolve()
    if (source/'_internal/component-bundle.json').is_file():source=source/'_internal'
    manifest=json.loads((source/'component-bundle.json').read_text(encoding='utf-8'))
    if manifest.get('layout')!=identity['layout']:raise ValueError('Native bundle layout mismatch')
    for name, expected in identity['files'].items():
        with (source/name).open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:raise ValueError('Pinned component mismatch: '+name)
    output=ROOT/'build/native-components';output.mkdir(parents=True,exist_ok=True)
    for name in identity['files']:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/name,target)
    shutil.copy2(source/'component-bundle.json',output/'component-bundle.json')
    print('Verified native bundle: '+str(output))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');prepare(parser.parse_args().source)
