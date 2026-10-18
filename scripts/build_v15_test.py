"""Build the sole local V1.5 user test EXE, then retire known obsolete outputs.

Run: .venv-ocr/Scripts/python.exe scripts/build_v15_test.py
Does not publish, touch account data, or delete unrelated releases.
"""
from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop'))
from build import build

TEST_ROOT = (ROOT / 'dist/windows/test-v1.5').resolve()
assert TEST_ROOT.is_relative_to((ROOT / 'dist/windows').resolve())
STAGE_ROOT = (ROOT / 'dist/windows/.staging-v15').resolve()
assert STAGE_ROOT.is_relative_to((ROOT / 'dist/windows').resolve())
parser = argparse.ArgumentParser(description='Build and promote the single local V1.5 user test EXE.')
parser.add_argument('--promote-staged', action='store_true', help='Promote an already built and verified staging EXE without rebuilding.')
args = parser.parse_args()
if not args.promote_staged:
    build('user', str(STAGE_ROOT), app_version='1.5', app_revision=0)
staged = STAGE_ROOT / 'KekeAssistant.exe'
if not staged.is_file() or staged.stat().st_size < 10_000_000:
    raise RuntimeError('Staging test package missing; existing test package left untouched')
from PyInstaller.archive.readers import CArchiveReader

def verify(exe):
    archive = CArchiveReader(str(exe))
    modules = archive.open_embedded_archive('PYZ.pyz').toc
    required = {'inventory.equipment_plans', 'inventory.account_uid_reader.reader_api'}
    if not required.issubset(modules):
        raise RuntimeError('Persistent plans or game UID reader module missing from EXE')
    if 'inventory\\account_uid_reader\\native\\KekeNativeReader.dll' not in archive.toc:
        raise RuntimeError('Pinned read-only UID helper missing from EXE')

verify(staged)
TEST_ROOT.mkdir(parents=True, exist_ok=True)
latest = TEST_ROOT / 'KekeAssistant.exe'
try:
    os.replace(staged, latest)
except PermissionError as error:
    raise RuntimeError('Test EXE is still open. Close KekeAssistant and rerun with --promote-staged; the verified staging copy is preserved.') from error
verify(latest)
if STAGE_ROOT.is_dir() and not any(STAGE_ROOT.iterdir()):
    STAGE_ROOT.rmdir()
if {path.resolve() for path in TEST_ROOT.rglob('*.exe')} != {latest.resolve()}:
    raise RuntimeError('V1.5 test folder must contain exactly one executable')

# Explicit outputs of earlier local builds, checked inside this workspace.
old_files = [
    'test-v1.5/KekeAssistant-v1.5-test.exe',
    'test-v1.5-update/KekeAssistant-v1.5-test.exe',
    'test-v1.5-scoring-update/KekeAssistant.exe',
    'test-v1.5-owned-role-update/KekeAssistant.exe',
    'test-v1.5-drive-scoring-update/KekeAssistant.exe',
]
for relative in old_files:
    old = (ROOT / 'dist/windows' / relative).resolve()
    if not old.is_relative_to((ROOT / 'dist/windows').resolve()) or old == latest:
        raise RuntimeError('Unsafe obsolete output path')
    old.unlink(missing_ok=True)
    if old.parent != TEST_ROOT and old.parent.is_dir() and not any(old.parent.iterdir()):
        old.parent.rmdir()  # Empty output folder only; never recurse into user data.
print('Sole V1.5 local test package:', latest)
