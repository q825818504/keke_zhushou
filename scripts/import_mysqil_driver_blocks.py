#!/usr/bin/env python3
"""Normalize Mysqil driver-block catalog pages and guide from local snapshots."""
from __future__ import annotations

import html
import json
import re
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ROSTER_PATH = ROOT / "data/mysqil/driver-blocks/roster.json"
OUTPUT_JSON = ROOT / "data/knowledge/encyclopedia/driver_blocks.json"
OUTPUT_JS = ROOT / "data/knowledge/encyclopedia/driver_blocks.js"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
MODIFICATIONS = "从保存的来源页面提取并结构化；原始 HTML 快照单独保留。"
QUALITY = {
    "gold": {"grade": "S", "source_color": "orange", "label": "金"},
    "purple": {"grade": "A", "source_color": "purple", "label": "紫"},
    "blue": {"grade": "B", "source_color": "blue", "label": "蓝"},
}
ROMAN_MODELS = {2: "Ⅱ型", 3: "Ⅲ型", 4: "Ⅳ型"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
GUIDE_HEADINGS = {
    "驱动块是什么？",
    "型号特化（Ⅱ / Ⅲ / Ⅳ 型）",
    "词条系统（卡带 vs 驱动块）",
    "输出角色副词条优先级",
    "获取与刷取",
    "形状",
}


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


def element_by_id(root: Element, element_id: str) -> Element | None:
    return first(root, lambda node: node.attrs.get("id") == element_id)


def parent_with_tag(node: Element | None, tag: str) -> Element | None:
    node = node.parent if node else None
    while node:
        if node.tag == tag:
            return node
        node = node.parent
    return None


def read_json_attribute(node: Element | None, name: str, source_url: str):
    if not node or name not in node.attrs:
        raise ValueError(f"Missing {name} JSON attribute on {source_url}")
    try:
        return json.loads(html.unescape(node.attrs[name]))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid embedded {name} JSON on {source_url}: {exc}") from exc


def shape_label_from_index(label: str, model: str) -> str:
    value = clean(label)
    value = re.sub(rf"^{re.escape(model)}驱动\s*\d*\s*格?\s*", "", value)
    value = re.sub(r"\s*\d+\s*格\s*$", "", value)
    return clean(value)


def read_asset_map(manifest: dict) -> dict[str, dict]:
    assets = {}
    for asset in manifest.get("assets", []):
        url = asset.get("source_url")
        if not url or url in assets:
            raise ValueError(f"Missing or duplicate source asset URL: {url}")
        path = ROOT / asset["local_path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_sha = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        if actual_sha != asset.get("sha256"):
            raise ValueError(f"Asset hash mismatch: {path}")
        assets[url] = asset
    return assets


def read_quality_page(item: dict, asset_map: dict[str, dict]) -> dict:
    source_url = item["source_url"]
    snapshot = ROOT / item["raw_page"]
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    raw = snapshot.read_text(encoding="utf-8-sig")
    tree = parse(raw)
    main = first(tree, lambda node: node.tag == "main")
    if not main:
        raise ValueError(f"Missing main content: {source_url}")
    title_node = first(main, lambda node: node.tag == "h1")
    title = clean(title_node.text()) if title_node else ""
    if not title or title != item.get("name"):
        raise ValueError(f"Source title mismatch for {item['id']}: roster={item.get('name')!r}, page={title!r}")
    title_node = first(tree, lambda node: node.tag == "title")
    page_title = clean(title_node.text()) if title_node else ""
    grade_match = re.search(r"·\s*(S|A|B)\s*·", page_title)
    quality = QUALITY[item["quality"]]
    if not grade_match or grade_match.group(1) != quality["grade"]:
        raise ValueError(f"Quality grade mismatch for {source_url}: expected {quality['grade']}, title={page_title!r}")
    if "CC BY-NC-SA 4.0" not in raw:
        raise ValueError(f"Missing attribution/license footer in {source_url}")

    panel = element_by_id(main, "driver-stats-panel")
    descriptor = read_json_attribute(panel, "data-json", source_url)
    substat_node = element_by_id(main, "driver-substats")
    random_stats = read_json_attribute(substat_node, "data-json", source_url)
    if str(descriptor.get("id", "")).casefold() != item["id"].casefold():
        raise ValueError(f"Embedded driver ID mismatch on {source_url}: {descriptor.get('id')}")
    if descriptor.get("quality") != quality["source_color"]:
        raise ValueError(f"Embedded quality mismatch on {source_url}: {descriptor.get('quality')}")

    slider = first(main, lambda node: node.tag == "input" and "data-lv-slider" in node.attrs)
    if not slider:
        raise ValueError(f"Missing level slider on {source_url}")
    try:
        level_min = int(slider.attrs["min"])
        level_max = int(slider.attrs["max"])
        current_level = int(slider.attrs["value"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Invalid level slider bounds on {source_url}") from exc
    main_stats = []
    for stat in descriptor.get("main_stats", []):
        values = stat.get("values")
        if not isinstance(values, list) or len(values) != level_max - level_min + 1:
            raise ValueError(f"Main-stat curve does not cover every slider value on {source_url}: {stat.get('id')}")
        main_stats.append({
            "id": stat.get("id", ""),
            "name": clean(stat.get("name")),
            "source_icon": stat.get("icon", ""),
            "values": values,
        })
    if len(main_stats) != 2:
        raise ValueError(f"Expected fixed ATK and HP main stats on {source_url}, found {len(main_stats)}")

    slot_data = descriptor.get("sub_stats", [])
    slot_count = sum(int(entry.get("amount_stats", 0)) for entry in slot_data if isinstance(entry, dict))
    if slot_count != 4:
        raise ValueError(f"Expected four random-stat slots on {source_url}, found {slot_count}")
    if not isinstance(random_stats, list) or len(random_stats) != 11:
        raise ValueError(f"Expected 11 random-stat choices on {source_url}, found {len(random_stats) if isinstance(random_stats, list) else 'non-list'}")

    normalized_random_stats = []
    for stat in random_stats:
        icon_url = "https://wiki.mysqil.com" + stat.get("icon", "") if stat.get("icon", "").startswith("/") else stat.get("icon", "")
        icon_asset = asset_map.get(icon_url)
        if not icon_asset:
            raise ValueError(f"Missing local stat icon for {stat.get('id')} on {source_url}: {icon_url}")
        normalized_random_stats.append({
            "id": stat.get("id", ""),
            "name": clean(stat.get("name")),
            "is_percent": bool(stat.get("isPercent")),
            "value": stat.get("value"),
            "icon": {"source_url": icon_url, "local_path": icon_asset["local_path"], "sha256": icon_asset["sha256"]},
        })

    page_assets = {asset["source_url"]: asset for asset in item.get("images", [])}
    images = {}
    for color in ("gold", "purple", "blue"):
        url = next((url for url in page_assets if f"/images/drivers/{color}/" in urlparse(url).path), "")
        asset = asset_map.get(url)
        if not asset:
            raise ValueError(f"Missing {color} driver artwork for {item['shape_id']} ({item['quality']})")
        images[color] = {"source_url": url, "local_path": asset["local_path"], "sha256": asset["sha256"]}

    main_model = int(descriptor.get("ownGridNum", 0))
    model = ROMAN_MODELS.get(main_model, "")
    if not model:
        raise ValueError(f"Unexpected driver model/grid count on {source_url}: {main_model}")
    shape_label = shape_label_from_index(item.get("index_label", ""), model)
    if not shape_label:
        raise ValueError(f"Could not read source shape label for {item['shape_id']} from the index card")
    page_images = [asset_map[url] for url in page_assets if url in asset_map]

    return {
        "quality": item["quality"],
        "grade": quality["grade"],
        "source_color": descriptor["quality"],
        "level": {"min": level_min, "max": level_max, "default": current_level},
        "main_stats": main_stats,
        "random_stats": normalized_random_stats,
        "random_slot_count": slot_count,
        "images": images,
        "source_page": {
            "url": source_url,
            "title": page_title,
            "snapshot_path": item["raw_page"],
            "index_label": item.get("index_label", ""),
            "assets": page_images,
        },
        "source_data": {
            "id": descriptor.get("id"),
            "type_id": descriptor.get("type_id"),
            "type_geometry": descriptor.get("type_geometry"),
            "own_grid_num": main_model,
            "set_effect": descriptor.get("set_effect"),
            "sub_stats": slot_data,
        },
    }


def guide_content_blocks(section: Element) -> list[dict]:
    blocks = []

    def walk(node: Element):
        for child in node.children:
            if not isinstance(child, Element):
                continue
            if child.tag in {"script", "style", "nav", "header", "footer"}:
                continue
            if child.tag == "p":
                value = clean(child.text())
                if value:
                    blocks.append({"type": "paragraph", "text": value})
            elif child.tag in {"ul", "ol"}:
                entries = [clean(entry.text()) for entry in child.descendants("li")]
                if entries:
                    blocks.append({"type": "list", "items": entries})
            elif child.tag == "table":
                rows = []
                for row in child.descendants("tr"):
                    cells = [clean(cell.text()) for cell in row.children if isinstance(cell, Element) and cell.tag in {"th", "td"}]
                    if cells:
                        rows.append(cells)
                if rows:
                    blocks.append({"type": "table", "rows": rows})
            elif child.tag in {"h3", "h4"}:
                value = clean(child.text())
                if value:
                    blocks.append({"type": "heading", "text": value})
            else:
                walk(child)

    walk(section)
    return blocks


def import_guide(manifest: dict, source: dict) -> dict:
    guide_manifest = manifest.get("mechanism_guide", {})
    if guide_manifest.get("status") != "saved" or not guide_manifest.get("raw_page"):
        return {"status": guide_manifest.get("status", "unavailable"), "source": guide_manifest}
    snapshot = ROOT / guide_manifest["raw_page"]
    if not snapshot.is_file():
        raise FileNotFoundError(snapshot)
    raw = snapshot.read_text(encoding="utf-8-sig")
    tree = parse(raw)
    main = first(tree, lambda node: node.tag == "main")
    if not main:
        raise ValueError(f"Missing mechanism-guide main content: {guide_manifest['source_url']}")
    headings = [node for node in main.descendants("h2") if clean(node.text()) in GUIDE_HEADINGS]
    sections = []
    for heading_node in headings:
        section = parent_with_tag(heading_node, "section")
        if not section:
            raise ValueError(f"Missing section wrapper for guide heading: {clean(heading_node.text())}")
        sections.append({"title": clean(heading_node.text()), "content": guide_content_blocks(section)})
    if {section["title"] for section in sections} != GUIDE_HEADINGS:
        raise ValueError(f"Mechanism-guide sections incomplete: found {[section['title'] for section in sections]}")
    if "CC BY-NC-SA 4.0" not in raw:
        raise ValueError("Mechanism guide is missing the CC BY-NC-SA 4.0 footer")
    external_sources = []
    for paragraph in main.descendants("p"):
        text = clean(paragraph.text())
        if text.startswith("数据来源："):
            external_sources.append(text)
    return {
        "status": "imported",
        "source": {
            "url": guide_manifest["source_url"],
            "snapshot_path": guide_manifest["raw_page"],
            "author": source["source_author"],
            "license": source["source_license"],
            "license_url": source["source_license_url"],
            "modifications": MODIFICATIONS,
            "review_status": "pending",
        },
        "sections": sections,
        "secondary_source_notes": external_sources,
    }


def main():
    manifest = json.loads(ROSTER_PATH.read_text(encoding="utf-8-sig"))
    items = manifest.get("items", [])
    expected_shapes = manifest.get("expected_shape_count")
    expected_pages = manifest.get("expected_page_count")
    if not isinstance(expected_shapes, int) or expected_shapes != 12 or len(items) != expected_pages or expected_pages != expected_shapes * 3:
        raise ValueError(f"Source expects {expected_shapes} shapes/{expected_pages} pages; roster contains {len(items)} pages")
    if len({item.get("id") for item in items}) != expected_pages:
        raise ValueError("Duplicate driver-block quality-page IDs in source roster")
    asset_map = read_asset_map(manifest)
    origin = "https://wiki.mysqil.com"
    source = {
        "site": manifest.get("source", "Mysqil · 环世全鉴"),
        "source_author": manifest.get("source_author", "Matsuzaka Yuki"),
        "source_license": manifest.get("source_license", "CC BY-NC-SA 4.0"),
        "source_license_url": manifest.get("source_license_url", LICENSE_URL),
    }
    grouped: OrderedDict[str, dict] = OrderedDict()
    for page in items:
        shape_id = page.get("shape_id", "")
        if not shape_id:
            raise ValueError(f"Missing shape group for source page: {page.get('id')}")
        normalized_page = read_quality_page(page, asset_map)
        model = normalized_page["source_data"]["own_grid_num"]
        shape_record = grouped.setdefault(shape_id, {
            "id": shape_id,
            "name": clean(page.get("name")),
            "model": ROMAN_MODELS[model],
            "grid_count": model,
            "shape": shape_label_from_index(page.get("index_label", ""), ROMAN_MODELS[model]),
            "source_index_label": page.get("index_label", ""),
            "source_data": normalized_page["source_data"],
            "qualities": {},
        })
        if shape_record["grid_count"] != model or shape_record["shape"] != shape_label_from_index(page.get("index_label", ""), shape_record["model"]):
            raise ValueError(f"Inconsistent model or shape label across quality pages: {shape_id}")
        for key in ("type_id", "type_geometry", "own_grid_num", "set_effect", "sub_stats"):
            if shape_record["source_data"].get(key) != normalized_page["source_data"].get(key):
                raise ValueError(f"Driver shape metadata changes across quality pages for {shape_id}: {key}")
        tier = normalized_page.pop("quality")
        if tier in shape_record["qualities"]:
            raise ValueError(f"Duplicate {tier} page for {shape_id}")
        shape_record["qualities"][tier] = normalized_page
    if len(grouped) != expected_shapes:
        raise ValueError(f"Expected {expected_shapes} shape records, imported {len(grouped)}")
    for shape in grouped.values():
        if set(shape["qualities"]) != set(QUALITY):
            raise ValueError(f"Incomplete quality pages for {shape['id']}: {sorted(shape['qualities'])}")
        if not shape["shape"]:
            raise ValueError(f"Missing shape display name: {shape['id']}")

    guide = import_guide(manifest, source)
    output = {
        "schema_version": 1,
        "id": "driver-blocks",
        "name": "驱动块",
        "source_index": manifest["source_index"],
        "source": {
            "origin": origin,
            "site": source["site"],
            "source_author": source["source_author"],
            "source_license": source["source_license"],
            "source_license_url": source["source_license_url"],
            "modifications": MODIFICATIONS,
            "retrieved_at": manifest.get("retrieved_at"),
            "raw_index_path": manifest.get("index_raw_page"),
        },
        "count": len(grouped),
        "page_count": len(items),
        "model_counts": manifest.get("model_counts", {}),
        "items": list(grouped.values()),
        "mechanism_guide": guide,
        "assets": manifest.get("assets", []),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    OUTPUT_JSON.write_text(serialized, encoding="utf-8", newline="")
    OUTPUT_JS.write_text(
        "window.driverBlockKnowledge = JSON.parse(" + json.dumps(serialized, ensure_ascii=False) + ");\n",
        encoding="utf-8",
        newline="",
    )
    print(f"Imported {len(grouped)} shapes from {len(items)} quality pages; {len(asset_map)} images; guide={guide['status']}.")
    print(f"Wrote {OUTPUT_JSON.relative_to(ROOT)} and {OUTPUT_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
