# Adapted from NTE-Drive-Calculator, commit 0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1. AGPL-3.0.
# 定义角色识别与自动装配遍历共享的不可变识别结果。
"""Shared role-recognition contract for navigation and planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleRecognition:
    """A normalized role recognition result."""

    role_name: str | None
    method: str
    confidence: float
    raw_text: str = ""
