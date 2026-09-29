#!/usr/bin/env python3
"""Normalize locally downloaded Mysqil 空幕 (cassette) pages into app data.

Mysqil credits Matsuzaka Yuki and licenses its community content CC BY-NC-SA 4.0.
Keep source links and attribution with each imported record and in the public UI.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Mysqil · 环世全鉴"
LICENSE = "CC BY-NC-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
MODIFICATIONS = "从保存的来源页面提取并结构化；原始 HTML 快照单独保留。"
QUALITY_ORDER = ("gold", "purple", "blue")
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

    def direct(self, tag: str | None = None) -> list[Element]:
        return [child for child in self.children if isinstance(child, Element) and (tag is None or child.tag == tag)]

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


def first(root: Element | None, predicate):
    return next((node for node in root.descendants() if predicate(node)), None) if root else None


def heading(root: Element, tag: str, label: str):
    return first(root, lambda node: node.tag == tag and clean(node.text()) == label)


def parent_with_tag(node: Element | None, tag: str):
    node = node.parent if node else None
    while node:
        if node.tag == tag:
            return node
        node = node.parent
    return None


def card_for_heading(node: Element | None):
    node = node.parent if node else None
    while node:
        if node.tag == "div" and "bg-card" in node.classes():
            return node
        node = node.parent
    return None


def paragraphs(node: Element | None) -> list[str]:
    return [clean(child.text()) for child in node.descendants("p") if clean(child.text())] if node else []


def read_set_effect(section: Element | None, label: str) -> str:
    if not section:
        return ""
    for card in section.descendants("div"):
        if "bg-card" not in card.classes():
            continue
        marker = first(card, lambda node: node.tag == "span" and clean(node.text()) == label)
        if marker:
            return clean(first(card, lambda node: node.tag == "p").text()) if first(card, lambda node: node.tag == "p") else ""
    return ""


def parse_affix_pool(section: Element, label_fragment: str) -> dict:
    title = next((node for node in section.descendants("h3") if label_fragment in clean(node.text())), None)
    card = card_for_heading(title)
    if not card:
        return {"items": [], "note": ""}
    chips = first(card, lambda node: node.tag == "div" and "flex-wrap" in node.classes() and "gap-1.5" in node.classes())
    items = [clean(child.text()) for child in chips.direct("span") if clean(child.text())] if chips else []
    note_node = first(card, lambda node: node.tag == "p")
    return {"items": items, "note": clean(note_node.text()) if note_node else ""}


def parse_quality(main: Element, section: Element) -> dict:
    title = next((node for node in section.descendants("h3") if "品质差异" in clean(node.text())), None)
    card = card_for_heading(title)
    if not card:
        return {"role_note": "", "source_note": "", "note": "", "tiers": []}
    note_node = first(card, lambda node: node.tag == "p")
    grid = first(card, lambda node: node.tag == "div" and any("grid-cols-3" in cls for cls in node.classes()))
    tiers = []
    for entry in grid.direct("div") if grid else []:
        quality = next((clean(node.text()) for node in entry.descendants() if node.tag in {"div", "span"} and clean(node.text()) in {"金", "紫", "蓝"}), "")
        description_node = first(entry, lambda node: node.tag == "p")
        description = clean(description_node.text()) if description_node else ""
        if quality and description:
            tiers.append({"quality": quality, "description": description})
    role_node = first(main, lambda node: node.tag == "span" and node.attrs.get("data-tier-field") == "role")
    source_node = first(main, lambda node: node.tag == "span" and node.attrs.get("data-tier-field") == "source")
    return {
        "role_note": clean(role_node.text()) if role_node else "",
        "source_note": clean(source_node.text()) if source_node else "",
        "note": clean(note_node.text()) if note_node else "",
        "tiers": tiers,
    }


def parse_overview(main: Element) -> str:
    section_heading = heading(main, "h2", "套装概述")
    section = parent_with_tag(section_heading, "section")
    return "\n\n".join(paragraphs(section))


def import_item(item: dict, provenance: dict) -> dict:
    snapshot = ROOT / Path(item["raw_page"])
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    raw = snapshot.read_text(encoding="utf-8-sig")
    tree = parse(raw)
    main = first(tree, lambda node: node.tag == "main")
    if not main:
        raise ValueError(f"Missing main content: {item['source_url']}")

    title_node = first(main, lambda node: node.tag == "h1")
    title = clean(title_node.text()) if title_node else ""
    if not title or title != item["name"]:
        raise ValueError(f"Source title mismatch for {item['id']}: roster={item['name']!r}, page={title!r}")

    header = first(main, lambda node: node.tag == "header")
    header_spans = [clean(node.text()) for node in header.descendants("span") if clean(node.text())] if header else []
    category = next((value for value in header_spans if value in {"属性专属", "泛用功能"}), "")
    element = next((value for value in header_spans if value in {"光属性", "暗属性", "灵属性", "咒属性", "魂属性", "相属性"}), "")

    effects_heading = heading(main, "h2", "套装效果")
    effects_section = parent_with_tag(effects_heading, "section")
    acquisition_label = first(main, lambda node: node.tag == "p" and clean(node.text()) == "获取途径")
    acquisition_section = parent_with_tag(acquisition_label, "section")
    acquisition_values = paragraphs(acquisition_section)
    acquisition_index = acquisition_values.index("获取途径") if "获取途径" in acquisition_values else -1
    acquisition = acquisition_values[acquisition_index + 1] if acquisition_index >= 0 and acquisition_index + 1 < len(acquisition_values) else ""

    mechanism_heading = heading(main, "h2", "词条机制")
    mechanism = parent_with_tag(mechanism_heading, "section")
    if not mechanism:
        raise ValueError(f"Missing affix mechanism section: {item['source_url']}")
    main_pool = parse_affix_pool(mechanism, "卡带主属性")
    sub_pool = parse_affix_pool(mechanism, "可能出现的副词条")
    quality = parse_quality(main, mechanism)

    assets_by_quality = {asset["quality"]: asset for asset in item.get("images", [])}
    if set(assets_by_quality) != set(QUALITY_ORDER):
        raise ValueError(f"Expected Gold/Purple/Blue image assets for {item['id']}, found {sorted(assets_by_quality)}")
    image_nodes = [node for node in main.descendants("img") if node.attrs.get("data-tier-img") in QUALITY_ORDER]
    if len(image_nodes) != 3:
        raise ValueError(f"Expected three source tier images on {item['source_url']}, found {len(image_nodes)}")
    for image_node in image_nodes:
        quality_id = image_node.attrs.get("data-tier-img")
        expected_url = provenance["origin"] + (image_node.attrs.get("src") or "")
        if assets_by_quality[quality_id]["source_url"] != expected_url:
            raise ValueError(f"Source image URL mismatch for {item['id']} ({quality_id})")

    return {
        "id": item["id"],
        "name": title,
        "category": category,
        "element": element,
        "set_effects": {
            "two_piece": read_set_effect(effects_section, "2件套"),
            "four_piece": read_set_effect(effects_section, "4件套"),
        },
        "acquisition": acquisition,
        "main_affix_pool": main_pool,
        "sub_affix_pool": sub_pool,
        "quality": quality,
        "overview": parse_overview(main),
        "images": {quality_id: assets_by_quality[quality_id] for quality_id in QUALITY_ORDER},
        "source": {
            "site": provenance["source"],
            "author": provenance["source_author"],
            "license": provenance["source_license"],
            "license_url": provenance["source_license_url"],
            "modifications": MODIFICATIONS,
            "review_status": "pending",
            "url": item["source_url"],
            "snapshot_path": item["raw_page"],
        },
    }


def main():
    roster_path = ROOT / "data/mysqil/cassettes/roster.json"
    manifest = json.loads(roster_path.read_text(encoding="utf-8-sig"))
    items = manifest.get("items", [])
    expected_count = manifest.get("expected_count")
    if not isinstance(expected_count, int) or expected_count < 1 or len(items) != expected_count:
        raise ValueError(f"Source index expects {expected_count} cassettes, roster contains {len(items)}")
    ids = [item.get("id") for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate cassette IDs in source roster")
    provenance = {
        "origin": "https://wiki.mysqil.com",
        "source": manifest.get("source", SOURCE),
        "source_author": manifest.get("source_author", "Matsuzaka Yuki"),
        "source_license": manifest.get("source_license", LICENSE),
        "source_license_url": manifest.get("source_license_url", LICENSE_URL),
    }
    entries = [import_item(item, provenance) for item in items]
    if len(entries) != expected_count:
        raise ValueError("Catalog import incomplete")
    if any(not entry["set_effects"]["two_piece"] or not entry["set_effects"]["four_piece"] for entry in entries):
        raise ValueError("One or more source set effects were not parsed; refusing to publish incomplete records")
    if any(not entry["source"]["snapshot_path"] or not all(image.get("local_path") for image in entry["images"].values()) for entry in entries):
        raise ValueError("Catalog import is missing a snapshot path or local image")

    output = {
        "schema_version": 1,
        "id": "sky-curtains",
        "name": "空幕",
        "source_index": manifest["source_index"],
        "source": provenance,
        "retrieved_at": manifest.get("retrieved_at"),
        "count": len(entries),
        "items": entries,
    }
    json_path = ROOT / "data/knowledge/encyclopedia/sky_curtains.json"
    js_path = ROOT / "data/knowledge/encyclopedia/sky_curtains.js"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    json_path.write_text(serialized, encoding="utf-8", newline="")
    js_path.write_text("window.skyCurtainKnowledge = JSON.parse(" + json.dumps(serialized, ensure_ascii=False) + ");\n", encoding="utf-8", newline="")
    complete_images = sum(len(entry["images"]) for entry in entries)
    print(f"Imported {len(entries)} sky curtain sets with {complete_images} local quality images.")
    print(f"Wrote {json_path.relative_to(ROOT)} and {js_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
