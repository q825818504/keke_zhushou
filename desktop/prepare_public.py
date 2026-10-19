"""Generate a public-only asset tree. Never copy the repository wholesale."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "desktop" / "public"


def prepare_public(app_version='1.0',app_revision=0) -> Path:
    if not OUTPUT.resolve().is_relative_to((ROOT / "build/desktop").resolve()):
        raise RuntimeError("Generated public output escaped build/desktop")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    styles_revision = hashlib.sha256((ROOT / "styles.css").read_bytes()).hexdigest()[:12]
    desktop_styles_revision = hashlib.sha256((ROOT / "desktop/desktop.css").read_bytes()).hexdigest()[:12]
    # Remove only this generated, explicitly contained output from earlier builds.
    for child in OUTPUT.iterdir():
        if child.is_symlink():
            child.unlink()
        elif child.is_dir() and child.resolve().is_relative_to(OUTPUT.resolve()):
            shutil.rmtree(child)
        elif child.is_file():
            child.unlink()
        else:
            raise RuntimeError("Unexpected generated output path: " + str(child))
    soup = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")
    view = soup.select_one("#userExperienceView")
    view.select_one("#userPageTitle").string = "角色图鉴"
    view.select_one(".user-page-intro p").string = "查看机制、配装与养成材料。"
    view.select_one(".user-eyebrow").decompose()
    view.select_one(".user-footer").decompose()
    toast = soup.select_one("#toast")
    bundles = [tag["src"] for tag in soup.select("script[src]") if tag["src"].startswith("data/knowledge/")]
    from public_config import export_config
    export_config(ROOT, OUTPUT)
    bundles=['public-config.js']
    (OUTPUT/'public-config.js').write_text('// Public JSON bindings are served by the local runtime.\n',encoding='utf-8')
    (OUTPUT / "drive_layout_solver.js").write_bytes((ROOT / "drive_layout_solver.js").read_bytes())
    (OUTPUT / "cassette_scoring.js").write_bytes((ROOT / "cassette_scoring.js").read_bytes())
    for script in ('loadout_optimizer.js','loadout_worker.js'):
        (OUTPUT / script).write_bytes((ROOT / script).read_bytes())
    (OUTPUT / "terminal_puzzle.js").write_bytes((ROOT / "terminal_puzzle.js").read_bytes())
    (OUTPUT / "styles.css").write_bytes((ROOT / "styles.css").read_bytes())
    (OUTPUT / "desktop.css").write_bytes((ROOT / "desktop/desktop.css").read_bytes())
    (OUTPUT / "desktop.js").write_bytes((ROOT / "desktop/user_chrome.js").read_bytes())
    shutil.copyfile(ROOT/'desktop/assets/mint-avatar.png',OUTPUT/'mint-avatar.png')
    notes=ROOT/'desktop/releases/user'/('v'+app_version+'.md')
    history=[]
    from update_protocol import version
    for file in (ROOT/'desktop/releases/user').glob('v*.md'):
        name=file.stem[1:]
        if version(name)<=version(app_version):history.append({'version':name,'notes':file.read_text(encoding='utf-8')})
    history.sort(key=lambda row:version(row['version']),reverse=True)
    (OUTPUT/'release-history.json').write_text(json.dumps(history,ensure_ascii=False),encoding='utf-8')
    (OUTPUT/'release-notes.json').write_text(json.dumps({'version':app_version,'revision':app_revision,'notes':notes.read_text(encoding='utf-8') if notes.exists() else '当前版本暂无升级说明。'},ensure_ascii=False),encoding='utf-8')
    (OUTPUT / "recommendations.js").write_text(
        'window.CharacterRecommendations = { createKnowledge(original) {'
        'const recommended = JSON.parse(JSON.stringify(original.recommended || {}));'
        'const override = window.characterOverrides?.characters?.[original.id]?.recommended;'
        'for (const kind of ["weapon","cassette"]) if (override?.[kind]) recommended[kind] = JSON.parse(JSON.stringify(override[kind]));'
        'if (override?.terminal_puzzle) recommended.terminal_puzzle = JSON.parse(JSON.stringify(override.terminal_puzzle));'
        'return { ...original, recommended }; } };', encoding="utf-8")
    subprocess.run(["node", str(ROOT / "desktop/compile_user.cjs"), str(OUTPUT / "app.js")], check=True)
    (OUTPUT / "inventory_sync.js").write_bytes((ROOT / "inventory_sync.js").read_bytes())
    (OUTPUT / "vision_scan.js").write_bytes((ROOT / "vision_scan.js").read_bytes())
    (OUTPUT / "native_assembly.js").write_bytes((ROOT / "native_assembly.js").read_bytes())
    (OUTPUT / "native_assembly_planner.js").write_bytes((ROOT / "native_assembly_planner.js").read_bytes())
    (OUTPUT / "role_build.js").write_bytes((ROOT / "role_build.js").read_bytes())
    (OUTPUT / "role_build_standard.js").write_bytes((ROOT / "role_build_standard.js").read_bytes())
    nav = '<nav id="userPrimaryNav" aria-label="功能导航">'
    for route, label in [("team", "自动配队"), ("characters", "角色"), ("arc-drives", "弧盘"), ("cassettes", "空幕"), ("drive-blocks", "驱动块"), ("role-build", "角色配装"), ("role-build-plus", "角色配装"), ("inventory", "背包数据"), ("vision", "读取数据")]:
        nav += '<button class="user-primary-nav-item" type="button" data-user-route="' + route + '">' + label + ('<span class="role-build-plus" aria-label="PLUS">PLUS</span>' if route == 'role-build-plus' else '') + '</button>'
    nav += "</nav>"
    scripts = "".join('<script src="' + path + '"></script>' for path in bundles + ["recommendations.js", "cassette_scoring.js", "drive_layout_solver.js", "terminal_puzzle.js", "inventory_sync.js", "native_assembly_planner.js", "native_assembly.js", "role_build.js", "role_build_standard.js", "vision_scan.js", "app.js"])
    html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>可可助手</title><link rel="stylesheet" href="styles.css?v={styles_revision}">'
        f'<link rel="stylesheet" href="desktop.css?v={desktop_styles_revision}"><script src="desktop.js"></script></head>'
        '<body class="desktop-mode user-mode"><div class="app-shell">'
        '<aside class="desktop-sidebar"><div class="desktop-brand"><img class="desktop-app-mark" src="mint-avatar.png" alt="薄荷">'
        '<div><strong>可可助手</strong><small>配队与养成助手</small></div></div>'
        '<p class="desktop-nav-label">功能</p>' + nav +
        f'<div class="desktop-sidebar-foot">Windows 桌面版 · v{app_version}<br>Ctrl + 1–9 快速切换<br><button id="releaseNotesButton" type="button">更新内容</button><button id="diagnosticsButton" type="button">诊断日志</button></div></aside>'
        '<main class="main-content"><header class="topbar"><div class="breadcrumb"><span>可可助手</span>'
        '<strong id="activeBreadcrumb">自动配队</strong></div></header>' +
        str(view) + '</main></div>' + str(toast) + scripts + '</body></html>'
    )
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    # Only local images actually referenced by the public bundles enter the release.
    references = set()
    for file in OUTPUT.rglob("*.js"):
        references.update(re.findall(r'data/[^"\s]+?\.(?:webp|png|jpe?g|gif|svg)', file.read_text(encoding="utf-8")))
    missing = []
    for relative in references:
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            missing.append(relative)
            continue
        target = OUTPUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if missing:
        raise RuntimeError("Public asset references are missing: " + json.dumps(missing[:15], ensure_ascii=False))
    (OUTPUT / "ABOUT.txt").write_text(
        f"可可助手 Windows 桌面版 v{app_version}\n"
        "图鉴与异能环合资料：环世全鉴 https://wiki.mysqil.com/ 作者 Matsuzaka Yuki。\n"
        "按 CC BY-NC-SA 4.0 使用、整理及共享：https://creativecommons.org/licenses/by-nc-sa/4.0/\n"
        "图鉴资料已整理为本地结构化记录，界面使用的图片随应用本地打包；原始页面快照不进入用户版。\n"
        "公共配置由Gitee发布服务更新，下载失败可使用完整本地配置。\n",
        encoding="utf-8")
    files = {str(file.relative_to(OUTPUT)).replace("\\", "/"): hashlib.sha256(file.read_bytes()).hexdigest()
             for file in OUTPUT.rglob("*") if file.is_file()}
    archived_wiki_pages = [name for name in files
                           if name.startswith("data/mysqil/") and re.search(r"/raw/.*\.html?$", name, re.IGNORECASE)]
    if archived_wiki_pages:
        raise RuntimeError("Raw Wiki HTML archives must not enter the user release; ship normalized data and local assets only.")
    forbidden_files = {"admin_bridge.js", "team_manager.js", "reactions.js", "character_recommendations.js"}
    if forbidden_files.intersection(Path(name).name for name in files):
        raise RuntimeError("Private module entered public release")
    if any(name.startswith((".git/", ".planning/", "scripts/")) for name in files):
        raise RuntimeError("Private directory entered public release")
    page = BeautifulSoup(html, "html.parser")
    if page.select("#userAdminButton, #roleManagementView, #guideManagerView, #repoSyncDialog"):
        raise RuntimeError("Admin DOM entered public release")
    manifest = {"schema": 1, "version": app_version, "built_at": datetime.now(timezone.utc).isoformat(), "files": files}
    (OUTPUT / "public-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Public release: " + str(len(files)) + " files; " + str(len(references)) + " referenced images.")
    return OUTPUT


if __name__ == "__main__":
    prepare_public()
