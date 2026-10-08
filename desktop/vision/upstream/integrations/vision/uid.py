# Adapted from NTE-Drive-Calculator, commit 0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1. AGPL-3.0.
# 解析阶段使用的本地 UID 去重工具。
"""Helpers for temporary OCR-parser identifiers."""


def make_unique_uid(uid: str, existing_uids: set) -> str:
    if uid not in existing_uids:
        return uid
    base = uid
    suffix = 2
    while f"{base}_{suffix}" in existing_uids:
        suffix += 1
    return f"{base}_{suffix}"
