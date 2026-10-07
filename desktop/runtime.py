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
from urllib.parse import unquote, urlsplit
import mimetypes
import hashlib
import webview

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


def public_server(root: Path, port: int, workspace=None):
    manifest = json.loads((root / "public-manifest.json").read_text(encoding="utf-8"))
    allowed = set(manifest["files"]) | {"public-manifest.json"}
    knowledge_files = {name for name in allowed if name.startswith("data/knowledge/") and name.endswith(".js")}

    def data_root():
        return workspace() if callable(workspace) else workspace

    def source_for(relative):
        local = data_root()
        image = relative.startswith("data/resources/") and Path(relative).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}
        if relative not in allowed and not image:
            return None
        if local and (relative in knowledge_files or image):
            source = (local / relative).resolve()
            boundary = local / ("data/resources" if image else "data/knowledge")
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
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get("Host") != "127.0.0.1:" + str(self.server.server_port):
                self.send_error(403)
                return
            relative = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
            if ".." in Path(relative).parts or "\\" in relative:
                self.send_error(404)
                return
            if relative == "local-data-version":
                payload = json.dumps({"version": version()}).encode()
                mime = "application/json"
            else:
                source = source_for(relative)
                if source is None or not source.is_file():
                    self.send_error(404)
                    return
                payload = source.read_bytes()
                mime = mimetypes.guess_type(relative)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            self.send_error(405)

    return ThreadingHTTPServer(("127.0.0.1", port), ReadOnlyHandler)


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
    from webview.menu import Menu, MenuAction
    about_text = ("可可助手 · Windows 桌面版 0.1\n\n"
                  "资料来源：环世全鉴，Matsuzaka Yuki\nCC BY-NC-SA 4.0\n\n"
                  "优先读取本机管理资料；未连接本机资料库时使用内置资料。在线更新尚未配置。")
    menu = [Menu("可可助手", [MenuAction("关于可可助手", lambda: message("关于可可助手", about_text))])]

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
                      storage_path=str(profile), menu=menu)
    finally:
        server.shutdown()
        server.server_close()


def guarded(main):
    try:
        main()
    except Exception as error:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        (APP_DATA / "desktop-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        detail = str(error)
        if isinstance(error, OSError) and getattr(error, "winerror", None) == 10048:
            detail = "本地服务端口已被占用。请关闭之前启动的管理服务或助手实例后重试。"
        message("可可助手启动失败", detail + "\n\n详细日志：" + str(APP_DATA / "desktop-error.log"))
