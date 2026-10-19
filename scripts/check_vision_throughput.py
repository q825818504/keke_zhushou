"""Large durable-path scan regressions, without game input or real player data."""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from vision.service import VisionService


def check(mode):
    count=1500
    captured=threading.Event();release=threading.Event();checkpoint_entered=threading.Event()
    samples=[]
    class SlowEngine:
        def __init__(self,*args):pass
        def parse(self,path):
            if not release.wait(10):raise RuntimeError('fixture OCR timeout')
            return {'records':[{'category':'drive','name':'fixture'}],
                    'lines':[{'text':'fixture original OCR evidence '*40}]}
    class BurstScanner:
        def __init__(self,_mode,directory,guard):self.directory=Path(directory)
        def start_scan(self,total,on_capture,**kwargs):
            started=time.perf_counter()
            for index in range(total):
                path=self.directory/f'{index:05d}.png'
                path.write_bytes(b'fixture file; injected engine does not decode pixels')
                on_capture(path)
                if index==0 and not checkpoint_entered.wait(3):raise RuntimeError('checkpoint did not run')
                if index in (99,total-1):
                    before=time.perf_counter()
                    status=service.status(compact=True)
                    samples.append((len(json.dumps(status)),time.perf_counter()-before))
            elapsed=time.perf_counter()-started
            captured.set()
            if not release.wait(10):raise RuntimeError('fixture release timeout')
            samples.append(elapsed)
            return total
    with tempfile.TemporaryDirectory() as directory:
        service=VisionService(directory,engine_factory=SlowEngine,scanner_factory=BurstScanner)
        service.guard=lambda capability:service.check_capture()
        service.CHECKPOINT_INTERVAL=.001
        write=service._write
        def blocked_write(path,value):
            if value.get('images') and value.get('state')=='pending':
                checkpoint_entered.set()
                if not release.wait(10):raise RuntimeError('fixture disk timeout')
            return write(path,value)
        keyboard=SimpleNamespace(add_hotkey=lambda *args:1,remove_hotkey=lambda *args:None)
        with patch.dict(sys.modules,{'keyboard':keyboard}),patch('vision.service.time.sleep'),patch.object(service,'_write',side_effect=blocked_write):
            service.start(mode,'fixture',count=count,account_uid='123456789012')
            try:
                assert captured.wait(5),f'{mode} capture stalled behind OCR or checkpoint I/O'
                status=service.status(compact=True)
                assert status['job']['captured']==count,status['job']
                assert status['job']['processed']==0,'OCR fixture must still be blocked'
                assert status['batch']['images']==[] and status['batch']['records']==[]
                assert abs(samples[1][0]-samples[0][0])<128,samples
                assert all(size<4096 and elapsed<.25 for size,elapsed in samples),samples
            finally:release.set()
            service.thread.join(15)
            assert not service.thread.is_alive()
            batch=service.status()['batch']
            assert batch['complete'] and len(batch['records'])==count,batch.get('state')
            saved=service.load('fixture',batch['id'])
            assert len(saved['images'])==count and len(saved['records'])==count
            print(f'{mode}: {count} synthetic captures in {samples[-1]:.3f}s with OCR and checkpoint blocked; '
                  f'progress {samples[0][0]} -> {samples[1][0]} bytes; final evidence restored.')


if __name__=='__main__':
    for mode in ('mouse','gamepad'):check(mode)
