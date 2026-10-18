"""Small bounded PE section-header reader used by the runtime discovery probes."""
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PESection:
    Name: bytes
    Misc_VirtualSize: int
    VirtualAddress: int
    Characteristics: int


def read_pe_sections(path):
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as stream:
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            raise ValueError("invalid DOS header")
        nt_offset = struct.unpack_from("<I", dos, 0x3C)[0]
        if not 64 <= nt_offset <= min(size - 24, 16 * 1024 * 1024):
            raise ValueError("PE header offset out of bounds")
        stream.seek(nt_offset)
        coff = stream.read(24)
        if len(coff) != 24 or coff[:4] != b"PE\0\0":
            raise ValueError("invalid PE signature")
        machine, section_count = struct.unpack_from("<HH", coff, 4)
        optional_size = struct.unpack_from("<H", coff, 20)[0]
        if machine != 0x8664 or not 1 <= section_count <= 96:
            raise ValueError("unsupported PE architecture or section count")
        if not 0x70 <= optional_size <= 4096:
            raise ValueError("invalid optional-header size")
        optional = stream.read(optional_size)
        if len(optional) != optional_size or struct.unpack_from("<H", optional, 0)[0] != 0x20B:
            raise ValueError("invalid PE32+ optional header")
        section_bytes = section_count * 40
        if stream.tell() + section_bytes > size:
            raise ValueError("section table out of file bounds")
        raw = stream.read(section_bytes)

    sections = []
    for index in range(section_count):
        row = raw[index * 40:(index + 1) * 40]
        name = row[:8].split(b"\0", 1)[0]
        virtual_size, virtual_address = struct.unpack_from("<II", row, 8)
        characteristics = struct.unpack_from("<I", row, 36)[0]
        if virtual_address > 0x80000000 or virtual_size > 0x80000000:
            raise ValueError("section virtual range out of bounds")
        sections.append(PESection(name, virtual_size, virtual_address, characteristics))
    return sections
