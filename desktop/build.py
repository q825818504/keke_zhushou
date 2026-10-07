"""Reproducible Windows EXE build. Public and private targets are separate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw
from prepare_public import prepare_public, ROOT


def make_icon(directory):
    image = Image.new("RGBA", (256, 256))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 252, 252), radius=60, fill="#7263ef")
    for x, height in [(67, 58), (112, 114), (157, 82)]:
        draw.rounded_rectangle((x, 190-height, x+28, 190), radius=12, fill="white")
    icon = directory / "keke.ico"
    image.save(icon, sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    return icon


def build(target, dist=None):
    dist = Path(dist or ROOT / "dist/windows").resolve()
    if not dist.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("Desktop output must stay within this project's dist directory")
    directory = ROOT / "build/desktop"
    directory.mkdir(parents=True, exist_ok=True)
    icon = make_icon(directory)
    if target == "user":
        public = prepare_public()
        data = [str(public) + ";public"]
        name = "KekeAssistant"
    else:
        data = [str(ROOT / "desktop/desktop.css") + ";desktop", str(ROOT / "desktop/desktop.js") + ";desktop"]
        name = "KekeAssistantAdmin"
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", name, "--icon", str(icon), "--paths", str(ROOT / "scripts"),
            "--distpath", str(dist), "--workpath", str(directory / "pyinstaller"),
            "--specpath", str(directory), "--exclude-module", "pytest"]
    for asset in data:
        args += ["--add-data", asset]
    args += [str(ROOT / ("desktop/" + target + "_entry.py"))]
    subprocess.run(args, check=True)
    exe = dist / (name + ".exe")
    if target == "user":
        from PyInstaller.archive.readers import CArchiveReader
        archive = CArchiveReader(str(exe))
        modules = archive.open_embedded_archive("PYZ.pyz").toc
        forbidden = {"admin_server", "admin_entry", "build_character_overrides_bundle", "build_team_templates_bundle"}
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
