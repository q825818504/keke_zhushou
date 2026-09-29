#!/usr/bin/env python3
"""Normalize locally downloaded Mysqil arc-drive pages into app data.

Mysqil credits Matsuzaka Yuki and licenses its community content CC BY-NC-SA 4.0.
Keep source links and attribution with the data and in the public UI.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Mysqil · 环世全鉴"
LICENSE = "CC BY-NC-SA 4.0"
LEVELS = [1, 20, 30, 40, 50, 60, 70, 80]
LEVEL_INDEXES = [0, 19, 29, 39, 49, 59, 69, 79]
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Element:
    def __init__(self, tag: str, attrs: list[tuple[str, str | None]], parent: Element | None = None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children: list[Element | str] = []

    def text(self) -> str:
        return "".join(child.text() if isinstance(child, Element) else child for child in self.children)

    def descendants(self, tag: str | None = None):
        for child in self.children:
            if isinstance(child, Element):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.descendants(tag)

    def direct(self) -> list[Element]:
        return [child for child in self.children if isinstance(child, Element)]

    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(data)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse(raw: str) -> Element:
    parser = TreeParser()
    parser.feed(raw)
    return parser.root


def first(root: Element, predicate):
    return next((node for node in root.descendants() if predicate(node)), None)


def heading_text(root: Element, tag: str, label: str):
    return first(root, lambda node: node.tag == tag and clean(node.text()) == label)


def parent_with_tag(node: Element | None, tag: str):
    node = node.parent if node else None
    while node:
        if node.tag == tag:
            return node
        node = node.parent
    return None


def first_paragraph_after(root: Element, label: str, tag: str):
    heading = heading_text(root, tag, label)
    section = parent_with_tag(heading, "section")
    return clean(first(section, lambda node: node.tag == "p").text()) if section and first(section, lambda node: node.tag == "p") else ""


def script_variables(root: Element) -> dict[str, str]:
    result = {}
    for node in root.descendants("script"):
        text = node.text()
        for match in re.finditer(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(\"(?:\\.|[^\"\\])*\")", text):
            result[match.group(1)] = match.group(2)
    return result


def js_value(variables: dict[str, str], name: str):
    literal = variables.get(name)
    if not literal:
        return None
    value = json.loads(literal)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def rank_effect(template: str, values: list[dict], rank: int) -> str:
    def replace_parameter(match):
        identifier = int(match.group(1))
        row = next((item for item in values if item.get("id_value") == identifier), None)
        options = row.get("values", []) if row else []
        return str(options[rank - 1]) if len(options) >= rank else match.group(0)

    result = re.sub(r"<lv>\{(\d+)\}</\s*>", replace_parameter, template)
    result = re.sub(r"<lv>(\d+)</\s*>", r"\1", result)
    result = re.sub(r"</?[^>]+>", "", result)
    return result.replace("\\r\\n", "\n").replace("\\n", "\n").strip()


def stat_rows(stats_node: Element | None, variables: dict[str, str]):
    if not stats_node:
        return []
    attack_values = js_value(variables, "atkValuesJson")
    secondary_values = js_value(variables, "subValuesJson")
    percent_sub = variables.get("isPercentSub", "").strip().lower() == "true"
    rows = []
    for value_node in stats_node.descendants("span"):
        marker = next((key for key in ("data-atk-value", "data-sub-value") if key in value_node.attrs), None)
        if not marker:
            continue
        row = value_node.parent
        spans = [node for node in row.direct() if node.tag == "span"] if row else []
        label = next((clean(node.text()) for node in spans if node is not value_node), "")
        icon = first(row, lambda node: node.tag == "img") if row else None
        curve = attack_values if marker == "data-atk-value" else secondary_values
        rows.append({
            "name": label,
            "current_value": clean(value_node.text()),
            "kind": "base_attack" if marker == "data-atk-value" else "secondary",
            "is_percent": False if marker == "data-atk-value" else percent_sub,
            "source_icon_url": icon.attrs.get("src", "") if icon else "",
            "level_values": curve if isinstance(curve, list) else None,
            "values_at_breakpoints": [curve[index] for index in LEVEL_INDEXES if len(curve) > index] if isinstance(curve, list) else [],
        })
    return rows


def import_item(item: dict, provenance: dict) -> dict:
    snapshot = ROOT / Path(item["raw_page"])
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    raw = snapshot.read_text(encoding="utf-8-sig")
    tree = parse(raw)
    main = first(tree, lambda node: node.tag == "main")
    if not main:
        raise ValueError(f"Missing main content: {item['source_url']}")

    title = clean(heading_text(main, "h1", item["name"]).text()) if heading_text(main, "h1", item["name"]) else item["name"]
    variables = script_variables(tree)
    effect_template = js_value(variables, "effectDescJson")
    effect_values = js_value(variables, "effectValuesJson") or []
    if not isinstance(effect_template, str):
        effect_template = ""
    if not isinstance(effect_values, list):
        effect_values = []

    passive = first(main, lambda node: node.attrs.get("data-component") == "weapon-passive")
    passive_title = ""
    max_rank = 5
    if passive:
        title_span = first(passive, lambda node: node.tag == "span" and ("text-lg" in node.classes() or "font-bold" in node.classes()))
        passive_title = clean(title_span.text()) if title_span else ""
        slider = first(passive, lambda node: node.tag == "input" and "data-r-slider" in node.attrs)
        if slider and slider.attrs.get("max", "").isdigit():
            max_rank = int(slider.attrs["max"])

    stats = first(main, lambda node: node.attrs.get("data-component") == "weapon-stats")
    image = first(main, lambda node: node.tag == "img" and urlparse(node.attrs.get("src", "")).path.startswith("/images/weapons/"))
    asset_by_url = {asset["source_url"]: asset for asset in item.get("assets", [])}
    image_url = provenance["origin"] + image.attrs["src"] if image else ""
    image_record = asset_by_url.get(image_url, {})
    overview = first_paragraph_after(main, "概述", "h2")
    description = first_paragraph_after(main, "说明", "h3")
    rank_descriptions = [rank_effect(effect_template, effect_values, rank) for rank in range(1, max_rank + 1)] if effect_template else []
    visible_effect = first(passive, lambda node: "data-passive-text" in node.attrs) if passive else None
    if not rank_descriptions and visible_effect:
        rank_descriptions = [clean(visible_effect.text())]

    return {
        "id": item["id"],
        "name": title,
        "rarity": item["rarity"],
        "type": item["type"],
        "description": description,
        "overview": overview,
        "stats": {
            "level_breakpoints": LEVELS,
            "level_value_indexes": LEVEL_INDEXES,
            "rows": stat_rows(stats, variables),
            "source_level_arrays": {
                "attack": js_value(variables, "atkValuesJson"),
                "secondary": js_value(variables, "subValuesJson"),
                "secondary_is_percent": variables.get("isPercentSub", "").strip().lower() == "true",
            },
        },
        "passive": {
            "title": passive_title,
            "description_template": effect_template,
            "rank_values": effect_values,
            "rank_descriptions": rank_descriptions,
        },
        "image": {
            "source_url": image_url,
            "local_path": image_record.get("local_path", ""),
            "sha256": image_record.get("sha256", ""),
        },
        "source": {
            "site": provenance["source"],
            "author": provenance["source_author"],
            "license": provenance["source_license"],
            "review_status": "pending",
            "url": item["source_url"],
            "snapshot_path": item["raw_page"],
        },
    }


def main():
    roster_path = ROOT / "data/mysqil/weapons/roster.json"
    manifest = json.loads(roster_path.read_text(encoding="utf-8-sig"))
    items = manifest.get("items", [])
    expected_count = manifest.get("expected_count")
    if not isinstance(expected_count, int) or expected_count < 1 or len(items) != expected_count:
        raise ValueError(f"Source index expects {expected_count} arc drives, roster contains {len(items)}")
    provenance = {
        "origin": "https://wiki.mysqil.com",
        "source": manifest.get("source", SOURCE),
        "source_author": manifest.get("source_author", "Matsuzaka Yuki"),
        "source_license": manifest.get("source_license", LICENSE),
    }
    entries = [import_item(item, provenance) for item in items]
    if len(entries) != expected_count or any(not entry["image"]["local_path"] for entry in entries):
        raise ValueError("Catalog import incomplete: one or more entries has no local image.")

    output = {
        "schema_version": 1,
        "id": "arc-drives",
        "name": "弧盘",
        "source_index": manifest["source_index"],
        "source": provenance,
        "retrieved_at": manifest.get("retrieved_at"),
        "count": len(entries),
        "items": entries,
    }
    json_path = ROOT / "data/knowledge/encyclopedia/arc_drives.json"
    js_path = ROOT / "data/knowledge/encyclopedia/arc_drives.js"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    json_path.write_text(serialized, encoding="utf-8", newline="")
    js_path.write_text("window.arcDriveKnowledge = JSON.parse(" + json.dumps(serialized, ensure_ascii=False) + ");\n", encoding="utf-8", newline="")
    effect_count = sum(bool(entry["passive"]["rank_descriptions"]) for entry in entries)
    stat_count = sum(bool(entry["stats"]["rows"]) for entry in entries)
    print(f"Imported {len(entries)} arc drives; {stat_count} have parsed stat rows; {effect_count} have rank effects.")
    print(f"Wrote {json_path.relative_to(ROOT)} and {js_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
