"""Find client request construction from read-only, matching module code.

Only executable ranges of the pinned HTGame image are scanned. No hooks,
protection changes, allocation, injection, game calls or RPC dispatch occur.
Code is saved only for verified string references and selected direct callers.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import time

from probe_cleanup_static_readonly import ROOT, StaticPe
from probe_cleanup_code_readonly import EXPECTED_SHA256
sys.path.insert(0, str(ROOT/'desktop'))
from inventory.account_uid_reader.process_reader import ProcessReader
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP


def inspect(args, report):
    image = StaticPe(args.game)
    try:
        if hashlib.sha256(image.data).hexdigest() != EXPECTED_SHA256:
            raise ValueError('Executable identity differs from this diagnostic')
        enum = next(row for row in image.enum_for('EquipDecompose_Request')
                    if row['enum'] == 'ECommonRPCMsgCToS')
        message_type = next(row['value'] for row in enum['entries'] if row['name'] == 'EquipDecompose_Request')
        report.update(game_sha256=EXPECTED_SHA256, message_enum=enum['enum'], message_member='EquipDecompose_Request')
        with ProcessReader(args.pid) as reader:
            identity = reader.identity()
            if Path(identity['executable']).resolve() != args.game.resolve():
                raise ValueError('Process image does not match selected input')
            modules = [row for row in reader.modules() if Path(row['path']).resolve() == args.game.resolve()]
            if len(modules) != 1:
                raise ValueError('Main module identity is ambiguous')
            module = modules[0]
            base = int(module['base'], 16)
            delta = base-image.base
            if reader.read(base, 2) != b'MZ':
                raise ValueError('Loaded image header is invalid')
            report.update(identity=identity, module_base=hex(base))
            targets = {}
            for key, text in [('common_rpc_name', 'ServerCommonFunRPC'),
                              ('decompose_confirmation', 'ui_equip_decompose_has_high_quality')]:
                pattern = text.encode('utf-16le')+b'\0\0'
                offset = image.data.find(pattern)
                if offset < 0 or image.data.find(pattern, offset+1) >= 0:
                    raise ValueError('Expected one exact UTF-16 target: '+text)
                targets[image.address(offset)+delta] = key
            decoder = Cs(CS_ARCH_X86, CS_MODE_64)
            decoder.detail = True
            cache = {}
            saved = {}
            started = time.monotonic()
            report.update(scanned_bytes=0, read_gaps=[], string_references=[],
                          direct_callers=[], chunks=[], omitted_functions=[])

            def get_function(runtime_address):
                bounds = image.function_range(runtime_address-delta)
                if not bounds or bounds[1]-bounds[0] > 65536:
                    report['omitted_functions'].append(hex(runtime_address))
                    return None
                begin, end = bounds
                if begin not in cache:
                    raw = reader.read(begin+delta, end-begin)
                    if reader.read(begin+delta, end-begin) != raw:
                        raise ValueError('Function bytes changed during observation')
                    instructions = list(decoder.disasm(raw, begin+delta))
                    cache[begin] = (begin+delta, end+delta, raw, instructions)
                    if len(cache) > 512:
                        raise ValueError('Caller analysis exceeds function budget')
                return cache[begin]

            def save_function(function, label):
                begin, end, raw, instructions = function
                if begin in saved:
                    saved[begin]['labels'].append(label)
                    return saved[begin]['label']
                if sum(chunk['size'] for chunk in report['chunks'])+len(raw) > 512*1024:
                    raise ValueError('Selected code output exceeds budget')
                chunk = {'label': label, 'labels': [label], 'static_va': hex(begin-delta),
                         'runtime_va': hex(begin), 'size': len(raw), 'complete_function': True,
                         'boundary_source': 'PE exception table; separate cold fragments may exist',
                         'decoded_bytes': sum(instruction.size for instruction in instructions),
                         'sha256': hashlib.sha256(raw).hexdigest(), 'bytes_hex': raw.hex()}
                report['chunks'].append(chunk)
                saved[begin] = chunk
                return label

            executable = [(base+rva, virtual_size) for rva, raw, size, virtual_size, flags in image.sections
                          if flags & 0x20000000]
            if sum(size for _, size in executable) > 224*1024*1024:
                raise ValueError('Executable module scan exceeds budget')

            def blocks():
                for section_start, section_size in executable:
                    if not base <= section_start < section_start+section_size <= base+module['size']:
                        raise ValueError('Executable section exceeds verified module')
                    tail = b''
                    for offset in range(0, section_size, 1024*1024):
                        if time.monotonic()-started > 110:
                            raise ValueError('Read-only scan exceeds time budget')
                        address = section_start+offset
                        size = min(1024*1024, section_size-offset)
                        try:
                            raw = reader.read(address, size)
                        except OSError as error:
                            report['read_gaps'].append({'address': hex(address), 'size': size, 'error': str(error)})
                            tail = b''
                            continue
                        report['scanned_bytes'] += size
                        yield address-len(tail), tail+raw
                        tail = raw[-6:]

            # The opcode scan only produces candidates. Full function decoding
            # must independently place each reference on an instruction boundary.
            pattern = re.compile(rb'(?=([\x48-\x4f]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d](.{4})))', re.S)
            wrappers = set()
            for address, raw in blocks():
                for match in pattern.finditer(raw):
                    site = address+match.start()
                    target = site+7+struct.unpack('<i', match.group(2))[0]
                    if target not in targets:
                        continue
                    function = get_function(site)
                    if function is None:
                        continue
                    instruction = next((row for row in function[3] if row.address == site), None)
                    if (instruction is None or instruction.mnemonic != 'lea'
                            or not any(op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP
                                       and site+instruction.size+op.mem.disp == target
                                       for op in instruction.operands)):
                        continue
                    key = targets[target]
                    label = save_function(function, key+'_reference')
                    report['string_references'].append({'kind': key, 'site': hex(site),
                                                        'function': hex(function[0]), 'code_label': label})
                    if key == 'common_rpc_name':
                        wrappers.add(function[0])
            report['request_wrapper_candidates'] = [hex(value) for value in sorted(wrappers)]
            if not wrappers or len(wrappers) > 8:
                raise ValueError('Could not resolve a bounded set of request wrapper candidates')

            seen_calls = set()
            for address, raw in blocks():
                offset = 0
                while True:
                    offset = raw.find(b'\xe8', offset)
                    if offset < 0 or offset+5 > len(raw):
                        break
                    site = address+offset
                    target = site+5+struct.unpack_from('<i', raw, offset+1)[0]
                    offset += 1
                    if target not in wrappers or site in seen_calls:
                        continue
                    function = get_function(site)
                    if function is None:
                        continue
                    instruction = next((row for row in function[3] if row.address == site), None)
                    if (instruction is None or instruction.mnemonic != 'call'
                            or not any(op.type == X86_OP_IMM and op.imm == target for op in instruction.operands)):
                        continue
                    seen_calls.add(site)
                    stores = [row for row in function[3]
                              if row.mnemonic.startswith('mov') and len(row.operands) == 2
                              and row.operands[0].type == X86_OP_MEM
                              and row.operands[1].type == X86_OP_IMM
                              and row.operands[1].imm == message_type]
                    row = {'site': hex(site), 'wrapper': hex(target), 'function': hex(function[0]),
                           'contains_decompose_enum_store_candidate': bool(stores)}
                    if stores:
                        row['code_label'] = save_function(function, 'decompose_type_store_caller_candidate')
                        row['enum_stores'] = [{'address': hex(store.address), 'instruction': store.mnemonic+' '+store.op_str}
                                              for store in stores]
                    report['direct_callers'].append(row)
                    if len(report['direct_callers']) > 256:
                        raise ValueError('Direct caller count exceeds budget')
            if reader.identity() != identity:
                raise ValueError('Process identity changed during observation')
            report['elapsed_seconds'] = round(time.monotonic()-started, 3)
            report['status'] = 'read_only_request_path_observed'
    finally:
        image.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.pid <= 0 or not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Invalid process or report destination')
    report = {'read_only': True, 'writes_game_memory': False, 'game_calls': False,
              'sends_requests': False, 'opens_process_with': '0x410',
              'elevated': bool(ctypes.windll.shell32.IsUserAnAdmin()),
              'limitations': ['Direct-call evidence does not cover inlined or indirect wrapper calls.',
                             'A matching enum constant alone does not verify payload semantics.',
                             'No decomposition was performed.']}
    try:
        inspect(args, report)
    except Exception as error:
        report.update(status='failed', error=str(error), windows_error=getattr(error, 'winerror', None))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'output': str(output),
                      'callers': len(report.get('direct_callers', [])), 'error': report.get('error')}))
    return 0 if report['status'] == 'read_only_request_path_observed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
