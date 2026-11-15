"""Find direct rel32 references to the current decomposition RPC thunk.

This diagnostic reads only the matching HTGame.exe image and selected
executable memory sections. It never writes memory, injects, suspends threads,
installs hooks, or calls game functions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'build' / 'cleanup-research-tools'))
sys.path.insert(0, str(ROOT / 'desktop'))

from probe_cleanup_static_readonly import StaticPe
from inventory.account_uid_reader.process_reader import ProcessReader

EXPECTED_SHA256 = '032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788'
PREFERRED_IMAGE_BASE = 0x140000000
SENDER_STATIC_VA = 0x14947B780
CHUNK_SIZE = 1024 * 1024
MAX_EXECUTABLE_BYTES = 256 * 1024 * 1024


def inspect(pid: int, game_path: Path) -> dict:
    image = StaticPe(game_path)
    try:
        digest = hashlib.sha256(image.data).hexdigest()
        if digest != EXPECTED_SHA256:
            raise ValueError('The game executable is not the pinned current build')
        if image.base != PREFERRED_IMAGE_BASE:
            raise ValueError('Unexpected preferred image base')

        with ProcessReader(pid) as reader:
            identity = reader.identity()
            if Path(identity['executable']).resolve() != game_path.resolve():
                raise ValueError('PID executable does not match the selected game')
            modules = [row for row in reader.modules()
                       if Path(row['path']).resolve() == game_path.resolve()]
            if len(modules) != 1:
                raise ValueError('Cannot uniquely verify the main game module')
            module = modules[0]
            base = int(module['base'], 16)
            required_image_size = max(rva + max(raw_size, virtual_size)
                                      for rva, _raw, raw_size, virtual_size, _flags in image.sections)
            if int(module['size']) < required_image_size:
                raise ValueError('Main module does not cover the pinned executable sections')
            if reader.read(base, 2) != b'MZ':
                raise ValueError('Loaded main-module header did not match PE')

            target = base + (SENDER_STATIC_VA - image.base)
            candidates: set[int] = set()
            scanned = 0
            executable_sections = [s for s in image.sections if s[4] & 0x20000000]
            total_section_bytes = sum(max(s[2], s[3]) for s in executable_sections)
            if not executable_sections or total_section_bytes > MAX_EXECUTABLE_BYTES:
                raise ValueError('Executable-section scan exceeds the configured bound')

            for rva, _raw, raw_size, virtual_size, _flags in executable_sections:
                section_size = max(raw_size, virtual_size)
                cursor = 0
                while cursor < section_size:
                    remaining = section_size - cursor
                    read_size = min(CHUNK_SIZE, remaining)
                    block = reader.read(base + rva + cursor, read_size)
                    scanned += read_size
                    limit = max(0, len(block) - 4)
                    for offset in range(limit):
                        opcode = block[offset]
                        if opcode not in (0xE8, 0xE9):
                            continue
                        displacement = struct.unpack_from('<i', block, offset + 1)[0]
                        site = base + rva + cursor + offset
                        if site + 5 + displacement == target:
                            candidates.add(site)
                    if remaining <= read_size:
                        break
                    cursor += read_size - 4

            from capstone import Cs, CS_ARCH_X86, CS_MODE_64
            from capstone.x86 import X86_OP_IMM
            decoder = Cs(CS_ARCH_X86, CS_MODE_64)
            decoder.detail = True
            references = []
            for site in sorted(candidates):
                static_site = image.base + (site - base)
                bounds = image.function_range(static_site)
                decoded = None
                if bounds and bounds[1] - bounds[0] <= CHUNK_SIZE:
                    function_start = base + (bounds[0] - image.base)
                    code = reader.read(function_start, bounds[1] - bounds[0])
                    for instruction in decoder.disasm(code, function_start):
                        if instruction.address != site:
                            continue
                        immediate = (instruction.operands[0].imm
                                     if instruction.operands and instruction.operands[0].type == X86_OP_IMM
                                     else None)
                        if (instruction.mnemonic in ('call', 'jmp') and immediate == target):
                            decoded = {
                                'instruction': f'{instruction.mnemonic} {instruction.op_str}',
                                'function_start': hex(bounds[0]),
                            }
                        break
                references.append({
                    'runtime_site': hex(site),
                    'static_site': hex(static_site),
                    'validated_instruction': decoded,
                })

            if reader.identity() != identity:
                raise ValueError('Game process identity changed during the read')
            return {
                'status': 'read_only_runtime_scan_complete',
                'read_only': True,
                'game_calls': False,
                'writes_game_memory': False,
                'injection': False,
                'game_sha256': digest,
                'pid': pid,
                'process_identity': identity,
                'loaded_module': module,
                'sender_static_va': hex(SENDER_STATIC_VA),
                'sender_runtime_va': hex(target),
                'executable_sections_scanned': len(executable_sections),
                'bytes_scanned': scanned,
                'direct_rel32_references': references,
                'limitations': [
                    'This finds direct E8/E9 relative references only; indirect reflection and vtable dispatch are not covered.',
                    'A reference proves code linkage only, not that the function was called or a request was accepted.',
                    'No decomposition request was sent and no game function was invoked.',
                ],
            }
    finally:
        image.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / 'cleanup-research-current'
                        / 'current-rpc-callers-readonly.json')
    args = parser.parse_args()
    try:
        report = inspect(args.pid, args.game.resolve())
    except Exception as error:
        report = {
            'status': 'unavailable',
            'read_only': True,
            'game_calls': False,
            'writes_game_memory': False,
            'injection': False,
            'error': str(error),
            'windows_error': getattr(error, 'winerror', None),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'status': report['status'],
        'output': str(args.output),
        'bytes_scanned': report.get('bytes_scanned'),
        'references': len(report.get('direct_rel32_references', [])),
        'error': report.get('error'),
    }, ensure_ascii=False))
    return 0 if report['status'] == 'read_only_runtime_scan_complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
