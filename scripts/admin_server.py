#!/usr/bin/env python3
"""Loopback-only admin bridge for writing maintained data and syncing Git."""

from __future__ import annotations

import base64
import argparse
import copy
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "data" / "knowledge"
TEAM_SOURCE = KNOWLEDGE / "team_templates.json"
TEAM_OVERRIDES = KNOWLEDGE / "team_overrides.json"
TEAM_BUNDLE = KNOWLEDGE / "team_templates.js"
CHAR_OVERRIDES = KNOWLEDGE / "character_overrides.json"
CHAR_BUNDLE = KNOWLEDGE / "character_overrides.js"
ESPER_CYCLES = KNOWLEDGE / "esper_cycles.json"
ESPER_CYCLE_BUNDLE = KNOWLEDGE / "esper_cycles.js"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024
SAFE_ROOT_FILES = {
    "index.html", "app.js", "styles.css", "team_manager.js",
    "character_recommendations.js", "reactions.js", "admin_bridge.js", "terminal_puzzle.js", "terminal_editor.js", "drive_layout_solver.js",
}
ELEMENTS = {"光", "暗", "灵", "咒", "魂", "相"}
ROLE_BASIC_FIELDS = {"rarity", "element", "cassette_type", "role", "position", "rating", "summary"}
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,120}$")
GIT_PATHS = {
    "data/knowledge/team_overrides.json",
    "data/knowledge/team_templates.js",
    "data/knowledge/character_overrides.json",
    "data/knowledge/character_overrides.js",
    "data/knowledge/esper_cycles.json",
    "data/knowledge/esper_cycles.js",
}

sys.path.insert(0, str(ROOT / "scripts"))
from build_character_overrides_bundle import render_bundle as render_character_bundle  # noqa: E402
from build_team_templates_bundle import render_bundle as render_team_bundle  # noqa: E402
sys.path.insert(0,str(ROOT/'desktop'))
import release_publish


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return copy.deepcopy(default)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _pretty_json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _backup_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return base / "KekeAssistant" / "repo-write-backups"


def _write_transaction(changes: dict[Path, bytes], deletes: tuple[Path, ...] = ()) -> None:
    targets = list(dict.fromkeys([*changes.keys(), *deletes]))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = _backup_root() / stamp
    old_bytes: dict[Path, bytes | None] = {}
    staged: dict[Path, Path] = {}
    for path in targets:
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("拒绝写入仓库目录以外的文件")
        old_bytes[path] = path.read_bytes() if path.is_file() else None
        if old_bytes[path] is not None:
            backup_path = backup_dir / path.relative_to(ROOT)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
    try:
        for path, payload in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
                staged[path] = Path(stream.name)
        for path, staged_path in staged.items():
            os.replace(staged_path, path)
        for path in deletes:
            path.unlink(missing_ok=True)
    except Exception:
        for path, original in old_bytes.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.restore.", delete=False) as stream:
                    stream.write(original)
                    restore_path = Path(stream.name)
                os.replace(restore_path, path)
        raise
    finally:
        for staged_path in staged.values():
            staged_path.unlink(missing_ok=True)


def _character_ids() -> set[str]:
    ids = set()
    for path in (KNOWLEDGE / "characters").glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        ident = value.get("id") if isinstance(value, dict) else None
        if isinstance(ident, str) and ID_PATTERN.fullmatch(ident):
            ids.add(ident)
    return ids


def _character_name(ident: str) -> str:
    for path in (KNOWLEDGE / "characters").glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, dict) and value.get("id") == ident and isinstance(value.get("name"), str):
            return value["name"]
    return ident


def _layout_relative_paths(ident: str) -> set[str]:
    if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident):
        return set()
    base = f"data/resources/characters/{ident}/drive-layout"
    return {base + suffix for suffix in (".png", ".jpg", ".webp")}


def _validate_team(record: dict, known_ids: set[str], expected_id: str | None = None) -> dict:
    if not isinstance(record, dict):
        raise ValueError("阵容记录必须是对象")
    ident = record.get("id")
    if not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident) or (expected_id and ident != expected_id):
        raise ValueError("阵容编号无效")
    members = record.get("member_character_ids")
    if (not isinstance(members, list) or len(members) != 4
            or any(not isinstance(item, str) for item in members)
            or len(set(members)) != 4 or any(item not in known_ids for item in members)):
        raise ValueError(f"阵容 {ident} 必须包含四名不同的已知角色")
    if record.get("source_core_character_id") not in members:
        raise ValueError(f"阵容 {ident} 的主C必须在队伍中")
    title = record.get("source_archetype")
    if not isinstance(title, str) or not title.strip() or len(title) > 80:
        raise ValueError(f"阵容 {ident} 名称需为 1–80 个字符")
    editorial = record.get("editorial") or {}
    if not isinstance(editorial, dict):
        raise ValueError(f"阵容 {ident} 的攻略说明格式无效")
    notes = editorial.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 3000:
        raise ValueError(f"阵容 {ident} 的攻略说明不能超过 3000 字")
    return copy.deepcopy(record)


def _validate_team_overrides(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("阵容覆盖数据格式无效")
    edits = value.get("edits", {})
    removed = value.get("removed", [])
    if not isinstance(edits, dict) or len(edits) > 2000 or not isinstance(removed, list) or len(removed) > 2000:
        raise ValueError("阵容覆盖数据超出允许范围")
    known_ids = _character_ids()
    checked = {}
    for ident, team in edits.items():
        checked[ident] = _validate_team(team, known_ids, ident)
    if any(not isinstance(ident, str) or not ID_PATTERN.fullmatch(ident) for ident in removed):
        raise ValueError("已删除阵容编号无效")
    return {"schema_version": "1.0.0", "edits": checked, "removed": sorted(set(removed))}


def _validate_terminal_puzzle(ident: str, value: dict, cassette_id=None) -> dict:
    """Validate fixed catalog footprints against the character's actual terminal."""
    footprints = {
        "cell2_style1_1": [(0, 0), (0, 1)], "cell2_style2_1": [(0, 0), (1, 0)],
        "cell3_style1_1": [(0, 0), (0, 1), (0, 2)], "cell3_style2_1": [(0, 0), (1, 0), (2, 0)],
        "cell3_style3_1": [(0, 0), (0, 1), (1, 0)], "cell3_style4_1": [(0, 0), (0, 1), (1, 1)],
        "cell3_style5_1": [(0, 0), (1, 0), (1, 1)], "cell3_style6_1": [(0, 1), (1, 0), (1, 1)],
        "cell4_style1_1": [(0, 0), (0, 1), (0, 2), (0, 3)], "cell4_style2_1": [(0, 0), (1, 0), (2, 0), (3, 0)],
        "cell4_style5_1": [(0, 1), (0, 2), (1, 0), (1, 1)], "cell4_style6_1": [(0, 1), (1, 0), (1, 1), (2, 0)],
    }
    character = json.loads((KNOWLEDGE / "characters" / (ident + ".json")).read_text(encoding="utf-8"))
    terminal = character.get("terminal") or character.get("recommended", {}).get("cassette", {}).get("terminal") or {}
    slots = {(slot["row"], slot["column"]) for slot in terminal.get("layout", {}).get("active_slots", [])}
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1
            or type(value.get("preferred_model")) is not int or value["preferred_model"] not in (0, 2, 3, 4)
            or not isinstance(value.get("pieces"), list) or not slots or len(value["pieces"]) > len(slots) // 2):
        raise ValueError("终端摆法格式无效")
    occupied, ids, pieces = set(), set(), []
    for piece in value["pieces"]:
        if (not isinstance(piece, dict) or not isinstance(piece.get("id"), str)
                or not re.fullmatch(r"D\d{2,3}", piece["id"]) or piece["id"] in ids
                or not isinstance(piece.get("shape_id"), str) or piece["shape_id"] not in footprints
                or type(piece.get("row")) is not int or type(piece.get("column")) is not int):
            raise ValueError("终端驱动编号或形状无效")
        cells = {(piece["row"] + r, piece["column"] + c) for r, c in footprints[piece["shape_id"]]}
        if not cells <= slots or cells & occupied:
            raise ValueError("终端驱动重叠或超出可用槽位")
        occupied.update(cells)
        ids.add(piece["id"])
        pieces.append({key: piece[key] for key in ("id", "shape_id", "row", "column")})
    cassette_id = cassette_id or value.get("cassette_id")
    catalog = json.loads((KNOWLEDGE / "encyclopedia/sky_curtains.json").read_text(encoding="utf-8"))
    cassette = next((item for item in catalog["items"] if item["id"] == cassette_id), None)
    required = cassette.get("set_requirements", {}).get("required_drives") if cassette else None
    if not required or value.get("cassette_id") != cassette_id:
        raise ValueError("摆法与所选空幕不一致，请重新计算")
    counts = {}
    for piece in pieces:
        counts[piece["shape_id"]] = counts.get(piece["shape_id"], 0) + 1
    if any(counts.get(item["shape_id"], 0) < item["count"] for item in required):
        raise ValueError("摆法未满足完整4件套所需形状")
    return {"version": 1, "preferred_model": value["preferred_model"], "cassette_id": cassette_id, "pieces": pieces}


def _validate_recommendations(value: dict) -> dict:
    if not isinstance(value, dict) or len(value) > 200:
        raise ValueError("角色推荐数据格式无效")
    known = _character_ids()
    checked = {}
    for ident, recommendation in value.items():
        if ident not in known or not isinstance(recommendation, dict):
            raise ValueError(f"未知角色或无效推荐：{ident}")
        record = {}
        for kind in ("weapon", "cassette"):
            item = recommendation.get(kind)
            if item is None:
                record[kind] = None
                continue
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str):
                raise ValueError(f"{ident} 的 {kind} 推荐格式无效")
            if len(item["id"]) > 120 or len(item["name"]) > 120:
                raise ValueError("推荐名称或编号过长")
            for affix_key in ("recommended_main_affixes", "recommended_sub_affixes"):
                affixes = item.get(affix_key, [])
                if not isinstance(affixes, list) or len(affixes) > 40:
                    raise ValueError("推荐词条列表格式无效")
                for affix in affixes:
                    priority = affix.get("priority") if isinstance(affix, dict) else None
                    if (not isinstance(affix, dict) or not isinstance(affix.get("name"), str)
                            or type(priority) is not int or not 1 <= priority <= 5):
                        raise ValueError("词条优先级必须为 1–5")
            record[kind] = copy.deepcopy(item)
        if "terminal_puzzle" in recommendation:
            record["terminal_puzzle"] = _validate_terminal_puzzle(ident, recommendation["terminal_puzzle"], (recommendation.get("cassette") or {}).get("id"))
        checked[ident] = record
    return checked


def _validate_basic_patch(value: dict) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("basic"), dict):
        raise ValueError("角色基础资料格式无效")
    name = value.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError("角色名称需为 1–80 个字符")
    basic = value["basic"]
    if set(basic) - ROLE_BASIC_FIELDS:
        raise ValueError("角色基础资料包含不允许修改的字段")
    checked = {}
    for key, item in basic.items():
        if not isinstance(item, str) or len(item) > 300:
            raise ValueError(f"基础资料字段 {key} 格式无效")
        checked[key] = item.strip()
    if checked.get("element") and checked["element"] not in ELEMENTS:
        raise ValueError("角色属性无效")
    return {"name": name.strip(), "basic": checked}


def _validated_text(value, field: str, limit: int, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{field} 格式无效")
    return value.strip() if field.endswith("名称") or field.endswith("标签") else value


def _validate_character_content(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("角色技能、觉醒与共鸣资料格式无效")
    checked = {}
    if "skills" in value:
        skills = value["skills"]
        if not isinstance(skills, list) or len(skills) > 50:
            raise ValueError("角色技能数量无效")
        result = []
        for skill in skills:
            if not isinstance(skill, dict):
                raise ValueError("技能条目格式无效")
            item = copy.deepcopy(skill)
            item["name"] = _validated_text(item.get("name"), "技能名称", 200, required=True)
            for key, label, limit in (("id", "技能 ID", 200), ("category", "技能分类", 100), ("raw_text", "技能描述", 20000)):
                if key in item:
                    item[key] = _validated_text(item[key] if item[key] is not None else "", label, limit)
            if "level_cap" in item:
                level_cap = item["level_cap"]
                # Passive, peculiarity, and city skills use 0 to mean they do
                # not have an upgradeable level cap in the source data.
                if isinstance(level_cap, bool) or not isinstance(level_cap, int) or not 0 <= level_cap <= 99:
                    raise ValueError("技能等级上限需为 0–99 的整数")
            parts = item.get("description_parts", [])
            if not isinstance(parts, list) or len(parts) > 100:
                raise ValueError("技能分段说明数量无效")
            for part in parts:
                if not isinstance(part, dict):
                    raise ValueError("技能分段说明格式无效")
                if "name" in part:
                    part["name"] = _validated_text(part["name"] if part["name"] is not None else "", "分段标题", 200)
                if "text" in part:
                    part["text"] = _validated_text(part["text"] if part["text"] is not None else "", "分段内容", 5000)
            parameters = item.get("parameters", [])
            if not isinstance(parameters, list) or len(parameters) > 100:
                raise ValueError("技能倍率参数数量无效")
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    raise ValueError("技能倍率参数格式无效")
                if "label" in parameter:
                    parameter["label"] = _validated_text(parameter["label"] if parameter["label"] is not None else "", "参数名称", 200)
                values = parameter.get("values", [])
                if not isinstance(values, list) or len(values) > 100:
                    raise ValueError("技能倍率数值数量无效")
                parameter["values"] = [
                    _validated_text(str(entry) if isinstance(entry, (int, float)) and not isinstance(entry, bool) else entry, "技能倍率数值", 300)
                    for entry in values
                ]
                if "current_value" in parameter:
                    current_value = parameter["current_value"]
                    if current_value is None:
                        current_value = ""
                    elif isinstance(current_value, (int, float)) and not isinstance(current_value, bool):
                        current_value = str(current_value)
                    parameter["current_value"] = _validated_text(current_value, "当前倍率数值", 300)
            result.append(item)
        checked["skills"] = result
    if "awakenings" in value:
        awakenings = value["awakenings"]
        if not isinstance(awakenings, list) or len(awakenings) > 30:
            raise ValueError("觉醒节点数量无效")
        result = []
        for awakening in awakenings:
            if not isinstance(awakening, dict):
                raise ValueError("觉醒节点格式无效")
            item = copy.deepcopy(awakening)
            item["name"] = _validated_text(item.get("name"), "觉醒名称", 200, required=True)
            item["description"] = _validated_text(item.get("description") if item.get("description") is not None else "", "觉醒描述", 5000)
            if "asset" in item:
                item["asset"] = _validated_text(item["asset"] if item["asset"] is not None else "", "觉醒图片路径", 500)
            result.append(item)
        checked["awakenings"] = result
    if "resonance" in value:
        resonance = value["resonance"]
        if not isinstance(resonance, list) or len(resonance) > 30:
            raise ValueError("共鸣节点数量无效")
        result = []
        for entry in resonance:
            if not isinstance(entry, dict):
                raise ValueError("共鸣节点格式无效")
            item = copy.deepcopy(entry)
            item["name"] = _validated_text(item.get("name"), "共鸣节点名称", 200, required=True)
            item["description"] = _validated_text(item.get("description") if item.get("description") is not None else "", "共鸣节点描述", 5000)
            if "asset" in item:
                item["asset"] = _validated_text(item["asset"] if item["asset"] is not None else "", "共鸣节点图片路径", 500)
            level = item.get("level")
            if level is not None and (isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 6):
                raise ValueError("共鸣等级需为 1–6 的整数")
            result.append(item)
        checked["resonance"] = result
    return checked


def _load_esper_cycles() -> dict:
    value = _read_json(ESPER_CYCLES, {"schema_version": "1.0.0", "cycles": []})
    if not isinstance(value.get("cycles"), list):
        raise ValueError("反应资料格式无效")
    return value


def _validate_reaction_enhancements(value: list, cycle_document: dict) -> list:
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError("角色反应强化数量无效")
    known_cycles = {cycle.get("id"): cycle for cycle in cycle_document["cycles"] if isinstance(cycle, dict) and isinstance(cycle.get("id"), str)}
    checked = []
    seen = set()
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("角色反应强化条目格式无效")
        cycle_id = entry.get("cycle_id")
        if not isinstance(cycle_id, str) or cycle_id not in known_cycles:
            raise ValueError("角色反应强化缺少有效反应类型")
        if cycle_id in seen:
            raise ValueError("同一角色不能重复选择相同反应类型")
        seen.add(cycle_id)
        item = copy.deepcopy(entry)
        item["cycle_id"] = cycle_id
        item["label"] = _validated_text(item.get("label", "被动技能"), "强化标签", 100)
        item["description"] = _validated_text(item.get("description", ""), "反应强化描述", 5000)
        if "image" in item and item["image"] is not None and not isinstance(item["image"], dict):
            raise ValueError("反应强化图片资料格式无效")
        checked.append(item)
    return checked


def _replace_character_reaction_enhancements(cycle_document: dict, ident: str, name: str, entries: list) -> None:
    by_cycle = {entry["cycle_id"]: entry for entry in entries}
    for cycle in cycle_document["cycles"]:
        current = cycle.get("enhancements", [])
        if not isinstance(current, list):
            raise ValueError("反应强化资料格式无效")
        retained = [entry for entry in current if not isinstance(entry, dict) or entry.get("character_id") != ident]
        entry = by_cycle.get(cycle.get("id"))
        if entry:
            record = copy.deepcopy(entry)
            record.pop("cycle_id", None)
            record.pop("cycle_name", None)
            record["character_id"] = ident
            record["character_name"] = name
            retained.append(record)
        cycle["enhancements"] = retained


def _load_character_overrides() -> dict:
    value = _read_json(CHAR_OVERRIDES, {"schema_version": "1.0.0", "characters": {}})
    characters = value.get("characters", {})
    if not isinstance(characters, dict):
        raise ValueError("角色覆盖数据格式无效")
    return {"schema_version": "1.0.0", "characters": characters}


def _commit_bundles(team_overrides: dict | None = None, character_overrides: dict | None = None,
                    esper_cycles: dict | None = None,
                    extra_changes: dict[Path, bytes] | None = None, deletes: tuple[Path, ...] = ()) -> None:
    changes = dict(extra_changes or {})
    if team_overrides is not None:
        catalog = _read_json(TEAM_SOURCE, {"schema_version": "1.0.0", "teams": []})
        changes[TEAM_OVERRIDES] = _pretty_json(team_overrides)
        changes[TEAM_BUNDLE] = render_team_bundle(catalog, team_overrides).encode("utf-8")
    if character_overrides is not None:
        changes[CHAR_OVERRIDES] = _pretty_json(character_overrides)
        changes[CHAR_BUNDLE] = render_character_bundle(character_overrides).encode("utf-8")
    if esper_cycles is not None:
        changes[ESPER_CYCLES] = _pretty_json(esper_cycles)
        bundle = "window.esperCycleKnowledge = " + json.dumps(esper_cycles, ensure_ascii=False, separators=(",", ":")) + ";\n"
        changes[ESPER_CYCLE_BUNDLE] = bundle.encode("utf-8")
    _write_transaction(changes, deletes)


def _run_git(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("未找到 Git。请先安装 Git for Windows 或 GitHub Desktop。")
    return subprocess.run(
        [git, "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        shell=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def _git_status() -> dict:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch.returncode != 0:
        raise RuntimeError(branch.stderr.strip() or "无法读取当前 Git 分支")
    branch_name = branch.stdout.strip()
    if not branch_name or branch_name == "HEAD":
        raise RuntimeError("当前处于 detached HEAD；请用 GitHub Desktop 切换到 main 分支")
    status = _run_git(["status", "--porcelain=v1", "--untracked-files=normal"])
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "无法读取 Git 工作区状态")
    upstream = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    upstream_name = upstream.stdout.strip() if upstream.returncode == 0 else f"origin/{branch_name}"
    behind = ahead = 0
    count = _run_git(["rev-list", "--left-right", "--count", f"{upstream_name}...HEAD"])
    if count.returncode == 0:
        values = count.stdout.split()
        if len(values) == 2:
            behind, ahead = map(int, values)
    entries = [line for line in status.stdout.splitlines() if line]
    return {
        "available": True,
        "branch": branch_name,
        "upstream": upstream_name,
        "behind": behind,
        "ahead": ahead,
        "dirty": bool(entries),
        "changes": entries[:100],
        "remoteConfigured": _run_git(["remote", "get-url", "origin"]).returncode == 0,
    }


def _managed_git_paths() -> list[str]:
    paths = set(GIT_PATHS)
    tracked_layout_paths: set[str] = set()
    tracked_layouts = _run_git(["ls-files", "-z", "--", "data/resources/characters/*/drive-layout.*"])
    if tracked_layouts.returncode == 0:
        tracked_layout_paths = {path for path in tracked_layouts.stdout.split("\0") if path}
        paths.update(tracked_layout_paths)
    resource_root = ROOT / "data" / "resources" / "characters"
    if resource_root.exists():
        for candidate in resource_root.glob("*/drive-layout.*"):
            if candidate.suffix.lower() in {".png", ".jpg", ".webp"}:
                paths.add(candidate.relative_to(ROOT).as_posix())
    return sorted(path for path in paths if path in tracked_layout_paths or (ROOT / Path(path)).is_file())


def _git_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr.strip() or result.stdout.strip() or f"Git 命令失败（退出码 {result.returncode}）")[-3000:]


def _paths_overlap(left: str, right: str) -> bool:
    left = left.replace("\\", "/").strip("/")
    right = right.replace("\\", "/").strip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


class Handler(BaseHTTPRequestHandler):
    server_version = "KekeAdminBridge/1.0"
    sys_version = ""

    def log_message(self, _format: str, *_args) -> None:
        return

    def _json(self, value: dict, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _check_local_request(self) -> None:
        self._check_local_host()
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get("Origin") != expected_origin:
            raise PermissionError("请求来源不匹配，请从本地管理页面操作")

    def _check_local_host(self) -> None:
        expected_host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host", "").lower() != expected_host:
            raise PermissionError("拒绝非本机请求")

    def _body(self, limit: int = MAX_JSON_BYTES) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("请求长度无效") from error
        if length <= 0 or length > limit:
            raise ValueError("请求内容为空或超过大小限制")
        return self.rfile.read(length)

    def _body_json(self, limit: int = MAX_JSON_BYTES) -> dict:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("请求 Content-Type 必须为 application/json")
        try:
            value = json.loads(self._body(limit).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("请求 JSON 格式无效") from error
        if not isinstance(value, dict):
            raise ValueError("请求内容必须是 JSON 对象")
        return value

    def _respond_error(self, error: Exception) -> None:
        status = 403 if isinstance(error, PermissionError) else 409 if isinstance(error, RuntimeError) else 400 if isinstance(error, ValueError) else 500
        self._json({"ok": False, "error": str(error)}, status)

    def do_GET(self) -> None:
        try:
            self._check_local_host()
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{self.server.server_port}":
                raise PermissionError("请求来源不匹配")
        except Exception as error:
            self._respond_error(error)
            return
        parsed = urlsplit(self.path)
        if parsed.path == '/api/release/status':
            try:
                values=release_publish.read_secrets()
                state=_read_json(ROOT/'desktop/release-state.json',{'last_published':None,'config_revision':0})
                self._json({'ok':True,'configured':bool(values.get('gitee_token')),'version':state['last_published'],'config_revision':state['config_revision']})
            except Exception:
                self._json({'ok':True,'configured':False,'error':'本机发布凭据不可用'})
            return
        if parsed.path == "/api/ping":
            self._json({"ok": True, "service": "keke-admin", "version": 3, "capabilities": ["character-save", "character-profile-content-save"]})
            return
        if parsed.path == "/api/status":
            try:
                status = _git_status()
                self._json({"ok": True, "git": status})
            except Exception as error:
                self._json({"ok": True, "git": {"available": False, "error": str(error)}})
            return
        self._serve_static(unquote(parsed.path))

    def _serve_static(self, request_path: str) -> None:
        relative = request_path.lstrip("/") or "index.html"
        parts = Path(relative).parts
        if not parts or any(part.startswith(".") for part in parts) or any(part in {"scripts", "artifacts", ".planning", ".git"} for part in parts):
            self.send_error(404)
            return
        allowed = relative in SAFE_ROOT_FILES or relative.startswith("data/knowledge/") or relative.startswith("data/resources/")
        if not allowed:
            self.send_error(404)
            return
        target = (ROOT / Path(relative)).resolve()
        if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
            self.send_error(404)
            return
        payload = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type in {"text/javascript", "application/javascript"}:
            content_type += "; charset=utf-8"
        elif content_type.startswith("text/") or content_type in {"application/json", "image/svg+xml"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        try:
            self._check_local_request()
            parsed = urlsplit(self.path)
            if parsed.path == '/api/release/credentials':
                self._json(release_publish.configure(self._body_json().get('token')))
                return
            if parsed.path == '/api/release/config':
                if _run_git(['remote','get-url','origin']).stdout.strip()!='https://github.com/q825818504/keke_zhushou.git':
                    raise RuntimeError('公共配置只能从指定GitHub维护仓库发布')
                fetched=_run_git(['fetch','origin'],timeout=90)
                if fetched.returncode: raise RuntimeError(_git_error(fetched))
                state=_git_status()
                if state.get('ahead') or state.get('behind'):
                    raise RuntimeError('请先将维护资料同步到GitHub，再发布公共配置')
                for diff in (['diff','--name-only'],['diff','--cached','--name-only']):
                    dirty=_run_git([*diff,'--','data/knowledge','data/resources'])
                    if dirty.stdout.strip(): raise RuntimeError('请先保存并同步维护资料到GitHub')
                from build_release import prepare
                output=prepare(ROOT,config_only=True)
                if output is None:
                    self._json({'ok':True,'message':'公共配置与上次发行一致，无需重复发布'})
                    return
                self._json(release_publish.publish(ROOT,output))
                return
            if parsed.path == "/api/teams":
                body = self._body_json()
                overrides = _validate_team_overrides(body.get("overrides"))
                _commit_bundles(team_overrides=overrides)
                self._json({"ok": True, "message": "攻略阵容已写入项目资料"})
                return
            if parsed.path == "/api/characters/save":
                body = self._body_json()
                ident = body.get("id")
                if not isinstance(ident, str) or ident not in _character_ids():
                    raise ValueError("未知角色编号")
                patch = _validate_basic_patch(body.get("patch"))
                content = _validate_character_content(body.get("content", {}))
                recommendation = _validate_recommendations({ident: body.get("recommended")})[ident]
                document = _load_character_overrides()
                current = document["characters"].setdefault(ident, {})
                current["name"] = patch["name"]
                current["basic"] = {**current.get("basic", {}), **patch["basic"]}
                current.update(content)
                current["recommended"] = recommendation
                cycle_document = None
                if "reaction_enhancements" in body:
                    cycle_document = _load_esper_cycles()
                    entries = _validate_reaction_enhancements(body["reaction_enhancements"], cycle_document)
                    _replace_character_reaction_enhancements(cycle_document, ident, patch["name"], entries)
                    current["reaction_enhancements"] = entries
                _commit_bundles(character_overrides=document, esper_cycles=cycle_document)
                self._json({"ok": True, "message": "角色全部修改已保存"})
                return
            if parsed.path == "/api/characters/basic":
                body = self._body_json()
                ident = body.get("id")
                if not isinstance(ident, str) or ident not in _character_ids():
                    raise ValueError("未知角色编号")
                patch = _validate_basic_patch(body.get("patch"))
                document = _load_character_overrides()
                current = document["characters"].setdefault(ident, {})
                current["name"] = patch["name"]
                current["basic"] = {**current.get("basic", {}), **patch["basic"]}
                _commit_bundles(character_overrides=document)
                self._json({"ok": True, "message": "角色资料已写入项目"})
                return
            if parsed.path == "/api/characters/recommendations":
                body = self._body_json()
                recommendations = _validate_recommendations(body.get("recommendations"))
                document = _load_character_overrides()
                for record in document["characters"].values():
                    record.pop("recommended", None)
                for ident, recommendation in recommendations.items():
                    document["characters"].setdefault(ident, {})["recommended"] = recommendation
                _commit_bundles(character_overrides=document)
                self._json({"ok": True, "message": "角色推荐与词条优先级已写入项目"})
                return
            if parsed.path == "/api/characters/layout":
                query = parse_qs(parsed.query)
                ident = query.get("id", [""])[0]
                if not isinstance(ident, str) or ident not in _character_ids():
                    raise ValueError("未知角色编号")
                mime = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
                suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime)
                if not suffix:
                    raise ValueError("只支持 PNG、JPG 或 WebP 图片")
                payload = self._body(MAX_IMAGE_BYTES)
                if not _valid_image(payload, mime):
                    raise ValueError("图片内容与文件类型不匹配")
                relative = f"data/resources/characters/{ident}/drive-layout{suffix}"
                image_path = ROOT / Path(relative)
                document = _load_character_overrides()
                current = document["characters"].setdefault(ident, {})
                old = current.get("drive_layout_image", "")
                deletes = ()
                if old in _layout_relative_paths(ident) and old != relative:
                    deletes = (ROOT / Path(old),)
                current["drive_layout_image"] = relative
                _commit_bundles(character_overrides=document, extra_changes={image_path: payload}, deletes=deletes)
                self._json({"ok": True, "path": relative})
                return
            if parsed.path == "/api/characters/layout/delete":
                body = self._body_json()
                ident = body.get("id")
                if not isinstance(ident, str) or ident not in _character_ids():
                    raise ValueError("未知角色编号")
                document = _load_character_overrides()
                current = document["characters"].setdefault(ident, {})
                old = current.pop("drive_layout_image", "")
                deletes = ()
                if old in _layout_relative_paths(ident):
                    deletes = (ROOT / Path(old),)
                _commit_bundles(character_overrides=document, deletes=deletes)
                self._json({"ok": True})
                return
            if parsed.path == "/api/migrate":
                self._migrate_legacy_data(self._body_json(32 * 1024 * 1024))
                return
            if parsed.path == "/api/git/fetch":
                result = _run_git(["fetch", "origin"], timeout=90)
                if result.returncode != 0:
                    raise RuntimeError(_git_error(result))
                self._json({"ok": True, "git": _git_status()})
                return
            if parsed.path == "/api/git/pull":
                fetched = _run_git(["fetch", "origin"], timeout=90)
                if fetched.returncode != 0:
                    raise RuntimeError(_git_error(fetched))
                state = _git_status()
                upstream = state["upstream"]
                if not upstream.startswith("origin/"):
                    raise RuntimeError("当前分支没有跟踪 origin 远端；请先在 GitHub Desktop 检查仓库设置。")
                remote_exists = _run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{upstream}"])
                if remote_exists.returncode != 0:
                    raise RuntimeError(f"远端分支 {upstream} 不存在；请先在 GitHub Desktop 检查仓库设置。")
                remote_changes = _run_git(["diff", "--name-only", "-z", "HEAD", upstream])
                local_changes = _run_git(["diff", "--name-only", "-z", "HEAD"])
                untracked = _run_git(["ls-files", "--others", "--exclude-standard", "-z"])
                if any(result.returncode != 0 for result in (remote_changes, local_changes, untracked)):
                    failed = next(result for result in (remote_changes, local_changes, untracked) if result.returncode != 0)
                    raise RuntimeError(_git_error(failed))
                remote_paths = {path for path in remote_changes.stdout.split("\0") if path}
                local_paths = {path for path in local_changes.stdout.split("\0") if path}
                local_paths.update(path for path in untracked.stdout.split("\0") if path)
                conflicts = sorted(
                    local for local in local_paths
                    if any(_paths_overlap(local, remote) for remote in remote_paths)
                )
                if conflicts:
                    raise RuntimeError(
                        "GitHub 更新與本地未提交內容涉及相同路徑，沒有執行拉取："
                        + ", ".join(conflicts[:8])
                        + "。請用 GitHub Desktop 檢查差異後再同步。"
                    )
                result = _run_git(["merge", "--ff-only", upstream], timeout=120)
                if result.returncode != 0:
                    raise RuntimeError(_git_error(result))
                self._json({"ok": True, "git": _git_status(), "message": "已拉取 GitHub 更新；建议刷新页面载入新资料。"})
                return
            if parsed.path == "/api/git/sync":
                self._sync_git(self._body_json())
                return
            self.send_error(404)
        except Exception as error:
            self._respond_error(error)

    def _migrate_legacy_data(self, body: dict) -> None:
        if body.get("schema_version") != "1.0.0":
            raise ValueError("浏览器备份版本不受支持")
        teams = _validate_team_overrides(body.get("team_overrides", {"edits": {}, "removed": []}))
        recommendations = _validate_recommendations(body.get("character_recommendations", {}))
        basics = body.get("character_basics", {})
        if not isinstance(basics, dict):
            raise ValueError("角色基础资料备份格式无效")
        contents = body.get("character_content", {})
        if not isinstance(contents, dict) or len(contents) > 200:
            raise ValueError("角色资料内容备份格式无效")
        reaction_enhancements = body.get("character_reaction_enhancements", {})
        if not isinstance(reaction_enhancements, dict) or len(reaction_enhancements) > 200:
            raise ValueError("角色反应强化备份格式无效")
        layouts = body.get("drive_layouts", [])
        if not isinstance(layouts, list) or len(layouts) > 200:
            raise ValueError("摆放图备份数量无效")

        existing_teams = _read_json(TEAM_OVERRIDES, {"edits": {}, "removed": []})
        existing_teams["edits"] = {**existing_teams.get("edits", {}), **teams["edits"]}
        existing_teams["removed"] = sorted(set(existing_teams.get("removed", [])) | set(teams["removed"]))
        existing_teams = _validate_team_overrides(existing_teams)

        document = _load_character_overrides()
        for ident, patch in basics.items():
            if ident not in _character_ids():
                raise ValueError(f"浏览器备份含未知角色：{ident}")
            checked = _validate_basic_patch(patch)
            current = document["characters"].setdefault(ident, {})
            current["name"] = checked["name"]
            current["basic"] = {**current.get("basic", {}), **checked["basic"]}
        for ident, recommendation in recommendations.items():
            document["characters"].setdefault(ident, {})["recommended"] = recommendation
        for ident, content in contents.items():
            if ident not in _character_ids():
                raise ValueError(f"浏览器备份含未知角色：{ident}")
            checked = _validate_character_content(content)
            document["characters"].setdefault(ident, {}).update(checked)

        cycle_document = _load_esper_cycles() if reaction_enhancements else None
        if cycle_document is not None:
            for ident, entries in reaction_enhancements.items():
                if ident not in _character_ids():
                    raise ValueError(f"浏览器备份含未知角色：{ident}")
                checked = _validate_reaction_enhancements(entries, cycle_document)
                current = document["characters"].get(ident, {})
                name = current.get("name") or _character_name(ident)
                _replace_character_reaction_enhancements(cycle_document, ident, name, checked)
                document["characters"].setdefault(ident, {})["reaction_enhancements"] = checked

        extra_changes: dict[Path, bytes] = {}
        for record in layouts:
            ident = record.get("id") if isinstance(record, dict) else None
            mime = record.get("mime_type") if isinstance(record, dict) else None
            encoded = record.get("data_base64") if isinstance(record, dict) else None
            suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime)
            if not isinstance(ident, str) or ident not in _character_ids() or not suffix or not isinstance(encoded, str):
                raise ValueError("摆放图备份记录无效")
            try:
                payload = base64.b64decode(encoded, validate=True)
            except Exception as error:
                raise ValueError("摆放图备份编码无效") from error
            if len(payload) > MAX_IMAGE_BYTES or not _valid_image(payload, mime):
                raise ValueError("摆放图备份内容无效或过大")
            relative = f"data/resources/characters/{ident}/drive-layout{suffix}"
            extra_changes[ROOT / Path(relative)] = payload
            document["characters"].setdefault(ident, {})["drive_layout_image"] = relative

        _commit_bundles(team_overrides=existing_teams, character_overrides=document, esper_cycles=cycle_document, extra_changes=extra_changes)
        self._json({"ok": True, "message": "浏览器本地资料已合并到项目；原浏览器数据未自动删除，可确认后手动清理。"})

    def _sync_git(self, body: dict) -> None:
        message = body.get("message", "更新可可助手资料")
        if not isinstance(message, str) or not message.strip() or len(message) > 120:
            raise ValueError("提交说明需为 1–120 个字符")
        staged = _run_git(["diff", "--cached", "--quiet"])
        if staged.returncode == 1:
            raise RuntimeError("Git 暂存区已有其他修改。为避免把别的文件提交进来，请先用 GitHub Desktop 处理。")
        if staged.returncode not in (0, 1):
            raise RuntimeError(_git_error(staged))
        state = _git_status()
        if not state["remoteConfigured"]:
            raise RuntimeError("仓库没有 origin 远程地址；请先在 GitHub Desktop 中配置私有仓库。")
        fetched = _run_git(["fetch", "origin"], timeout=90)
        if fetched.returncode != 0:
            raise RuntimeError(_git_error(fetched))
        state = _git_status()
        tracked_dirty = _run_git(["diff", "--name-only"])
        tracked_paths = {line.strip().replace("\\", "/") for line in tracked_dirty.stdout.splitlines() if line.strip()}
        managed = set(_managed_git_paths())
        unrelated = sorted(tracked_paths - managed)
        if state["behind"] and unrelated:
            raise RuntimeError("GitHub 有较新提交，同时本地还有其他文件改动。没有执行拉取或提交；请先在 GitHub Desktop 检查并解决后再同步。")
        paths = _managed_git_paths()
        if paths:
            added = _run_git(["add", "--", *paths])
            if added.returncode != 0:
                raise RuntimeError(_git_error(added))
        staged_after = _run_git(["diff", "--cached", "--quiet"])
        if staged_after.returncode == 0:
            if state['ahead'] and not state['behind']:
                pushed=_run_git(['push','origin',f"HEAD:refs/heads/{state['branch']}"],timeout=120)
                if pushed.returncode: raise RuntimeError(_git_error(pushed))
            self._json({"ok": True, "message": "没有待提交的管理资料。", "git": _git_status()})
            return
        committed = _run_git(["commit", "-m", message.strip()], timeout=60)
        if committed.returncode != 0:
            raise RuntimeError(_git_error(committed))
        if state["behind"]:
            pulled = _run_git(["pull", "--rebase", "origin", state["branch"]], timeout=120)
            if pulled.returncode != 0:
                raise RuntimeError("本地资料已安全提交，但与 GitHub 有冲突，未强制覆盖。请在 GitHub Desktop 中解决冲突后再推送。\n" + _git_error(pulled))
        pushed = _run_git(["push", "origin", f"HEAD:refs/heads/{state['branch']}"], timeout=120)
        if pushed.returncode != 0:
            raise RuntimeError("本地资料已提交，推送未完成；没有丢弃本地提交。请检查网络/凭据或在 GitHub Desktop 中重试。\n" + _git_error(pushed))
        self._json({"ok": True, "message": "管理资料已提交并推送到 GitHub。", "git": _git_status()})


def _valid_image(payload: bytes, mime: str) -> bool:
    if mime == "image/png":
        return payload.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return payload.startswith(b"\xff\xd8\xff")
    if mime == "image/webp":
        return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the loopback-only Keke Assistant admin service")
    parser.add_argument("--port", type=int, default=8765, help="local port (default: 8765; use 0 for an ephemeral port)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/index.html"
    print(f"可可助手本地管理端：{url}", flush=True)
    print("仅监听本机回环地址；按 Ctrl+C 停止。Git 凭据由本机 Git Credential Manager 管理。", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\n本地管理端已停止。", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
