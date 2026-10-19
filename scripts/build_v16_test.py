"""Build and audit the local V1.6 test EXE, then remove older test packages.

Run: .venv-ocr/Scripts/python.exe scripts/build_v16_test.py
"""
from __future__ import annotations

from pathlib import Path
import argparse
import os
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop'))
from build import build

parser = argparse.ArgumentParser(description='Build one local V1.6 user test EXE.')
parser.add_argument('--promote-staged', action='store_true', help='Promote an already verified staging EXE.')
parser.add_argument('--revision', type=int, default=0, help='Local test revision; only the audited latest test package is retained.')
args = parser.parse_args()
if not 0 <= args.revision <= 999:parser.error('revision must be between 0 and 999')
suffix = f'-r{args.revision}' if args.revision else ''
WINDOWS_ROOT = (ROOT / 'dist/windows').resolve()
TEST_ROOT = (WINDOWS_ROOT / ('test-v1.6' + suffix)).resolve()
STAGE_ROOT = (WINDOWS_ROOT / ('.staging-v16' + suffix)).resolve()
for path in (TEST_ROOT, STAGE_ROOT):
    if not path.is_relative_to(WINDOWS_ROOT):
        raise RuntimeError('Unsafe build output path')

if not args.promote_staged:
    build('user', str(STAGE_ROOT), app_version='1.6', app_revision=args.revision)

staged = STAGE_ROOT / 'KekeAssistant.exe'
if not staged.is_file() or staged.stat().st_size < 10_000_000:
    raise RuntimeError('V1.6 staging EXE missing; existing test builds were left untouched')

from PyInstaller.archive.readers import CArchiveReader


def verify(exe: Path) -> None:
    archive = CArchiveReader(str(exe))
    modules = archive.open_embedded_archive('PYZ.pyz').toc
    required_modules = {
        'inventory.ui_assembly',
        'vision.stat_validation',
        'inventory.equipment_plans',
        'vision.upstream.features.drive_assembly.assembly_session',
        'vision.upstream.features.drive_assembly.executor',
        'vision.upstream.integrations.operation_guard',
    }
    if not required_modules.issubset(modules):
        raise RuntimeError('V1.6 OCR assembly modules missing from EXE: ' + repr(sorted(required_modules - set(modules))))
    entries = {str(entry).replace('\\', '/').lstrip('./') for entry in archive.toc}
    required_entries = {
        'public/index.html', 'public/role_build_standard.js', 'public/role_build.js',
        'public/public-manifest.json', 'vision/upstream/LICENSE',
        'vision/upstream/NOTICE.md', 'vision/upstream/source-manifest.json',
    }
    if not required_entries.issubset(entries):
        raise RuntimeError('V1.6 public or upstream license files missing from EXE: ' + repr(sorted(required_entries - entries)))


verify(staged)
TEST_ROOT.mkdir(parents=True, exist_ok=True)
latest = TEST_ROOT / 'KekeAssistant.exe'
try:
    os.replace(staged, latest)
except PermissionError as error:
    raise RuntimeError('V1.6 test EXE is open; verified staging copy is preserved.') from error
verify(latest)
for candidate in WINDOWS_ROOT.iterdir():
    if not candidate.is_dir() or candidate == TEST_ROOT or not re.fullmatch(r'test-v\d+(?:\.\d+)*(?:-r\d+)?',candidate.name):
        continue
    if candidate.is_symlink() or candidate.is_junction() or candidate.resolve().parent != WINDOWS_ROOT:
        raise RuntimeError('Refusing unsafe old test package path: '+str(candidate))
    entries=list(candidate.iterdir())
    if any(entry.name != 'KekeAssistant.exe' or not entry.is_file() or entry.is_symlink() for entry in entries):
        raise RuntimeError('Old test directory contains extra files; preserved: '+str(candidate))
    # Verified direct child containing only our test executable: no recursive delete.
    for entry in entries:entry.unlink()
    candidate.rmdir()
    print('Removed previous local test package: '+str(candidate))
if STAGE_ROOT.is_dir() and not any(STAGE_ROOT.iterdir()):
    STAGE_ROOT.rmdir()
print('Local V1.6 test package built and audited: ' + str(latest))
