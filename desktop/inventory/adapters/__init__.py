"""Capture adapters produce the Keke contract; UI and storage don't speak Core RPC."""
from dataclasses import dataclass
from typing import Protocol, Callable

class SessionChanged(RuntimeError):
    pass

@dataclass
class Observation:
    data: dict
    raw_snapshot: dict | None = None

class CaptureAdapter(Protocol):
    adapter_id: str
    domains: tuple[str, ...]
    def prepare(self, folder: str) -> None: ...
    def open(self, check: Callable[[],None]) -> None: ...
    def read(self, kind: str, check: Callable[[],None], previous: dict | None = None) -> Observation: ...
    def abort(self) -> None: ...
    def close(self) -> None: ...


def create_adapter(adapter_id='nte-native-v1'):
    if adapter_id!='nte-native-v1':
        raise ValueError('尚未安装该采集器')
    from .nte import NteAdapter
    return NteAdapter()
