"""Export a reviewed, version-pinned native profile from local read-only evidence.

Offline only: does not attach to or call the game. An unrelated executable or a
report missing the observed ServerComposeRPC identity is rejected.
"""
import hashlib
import json
from pathlib import Path
from probe_cleanup_static_readonly import StaticPe

ROOT = Path(__file__).resolve().parents[1]
CURRENT_SHA256 = '032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788'
FUNCTIONS = {
    'allocator': ('uid_array_allocator_current', 0x141485150),
    'builder': ('decompose_builder_current', 0x148d23b80),
    'sender': ('decompose_sender_current', 0x14947b780),
    'destroy': ('message_parameter_destructor_current', 0x141535720),
    'free': ('game_free_current', 0x141514700),
    'player_getter': ('current_player_state_getter', 0x148bbb730),
}


def main():
    directory = ROOT/'build'/'cleanup-research-current'
    report = json.loads((directory/'current-decompose-sender.json').read_text(encoding='utf-8'))
    registry = json.loads((directory/'object-registry.json').read_text(encoding='utf-8'))['processes'][0]
    material = json.loads((directory/'material-mode-comparison.json').read_text(encoding='utf-8'))
    if (report.get('status') != 'ui_code_relocated' or report.get('read_only') is not True
            or report.get('game_calls') is not False or report.get('writes_game_memory') is not False
            or report.get('game_sha256') != CURRENT_SHA256
            or registry.get('game_sha256') != CURRENT_SHA256
            or material.get('game_sha256') != CURRENT_SHA256
            or material.get('status') != 'material_mapping_observed'
            or material.get('mapping') != {'experience': True, 'rewind': False}
            or report.get('sender_name_observations') != [
                {'name': 'ServerComposeRPC', 'number': 0, 'static_va': '0x14fe134c8'}]):
        raise ValueError('Evidence does not match the reviewed sender and material contract')
    image = StaticPe(registry['identity']['executable'])
    try:
        if hashlib.sha256(image.data).hexdigest() != CURRENT_SHA256:
            raise ValueError('Current executable differs from the reviewed binary')
        metadata = image.function_metadata('ServerComposeRPC')
        if len(metadata) != 1 or metadata[0]['parameter_size'] != 32:
            raise ValueError('Sender reflection signature changed')
        chunks = {row['label']: row for row in report['chunks']}
        lines = ['// Generated offline from reviewed read-only evidence. Do not hand-edit.',
                 '#pragma once', '#include <array>', '#include <cstddef>', '#include <cstdint>',
                 'namespace keke::decomposition::profile {',
                 'struct Signature { std::uintptr_t rva; const unsigned char* bytes; std::size_t size; };',
                 'inline constexpr std::array<unsigned char, 32> game_sha256 = {'+
                 ','.join('0x'+CURRENT_SHA256[i:i+2] for i in range(0, 64, 2))+'};',
                 'inline constexpr std::uintptr_t image_size = '+hex(max(
                     rva+max(raw_size, virtual_size) for rva, raw, raw_size, virtual_size, flags in image.sections))+';']
        for filename, symbol in (('name-pool.json', 'name_pool'), ('object-registry.json', 'object_registry')):
            discovered = json.loads((directory/filename).read_text(encoding='utf-8'))['processes'][0]
            if discovered['identity'] != registry['identity']:
                raise ValueError('Global metadata comes from another process')
            candidate = next(row for row in discovered['candidates'] if row.get('verified'))
            lines.append('inline constexpr std::uintptr_t '+symbol+'_rva = '+hex(int(candidate['address'],16)-image.base)+';')
        entries = []
        for name, (label, address) in FUNCTIONS.items():
            chunk = chunks[label]
            raw = bytes.fromhex(chunk['bytes_hex'])
            if (int(chunk['static_va'], 16) != address or not chunk.get('complete_function')
                    or image.function_extent(address) != (address, address+len(raw))
                    or hashlib.sha256(raw).hexdigest() != chunk['sha256']):
                raise ValueError('Incomplete or changed code evidence: '+name)
            lines.append('inline constexpr std::uintptr_t '+name+'_rva = '+hex(address-image.base)+';')
            lines.append('inline constexpr unsigned char '+name+'_bytes[] = {')
            for offset in range(0, len(raw), 16):
                lines.append('    '+','.join(hex(value) for value in raw[offset:offset+16])+',')
            lines.append('};')
            entries.append('    Signature{'+name+'_rva, '+name+'_bytes, sizeof('+name+'_bytes)}')
        lines.append('inline constexpr std::array<Signature, '+str(len(entries))+'> signatures = {')
        lines.append(',\n'.join(entries))
        lines.extend(['};', '} // namespace keke::decomposition::profile', ''])
        target = ROOT/'native'/'decomposition'/'verified_profile.h'
        target.write_text('\n'.join(lines), encoding='utf-8')
        print(json.dumps({'output': str(target), 'functions': len(entries),
                          'game_sha256': CURRENT_SHA256, 'offline_only': True}))
    finally:
        image.close()


if __name__ == '__main__':
    main()
