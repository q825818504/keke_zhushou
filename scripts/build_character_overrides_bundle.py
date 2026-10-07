#!/usr/bin/env python3
"""Build the small maintainer override bundle without rewriting imported sources."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "knowledge" / "character_overrides.json"
TARGET = ROOT / "data" / "knowledge" / "character_overrides.js"


def render_bundle(overrides: dict) -> str:
    if not isinstance(overrides, dict) or not isinstance(overrides.get("characters", {}), dict):
        raise ValueError("character_overrides.json must contain a characters object")
    payload = json.dumps(overrides, ensure_ascii=False, separators=(",", ":"))
    return "window.characterOverrides = " + payload + ";\n"


def main() -> None:
    overrides = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    TARGET.write_text(render_bundle(overrides), encoding="utf-8", newline="")
    print(f"Built {TARGET.relative_to(ROOT)} from {SOURCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
