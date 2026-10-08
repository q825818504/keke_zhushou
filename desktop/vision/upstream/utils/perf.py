# Adapted from NTE-Drive-Calculator, commit 0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1. AGPL-3.0.
# 输出统一格式的性能统计日志。
"""Small helpers for PERF-prefixed runtime timing logs."""

from __future__ import annotations

import math
import re
from typing import Any

_SPACE_RE = re.compile(r"\s+")


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        if math.isfinite(value):
            return f"{value:.2f}"
        return str(value)
    text = str(value)
    return _SPACE_RE.sub("_", text.strip())


def format_perf_line(event: str, *, elapsed_ms: float, **fields: Any) -> str:
    parts = [f"PERF {event}", f"elapsed_ms={elapsed_ms:.2f}"]
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={_format_value(value)}")
    return " ".join(parts)


def log_perf(logger, event: str, *, elapsed_ms: float, **fields: Any) -> None:
    logger.info(format_perf_line(event, elapsed_ms=elapsed_ms, **fields))
