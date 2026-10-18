"""Private desktop manager. Maintains an external Git working copy, not bundled data."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from runtime import APP_DATA, BUNDLE, guarded, launch_window, single_instance

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import admin_server


def valid_workspace(path):
    return all((path / item).exists() for item in [".git", "index.html", "app.js", "data/knowledge"])


def choose_directory():
    import tkinter
    from tkinter import filedialog
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(title="选择可可助手项目资料库（包含 .git 与 index.html）")
    root.destroy()
    path = Path(selected).resolve() if selected else None
    if path and not valid_workspace(path):
        raise ValueError("所选目录不是可可助手 Git 工作副本")
    return path


def find_workspace(explicit):
    if explicit:
        path = Path(explicit).resolve()
        if not valid_workspace(path):
            raise ValueError("项目资料库无效：" + str(path))
        return path
    config = APP_DATA / "admin-workspace.json"
    if config.exists():
        try:
            path = Path(json.loads(config.read_text(encoding="utf-8"))["path"])
            if valid_workspace(path):
                return path
        except (ValueError, KeyError, OSError):
            pass
    for path in [Path.cwd(), *Path(sys.executable).parents, Path(__file__).resolve().parents[1]]:
        if valid_workspace(path):
            return path
    return choose_directory()


class WorkspaceApi:
    def __init__(self, path):
        self._path, self._pending, self._window, self._dirty = path, None, None, False

    def workspace(self):
        return str(self._path)

    def set_dirty(self, value):
        self._dirty = bool(value)

    def choose_workspace(self):
        import webview
        selected = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=str(self._path))
        if not selected:
            return False
        path = Path(selected[0]).resolve()
        if not valid_workspace(path):
            raise ValueError("请选择包含 .git 和 index.html 的可可助手项目目录")
        self._pending = path
        self._dirty = False
        self._window.destroy()
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace")
    parser.add_argument("--smoke-report")
    parser.add_argument("--screenshot")
    parser.add_argument("--verify-save", choices=["write", "read"])
    args = parser.parse_args()
    if not args.smoke_report and not single_instance("可可助手 · 资料管理", "admin"):
        return
    root = find_workspace(args.workspace)
    if root is None:
        return
    if args.verify_save and (not args.smoke_report or not (root / ".isolated-save-test").is_file()):
        raise ValueError("Save verification is restricted to marked isolated test workspaces")
    if not args.smoke_report:
        APP_DATA.mkdir(parents=True, exist_ok=True)
        (APP_DATA / "admin-workspace.json").write_text(json.dumps({"path": str(root)}, ensure_ascii=False), encoding="utf-8")
    # The frozen program owns no knowledge files. All writes target the selected working copy.
    admin_server.ROOT = root
    if args.verify_save:
        admin_server._backup_root = lambda: root / ".test-write-backups"
    admin_server.KNOWLEDGE = root / "data/knowledge"
    for name, filename in {"TEAM_SOURCE":"team_templates.json", "TEAM_OVERRIDES":"team_overrides.json",
                           "TEAM_BUNDLE":"team_templates.js", "CHAR_OVERRIDES":"character_overrides.json",
                           "CHAR_BUNDLE":"character_overrides.js", "ESPER_CYCLES":"esper_cycles.json",
                           "ESPER_CYCLE_BUNDLE":"esper_cycles.js"}.items():
        setattr(admin_server, name, admin_server.KNOWLEDGE / filename)
    ui_root = BUNDLE / "desktop" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

    class DesktopHandler(admin_server.Handler):
        def _serve_static(self, request_path):
            if request_path in ("/", "/index.html"):
                payload = (root / "index.html").read_text(encoding="utf-8").replace(
                    "</head>", '<link rel="stylesheet" href="desktop/desktop.css"><script src="desktop/desktop.js"></script></head>'
                ).replace('<body class="user-mode">', '<body class="user-mode desktop-mode">').encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            elif request_path in ("/desktop/desktop.css", "/desktop/desktop.js"):
                payload = (ui_root / request_path.rsplit("/", 1)[-1]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8" if request_path.endswith(".css") else "text/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                super()._serve_static(request_path)

    server = ThreadingHTTPServer(("127.0.0.1", 0 if args.smoke_report else 8765), DesktopHandler)
    server.daemon_threads = True
    api = WorkspaceApi(root)
    smoke = """(() => {
      const checks = { editor: !document.querySelector('#roleManagementView').hidden,
        characters: Object.keys(characterData).length >= 25, workspace: !!document.querySelector('#desktopWorkspace') };
      showGuideManager(); checks.lineups = !document.querySelector('#guideManagerView').hidden;
      showReactionSystem(); checks.reactions = !document.querySelector('#reactionSystemView').hidden;
      showUserExperience(); showUserRoute('team'); checks.preview = !document.querySelector('#userTeamRoute').hidden;
      showRoleManagement();
      return { checks, errors: window.__desktopErrors, title: document.title, workspace: """ + json.dumps(str(root)) + """ };
    })()"""
    action = None
    if args.verify_save:
        action = """(() => {
          applyCharacter('娜娜莉');
          window.__saveTestDone = false;
        """
        if args.verify_save == "write":
            action += """
              window.addEventListener('keke-role-saved', () => { window.__saveTestDone = true; }, { once: true });
              for (const kind of ['main', 'sub']) {
                const name = kind === 'main' ? '灵属性异能伤害增强' : '暴击率';
                const button = [...document.querySelectorAll('[data-affix-option="'+kind+'"]')].find(el => el.dataset.affixName === name);
                if (!button.classList.contains('is-selected')) button.click();
                const slider = [...document.querySelectorAll('[data-affix-option="'+kind+'"]')].find(el => el.dataset.affixName === name).closest('.affix-editor-row').querySelector('input');
                slider.value = kind === 'main' ? '5' : '4';
                slider.dispatchEvent(new Event('input', { bubbles: true }));
              }
              document.querySelector('#roleRating').value = 'T0';
              document.querySelector('#saveDraftButton').click();
            """
        else:
            action += "window.__saveTestDone = true;"
        action += "})()"
        smoke = """(() => {
          const c = characterData['娜娜莉'].knowledge.recommended.cassette;
          return { checks: {
            mainPriority: c.recommended_main_affixes.some(a => a.name === '灵属性异能伤害增强' && a.priority === 5),
            subPriority: c.recommended_sub_affixes.some(a => a.name === '暴击率' && a.priority === 4),
            savedButton: document.querySelector('#saveDraftButton').textContent.trim() === '保存'
          }, errors: window.__desktopErrors };
        })()"""
    launch_window("可可助手 · 资料管理", "admin", server, api=api,
                  report=args.smoke_report, screenshot=args.screenshot, smoke_js=smoke, smoke_action=action)
    if api._pending:
        command = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve())]
        subprocess.Popen(command + ["--workspace", str(api._pending)], creationflags=subprocess.CREATE_NO_WINDOW)


if __name__ == "__main__":
    guarded(main)
