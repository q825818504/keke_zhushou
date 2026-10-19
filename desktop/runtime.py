"""Shared window runtime; deliberately has no editor or Git imports."""
from pathlib import Path
import ctypes
import atexit
import base64
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit, parse_qs
import mimetypes
import hashlib
import secrets
import webview
import diagnostics

APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "KekeAssistant"
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def single_instance(title, mode):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, "Local\\KekeAssistantDesktop-" + mode)
    if ctypes.get_last_error() == 183:
        ctypes.windll.user32.FindWindowW.restype = ctypes.c_void_p
        existing = ctypes.windll.user32.FindWindowW(None, title)
        if existing:
            ctypes.windll.user32.ShowWindow(ctypes.c_void_p(existing), 9)
            ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(existing))
        kernel.CloseHandle(ctypes.c_void_p(handle))
        return False
    atexit.register(lambda: kernel.CloseHandle(ctypes.c_void_p(handle)))
    return True


def message(title, text):
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)


def local_workspace():
    """Locate the selected local data only; never expose its management files."""
    try:
        value = json.loads((APP_DATA / "admin-workspace.json").read_text(encoding="utf-8"))
        path = Path(value["path"]).resolve()
        if (path / "data/knowledge/characters.js").is_file():
            return path
        # Older projects use a different character bundle filename.
        if (path / "data/knowledge/character_overrides.js").is_file():
            return path
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def public_server(root: Path, port: int, workspace=None, inventory=None, vision=None, configuration=None, startup_warning=None):
    inventory_token = secrets.token_urlsafe(32)
    # Consent belongs to this application run, never the persisted account config.
    native_risk = {'acknowledged': False, 'enabled': False}
    release_ready=False
    manifest = json.loads((root / "public-manifest.json").read_text(encoding="utf-8"))
    allowed = set(manifest["files"]) | {"public-manifest.json"}
    knowledge_files = {name for name in allowed if name.startswith("data/knowledge/") and name.endswith(".js")}

    def data_root():
        return workspace() if callable(workspace) else workspace

    def source_for(relative):
        local = configuration or data_root()
        image = relative.startswith('data/' if configuration else 'data/resources/') and Path(relative).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
        if relative not in allowed and not image:
            return None
        if local and (relative in knowledge_files or image):
            source = (local / relative).resolve()
            boundary = local / ('data' if configuration else "data/resources" if image else "data/knowledge")
            if source.is_relative_to(boundary.resolve()) and source.is_file():
                return source
        return root / relative if relative in allowed else None

    def version():
        digest = hashlib.sha256()
        local = data_root()
        digest.update(str(local).encode())
        for relative in sorted(knowledge_files):
            source = source_for(relative)
            if source and source.is_file():
                digest.update(source.read_bytes())
        if local:
            for source in sorted((local / "data/resources/characters").glob("*/drive-layout.*")):
                if source.resolve().is_relative_to((local / "data/resources").resolve()):
                    digest.update(str(source.stat().st_mtime_ns).encode())
        return digest.hexdigest()

    class ReadOnlyHandler(BaseHTTPRequestHandler):
        def handle_one_request(self):
            try: super().handle_one_request()
            except (ConnectionError, BrokenPipeError): pass
            except Exception:
                diagnostics.failure('本地功能请求失败')
                try: self.inventory_json({'error':'功能执行失败，请查看诊断日志'},500)
                except OSError: pass
        def log_message(self, *args):
            pass

        def inventory_json(self, value, code=200):
            payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.headers.get("Host") != "127.0.0.1:" + str(self.server.server_port):
                self.send_error(403)
                return
            relative = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
            if relative=='release/status':
                from release_lifecycle import release_status
                self.inventory_json(release_status(root,APP_DATA));return
            if relative=='diagnostics/recent':
                self.inventory_json(diagnostics.recent()); return
            if ".." in Path(relative).parts or "\\" in relative:
                self.send_error(404)
                return
            if relative == 'inventory/status' and inventory:
                self.inventory_json({**inventory.status(), 'token':inventory_token, 'native_risk':dict(native_risk)})
                return
            if relative == 'inventory/ui-assembly/status' and inventory:
                self.inventory_json(inventory.ui_assembly.status())
                return
            if relative == 'inventory/snapshot' and inventory:
                account = parse_qs(urlsplit(self.path).query).get('account', [inventory.config['account']])[0]
                if not account or len(account)>80:
                    self.inventory_json({'error':'账号标签无效'}, 400)
                    return
                try:
                    self.inventory_json(inventory.view(account,parse_qs(urlsplit(self.path).query).get('source',['auto'])[0]))
                except (OSError, ValueError):
                    self.inventory_json({'error':'本机快照读取失败，请保留文件检查'}, 500)
                return
            if relative.startswith('vision/') and vision:
                params=parse_qs(urlsplit(self.path).query)
                account=params.get('account',[inventory.config.get('account','默认账号') if inventory else '默认账号'])[0]
                try:
                    if relative=='vision/status':self.inventory_json({**vision.status(compact=True),'token':inventory_token})
                    elif relative=='vision/history':self.inventory_json(vision.history(account))
                    elif relative=='vision/batch':self.inventory_json(vision.load(account,params.get('id',[''])[0]))
                    elif relative=='vision/image':
                        source=vision.image(account,params.get('id',[''])[0],params.get('name',[''])[0])
                        payload=source.read_bytes();self.send_response(200)
                        self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(payload)))
                        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
                        self.end_headers();self.wfile.write(payload)
                    else:self.send_error(404)
                except (ValueError,OSError):self.inventory_json({'error':'视觉批次或图片读取失败'},400)
                return
            if relative == 'public-config.js' and (root/'config.json').is_file():
                from update_protocol import load_config
                bindings=load_config(configuration or root)['bindings']
                payload=('\n'.join('window['+json.dumps(key)+']=JSON.parse('+json.dumps(json.dumps(value,ensure_ascii=True))+');' for key,value in bindings.items())).encode('utf-8')
                mime='application/javascript'
            elif relative == "local-data-version":
                payload = json.dumps({"version": version()}).encode()
                mime = "application/json"
            else:
                source = source_for(relative)
                if source is None or not source.is_file():
                    self.send_error(404)
                    return
                payload = source.read_bytes()
                if relative=='index.html' and startup_warning:
                    import html
                    notice='<div class="inventory-status" data-tone="warning" role="status">'+html.escape(startup_warning)+'</div>'
                    payload=payload.decode('utf-8').replace('</header>','</header>'+notice,1).encode('utf-8')
                mime = mimetypes.guess_type(relative)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            nonlocal release_ready
            expected_host = '127.0.0.1:' + str(self.server.server_port)
            if (self.headers.get('Host') != expected_host or self.headers.get('Origin') != 'http://' + expected_host
                or self.headers.get('X-Keke-Inventory') != inventory_token):
                self.send_error(403)
                return
            path=urlsplit(self.path).path
            if path.startswith('/diagnostics/'):
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<=length<=4096:raise ValueError('请求太大')
                    body=json.loads(self.rfile.read(length) or '{}')
                    if path=='/diagnostics/export':
                        file=diagnostics.export();os.startfile(str(file.parent))
                        self.inventory_json({'file':str(file)})
                    elif path=='/diagnostics/refresh':
                        diagnostics.refresh_windows_events();self.inventory_json(diagnostics.recent())
                    elif path=='/diagnostics/client-error':
                        diagnostics.event('界面错误',detail=str(body.get('message',''))[:2000]);self.inventory_json({'ok':True})
                    else:self.send_error(404)
                except Exception:
                    diagnostics.failure('诊断操作失败');self.inventory_json({'error':'诊断操作失败，请查看本地日志'},500)
                return
            if path in ('/release/ready','/release/acknowledge'):
                from release_lifecycle import cleanup_versions,acknowledge
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=4096:self.send_error(400);return
                self.rfile.read(length)
                if path.endswith('acknowledge'):acknowledge(root,APP_DATA)
                elif not release_ready:
                    release_ready=True
                    threading.Thread(target=cleanup_versions,args=(sys.executable,getattr(sys,'frozen',False)),daemon=True,name='release-cleanup').start()
                self.inventory_json({'ok':True});return
            diagnostics.event('功能请求',path=path)
            path = urlsplit(self.path).path
            if vision and path in ('/vision/start','/vision/cancel','/vision/stop-capture','/vision/open-folder','/vision/correct'):
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=96*1024*1024 or self.headers.get('Content-Type')!='application/json':raise ValueError('请求格式或大小无效')
                    body=json.loads(self.rfile.read(length))
                    if not isinstance(body,dict):raise ValueError('请求格式无效')
                    if path=='/vision/cancel':result=vision.cancel()
                    elif path=='/vision/stop-capture':result=vision.stop_capture()
                    elif path=='/vision/open-folder':result=vision.open_folder(body.get('account'),body.get('id'))
                    elif path=='/vision/correct':result=vision.correct(body.get('account'),body.get('id'),body.get('index'),body.get('record'))
                    else:
                        if inventory:
                            with inventory.lock:
                                if inventory.native_busy():raise ValueError('请先等待原生读取或装备操作结束')
                                mode=body.get('mode')
                                account=body.get('account')
                                profile=inventory.accounts.get(account)
                                supplied_uid=body.get('account_uid')
                                if mode=='retry':
                                    if not profile:raise ValueError('请先选择识别批次所属账号资料')
                                    batch=vision.load(account,body.get('id'))
                                    account_uid=batch.get('account_uid') or profile.get('uid')
                                    if supplied_uid and supplied_uid!=account_uid:raise ValueError('重试UID与原批次不一致')
                                    if not account_uid:raise ValueError('此旧批次尚未绑定UID，请先在背包数据中手动绑定账号资料')
                                    if profile.get('uid') != account_uid:raise ValueError('请先将此批次所属资料手动绑定到对应 UID')
                                else:
                                    from inventory.accounts import validate_uid
                                    account_uid=validate_uid(supplied_uid)
                                    profile=inventory.accounts.resolve_uid(account_uid)
                                    account=profile['account']
                                result=vision.start(mode,account,body.get('count'),body.get('files'),body.get('id'),account_uid)
                        else:result=vision.start(body.get('mode'),body.get('account'),body.get('count'),body.get('files'),body.get('id'),body.get('account_uid'))
                    self.inventory_json(result)
                except (ValueError,OSError) as error:
                    diagnostics.failure('识别扫描请求失败');self.inventory_json({'error':str(error)},400)
                return
            if not inventory or path not in ('/inventory/risk/acknowledge','/inventory/risk-mode','/inventory/start','/inventory/cancel','/inventory/delete','/inventory/account/delete','/inventory/account/select','/inventory/account/note','/inventory/account/bind','/inventory/components/check','/inventory/components/deploy','/inventory/components/remove',
                '/inventory/equipment/inspect','/inventory/equipment/preview','/inventory/equipment/assemble-preview','/inventory/equipment/start','/inventory/equipment/cancel',
                '/inventory/equipment/save-build','/inventory/equipment/delete-build','/inventory/equipment/saved-preview',
                '/inventory/ui-assembly/start','/inventory/ui-assembly/cancel'):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 <= length <= 4096 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('请求格式无效')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body,dict):
                    raise ValueError('请求格式无效')
                if path in ('/inventory/risk/acknowledge', '/inventory/risk-mode'):
                    with inventory.lock:
                        if path.endswith('/acknowledge'):
                            native_risk['acknowledged'] = True
                        else:
                            enabled = body.get('enabled')
                            if type(enabled) is not bool:raise ValueError('风险模式状态无效')
                            if enabled and not native_risk['acknowledged']:raise ValueError('请先阅读并确认 DLL 读取风险提示')
                            if inventory.native_busy():raise ValueError('请等待当前原生读取或装备操作结束后再切换风险模式')
                            native_risk['enabled'] = enabled
                        result = dict(native_risk)
                elif path=='/inventory/account/delete':
                    result=inventory.delete_account(body.get('account'),body.get('uid'))
                elif path=='/inventory/account/select':
                    result=inventory.select_account(body.get('account'))
                elif path=='/inventory/account/note':
                    result=inventory.set_account_note(body.get('account'),body.get('note'))
                elif path=='/inventory/account/bind':
                    result=inventory.bind_account_uid(body.get('account'),body.get('uid'),body.get('replace_existing',False))
                elif path=='/inventory/ui-assembly/start':
                    result=inventory.ui_assembly.start(body.get('account'),body.get('source'),body.get('role_name'),
                        body.get('role_id'),body.get('board'),body.get('core'),body.get('modules'),body.get('role_alias'),body.get('source_saved_at'))
                elif path=='/inventory/ui-assembly/cancel':
                    result=inventory.ui_assembly.cancel()
                elif '/equipment/' in path:
                    action=path.rsplit('/',1)[1]
                    if action=='inspect':result=inventory.equipment.inspect(body.get('account') or inventory.config.get('account'))
                    elif action=='save-build':result=inventory.equipment.save_build_plan(body.get('account'),body.get('selection_id'),body.get('character_id'),body.get('core'),body.get('modules'),body.get('exclude_others'),body.get('complete'))
                    elif action=='delete-build':result=inventory.equipment.delete_build_plan(body.get('account'),body.get('character_id'))
                    elif action=='saved-preview':result=inventory.equipment.preview_saved(body.get('account'),body.get('character_id'))
                    elif action=='preview':result=inventory.equipment.preview(body.get('account'),body.get('character_ids'),body.get('categories'))
                    elif action=='assemble-preview':result=inventory.equipment.preview_assembly(body.get('account'),body.get('selection_id'),body.get('character_id'),body.get('core'),body.get('modules'),body.get('placement_mode'))
                    elif action=='start':result=inventory.equipment.start(body.get('token'))
                    else:result=inventory.equipment.cancel()
                elif path=='/inventory/delete':
                    result=inventory.delete(body.get('account'),body.get('source'))
                elif '/components/' in path:
                    if not inventory.components:raise ValueError('此版本尚未内置原生组件')
                    action=path.rsplit('/',1)[1]
                    method={'check':inventory.components.inspect,'deploy':inventory.components.deploy,'remove':inventory.components.remove}[action]
                    with inventory.lock:
                        if action=='deploy' and not (native_risk['acknowledged'] and native_risk['enabled']):
                            raise ValueError('请先在读取数据中启用风险模式，再部署 DLL 组件')
                        if inventory.native_busy():raise ValueError('原生读取或装备操作期间不能修改组件')
                        result=method(body.get('game_directory'))
                else:
                    with inventory.lock:
                        if path=='/inventory/start' and not (native_risk['acknowledged'] and native_risk['enabled']):
                            raise ValueError('请先在读取数据中启用风险模式，再使用 DLL 读取')
                        result = inventory.cancel() if path.endswith('/cancel') else inventory.start(account=body.get('account'))
                self.inventory_json(result)
            except (ValueError, OSError, RuntimeError) as error:
                diagnostics.failure('原生读取、装备或组件操作失败')
                self.inventory_json({'error':str(error)}, 400)


    server = ThreadingHTTPServer(("127.0.0.1", port), ReadOnlyHandler)
    server.vision = vision
    server.inventory = inventory
    return server


def launch_window(title, mode, server, api=None, report=None, screenshot=None, smoke_js=None, smoke_action=None):
    profile = APP_DATA / ("desktop-" + mode)
    profile.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    window = webview.create_window(title, "http://127.0.0.1:" + str(server.server_port) + "/index.html?desktop=" + mode,
                                  js_api=api, width=1380, height=900, min_size=(960, 680),
                                  background_color="#f7f7fa", text_select=True)
    if api is not None:
        api._window = window
    loaded = threading.Event()
    window.events.loaded += lambda: loaded.set()
    if api is not None:
        def allow_close():
            if report or not getattr(api, "_dirty", False):
                return True
            return ctypes.windll.user32.MessageBoxW(None, "编辑有未保存的修改，仍要关闭吗？", title, 0x24) == 6
        window.events.closing += allow_close
    webview.settings["ALLOW_DOWNLOADS"] = True
    def smoke():
        result = {"ok": False, "mode": mode}
        try:
            if not loaded.wait(35):
                raise RuntimeError("Desktop window did not load")
            time.sleep(1)
            if smoke_action:
                window.evaluate_js(smoke_action)
                deadline = time.monotonic() + 15
                while not window.evaluate_js("window.__saveTestDone === true"):
                    if time.monotonic() > deadline:
                        raise RuntimeError("Actual EXE save did not complete: " + str(window.evaluate_js("document.querySelector('#toastText').textContent")))
                    time.sleep(.15)
            result.update(window.evaluate_js(smoke_js))
            if api is not None:
                result.setdefault("checks", {})["noUnsavedAfterTest"] = not api._dirty
            result["ok"] = not result.get("errors") and all(result.get("checks", {}).values())
            if screenshot:
                from System import Func, Object
                time.sleep(.5)
                tasks = []
                def capture_content():
                    tasks.append(window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
                        "Page.captureScreenshot", '{"format":"png","captureBeyondViewport":false}'))
                    return None
                window.native.webview.Invoke(Func[Object](capture_content))
                payload = json.loads(tasks[0].Result)["data"]
                Path(screenshot).write_bytes(base64.b64decode(payload))
        except Exception:
            result["error"] = traceback.format_exc()
        finally:
            Path(report).parent.mkdir(parents=True, exist_ok=True)
            Path(report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            window.destroy()

    try:
        webview.start(smoke if report else None, gui="edgechromium", private_mode=bool(report),
                      storage_path=str(profile),icon=str(BUNDLE/'assets/mint-avatar.ico') if (BUNDLE/'assets/mint-avatar.ico').is_file() else None)
    finally:
        if getattr(server,"vision",None):
            server.vision.close()
        if getattr(server, "inventory", None):
            server.inventory.close()
        server.shutdown()
        server.server_close()


def guarded(main):
    mode='startup' if '--startup-check' in sys.argv else ('admin' if 'admin' in Path(sys.argv[0]).name.lower() else 'user')
    diagnostics.initialize(mode)
    try:
        main()
    except Exception as error:
        diagnostics.failure('助手未处理异常')
        APP_DATA.mkdir(parents=True, exist_ok=True)
        (APP_DATA / "desktop-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        detail = str(error)
        if isinstance(error, OSError) and getattr(error, "winerror", None) == 10048:
            detail = "本地服务端口已被占用。请关闭之前启动的管理服务或助手实例后重试。"
        message("可可助手启动失败", detail + "\n\n详细日志：" + str(APP_DATA / "desktop-error.log"))
