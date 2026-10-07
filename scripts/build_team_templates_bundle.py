#!/usr/bin/env python3
"""Build the browser bundle from the canonical local team-template catalog."""

from __future__ import annotations

import json
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "knowledge" / "team_templates.json"
OVERRIDES = ROOT / "data" / "knowledge" / "team_overrides.json"
TARGET = ROOT / "data" / "knowledge" / "team_templates.js"


def load_overrides() -> dict:
    if not OVERRIDES.exists():
        return {"schema_version": "1.0.0", "edits": {}, "removed": []}
    value = json.loads(OVERRIDES.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("team_overrides.json must be an object")
    edits = value.get("edits", {})
    removed = value.get("removed", [])
    if not isinstance(edits, dict) or not isinstance(removed, list):
        raise ValueError("team overrides must contain an edits object and removed array")
    return {"schema_version": "1.0.0", "edits": edits, "removed": removed}


def render_bundle(catalog: dict, overrides: dict) -> str:
    teams = catalog.get("teams", [])
    if not isinstance(teams, list):
        raise ValueError("team_templates.json must contain a teams array")
    merged = copy.deepcopy(catalog)
    ordered = []
    by_id = {}
    for team in teams:
        if not isinstance(team, dict) or not isinstance(team.get("id"), str):
            raise ValueError("every source team must have a string id")
        by_id[team["id"]] = len(ordered)
        ordered.append(copy.deepcopy(team))
    for ident, team in overrides["edits"].items():
        if not isinstance(team, dict) or team.get("id") != ident:
            raise ValueError(f"team override id mismatch: {ident}")
        if ident in by_id:
            ordered[by_id[ident]] = copy.deepcopy(team)
        else:
            by_id[ident] = len(ordered)
            ordered.append(copy.deepcopy(team))
    removed = set(overrides["removed"])
    merged["teams"] = [team for team in ordered if team["id"] not in removed]
    payload = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    override_payload = json.dumps(overrides, ensure_ascii=False, separators=(",", ":"))
    return (
        "window.teamTemplateKnowledge = " + payload + ";\n"
        "window.teamGuideOverrides = " + override_payload + ";\n"
    )


def main() -> None:
    catalog = json.loads(SOURCE.read_text(encoding="utf-8"))
    TARGET.write_text(render_bundle(catalog, load_overrides()), encoding="utf-8", newline="")
    print(f"Built {TARGET.relative_to(ROOT)} from {SOURCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
