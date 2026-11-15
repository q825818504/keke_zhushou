"""Verify the packaged bridge DLL and WH_GETMESSAGE path in an isolated child process.

This probe never opens the game process and never creates a valid bridge session.
The injected callback therefore logs a deliberate missing-session diagnostic and
cannot start the bridge worker or submit any game request.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'build' / 'native-decomposition'
WORK = BUILD / 'hook-validation'
COMPILER = ROOT / 'build' / 'cleanup-research-tools' / 'zig-x86_64-windows-0.14.1' / 'zig.exe'
SOURCE = ROOT / 'native' / 'decomposition' / 'hook_validation.cpp'
MINIMAL_SOURCE = ROOT / 'native' / 'decomposition' / 'hook_validation_minimal.cpp'


def run_probe(probe, bridge):
    result = subprocess.run([str(probe), '--controller', str(bridge)], cwd=WORK,
                            capture_output=True, text=True, timeout=20)
    report = {
        'return_code': result.returncode,
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'game_process_opened': False,
        'game_memory_read_or_written': False,
        'decomposition_request_sent': False,
    }
    match = re.search(r'target_pid=(\d+)', result.stdout)
    if match:
        log = bridge.parent / f"bridge-{match.group(1)}.log"
        if log.is_file():
            report['callback_log'] = str(log.relative_to(ROOT))
            report['callback_text'] = log.read_text(encoding='utf-8', errors='replace')
    report['verified'] = (
        result.returncode == 0
        and 'mapped=1 callback=1 post=1' in result.stdout
        and (('hook callback entered; bridge module pinned' in report.get('callback_text', ''))
             or ('minimal hook callback entered' in report.get('callback_text', '')))
    )
    return report


def main():
    bridge = BUILD / 'KekeDecompositionBridge.dll'
    identity = json.loads((ROOT / 'desktop' / 'native' / 'cleanup-identity.json').read_text(encoding='utf-8'))
    expected = identity['files']['KekeDecompositionBridge.dll']
    if hashlib.sha256(bridge.read_bytes()).hexdigest() != expected:
        raise RuntimeError('bridge DLL does not match the checked-in component identity')
    if not COMPILER.is_file():
        raise RuntimeError('reviewed local Zig compiler is unavailable')

    WORK.mkdir(parents=True, exist_ok=True)
    probe = WORK / 'hook-validation.exe'
    local_bridge = WORK / 'KekeDecompositionBridge.dll'
    shutil.copyfile(bridge, local_bridge)
    minimal_dir = WORK / 'minimal'
    minimal_dir.mkdir(exist_ok=True)
    minimal_bridge = minimal_dir / 'KekeDecompositionBridge.dll'
    environment = dict(os.environ)
    environment['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT / 'build' / 'cleanup-research-tools' / 'zig-cache')
    environment['ZIG_LOCAL_CACHE_DIR'] = str(WORK / 'zig-cache')
    subprocess.run([
        str(COMPILER), 'c++', '-target', 'x86_64-windows-gnu', '-std=c++17', '-O2',
        '-Wall', '-Wextra', '-Wpedantic', '-municode', str(SOURCE), '-lkernel32', '-luser32',
        '-o', str(probe),
    ], cwd=ROOT, env=environment, check=True)
    subprocess.run([
        str(COMPILER), 'c++', '-target', 'x86_64-windows-gnu', '-std=c++17', '-O2',
        '-Wall', '-Wextra', '-Wpedantic', '-shared', str(MINIMAL_SOURCE), '-lkernel32', '-luser32',
        '-o', str(minimal_bridge),
    ], cwd=ROOT, env=environment, check=True)
    actual_result = run_probe(probe, local_bridge)
    minimal_result = run_probe(probe, minimal_bridge)
    report = {
        'probe': 'isolated-child-process',
        'bridge_sha256': expected,
        'actual_bridge': actual_result,
        'minimal_control_dll': minimal_result,
    }
    report['game_process_opened'] = False
    report['game_memory_read_or_written'] = False
    report['decomposition_request_sent'] = False
    report['verified'] = actual_result['verified'] and minimal_result['verified']
    (WORK / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['verified']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
