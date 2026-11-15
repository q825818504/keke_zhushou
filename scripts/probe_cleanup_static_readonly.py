"""Inspect file-backed Unreal registration metadata without loading the game.

This tool has no process attachment, memory-writing, RPC or game invocation code.
The output distinguishes registered fields from unverified calling semantics.
Capstone is an optional local analysis dependency in build/cleanup-research-tools.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
import json
import mmap
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build' / 'cleanup-research-tools'))


class StaticPe:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.stream = self.path.open('rb')
        self.data = mmap.mmap(self.stream.fileno(), 0, access=mmap.ACCESS_READ)
        if not 0x100 <= len(self.data) <= 512 * 1024 * 1024:
            self.close()
            raise ValueError('PE size outside diagnostic budget')
        pe = self.unpack('<I', 0x3c)[0]
        if self.data[:2] != b'MZ' or self.data[pe:pe+4] != b'PE\0\0':
            self.close()
            raise ValueError('Input is not a PE file')
        machine, count = self.unpack('<HH', pe+4)
        optional_size = self.unpack('<H', pe+20)[0]
        if machine != 0x8664 or self.unpack('<H', pe+24)[0] != 0x20b:
            self.close()
            raise ValueError('Diagnostic only admits x86-64 PE32+')
        self.base = self.unpack('<Q', pe+48)[0]
        self.sections = []
        for index in range(count):
            offset = pe+24+optional_size+index*40
            virtual_size, rva, size, raw = self.unpack('<IIII', offset+8)
            flags = self.unpack('<I', offset+36)[0]
            if raw+size > len(self.data):
                raise ValueError('Section exceeds input file')
            self.sections.append((rva, raw, size, virtual_size, flags))
        directory_count = self.unpack('<I', pe+24+108)[0]
        self.functions = []
        if directory_count > 3:
            rva, size = self.unpack('<II', pe+24+112+3*8)
            offset = self.offset(self.base+rva, size) if rva and size else None
            if offset is not None and size % 12 == 0:
                for index in range(size // 12):
                    begin, end, unwind = self.unpack('<III', offset+index*12)
                    if begin < end and self.offset(self.base+begin, end-begin) is not None:
                        self.functions.append((self.base+begin, self.base+end, unwind))
        self.functions.sort()
        self.starts = [row[0] for row in self.functions]
        self._instructions = {}
        self.code_observations = {}

    def add_code_observations(self, report):
        if (report.get('status') != 'read_only_code_observed'
                or report.get('read_only') is not True
                or report.get('game_calls') is not False
                or report.get('writes_game_memory') is not False
                or report.get('game_sha256') != hashlib.sha256(self.data).hexdigest()):
            raise ValueError('Code observations do not match this read-only investigation')
        for chunk in report.get('chunks', []):
            start = int(chunk['static_va'], 16)
            raw = bytes.fromhex(chunk['bytes_hex'])
            bounds = self.function_extent(start)
            if (not bounds or bounds[0] != start or not chunk.get('complete_function')
                    or len(raw) != bounds[1]-bounds[0] or len(raw) > 262144
                    or hashlib.sha256(raw).hexdigest() != chunk['sha256']):
                continue
            self.code_observations[start] = raw
        self._instructions.clear()

    def close(self):
        if getattr(self, 'data', None) is not None:
            self.data.close()
        if getattr(self, 'stream', None) is not None:
            self.stream.close()

    def unpack(self, fmt, offset):
        if not 0 <= offset <= len(self.data)-struct.calcsize(fmt):
            raise ValueError('File read outside input')
        return struct.unpack_from(fmt, self.data, offset)

    def offset(self, address, size=1):
        for rva, raw, length, _, _ in self.sections:
            delta = address-self.base-rva
            if 0 <= delta and delta+size <= length:
                return raw+delta
        return None

    def address(self, offset):
        for rva, raw, length, _, _ in self.sections:
            if raw <= offset < raw+length:
                return self.base+rva+offset-raw
        return None

    def text(self, address, limit=256):
        offset = self.offset(address)
        if offset is None:
            return None
        value = self.data[offset:offset+limit].split(b'\0')[0]
        if not value or len(value) == limit or not all(32 <= byte < 127 for byte in value):
            return None
        return value.decode('ascii')

    def names(self, value):
        pattern = value.encode('ascii')+b'\0'
        offset = 0
        result = []
        while len(result) < 32:
            offset = self.data.find(pattern, offset)
            if offset < 0:
                break
            address = self.address(offset)
            if address is not None:
                result.append((offset, address))
            offset += 1
        return result

    def pointers_to(self, address, limit=64):
        pattern = struct.pack('<Q', address)
        offset = 0
        result = []
        while len(result) < limit:
            offset = self.data.find(pattern, offset)
            if offset < 0:
                break
            result.append(offset)
            offset += 1
        return result

    def function_range(self, address):
        index = bisect_right(self.starts, address)-1
        if index >= 0:
            begin, end, _ = self.functions[index]
            if begin <= address < end:
                return begin, end
        return None

    def unwind_root(self, entry):
        seen = set()
        while entry not in seen and len(seen) < 32:
            seen.add(entry)
            begin, end, unwind = entry
            offset = self.offset(self.base+unwind, 4)
            if offset is None:
                return None
            version_flags, _, count, _ = self.unpack('<BBBB', offset)
            if version_flags & 7 != 1:
                return None
            if not (version_flags >> 3) & 4:
                return entry
            parent = offset+4+((count+1) & ~1)*2
            root_begin, root_end, root_unwind = self.unpack('<III', parent)
            entry = (self.base+root_begin, self.base+root_end, root_unwind)
        return None

    def function_extent(self, address):
        """Contiguous unwind fragments; remote cold fragments remain unknown."""
        index = bisect_right(self.starts, address)-1
        if index < 0 or not self.functions[index][0] <= address < self.functions[index][1]:
            return None
        root = self.unwind_root(self.functions[index])
        if root is None:
            return self.functions[index][:2]
        begin, end, _ = root
        cursor = bisect_right(self.starts, begin)-1
        if cursor < 0 or self.starts[cursor] != begin:
            return self.functions[index][:2]
        for entry in self.functions[cursor+1:cursor+129]:
            if entry[0] != end or self.unwind_root(entry) != root:
                break
            end = entry[1]
        return begin, end

    def instructions(self, address):
        bounds = self.function_extent(address)
        if not bounds or bounds[1]-bounds[0] > 262144:
            return []
        begin, end = bounds
        if begin not in self._instructions:
            from capstone import Cs, CS_ARCH_X86, CS_MODE_64
            decoder = Cs(CS_ARCH_X86, CS_MODE_64)
            decoder.detail = True
            offset = self.offset(begin, end-begin)
            raw = self.code_observations.get(begin, self.data[offset:offset+end-begin])
            # File-backed game code can be absent/encoded. Zero bytes must not
            # be reported as a meaningful stream of x86 add instructions.
            self._instructions[begin] = list(decoder.disasm(raw, begin)) if any(raw) else []
        return self._instructions[begin]

    def data_operands(self, address):
        from capstone.x86 import X86_OP_MEM, X86_REG_RIP
        result = []
        for instruction in self.instructions(address):
            for operand in instruction.operands:
                if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                    target = instruction.address+instruction.size+operand.mem.disp
                    result.append((instruction.address, target, instruction.mnemonic, instruction.op_str))
        return result

    def property(self, address):
        offset = self.offset(address, 64)
        if offset is None:
            return None
        label = self.text(self.unpack('<Q', offset)[0])
        if not label or not label.isidentifier():
            return None
        flags = self.unpack('<Q', offset+16)[0]
        kind = self.unpack('<I', offset+24)[0]
        dim, byte_offset = self.unpack('<HH', offset+48)
        extra = self.unpack('<Q', offset+56)[0]
        boolean = (kind & 0x3f) == 0xc
        return {'name': label, 'registration_va': hex(address), 'property_flags': hex(flags),
                'generation_flags': hex(kind), 'array_dim': dim,
                'offset_candidate': None if boolean else byte_offset, 'extra_pointer': hex(extra),
                'boolean_layout_requires_setter_decode': boolean}

    def property_array(self, address, count):
        if not 0 <= count <= 128:
            return None
        if not count:
            return [] if address == 0 else None
        offset = self.offset(address, count*8)
        if offset is None:
            return None
        properties = [self.property(self.unpack('<Q', offset+i*8)[0]) for i in range(count)]
        return properties if all(properties) else None

    def struct_at(self, address):
        offset = self.offset(address, 56)
        if offset is None:
            return None
        outer, parent, ops, name, array = self.unpack('<QQQQQ', offset)
        count, size, align = self.unpack('<HHI', offset+40)
        label = self.text(name)
        if (not label or not label.isidentifier() or not 1 <= size <= 65535
                or align not in (1, 2, 4, 8, 16) or not self.function_range(outer)
                or not self.function_range(ops)):
            return None
        properties = self.property_array(array, count)
        if properties is None:
            return None
        return {'name': label, 'descriptor_va': hex(address), 'size': size, 'alignment': align,
                'registered_property_count': count, 'properties': properties,
                'status': 'static_registration_candidate'}

    def struct_constructor(self, address):
        result = []
        for _, target, mnemonic, _ in self.data_operands(address):
            if mnemonic == 'lea':
                candidate = self.struct_at(target)
                if candidate and candidate not in result:
                    result.append(candidate)
        return result

    def function_metadata(self, name):
        result = []
        for _, name_address in self.names(name):
            for reference in self.pointers_to(name_address):
                offset = reference-16
                if offset < 0:
                    continue
                outer, parent, label, array = self.unpack('<QQQQ', offset)
                count, size, objects, flags = self.unpack('<HHII', offset+32)
                if label != name_address or not self.function_range(outer) or not 1 <= count <= 128 or size > 65535:
                    continue
                properties = self.property_array(array, count)
                if properties is not None:
                    result.append({'name': name, 'descriptor_va': hex(self.address(offset)),
                                   'parameter_size': size, 'function_flags': hex(flags),
                                   'properties': properties})
        return result

    def enum_for(self, name):
        result = []
        qualifier = name.rsplit('::', 1)[0]+'::' if '::' in name else None
        def entry(offset):
            if not 0 <= offset <= len(self.data)-16:
                return None
            ptr, value = self.unpack('<Qq', offset)
            label = self.text(ptr)
            if qualifier and (not label or not label.startswith(qualifier)):
                return None
            return (label, value) if label and re.fullmatch(r'[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*', label) and -1 <= value <= 65535 else None
        for _, name_address in self.names(name):
            for reference in self.pointers_to(name_address):
                start = reference
                while entry(start-16) and reference-start < 65536:
                    start -= 16
                entries = []
                cursor = start
                while len(entries) < 4096 and entry(cursor):
                    label, value = entry(cursor)
                    entries.append({'name': label, 'value': value})
                    cursor += 16
                for owner in self.pointers_to(self.address(start)):
                    offset = owner-32
                    if offset < 0:
                        continue
                    label = self.text(self.unpack('<Q', offset+16)[0])
                    # NumEnumerators is uint16; subsequent bytes are enum flags.
                    count = self.unpack('<H', offset+44)[0]
                    if label and label.isidentifier() and count == len(entries):
                        candidate = {'enum': label, 'table_va': hex(self.address(start)),
                                     'count': count, 'entries': entries,
                                     'limitation': 'Registration enum values are not a complete wire protocol.'}
                        if candidate not in result:
                            result.append(candidate)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--code-report', type=Path)
    args = parser.parse_args()
    image = StaticPe(args.game)
    try:
        digest = hashlib.sha256(image.data).hexdigest()
        if args.expected_sha256 and digest != args.expected_sha256.lower():
            raise ValueError('Input identity differs from requested executable')
        if args.code_report:
            image.add_code_observations(json.loads(args.code_report.read_text(encoding='utf-8')))
        functions = []
        structures = {}
        for name in ('ServerCommonFunRPC', 'ClientCommonFunRPC', 'ServerEquipmentItemLocked',
                     'ServerComposeRPC'):
            for function in image.function_metadata(name):
                functions.append(function)
                for prop in function['properties']:
                    if prop['generation_flags'] == '0x19':
                        ctor = int(prop['extra_pointer'], 16)
                        structures[hex(ctor)] = image.struct_constructor(ctor)
        result = {'read_only': True, 'executes_target': False, 'attaches_to_process': False,
                  'sends_requests': False, 'game_sha256': digest,
                  'image_base': hex(image.base), 'functions': functions,
                  'referenced_structures': structures,
                  'request_enum': image.enum_for('EquipDecompose_Request'),
                  'limitations': ['Static metadata is not a verified decomposition call contract.',
                                 'Material mode, payload semantics and success receipt remain unverified.']}
        if hashlib.sha256(image.data).hexdigest() != digest:
            raise ValueError('Input file changed while reading')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'output': str(args.output.resolve()), 'functions': len(functions),
                          'referenced_structures': structures}, ensure_ascii=False))
    finally:
        image.close()


if __name__ == '__main__':
    main()
