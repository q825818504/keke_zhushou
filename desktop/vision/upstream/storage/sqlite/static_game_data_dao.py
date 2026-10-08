import json
from vision.upstream.integrations.bundled_resources import bundled_root
class StaticGameDataDao:
    def __init__(self,*args,**kwargs):self.data=json.loads((bundled_root()/'catalog.json').read_text(encoding='utf-8'))
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def list_shapes(self):return self.data['shapes']
    def list_suits(self):return self.data['suits']
