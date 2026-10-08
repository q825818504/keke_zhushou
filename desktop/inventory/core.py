"""NDJSON RPC transport. Never exposes arbitrary RPC methods to the web page."""
import json
import queue
import subprocess
import threading
import time
from collections import deque

class Core:
    def __init__(self, executable, pid, data_dir=None):
        command = [str(executable), 'serve-native', '--stdio', '--game-pid', str(pid)]
        if data_dir is not None and data_dir.is_dir():
            command += ['--data-dir', str(data_dir)]
        self.process = subprocess.Popen(command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.messages = queue.Queue(maxsize=128)
        self.stderr_tail = deque(maxlen=12)
        self.sequence = 0
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._drain, daemon=True).start()
        try:
            self.hello = self.call('core.hello', {'client_name':'KekeAssistant', 'client_version':'0.1', 'protocol_min':1, 'protocol_max':1})
        except Exception as error:
            self.close()
            detail = ' / '.join(self.stderr_tail)
            raise RuntimeError(str(error) + ('；' + detail if detail else '')) from error
        if self.hello.get('protocol_version') != 1:
            self.close()
            raise ValueError('采集组件协议版本不兼容')

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(8 * 1024 * 1024 + 1)
                if not line:
                    break
                if len(line) > 8 * 1024 * 1024:
                    raise ValueError('采集响应超过单页限制')
                value = json.loads(line)
                if isinstance(value, dict) and 'id' in value:
                    self.messages.put(value, timeout=1)
        except Exception as error:
            self.messages.put({'transport_error':str(error)})
        finally:
            try:
                self.messages.put_nowait({'transport_error':'采集连接已关闭'})
            except queue.Full:
                pass

    def _drain(self):
        for line in self.process.stderr:
            self.stderr_tail.append(line.strip()[:500])

    def call(self, method, params, check=lambda: None, timeout=15):
        check()
        self.sequence += 1
        request_id = self.sequence
        self.process.stdin.write(json.dumps({'jsonrpc':'2.0', 'id':request_id, 'method':method, 'params':params}) + '\n')
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            check()
            try:
                value = self.messages.get(timeout=.1)
            except queue.Empty:
                continue
            if 'transport_error' in value:
                raise RuntimeError(value['transport_error'])
            if value.get('id') != request_id:
                continue
            if 'error' in value:
                error = value['error']
                raise RuntimeError(str(error.get('message', '组件读取失败')))
            result = value.get('result')
            if not isinstance(result, dict):
                raise ValueError('采集组件返回格式无效')
            return result
        raise TimeoutError('游戏数据读取超时，请确认已登录且组件就绪')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream:
                stream.close()
