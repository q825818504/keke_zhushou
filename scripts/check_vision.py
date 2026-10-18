"""Vision pipeline regressions using images and injected capture, no game input."""
import sys,json,tempfile,base64,io,unittest,time,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from vision.service import VisionService
from runtime import public_server

FIXTURE_UID='123456789012'

class VisionTestService(VisionService):
    def start(self,mode,account,count=None,files=None,batch_id=None,account_uid=None):
        return super().start(mode,account,count,files,batch_id,account_uid or FIXTURE_UID)

def image_payload():
    stream=io.BytesIO();Image.new('RGB',(240,160),'white').save(stream,format='PNG')
    return {'data':base64.b64encode(stream.getvalue()).decode()}

class Engine:
    def __init__(self,*args):self.fail=False
    def parse(self,path):
        if self.fail:raise ValueError('fixture OCR failure')
        return {'records':[{'category':'drive','name':'<script>fixture</script>','sub_attributes':{'攻击力':48}}],
                'lines':[{'text':'攻击力48','confidence':.99,'box':[1,1,90,20]}]}

class Scanner:
    def __init__(self,mode,directory,guard):self.directory=Path(directory);self.guard=guard;self._stopped=False
    def start_scan(self,count=None,on_capture=None,commit_on_complete=True):
        self.guard('interface_input')
        for index in range(count or 2):
            path=self.directory/f'scan_{index:04d}.png';Image.new('RGB',(240,160),'white').save(path)
            if on_capture:on_capture(str(path),index+1,count or 2)
        return count or 2

class VisionTests(unittest.TestCase):
    def service(self,tmp):return VisionTestService(tmp,engine_factory=Engine,scanner_factory=Scanner)
    def done(self,service):
        service.thread.join(timeout=5);self.assertFalse(service.status()['job']['running']);return service.status()['batch']

    def test_atomic_write_retries_permission_error_and_preserves_previous_json(self):
        import os
        replace=os.replace
        with tempfile.TemporaryDirectory() as tmp:
            service=self.service(tmp);path=Path(tmp)/'batch.json'
            service._write(path,{'old':True})
            attempts=[]
            def transient(source,target):
                attempts.append(1)
                if len(attempts)<3:
                    self.assertEqual(json.loads(path.read_text()),{'old':True})
                    raise PermissionError('fixture shared read handle')
                return replace(source,target)
            with patch('vision.service.os.replace',side_effect=transient),patch('vision.service.time.sleep'):
                service._write(path,{'new':True})
            self.assertEqual(len(attempts),3)
            self.assertEqual(json.loads(path.read_text()),{'new':True})
            with patch('vision.service.os.replace',side_effect=PermissionError('locked')),patch('vision.service.time.sleep'):
                with self.assertRaises(PermissionError):service._write(path,{'lost':True})
            self.assertEqual(json.loads(path.read_text()),{'new':True})
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

    def test_120_gamepad_captures_survive_failed_progress_checkpoints(self):
        import itertools
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            service=self.service(tmp);service.guard=lambda capability:service.check_capture()
            write=service._write;failures=[]
            def checkpoint(path,value):
                if value.get('images') and value.get('state')=='pending':
                    failures.append(1);raise PermissionError('fixture occupied checkpoint')
                return write(path,value)
            with patch.object(service,'_write',side_effect=checkpoint),patch('vision.service.time.monotonic',side_effect=itertools.count()):
                service.start('gamepad','A',count=120);batch=self.done(service)
            self.assertTrue(failures,'fixture must exercise checkpoint failures')
            self.assertTrue(batch['complete']);self.assertTrue(batch['capture_complete'])
            self.assertEqual(len(batch['images']),120);self.assertEqual(len(batch['records']),120)
            self.assertTrue(service.load('A',batch['id'])['complete'])

    def test_gamepad_capture_does_not_wait_for_slow_ocr_after_32_images(self):
        captured=threading.Event();release=threading.Event()
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        class SlowEngine(Engine):
            def parse(self,path):
                if not release.wait(10):raise RuntimeError('fixture OCR timeout')
                return super().parse(path)
        class BurstScanner(Scanner):
            def start_scan(self,*args,**kwargs):
                count=super().start_scan(*args,**kwargs);captured.set();return count
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            service=VisionTestService(tmp,engine_factory=SlowEngine,scanner_factory=BurstScanner)
            service.guard=lambda capability:service.check_capture()
            service.start('gamepad','A',count=45)
            try:self.assertTrue(captured.wait(3),'controller stalled behind the OCR queue')
            finally:release.set()
            batch=self.done(service)
            self.assertEqual(len(batch['images']),45)
            self.assertEqual(len(batch['records']),45)
            self.assertTrue(batch['capture_complete'])

    def test_gamepad_fast_png_retains_original_pixels(self):
        from vision.gamepad_scanner import GamepadScanner
        pixels=bytes([20,80,140,255,0,128]*12)
        with tempfile.TemporaryDirectory() as tmp:
            scanner=GamepadScanner.__new__(GamepadScanner);scanner.capture_dir=tmp
            frame=SimpleNamespace(rgb=pixels,size=(6,4))
            with patch('vision.gamepad_scanner.capture_foreground_window',return_value=(frame,None)):
                filename=scanner.capture_panel(None,1)
            with Image.open(filename) as image:
                self.assertEqual(image.size,(6,4));self.assertEqual(image.tobytes(),pixels)

    def test_gamepad_adapter_removes_only_duplicate_countdown(self):
        from vision.gamepad_scanner import GamepadScanner, UpstreamGamepadScanner
        from vision.upstream.scanner.gamepad_controller import DEFAULT_SCAN_PROFILE
        def initialize(scanner,*args,**kwargs):scanner.action_profile=DEFAULT_SCAN_PROFILE
        with patch.object(UpstreamGamepadScanner,'__init__',initialize):
            scanner=GamepadScanner('fixture')
        self.assertEqual(scanner.action_profile.takeover_countdown_seconds,0)
        self.assertEqual(scanner.action_profile.move_hold_seconds,DEFAULT_SCAN_PROFILE.move_hold_seconds)
        self.assertEqual(scanner.action_profile.move_settle_seconds,DEFAULT_SCAN_PROFILE.move_settle_seconds)
        self.assertEqual(scanner.action_profile.row_move_settle_seconds,DEFAULT_SCAN_PROFILE.row_move_settle_seconds)

    def test_offline_duplicate_equipment_retained_and_accounts_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp);s.start('offline','A',files=[image_payload(),image_payload()]);b=self.done(s)
            self.assertEqual(len(b['records']),2)
            self.assertNotEqual(b['records'][0]['instance_id'],b['records'][1]['instance_id'])
            self.assertFalse(b['complete']);self.assertEqual(s.history('B'),[])
            self.assertEqual(s.load('A',b['id'])['records'],b['records'])
            self.assertTrue(s.image('A',b['id'],b['images'][0]['file']).is_file())
            with self.assertRaises(ValueError):s.image('A',b['id'],'../batch.json')

    def test_failure_retry_and_manual_correction_preserve_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp);engine=Engine();engine.fail=True;s.engine=engine
            s.start('offline','A',files=[image_payload()]);b=self.done(s)
            self.assertEqual(b['state'],'partial');self.assertEqual(b['records'],[])
            engine.fail=False;s.start('retry','A',batch_id=b['id']);b=self.done(s)
            identity=b['records'][0]['instance_id']
            corrected=s.correct('A',b['id'],0,{'category':'tape','instance_id':'forged','name':'修正'})
            self.assertEqual(corrected['records'][0]['instance_id'],identity)
            self.assertTrue(corrected['records'][0]['manually_corrected'])
            self.assertEqual(corrected['images'][0]['records'][0],corrected['records'][0])

    def test_all_capture_modes_and_completion_gate(self):
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        for mode in ('mouse','new','gamepad'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
                s=self.service(tmp);s.guard=lambda capability:s.check()
                s.start(mode,'A',count=3);b=self.done(s)
                self.assertEqual(len(b['records']),2 if mode=='new' else 3)
                self.assertEqual(b['complete'],mode!='new')

    def test_incomplete_capture_and_cancellation_do_not_claim_complete(self):
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            s=self.service(tmp);s.guard=lambda capability:s.check()
            class Incomplete(Scanner):
                def start_scan(self,count=None,on_capture=None,commit_on_complete=True):return super().start_scan(1)
            s.scanner_factory=Incomplete;s.start('mouse','A',count=3);b=self.done(s)
            self.assertFalse(b['complete']);self.assertEqual(b['state'],'partial');self.assertEqual(len(b['images']),1)
            self.assertEqual(len(b['records']),1);self.assertIn('未覆盖',b['capture_error'])
            with self.assertRaisesRegex(ValueError,'没有失败'):s.start('retry','A',batch_id=b['id'])
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp)
            class CancelEngine(Engine):
                def parse(self,path):s.stop.set();return super().parse(path)
            s.engine_factory=CancelEngine;s.start('offline','A',files=[image_payload(),image_payload()]);b=self.done(s)
            self.assertEqual(b['state'],'cancelled');self.assertFalse(b['complete'])
            self.assertEqual(len(b['records']),1)

    def test_capture_exception_automatically_parses_nested_images(self):
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            s=self.service(tmp);s.guard=lambda capability:s.check()
            class Interrupted(Scanner):
                def start_scan(self,count=None,on_capture=None,commit_on_complete=True):
                    nested=self.directory/'capture';nested.mkdir()
                    for index in range(3):Image.new('RGB',(240,160),'white').save(nested/f'scan_{index:04d}.png')
                    raise ValueError('第4件面板不稳定')
            s.scanner_factory=Interrupted;s.start('mouse','A',count=67);b=self.done(s)
            self.assertEqual(len(b['records']),3);self.assertFalse(b['complete'])
            self.assertEqual(b['capture_error'],'第4件面板不稳定');self.assertEqual(b['state'],'partial')
            self.assertFalse(any(image.get('error') for image in b['images']))
            self.assertIn('第4件面板不稳定',s.status()['job']['message'])

    def test_ocr_finishes_first_image_before_capture_finishes(self):
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        parsed=threading.Event();observed=[]
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            service=self.service(tmp);service.guard=lambda capability:service.check()
            class LiveEngine(Engine):
                def parse(self,path):
                    result=super().parse(path);parsed.set();return result
            class LiveScanner(Scanner):
                def start_scan(self,count=None,on_capture=None,commit_on_complete=True):
                    path=self.directory/'first.png';Image.new('RGB',(240,160),'white').save(path)
                    on_capture(str(path),1,count)
                    if not parsed.wait(2):raise RuntimeError('OCR did not start until acquisition finished')
                    deadline=time.monotonic()+2
                    while time.monotonic()<deadline:
                        live=service.status()
                        if live['batch']['records']:
                            observed.append(live['job']['running']);break
                        threading.Event().wait(.01)
                    return 1
            service.engine_factory=LiveEngine;service.scanner_factory=LiveScanner
            service.start('mouse','A',count=1);b=self.done(service)
            self.assertEqual(observed,[True]);self.assertEqual(len(b['records']),1);self.assertTrue(b['complete'])

    def test_new_without_tags_saves_no_probe_or_evidence(self):
        import numpy as np
        from vision.upstream.scanner.drone_scanner import DroneScanner
        scanner=object.__new__(DroneScanner);scanner._stopped=False
        scanner._reset_inventory_to_top=lambda:None
        with tempfile.TemporaryDirectory() as tmp:
            scanner.output_dir=tmp
            screenshot=np.zeros((160,240,4),dtype=np.uint8)
            scanner._apply_window_rect=lambda rect:None
            scanner._find_new_tags=lambda image:[]
            scanner._is_bottom_reached=lambda image:True
            from unittest.mock import MagicMock
            context=MagicMock();context.__enter__.return_value=context
            with patch('vision.upstream.scanner.drone_scanner.mss.MSS',return_value=context),patch('vision.upstream.scanner.drone_scanner.capture_foreground_window',return_value=(screenshot,None)),patch('vision.upstream.scanner.drone_scanner.time.sleep'):
                calls=[];self.assertEqual(scanner.start_scan(on_capture=lambda *args:calls.append(args)),0)
            self.assertEqual(calls,[]);self.assertEqual(list(Path(tmp).glob('*.png')),[])

    def test_empty_new_batch_does_not_initialize_ocr_and_reports_no_new(self):
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            service=self.service(tmp);service.guard=lambda capability:service.check()
            class Empty(Scanner):
                def start_scan(self,on_capture=None):return 0
            service.scanner_factory=Empty
            service.engine_factory=lambda directory: (_ for _ in ()).throw(AssertionError('empty batch must not initialize OCR'))
            service.start('new','A');batch=self.done(service)
            self.assertEqual(batch['images'],[]);self.assertEqual(batch['records'],[])
            self.assertEqual(batch['state'],'parsed');self.assertFalse(batch['complete'])
            self.assertIn('未发现新增装备',service.status()['job']['message'])

    def test_scrollbar_reset_and_scroll_feedback(self):
        import numpy as np
        from vision.mouse_scanner import detect_scroll_thumb,VerifiedMouseScanner
        from vision.upstream.integrations.vision.mouse_scan_capture import MouseCapturedFrame
        from vision.upstream.scanner.window_capture import WindowRect
        from vision.upstream.integrations.vision.mouse_inventory_scan import MouseScanSlot,MouseInventoryScanError
        from unittest.mock import Mock
        def frame(thumb_top):
            image=np.zeros((900,1600,3),dtype=np.uint8)
            image[thumb_top:thumb_top+18,1066:1071]=180
            return MouseCapturedFrame(image,WindowRect(0,0,1600,900),1)
        top,middle=frame(149),frame(400)
        self.assertTrue(detect_scroll_thumb(top.image).at_top)
        self.assertFalse(detect_scroll_thumb(middle.image).at_top)
        scanner=object.__new__(VerifiedMouseScanner)
        scanner._stopped=False;scanner.expected_count=1431;scanner._sleep=lambda duration:None
        scanner._input=Mock();scanner._capture_frame=lambda:top
        scanner._drag_inventory_list_to_top(middle)
        self.assertEqual(scanner._input.drag.call_count,1)
        self.assertEqual(scanner._input.drag.call_args.args[0][0],1067)
        scanner._input.reset_mock();scanner._drag_inventory_list_to_top(top)
        scanner._input.drag.assert_not_called()
        from vision.upstream.integrations.vision.mouse_inventory_scan import MouseInventoryLayout
        scanner.layout=MouseInventoryLayout();scanner.scroll_command_count=0;scanner.scroll_amounts=[]
        scanner._capture_frame=lambda:middle
        with patch('vision.mouse_scanner.detect_selected_card_center_y',side_effect=[390,202,202]):
            _,_,offset,bottom=scanner._scroll_to_next_page(middle,MouseScanSlot(28,0,3,6))
        self.assertFalse(bottom);self.assertEqual(offset,1)
        self.assertEqual(scanner._input.scroll.call_count,2)
        with patch('vision.mouse_scanner.detect_selected_card_center_y',return_value=None):
            with self.assertRaisesRegex(MouseInventoryScanError,'无法定位'):scanner._scroll_to_next_page(middle,MouseScanSlot(28,0,3,6))

    def test_f8_stops_capture_but_drains_all_saved_images(self):
        captured=threading.Event();release_ocr=threading.Event();hotkeys={}
        keyboard=SimpleNamespace(add_hotkey=lambda key,callback:hotkeys.setdefault(key,callback),remove_hotkey=lambda *args:None)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'):
            service=self.service(tmp);service.guard=lambda capability:service.check_capture()
            class SlowEngine(Engine):
                def parse(self,path):
                    if not release_ocr.wait(3):raise RuntimeError('fixture timeout')
                    return super().parse(path)
            class WaitingScanner(Scanner):
                def start_scan(self,count=None,on_capture=None,commit_on_complete=True):
                    for index in range(3):
                        path=self.directory/f'scan_{index:04d}.png';Image.new('RGB',(240,160),'white').save(path)
                        on_capture(str(path),index+1,count)
                    captured.set()
                    if not service.capture_stop.wait(3):raise RuntimeError('capture did not stop')
                    return 0
            service.engine_factory=SlowEngine;service.scanner_factory=WaitingScanner
            service.start('mouse','A',count=1431)
            self.assertTrue(captured.wait(3));hotkeys['f8']()
            self.assertFalse(service.stop.is_set());self.assertTrue(service.status()['job']['running'])
            with self.assertRaisesRegex(Exception,'停止采集'):service.check_capture()
            release_ocr.set();batch=self.done(service)
            self.assertEqual(len(batch['records']),3);self.assertEqual(len(batch['images']),3)
            self.assertFalse(any(row.get('pending') or row.get('error') for row in batch['images']))
            self.assertFalse(batch['complete']);self.assertTrue(batch['capture_stopped'])
            self.assertEqual(service.status()['job']['total'],3)
            self.assertEqual(batch['state'],'partial')

    def test_each_scan_has_its_own_local_folder_and_history_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=self.service(tmp);service.start('offline','A',files=[image_payload()]);first=self.done(service)
            service.start('offline','A',files=[image_payload()]);second=self.done(service)
            first_path=Path(first['storage']['images_directory']);second_path=Path(second['storage']['images_directory'])
            self.assertNotEqual(first_path,second_path)
            self.assertTrue((first_path/'00000.png').is_file());self.assertTrue((second_path/'00000.png').is_file())
            self.assertEqual(service.load('A',first['id'])['storage']['images_directory'],str(first_path))
            with self.assertRaises(ValueError):service.open_folder('A','../arbitrary')

    def test_input_privilege_preflight(self):
        from vision.windows_access import require_matching_input_privilege
        from unittest.mock import Mock
        kernel=Mock();kernel.GetCurrentProcess.return_value=1
        for values in ([False],[True,True],[True,False]):
            with patch('vision.windows_access.ctypes.WinDLL',return_value=kernel),patch('vision.windows_access.process_is_elevated',side_effect=values):
                if values==[True,False]:
                    with self.assertRaisesRegex(PermissionError,'管理员'):require_matching_input_privilege(2)
                else:require_matching_input_privilege(2)

    def test_actual_main_values_are_read_from_their_own_rows(self):
        from vision.engine import read_visible_panel_fields
        lines=[{'text':text,'box':box} for text,box in [
            ('+0',[1250,260,1300,280]),('主属性',[1100,380,1150,405]),
            ('攻击力',[1130,415,1190,437]),('8',[1470,415,1490,437]),
            ('生命值',[1130,452,1190,476]),('112',[1450,452,1490,476]),
            ('副属性',[1100,490,1150,510]),('伤害增加2.00%',[1130,590,1300,615]),
            ('+20',[800,260,850,280])]]
        self.assertEqual(read_visible_panel_fields(lines,1600),({'攻击力':8.0,'生命值':112.0},0))
        self.assertEqual(read_visible_panel_fields(lines[:1],1600),(None,None))

    def test_bad_upload_count_and_mode_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp)
            for mode,count in [('mouse',0),('gamepad',True),('arbitrary',2)]:
                with self.assertRaises(ValueError):s.start(mode,'A',count)
            with self.assertRaises(ValueError):s.start('offline','A',files=[{'data':'bad$'}])
            with self.assertRaises(ValueError):s.start('offline','',files=[image_payload()])

    def test_new_batches_require_valid_manual_uid(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=VisionService(tmp,engine_factory=Engine)
            with self.assertRaisesRegex(ValueError,'UID'):
                service.start('offline','A',files=[image_payload()])
            with self.assertRaisesRegex(ValueError,'UID'):
                service.start('offline','A',files=[image_payload()],account_uid='12x')

    def test_http_upload_security_and_image_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.service(tmp);server=public_server(Path('build/desktop/public'),0,vision=s)
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start();base='http://127.0.0.1:'+str(server.server_port)
            try:
                status=json.load(urlopen(base+'/vision/status'))
                headers={'Content-Type':'application/json','Origin':base,'X-Keke-Inventory':status['token']}
                with self.assertRaises(HTTPError):urlopen(Request(base+'/vision/start',data=b'{}',headers={'Content-Type':'application/json'}))
                body={'mode':'offline','account':'A','account_uid':FIXTURE_UID,'files':[image_payload()]}
                json.load(urlopen(Request(base+'/vision/start',data=json.dumps(body).encode(),headers=headers)))
                b=self.done(s)
                self.assertEqual(json.load(urlopen(base+'/vision/batch?account=A&id='+b['id']))['id'],b['id'])
                self.assertTrue(urlopen(base+'/vision/image?account=A&id='+b['id']+'&name=00000.png').read().startswith(b'\x89PNG'))
                with patch('vision.service.os.startfile') as open_directory:
                    payload=json.dumps({'account':'A','id':b['id']}).encode()
                    self.assertTrue(json.load(urlopen(Request(base+'/vision/open-folder',data=payload,headers=headers)))['opened'])
                    open_directory.assert_called_once_with(b['storage']['images_directory'])
                self.assertFalse(json.load(urlopen(Request(base+'/vision/stop-capture',data=b'{}',headers=headers)))['job']['running'])
                with self.assertRaises(HTTPError):urlopen(base+'/vision/image?account=A&id='+b['id']+'&name=../batch.json')
            finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main(verbosity=2)
