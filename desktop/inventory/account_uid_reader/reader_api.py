"""Small ctypes surface for the first-party read-only native helper."""
import ctypes as C
import hashlib
from pathlib import Path
import sys

READ = C.CFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint32)
NAME = C.CFUNCTYPE(C.c_uint32, C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint32)
EXPECTED_DLL_SHA256 = "45a5db8e189114bf2f236e7153e79a23ecba30e196f5a0d87feb124fbbd3414f"


class Field(C.Structure):
    _fields_ = [("property", C.c_uint64), ("offset", C.c_uint32), ("size", C.c_uint32)]


class Roots(C.Structure):
    _fields_ = [(name, C.c_uint64) for name in
                ("world", "game_instance", "controller", "player_state", "inventory")]


class ProcessNameCacheEntry(C.Structure):
    _fields_ = [("index", C.c_uint32), ("length", C.c_uint32),
                ("valid", C.c_uint32), ("reserved", C.c_uint32),
                ("utf8", C.c_char * 512)]


class ProcessReadContext(C.Structure):
    _fields_ = [("handle", C.c_void_p), ("calls", C.c_int64), ("bytes", C.c_int64),
                ("max_calls", C.c_uint64), ("max_bytes", C.c_uint64),
                ("name_block_addresses", C.c_void_p), ("name_block_count", C.c_uint32),
                ("name_cache", C.c_void_p), ("name_cache_capacity", C.c_uint32)]


def _native_path():
    if hasattr(sys, "_MEIPASS"):
        root = Path(sys._MEIPASS)
        return root / "inventory" / "account_uid_reader" / "native" / "KekeNativeReader.dll"
    return Path(__file__).resolve().parent / "native" / "KekeNativeReader.dll"


def load():
    path = _native_path()
    if not path.is_file():
        raise RuntimeError("UID只读组件缺失，请重新安装可可助手")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != EXPECTED_DLL_SHA256:
        raise RuntimeError("UID只读组件完整性校验失败，请重新安装可可助手")
    dll = C.CDLL(str(path))
    dll.keke_reader_api_version.argtypes = []
    dll.keke_reader_api_version.restype = C.c_uint32
    if dll.keke_reader_api_version() != 1:
        raise RuntimeError("UID只读组件版本不兼容")
    dll.keke_process_read_memory.argtypes = [C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint32]
    dll.keke_process_read_memory.restype = C.c_uint32
    dll.keke_process_account_read.argtypes = [C.POINTER(ProcessReadContext), C.c_uint32]
    dll.keke_process_account_read.restype = C.c_uint32
    dll.keke_process_name.argtypes = [C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint32]
    dll.keke_process_name.restype = C.c_uint32
    dll.keke_find_property.argtypes = [READ, NAME, C.c_void_p, C.c_uint64, C.c_char_p, C.POINTER(Field)]
    dll.keke_find_property.restype = C.c_uint32
    dll.keke_inventory_roots.argtypes = [READ, NAME, C.c_void_p, C.c_uint64, C.POINTER(Roots)]
    dll.keke_inventory_roots.restype = C.c_uint32
    return dll


class Adapter:
    def __init__(self, reader, pool, max_calls=800000, max_bytes=256 * 1024 * 1024):
        self.reader = reader
        self.dll = load()
        if not reader.handle:
            raise RuntimeError("游戏进程读取句柄已关闭")
        self.native_context = ProcessReadContext(
            C.cast(reader.handle, C.c_void_p), 0, 0, max_calls, max_bytes,
            None, 0, None, 0,
        )
        self.read_user = C.cast(C.pointer(self.native_context), C.c_void_p)
        self.read_cb = C.cast(self.dll.keke_process_read_memory, READ)
        self.name_cb = C.cast(self.dll.keke_process_name, NAME)
        blocks = struct_unpack_blocks(self, pool)
        self.name_block_addresses = (C.c_uint64 * len(blocks))(*blocks)
        self.name_cache_capacity = 1024
        self.name_cache = (ProcessNameCacheEntry * self.name_cache_capacity)()
        self.native_context.name_block_addresses = C.cast(self.name_block_addresses, C.c_void_p).value
        self.native_context.name_block_count = len(blocks)
        self.native_context.name_cache = C.cast(self.name_cache, C.c_void_p).value
        self.native_context.name_cache_capacity = self.name_cache_capacity
        self.cache = {}

    def read(self, address, size):
        if (type(address) is not int or not 0x10000 <= address < 0x800000000000
                or type(size) is not int or not 1 <= size <= 1024 * 1024):
            raise ValueError("UID只读组件请求超出边界")
        if self.dll.keke_process_account_read(C.byref(self.native_context), size) != 0:
            raise RuntimeError("UID只读读取超过安全预算")
        return self.reader.read(address, size)

    def name(self, token):
        token = int(token)
        if token not in self.cache:
            output = C.create_string_buffer(4096)
            if self.name_cb(self.read_user, token, output, len(output)) != 1:
                raise ValueError("NamePool名称解析失败")
            self.cache[token] = output.value.decode("utf-8", errors="strict")
        return self.cache[token]

    def object_name(self, address):
        return self.name(int.from_bytes(self.read(address + 24, 8), "little"))

    def class_name(self, address):
        return self.object_name(int.from_bytes(self.read(address + 16, 8), "little"))

    def field(self, dll, address, label):
        field = Field()
        status = dll.keke_find_property(self.read_cb, self.name_cb, self.read_user,
                                        address, label.encode("ascii"), C.byref(field))
        return status, field


def struct_unpack_blocks(adapter, pool):
    import struct
    count = pool.get("current_block")
    address = int(pool.get("address", "0"), 16)
    if type(count) is not int or not 0 <= count < 8192:
        raise ValueError("NamePool块数量无效")
    raw = adapter.read(address + 16, (count + 1) * 8)
    blocks = struct.unpack("<" + "Q" * (count + 1), raw)
    if any(not 0x10000 <= block < 0x800000000000 for block in blocks):
        raise ValueError("NamePool块地址无效")
    return blocks
