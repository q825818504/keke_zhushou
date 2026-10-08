# Adapted from NTE-Drive-Calculator, commit 0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1. AGPL-3.0.
# 定义项目通用异常类型。
"""Project-specific exception types."""

class NTEBaseError(Exception):
    pass


class OCRParseError(NTEBaseError):
    pass


class InventoryEmptyError(NTEBaseError):
    pass


class ConfigMissingError(NTEBaseError):
    pass
