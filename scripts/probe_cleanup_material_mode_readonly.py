"""Observe the cleanup UI's existing material flag, without UI/game input."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'desktop'))
from inventory.account_uid_reader.process_reader import ProcessReader
from probe_cleanup_objects_readonly import inspect

EXPECTED_SHA256 = '303e82a2d85833f2a780424ca3650dc5b64d2793c3d88806818a54630ad961bf'


def validate_material_layout(registry):
    """Revalidate only these UI fields against previously observed live code."""
    from probe_cleanup_static_readonly import StaticPe
    evidence_path = ROOT/'build'/'cleanup-research-current'/'runtime-code-readonly-v7.json'
    evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
    if registry.get('game_sha256') == '032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788':
        # Independently relocated and disassembled on 2026-10-22. These are
        # material-widget callbacks only, not approved request entry points.
        relocated = json.loads((evidence_path.parent/'material-ui-relocated.json').read_text(encoding='utf-8'))
        mapping = {'cleanup_ui_binding_current': 'cleanup_ui_vtable_0x310',
                   'ui_callback_0x8d48110': 'decompose_mat_control_callback_candidate',
                   'ui_callback_0x8d480f0': 'decompose_capital_control_callback_candidate'}
        if (relocated.get('game_sha256') != registry['game_sha256']
                or relocated.get('status') != 'ui_code_relocated'
                or relocated.get('read_only') is not True
                or relocated.get('game_calls') is not False):
            raise ValueError('Current material relocation evidence is unavailable')
        evidence = dict(relocated, status='read_only_code_observed', chunks=[
            dict(row, label=mapping[row['label']], complete_function=row['label']=='cleanup_ui_binding_current')
            for row in relocated['chunks'] if row['label'] in mapping])
    if (evidence.get('game_sha256') != EXPECTED_SHA256
            and evidence.get('game_sha256') != '032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788'):
        raise ValueError('Material evidence version is not reviewed')
    if (
            evidence.get('read_only') is not True
            or evidence.get('game_calls') is not False
            or evidence.get('status') != 'read_only_code_observed'):
        raise ValueError('Previous material code evidence is unavailable')
    image = StaticPe(registry['identity']['executable'])
    try:
        digest = hashlib.sha256(image.data).hexdigest()
        if digest != registry.get('game_sha256'):
            raise ValueError('Game file changed after discovery')
        fields = {}
        for name, expected in (('RadioBox_Mat', 0x1368), ('RadioBox_Capital', 0x1370)):
            properties = []
            for _, va in image.names(name):
                for reference in image.pointers_to(va):
                    prop = image.property(image.address(reference))
                    if prop and prop.get('generation_flags') == '0x12':
                        properties.append(prop)
            if len(properties) != 1 or properties[0]['offset_candidate'] != expected:
                raise ValueError('Current material widget registration changed: '+name)
            fields[name] = properties[0]
        labels = {'decompose_mat_control_callback_candidate',
                  'decompose_capital_control_callback_candidate', 'cleanup_ui_vtable_0x310'}
        chunks = [row for row in evidence['chunks'] if row['label'] in labels]
        if len(chunks) != len(labels):
            raise ValueError('Material callback/binding evidence is incomplete')
        checked = []
        with ProcessReader(registry['pid']) as reader:
            if reader.identity() != registry['identity']:
                raise ValueError('Game process changed before layout verification')
            modules = [row for row in reader.modules()
                       if Path(row['path']).resolve() == image.path]
            if len(modules) != 1:
                raise ValueError('Matching game module is ambiguous')
            module = modules[0]
            base = int(module['base'], 16)
            for chunk in chunks:
                expected = bytes.fromhex(chunk['bytes_hex'])
                static = int(chunk['static_va'], 16)
                if hashlib.sha256(expected).hexdigest() != chunk['sha256'] or len(expected) > 4096:
                    raise ValueError('Material code evidence is invalid')
                address = base+static-image.base
                if not base <= address < address+len(expected) <= base+module['size']:
                    raise ValueError('Material code lies outside matching module')
                actual = reader.read(address, len(expected))
                if reader.read(address, len(expected)) != actual:
                    raise ValueError('Material code changed during observation')
                if actual != expected:
                    partial = {'read_only': True, 'game_calls': False,
                               'writes_game_memory': False, 'game_sha256': digest,
                               'label': chunk['label'], 'static_va': hex(static),
                               'bytes_hex': actual.hex(),
                               'function_extent': image.function_extent(static)}
                    (ROOT/'build'/'cleanup-research-current'/'material-code-changed.json').write_text(
                        json.dumps(partial, indent=2), encoding='utf-8')
                    raise ValueError('Current material callbacks changed; redisassembly is required')
                if chunk.get('complete_function') and image.function_extent(static) != (static, static+len(expected)):
                    raise ValueError('Material binding function boundaries changed')
                checked.append({'label': chunk['label'], 'sha256': chunk['sha256']})
        return {'game_sha256': digest, 'field_registrations': fields,
                'identical_live_code': checked,
                'scope': 'Material UI flag only; does not approve request addresses or execution'}
    finally:
        image.close()


def observe(label):
    directory = ROOT/'build'/'cleanup-research-current'
    registry = json.loads((directory/'object-registry.json').read_text(encoding='utf-8'))['processes'][0]
    layout = validate_material_layout(registry)
    metadata = inspect(directory)
    if metadata.get('status') != 'metadata_only':
        raise ValueError('Cleanup metadata observation is unavailable')
    candidates = [row for row in metadata['matches']
                  if row['class'] == 'BPUI_EquipDecomposeTips_C'
                  and not row['name'].startswith('Default__')]
    observations = []
    with ProcessReader(registry['pid']) as reader:
        if reader.identity() != registry['identity']:
            raise ValueError('Game process identity changed')
        for row in candidates:
            address = int(row['address'], 16)
            saved = bytes.fromhex(row['header_hex'])[:40]
            if reader.read(address, 40) != saved:
                continue
            # CDOs and archetype/template widgets do not represent the open UI.
            flags = struct.unpack_from('<I', saved, 8)[0]
            if flags & (0x10 | 0x20):
                continue
            raw_flag = reader.read(address+0x1390, 1)
            count = struct.unpack('<i', reader.read(address+0x1388, 4))[0]
            if raw_flag[0] not in (0, 1) or not 0 <= count <= 10000:
                raise ValueError('Cleanup UI field bounds do not match observed code')
            if reader.read(address, 40) != saved or reader.read(address+0x1390, 1) != raw_flag:
                raise ValueError('Cleanup UI changed while reading')
            observations.append({'object_name': row['name'], 'object_address': row['address'],
                                 'class': row['class'], 'native_material_flag': bool(raw_flag[0]),
                                 'selected_count': count,
                                 'parent_names': [parent['name'] for parent in row['parents']]})
        if reader.identity() != registry['identity']:
            raise ValueError('Game process identity changed during observation')
    if not observations:
        raise ValueError('No current decomposition UI instance was found; open the game decomposition page')
    return {'status': 'material_ui_observed', 'user_selected_label': label,
            'layout_verification': layout,
            'observations': observations,
            'unambiguous_flag': len({row['native_material_flag'] for row in observations}) == 1,
            'limitation': 'The label is user-confirmed UI state; no game action or item payload was read.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True, choices=('experience', 'rewind'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--refresh', action='store_true', help='Rediscover read-only metadata after a game restart')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Report must stay in workspace build')
    report = {'read_only': True, 'writes_game_memory': False, 'game_calls': False,
              'sends_requests': False, 'reads_item_uid_list': False,
              'elevated': bool(ctypes.windll.shell32.IsUserAnAdmin())}
    try:
        if args.refresh:
            from probe_cleanup_readonly import discover
            directory = ROOT/'build'/'cleanup-research-current'
            metadata = discover(directory)
            (directory/'runtime-cleanup-metadata.json').write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        report.update(observe(args.label))
    except Exception as error:
        report.update(status='failed', error=str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'output': str(output), 'error': report.get('error')}))
    return 0 if report['status'] == 'material_ui_observed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
