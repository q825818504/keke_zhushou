"""Reproducible Windows EXE build. Public and private targets are separate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from prepare_public import prepare_public, ROOT


def make_icon(directory):
    import shutil
    directory.mkdir(parents=True,exist_ok=True)
    icon=directory/'keke.ico'
    shutil.copyfile(ROOT/'desktop/assets/mint-avatar.ico',icon)
    return icon


def build(target, dist=None, layout='onefile', app_version='1.0',app_revision=0):
    default_dist = ROOT / ("dist/windows/admin" if target == "admin" else "dist/windows")
    dist = Path(dist or default_dist).resolve()
    if not dist.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("Desktop output must stay within this project's dist directory")
    if target == "admin":
        try:
            import requests  # noqa: F401
        except ImportError as error:
            raise RuntimeError("Admin EXE builds require requests from desktop/requirements.txt") from error
    directory = ROOT / "build/desktop"
    directory.mkdir(parents=True, exist_ok=True)
    icon = make_icon(directory)
    if target == "user":
        from native.components import ComponentManager
        manager=ComponentManager(ROOT/'build/native-build-check')
        manager.component_root()
        public = prepare_public(app_version,app_revision)
        data = [str(public) + ";public", str(ROOT / "desktop/inventory/component-identity.json") + ";inventory", str(ROOT / "desktop/vision/resources") + ";vision/resources", str(ROOT / "desktop/vision/upstream/LICENSE") + ";vision/upstream", str(ROOT / "desktop/vision/upstream/NOTICE.md") + ";vision/upstream", str(ROOT / "desktop/vision/upstream/source-manifest.json") + ";vision/upstream"]
        data += [str(ROOT / 'build/native-components') + ';native-components', str(ROOT / 'desktop/native/component-identity.json') + ';native', str(ROOT / 'desktop/native/NOTICE.md') + ';native']
        data += [str(ROOT/'desktop/assets'/name)+';assets' for name in ('mint-avatar.ico','mint-avatar.png')]
        data += [str(ROOT/'desktop/inventory/equipment-layouts.json')+';inventory']
        data += [str(ROOT/'desktop/inventory/account_uid_reader/native/KekeNativeReader.dll')+';inventory/account_uid_reader/native']
        name = "KekeAssistant"
        if layout=='directory':
            trust=json.loads((ROOT/'desktop/update-trust.json').read_text())
            (directory/'release-info.json').write_text(json.dumps({'version':app_version,'revision':app_revision,'public_key':trust['public_key']}),encoding='utf-8')
            data += [str(directory/'release-info.json')+';.']
            name='KekeAssistantApp'
    else:
        data = [str(ROOT / "desktop/desktop.css") + ";desktop", str(ROOT / "desktop/desktop.js") + ";desktop"]
        name = "KekeAssistantAdmin"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", '--onedir' if layout=='directory' else '--onefile', "--windowed",
            "--name", name, "--icon", str(icon), "--paths", str(ROOT / "scripts"),
            "--distpath", str(dist), "--workpath", str(directory / "pyinstaller"),
            "--specpath", str(directory), "--exclude-module", "pytest"]
    if target=="user":
        for package in ['rapidocr_onnxruntime','onnxruntime','vgamepad']:
            args += ['--collect-data',package,'--collect-binaries',package,'--collect-submodules',package]
    for asset in data:
        args += ["--add-data", asset]
    args += [str(ROOT / ("desktop/" + target + "_entry.py"))]
    subprocess.run(args, check=True)
    exe = dist / (name + ".exe")
    if layout=='directory': exe=dist/name/(name+'.exe')
    if target == "user":
        from PyInstaller.archive.readers import CArchiveReader
        archive = CArchiveReader(str(exe))
        modules = archive.open_embedded_archive("PYZ.pyz").toc
        forbidden = {"admin_server", "admin_entry", "build_character_overrides_bundle", "build_team_templates_bundle",
                     'release_publish','release_credentials','build_release'}
        if forbidden.intersection(modules):
            raise RuntimeError("Admin Python module entered user EXE")
        if any("admin_bridge" in entry or "team_manager" in entry or ".git/" in entry for entry in archive.toc):
            raise RuntimeError("Private files entered user EXE")
    print("Built and audited: " + str(exe))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["all", "user", "admin"], nargs="?", default="all")
    parser.add_argument("--dist-dir")
    args = parser.parse_args()
    for target in (["user","admin"] if args.target == "all" else [args.target]):
        build(target, args.dist_dir)
