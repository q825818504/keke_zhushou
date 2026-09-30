#!/usr/bin/env python3
"""Build the browser bundle from the canonical local team-template catalog."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "knowledge" / "team_templates.json"
TARGET = ROOT / "data" / "knowledge" / "team_templates.js"


def main() -> None:
    catalog = json.loads(SOURCE.read_text(encoding="utf-8"))
    payload = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    TARGET.write_text("window.teamTemplateKnowledge = " + payload + ";" + chr(10), encoding="utf-8", newline="")
    print(f"Built {TARGET.relative_to(ROOT)} from {SOURCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
