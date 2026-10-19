import json
from vision.upstream.integrations.bundled_resources import bundled_root


class StaticGameDataError(RuntimeError):
    pass


class StaticGameDataDao:
    def __init__(self,*args,**kwargs):
        try:
            self.data=json.loads((bundled_root()/'catalog.json').read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise StaticGameDataError('静态角色与装备目录不可用') from error
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def list_shapes(self):return self.data['shapes']
    def list_suits(self):return self.data['suits']
    def list_role_template_characters(self):
        """Provide OCR name candidates from the bundled public character catalog."""
        seen=set();rows=[]
        for character in self.data.get('characters',[]):
            name=str(character.get('name_zh') or '').strip()
            if name and name not in seen:
                rows.append({'name_zh':name});seen.add(name)
        return rows
