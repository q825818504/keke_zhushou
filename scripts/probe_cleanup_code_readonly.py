"""Read a fixed, bounded set of matching game code ranges for offline research.

No writes, hooks, suspension, remote allocation, injection or game calls exist in
this diagnostic. ProcessReader requests QUERY_INFORMATION | VM_READ only.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import sys
import struct

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'desktop'))
from inventory.account_uid_reader.process_reader import ProcessReader
from inventory.account_uid_reader.discover_runtime_objects import validate, pointer
from inventory.account_uid_reader.discover_runtime_names import decode
from probe_cleanup_static_readonly import StaticPe

EXPECTED_SHA256 = '303e82a2d85833f2a780424ca3650dc5b64d2793c3d88806818a54630ad961bf'
RANGES = {
    'common_message_struct_constructor_candidate': 0x146bba0b0,
    'item_uid_struct_constructor_baseline': 0x147561c50,
    'server_common_ufunction_constructor': 0x149418200,
    'server_common_native_thunk_candidate': 0x1494d2510,
    'client_common_ufunction_constructor': 0x14940a590,
    'client_common_native_thunk_candidate': 0x14949b5b0,
    'native_parameter_property_accessor_candidate': 0x1418a5c30,
    # Derived from the captured high-quality decomposition confirmation path.
    'client_decompose_message_builder_candidate': 0x148d23d40,
    'client_decompose_rpc_wrapper_candidate': 0x14947b980,
    'decompose_mat_control_callback_candidate': 0x148d482d0,
    'decompose_capital_control_callback_candidate': 0x148d482b0,
    'decompose_uid_array_allocator_candidate': 0x141485150,
    'decompose_message_bool_parameter_candidate': 0x146ed12b0,
    'decompose_message_uid_parameter_candidate': 0x147f5f5a0,
    'decompose_message_parameter_copy_candidate': 0x144c67040,
    'decompose_message_parameter_destroy_candidate': 0x141535720,
    'decompose_game_free_candidate': 0x141514700,
}


def player_default_object(reader, identity, class_name='HTPlayerState', expected_sha256=EXPECTED_SHA256):
    if class_name not in ('HTPlayerState', 'HTUI_EquipDecomposeTips'):
        raise ValueError('Unsupported diagnostic class')
    wanted_name = 'Default__'+class_name
    directory = ROOT/'build'/'cleanup-research-current'
    registry = json.loads((directory/'object-registry.json').read_text(encoding='utf-8'))['processes'][0]
    pool = json.loads((directory/'name-pool.json').read_text(encoding='utf-8'))['processes'][0]
    if registry['identity'] != identity or registry['game_sha256'] != expected_sha256:
        raise ValueError('Saved object profile no longer matches the game process')
    reg = next(row for row in registry['candidates'] if row.get('verified'))
    names = next(row for row in pool['candidates'] if row.get('verified'))
    reg_address = int(reg['address'], 16)
    values = struct.unpack('<QQiiii', reader.read(reg_address, 32))
    if not validate(reader, reg_address, values).get('verified'):
        raise ValueError('Object registry failed structural validation')
    chunks, _, _, count, _, chunk_count = values
    if not 0 < count <= 1000000 or not 0 < chunk_count <= 64:
        raise ValueError('Object registry exceeds the diagnostic budget')
    chunk_table = reader.read(chunks, chunk_count*8)
    chunk_ptrs = struct.unpack('<'+'Q'*chunk_count, chunk_table)
    name_address = int(names['address'], 16)
    block, cursor = struct.unpack('<II', reader.read(name_address+8, 8))
    if not 0 <= block < 512 or not 0 < cursor <= 131072:
        raise ValueError('Name pool exceeds the diagnostic budget')
    blocks = struct.unpack('<'+'Q'*(block+1), reader.read(name_address+16, (block+1)*8))
    selected = set()
    for index, address in enumerate(blocks):
        raw = reader.read(address, cursor if index == block else 131072)
        offset = 0
        while offset+2 <= len(raw):
            header = struct.unpack_from('<H', raw, offset)[0]
            length, wide = header >> 6, header & 1
            end = offset+2+length*(2 if wide else 1)
            if not 0 < length <= 1023 or end > len(raw):
                break
            wanted = wanted_name.encode('utf-16le' if wide else 'ascii')
            if raw[offset+2:end] == wanted:
                selected.add((index << 16) | (offset//2))
            offset = (end+1) & ~1
    if not selected:
        raise ValueError('PlayerState class default object name was not found')
    found = []
    for chunk_index, address in enumerate(chunk_ptrs):
        rows = min(65536, count-chunk_index*65536)
        if rows <= 0:
            break
        for start in range(0, rows, 4096):
            raw = reader.read(address+start*24, min(4096, rows-start)*24)
            for offset in range(0, len(raw), 24):
                obj = struct.unpack_from('<Q', raw, offset)[0]
                if not pointer(obj):
                    continue
                header = reader.read(obj, 40)
                token = struct.unpack_from('<Q', header, 24)[0]
                if token & 0xffffffff not in selected:
                    continue
                index = chunk_index*65536+start+offset//24
                if struct.unpack_from('<i', header, 12)[0] != index:
                    continue
                flags = struct.unpack_from('<I', header, 8)[0]
                cls = struct.unpack_from('<Q', header, 16)[0]
                if not flags & 0x10 or not pointer(cls):
                    continue
                actual_class_name = decode(reader, blocks, struct.unpack('<I', reader.read(cls+24, 4))[0])
                if actual_class_name != class_name:
                    continue
                if reader.read(obj, 40) != header:
                    raise ValueError('PlayerState default object changed during observation')
                found.append({'address': hex(obj), 'vtable': hex(struct.unpack_from('<Q', header)[0]),
                              'name': wanted_name, 'class': class_name,
                              'object_flags': hex(flags)})
    if reader.read(chunks, chunk_count*8) != chunk_table or len(found) != 1:
        raise ValueError('Object table changed or PlayerState default object is ambiguous')
    return found[0]


def inspect(pid, game):
    image = StaticPe(game)
    try:
        digest = hashlib.sha256(image.data).hexdigest()
        if digest != EXPECTED_SHA256:
            raise ValueError('This diagnostic is pinned to a different executable')
        with ProcessReader(pid) as reader:
            identity = reader.identity()
            if Path(identity['executable']).resolve() != game.resolve():
                raise ValueError('Process executable differs from selected input')
            modules = [row for row in reader.modules()
                       if Path(row['path']).resolve() == game.resolve()]
            if len(modules) != 1:
                raise ValueError('Cannot uniquely verify the main game module')
            module = modules[0]
            base = int(module['base'], 16)
            if reader.read(base, 2) != b'MZ':
                raise ValueError('Loaded module header does not match PE')
            chunks = []
            total = 0
            def capture(label, static_va, limit=4096):
                nonlocal total
                bounds = image.function_extent(static_va)
                exact = bool(bounds and bounds[0] == static_va)
                # Trivial leaf validation functions can omit .pdata entries.
                # Read only a small prefix and retain the unresolved boundary.
                start, end = bounds if exact else (static_va, static_va+min(256, limit))
                size = min(end-start, limit)
                total += size
                if total > 196608:
                    raise ValueError('Code read exceeds diagnostic budget')
                address = base+start-image.base
                if not base <= address < address+size <= base+module['size']:
                    raise ValueError('Code range exceeds matching game module')
                raw = reader.read(address, size)
                if reader.read(address, size) != raw:
                    raise ValueError('Code range changed during observation')
                offset = image.offset(start, size)
                disk = image.data[offset:offset+size] if offset is not None else None
                chunks.append({'label': label, 'static_va': hex(start),
                               'runtime_va': hex(address), 'size': size,
                               'complete_function': exact and size == end-start,
                               'boundary_source': 'contiguous PE unwind fragments; remote fragments unknown' if exact else 'bounded prefix; boundary unresolved',
                               'same_as_disk': raw == disk,
                               'sha256': hashlib.sha256(raw).hexdigest(),
                               'bytes_hex': raw.hex()})
                return chunks[-1]
            for label, static_va in RANGES.items():
                capture(label, static_va)
            from capstone import Cs, CS_ARCH_X86, CS_MODE_64
            from capstone.x86 import X86_OP_MEM, X86_REG_RAX
            decoder = Cs(CS_ARCH_X86, CS_MODE_64)
            decoder.detail = True
            native = next(row for row in chunks if row['label'] == 'server_common_native_thunk_candidate')
            slots = set()
            for instruction in decoder.disasm(bytes.fromhex(native['bytes_hex']), int(native['runtime_va'], 16)):
                if instruction.mnemonic != 'call':
                    continue
                for operand in instruction.operands:
                    if (operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RAX
                            and 0x1000 <= operand.mem.disp < 0x4000 and operand.mem.disp % 8 == 0):
                        slots.add(operand.mem.disp)
            if not 1 <= len(slots) <= 3:
                raise ValueError('Native thunk did not expose a bounded candidate vtable dispatch')
            default = player_default_object(reader, identity)
            vtable = int(default['vtable'], 16)
            if not base <= vtable < base+module['size']-0x4000:
                raise ValueError('PlayerState vtable lies outside the verified game image')
            dispatch = []
            for slot in sorted(slots):
                raw_pointer = reader.read(vtable+slot, 8)
                runtime = struct.unpack('<Q', raw_pointer)[0]
                if reader.read(vtable+slot, 8) != raw_pointer:
                    raise ValueError('Virtual dispatch pointer changed during observation')
                static = runtime-base+image.base
                chunk = capture('server_common_vtable_'+hex(slot), static, limit=65536)
                dispatch.append({'slot': hex(slot), 'target_va': hex(runtime), 'code_label': chunk['label']})
            tips_default = player_default_object(reader, identity, 'HTUI_EquipDecomposeTips')
            tips_vtable = int(tips_default['vtable'], 16)
            if not base <= tips_vtable < base+module['size']-2048:
                raise ValueError('Cleanup UI vtable lies outside matching module')
            ui_candidates = []
            table = reader.read(tips_vtable, 2048)
            for index in range(256):
                runtime = struct.unpack_from('<Q', table, index*8)[0]
                static = runtime-base+image.base
                if not 0x148cfdfb1 <= static < 0x148d7dfb1:
                    continue
                if len(ui_candidates) >= 12:
                    raise ValueError('Cleanup UI override count exceeds diagnostic budget')
                chunk = capture('cleanup_ui_vtable_'+hex(index*8), static, limit=16384)
                ui_candidates.append({'slot': hex(index*8), 'target_va': hex(runtime), 'code_label': chunk['label']})
            if reader.read(tips_vtable, 2048) != table:
                raise ValueError('Cleanup UI virtual table changed during observation')
            # The live sender loads this FName before looking up its UFunction.
            # Decode the existing name; never invoke the function or change it.
            pool_profile = json.loads((ROOT/'build'/'cleanup-research-current'/'name-pool.json').read_text(encoding='utf-8'))['processes'][0]
            pool_row = next(row for row in pool_profile['candidates'] if row.get('verified'))
            pool_address = int(pool_row['address'], 16)
            block, cursor = struct.unpack('<II', reader.read(pool_address+8, 8))
            if not 0 <= block < 512 or not 0 < cursor <= 131072:
                raise ValueError('Sender name pool exceeds diagnostic bounds')
            blocks = struct.unpack('<'+'Q'*(block+1), reader.read(pool_address+16, (block+1)*8))
            name_address = base+0x14fe134c8-image.base
            name_raw = reader.read(name_address, 8)
            name_index, name_number = struct.unpack('<II', name_raw)
            sender_name = decode(reader, blocks, name_index)
            if reader.read(name_address, 8) != name_raw:
                raise ValueError('Sender function name changed while observing')
            sender_identity = {'fname_global_static_va': '0x14fe134c8',
                               'name': sender_name, 'number': name_number}
            if identity != reader.identity():
                raise ValueError('Process identity changed during observation')
        return {'status': 'read_only_code_observed', 'game_sha256': digest,
                'identity': identity, 'module_base': hex(base), 'total_bytes': total,
                'player_default_object': default, 'virtual_dispatch_candidates': dispatch,
                'cleanup_ui_class_default_object': tips_default, 'ui_vtable_candidates': ui_candidates,
                'sender_function_identity': sender_identity,
                'chunks': chunks, 'limitations': [
                    'Observed code does not establish a verified decomposition payload.',
                    'No game function was called and no game request was sent.']}
    finally:
        image.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Report must stay in the workspace build directory')
    if args.pid <= 0:
        raise ValueError('Invalid process ID')
    report = {'read_only': True, 'writes_game_memory': False, 'game_calls': False,
              'sends_requests': False, 'opens_process_with': '0x410',
              'elevated': bool(ctypes.windll.shell32.IsUserAnAdmin())}
    try:
        report.update(inspect(args.pid, args.game))
    except Exception as error:
        report.update(status='failed', error=str(error), windows_error=getattr(error, 'winerror', None))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'output': str(output),
                      'bytes_read': report.get('total_bytes', 0), 'error': report.get('error')},
                     ensure_ascii=False))
    return 0 if report['status'] == 'read_only_code_observed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
