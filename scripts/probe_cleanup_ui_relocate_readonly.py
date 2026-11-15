"""Relocate current cleanup UI callbacks through its validated CDO vtable."""
import hashlib
import argparse
import json
import struct
from pathlib import Path
from probe_cleanup_code_readonly import ROOT, ProcessReader, player_default_object
from probe_cleanup_static_readonly import StaticPe
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP
from inventory.account_uid_reader.discover_runtime_names import decode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sender', action='store_true', help='Follow the observed UI message construction calls')
    args = parser.parse_args()
    directory = ROOT/'build'/'cleanup-research-current'
    registry = json.loads((directory/'object-registry.json').read_text())['processes'][0]
    image = StaticPe(registry['identity']['executable'])
    report = {'read_only': True, 'game_calls': False, 'writes_game_memory': False,
              'status': 'failed', 'chunks': []}
    try:
        digest = hashlib.sha256(image.data).hexdigest()
        if digest != registry['game_sha256']:
            raise ValueError('Game file identity changed')
        report['game_sha256'] = digest
        decoder = Cs(CS_ARCH_X86, CS_MODE_64)
        decoder.detail = True
        with ProcessReader(registry['pid']) as reader:
            identity = reader.identity()
            cdo = player_default_object(reader, identity, 'HTUI_EquipDecomposeTips', digest)
            module = next(row for row in reader.modules() if Path(row['path']).resolve() == image.path)
            base = int(module['base'], 16)
            def capture(runtime, label, prefix=False):
                static = runtime-base+image.base
                bounds = image.function_extent(static)
                if prefix:
                    start, end = static, static+64
                else:
                    if not bounds or bounds[0] != static:
                        raise ValueError('UI function has no validated entry boundary')
                    start, end = bounds
                if not 0 < end-start <= 16384 or not base <= runtime < runtime+end-start <= base+module['size']:
                    raise ValueError('UI code exceeds bounded module range')
                raw = reader.read(runtime, end-start)
                if reader.read(runtime, len(raw)) != raw:
                    raise ValueError('UI code changed')
                report['chunks'].append({'label': label, 'static_va': hex(start),
                                         'bytes_hex': raw.hex(), 'sha256': hashlib.sha256(raw).hexdigest(),
                                         'complete_function': not prefix})
                return list(decoder.disasm(raw, runtime))
            vtable = int(cdo['vtable'], 16)
            init = struct.unpack('<Q', reader.read(vtable+0x310, 8))[0]
            instructions = capture(init, 'cleanup_ui_binding_current')
            callbacks = []
            for ins in instructions:
                if ins.mnemonic != 'lea':
                    continue
                for operand in ins.operands:
                    if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                        target = ins.address+ins.size+operand.mem.disp
                        if base <= target < base+module['size']:
                            callbacks.append(target)
                            capture(target, 'ui_callback_'+hex(target-base), prefix=True)
            if args.sender:
                if len(callbacks) != 3:
                    raise ValueError('Expected two material controls and one submit control')
                submit = capture(callbacks[2], 'decompose_submit_current')
                initial_calls = [ins for ins in submit[:20] if ins.mnemonic == 'call'
                                 and ins.operands[0].type == X86_OP_IMM]
                if not initial_calls:
                    raise ValueError('Current PlayerState getter was not observed')
                capture(initial_calls[0].operands[0].imm, 'current_player_state_getter')
                markers = [index for index, ins in enumerate(submit)
                           if ins.mnemonic == 'mov' and ins.op_str == 'edx, 0x63']
                if len(markers) != 1:
                    raise ValueError('Decompose request marker is ambiguous')
                calls = [ins for ins in submit[markers[0]+1:markers[0]+15]
                         if ins.mnemonic == 'call' and ins.operands[0].type == X86_OP_IMM]
                if len(calls) < 2:
                    raise ValueError('Could not observe builder and sender calls')
                builder = capture(calls[0].operands[0].imm, 'decompose_builder_current')
                sender = capture(calls[1].operands[0].imm, 'decompose_sender_current')
                direct_targets = {ins.operands[0].imm for ins in builder+sender
                                  if ins.mnemonic == 'call' and ins.operands[0].type == X86_OP_IMM}
                for static, label in ((0x141485150, 'uid_array_allocator_current'),
                                      (0x141535720, 'message_parameter_destructor_current'),
                                      (0x141514700, 'game_free_current')):
                    target = base+static-image.base
                    if target not in direct_targets:
                        raise ValueError('Expected memory helper is not referenced by current code')
                    capture(target, label)
                globals_seen = []
                pool = json.loads((directory/'name-pool.json').read_text())['processes'][0]
                pool_address = int(next(row for row in pool['candidates'] if row.get('verified'))['address'], 16)
                block, cursor = struct.unpack('<II', reader.read(pool_address+8, 8))
                if not 0 <= block < 512 or not 0 < cursor <= 131072:
                    raise ValueError('Name pool exceeds budget')
                blocks = struct.unpack('<'+'Q'*(block+1), reader.read(pool_address+16, (block+1)*8))
                for ins in sender:
                    if ins.mnemonic != 'mov' or not ins.op_str.startswith('rdx, qword ptr [rip '):
                        continue
                    operand = ins.operands[1]
                    address = ins.address+ins.size+operand.mem.disp
                    if not base <= address < base+module['size']-8:
                        continue
                    raw = reader.read(address, 8)
                    token, number = struct.unpack('<II', raw)
                    if token >> 16 > block:
                        continue
                    name = decode(reader, blocks, token)
                    if reader.read(address, 8) != raw:
                        raise ValueError('Sender name changed')
                    globals_seen.append({'name': name, 'number': number, 'static_va': hex(address-base+image.base)})
                report['sender_name_observations'] = globals_seen
            if reader.identity() != identity:
                raise ValueError('Process identity changed')
            report.update(status='ui_code_relocated', class_default_object=cdo)
    except Exception as error:
        report['error'] = str(error)
    finally:
        image.close()
        name = 'current-decompose-sender.json' if args.sender else 'material-ui-relocated.json'
        (directory/name).write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
