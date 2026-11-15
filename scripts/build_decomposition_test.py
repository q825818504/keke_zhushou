"""Build and verify the single local V1.7 native-bridge test executable."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = (ROOT / 'dist' / 'windows').resolve()
TARGET = (WINDOWS / 'test-v1.7').resolve()

required = ('bs4', 'cryptography', 'PyInstaller', 'webview', 'rapidocr_onnxruntime',
            'onnxruntime', 'vgamepad')
if any(importlib.util.find_spec(name) is None for name in required):
    preferred = ROOT / '.venv-ocr' / 'Scripts' / 'python.exe'
    if preferred.is_file() and Path(sys.executable).resolve() != preferred.resolve():
        os.execv(str(preferred), [str(preferred), str(Path(__file__).resolve())])
    raise RuntimeError('打包环境缺少桌面/OCR依赖，拒绝生成会丢失已有扫描功能的测试版')

subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_cleanup_native.py')],
               cwd=ROOT, check=True)
hook_validation = subprocess.run(
    [sys.executable, str(ROOT / 'scripts' / 'verify_decomposition_hook.py')],
    cwd=ROOT, capture_output=True, text=True)
hook_report_path = ROOT / 'build' / 'native-decomposition' / 'hook-validation' / 'verification.json'
hook_report = json.loads(hook_report_path.read_text(encoding='utf-8')) if hook_report_path.is_file() else {}
hook_validation_passed = hook_validation.returncode == 0 and hook_report.get('verified') is True
actual_probe = hook_report.get('actual_bridge', {})
probe_output = actual_probe.get('stdout', '') if isinstance(actual_probe, dict) else ''
raw_hook_result = next(
    (line.strip() for line in probe_output.splitlines() if line.startswith('RESULT ')),
    'offline hook probe did not produce a result line')
hook_result_match = re.search(
    r'RESULT (mapped=\d+ callback=\d+ post=\d+ retrieved=\d+ received=\d+)',
    raw_hook_result)
hook_validation_summary = ('RESULT ' + hook_result_match.group(1)
    if hook_result_match else raw_hook_result)
sys.path.insert(0, str(ROOT / 'desktop'))
from build import build  # noqa: E402
from PyInstaller.archive.readers import CArchiveReader  # noqa: E402

expected_identity = json.loads((ROOT / 'desktop' / 'native' / 'cleanup-identity.json').read_text(
    encoding='utf-8'))
TARGET.parent.mkdir(parents=True, exist_ok=True)
artifact = TARGET / 'KekeAssistant.exe'
backup = None
if artifact.is_file():
    backup_root = (ROOT / 'build').resolve()
    if not backup_root.is_relative_to(ROOT.resolve()):
        raise RuntimeError('测试包备份目录无效')
    descriptor, backup_name = tempfile.mkstemp(prefix='v17-test-backup-', suffix='.exe', dir=backup_root)
    os.close(descriptor)
    backup = Path(backup_name)
    shutil.copy2(artifact, backup)

try:
    build('user', str(TARGET), app_version='1.7', app_revision=1, native_decomposition=True)
    if not artifact.is_file():
        raise RuntimeError('测试构建未生成 KekeAssistant.exe')

    archive = CArchiveReader(str(artifact))
    entries = {name.replace('\\', '/'): name for name in archive.toc}
    required_files = ('native-decomposition/KekeDecompositionBridge.dll',
                      'native-decomposition/KekeDecompositionLoader.exe',
                      'native/cleanup-identity.json')
    if any(name not in entries for name in required_files):
        raise RuntimeError('分解桥接组件未完整进入测试包')
    packaged_identity = json.loads(archive.extract(entries['native/cleanup-identity.json']))
    if packaged_identity != expected_identity:
        raise RuntimeError('EXE 内嵌组件身份与本次构建清单不一致')
    for name, expected_hash in packaged_identity['files'].items():
        key = 'native-decomposition/' + name
        if key not in entries:
            raise RuntimeError('EXE 缺少组件：' + name)
        actual_hash = hashlib.sha256(archive.extract(entries[key])).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError('EXE 内嵌组件哈希不匹配：' + name)

    modules = archive.open_embedded_archive('PYZ.pyz').toc
    required_modules = ('inventory.decomposition', 'inventory.decomposition_bridge')
    if any(name not in modules for name in required_modules):
        raise RuntimeError('分解服务模块未完整进入测试包')
except BaseException:
    if backup and backup.is_file():
        shutil.copy2(backup, artifact)
        backup.unlink()
    raise
else:
    if backup and backup.is_file():
        backup.unlink()

digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
package_info = {
    'file': str(artifact),
    'bytes': artifact.stat().st_size,
    'sha256': digest,
    'native_loaded': False,
    'game_runtime_tested': False,
    'decomposition_request_sent': False,
    'isolated_hook_validation': ('passed' if hook_validation_passed else
        'not verified in current desktop environment: ' + hook_validation_summary),
    'package': 'V1.7 bridge diagnostic build with current native loader and bridge',
}
(TARGET / 'package-info.json').write_text(
    json.dumps(package_info, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if hook_validation_passed:
    hook_note = '隔离子进程验证通过：桥接 DLL 可通过 WH_GETMESSAGE 回调加载。该验证没有连接游戏或读取游戏内存。'
else:
    hook_note = ('当前 Codex 桌面隔离环境未能映射桥接 DLL。离线探针结果：' +
        hook_validation_summary + '。它没有打开游戏或发送分解请求，因此不能代表普通桌面游戏内结果。')
instructions = f'''内存桥接测试版 V1.7（诊断更新）

{hook_note}

加载器现在会同时向游戏窗口 HWND 和目标线程队列投递 WM_NULL，尝试唤醒 WH_GETMESSAGE 钩子。此改动尚无游戏内验证。

请先关闭旧版可可助手和游戏，再启动本包 KekeAssistant.exe 与游戏。进入“背包管理”后点击“加载分解桥接”，等待加载完成再点“检测桥接”。本包会显示当前目标进程、窗口线程、模块快照及桥接启动日志，便于定位游戏侧失败原因。

本包没有进行游戏内桥接实测，也没有发送分解申请。当前只核对桥接连接时，不要点击“分解”。如果检测仍失败，请把完整诊断文本和截图发回。

正式版 EXE 未替换。
'''
(TARGET / '测试说明.txt').write_text(instructions, encoding='utf-8')

test_executables = []
for candidate in WINDOWS.iterdir():
    if (candidate.is_dir() and not candidate.is_symlink() and
            (candidate.name.startswith('test-v') or
             candidate.name.startswith('native-decomposition-test-v'))):
        # Temporary PyInstaller staging folders are not published test builds.
        if 'staging' in candidate.name.casefold():
            continue
        resolved = candidate.resolve()
        if resolved.parent != WINDOWS or not resolved.is_relative_to(WINDOWS):
            raise RuntimeError('发现 dist/windows 外的测试包路径：' + str(candidate))
        test_executables.extend(resolved.glob('*.exe'))
if test_executables != [artifact]:
    raise RuntimeError('测试构建目录中不是唯一的测试 EXE：' + repr(test_executables))

print('Verified single V1.7 test package:', TARGET / 'KekeAssistant.exe')
print(json.dumps(package_info, ensure_ascii=False))
