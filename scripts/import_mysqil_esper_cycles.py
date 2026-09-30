#!/usr/bin/env python3
"""Import and reconcile the complete esper-cycle article from a local snapshot."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from import_mysqil_driver_blocks import Element, parse, clean

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://wiki.mysqil.com/esper-cycles"
DIRECTORY = ROOT / "data/mysqil/esper-cycles"
RAW = DIRECTORY / "raw/page.html"
MANIFEST = DIRECTORY / "roster.json"
OUTPUT = ROOT / "data/knowledge/esper_cycles.json"
EXPECTED = ["创生", "延滞", "盈蓄", "覆纹", "浊燃", "黯星", "失谐", "浸染"]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def normalized(value):
    return re.sub(r"\s+", "", value)

def text_content(node):
    if isinstance(node, str):
        return node
    if node.tag in {"script", "style", "svg"}:
        return ""
    if node.tag == "br":
        return "\n"
    return "".join(text_content(child) for child in node.children)

def first(node, predicate):
    return next((child for child in node.descendants() if predicate(child)), None)

def has_class(node, token):
    return token in (node.attrs.get("class") or "").split()

def asset_path(src):
    require(src.startswith("/images/") and ".." not in src and "?" not in src, "Unexpected asset path: " + src)
    return DIRECTORY / "assets" / src.removeprefix("/images/")

def fetch(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(url, headers={"User-Agent": "CocoaAssistant source-preserving importer"}), timeout=45) as response:
        require(response.status == 200, "HTTP failure: " + url)
        content = response.read()
    require(content, "Empty download: " + url)
    target.write_bytes(content)

def build(download=False, refresh=False):
    if refresh:
        fetch(SOURCE, RAW)
    require(RAW.exists(), "Download source page first, or run with --refresh.")
    raw = RAW.read_text(encoding="utf-8")
    document = parse(raw)
    main = first(document, lambda n: n.tag == "main")
    require(main is not None, "Missing article main.")
    cycle_list = first(main, lambda n: n.attrs.get("id") == "cycles-list")
    require(cycle_list is not None, "Missing cycle list.")
    cycle_nodes = [n for n in cycle_list.descendants() if n.attrs.get("data-cycle-name")]
    require([n.attrs["data-cycle-name"] for n in cycle_nodes] == EXPECTED, "Reaction roster/order changed; inspect source.")
    sources = sorted({n.attrs["src"] for n in main.descendants("img")})
    if download or refresh:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda src: fetch("https://wiki.mysqil.com" + src, asset_path(src)) if refresh or not asset_path(src).exists() else None, sources))
    assets = []
    for src in sources:
        path = asset_path(src)
        require(path.exists() and path.stat().st_size > 0, "Missing local asset: " + src)
        assets.append({"source_url": "https://wiki.mysqil.com" + src, "source_path": src, "local_path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    asset_map = {a["source_path"]: a for a in assets}
    heading = first(main, lambda n: n.tag == "h1")
    intro_block = next(n for n in main.children if isinstance(n, Element) and first(n, lambda c: c.tag == "strong" and clean(c.text()) == "系统说明"))
    intro = first(intro_block, lambda n: n.tag == "p")
    subtitle = first(heading.parent, lambda n: n.tag == "p")
    result = {
        "schema_version": "1.0.0",
        "title": clean(heading.text()),
        "subtitle": clean(subtitle.text()),
        "system_heading": "系统说明",
        "system_description": clean(intro.text()),
        "source": {
            "source_url": SOURCE, "site": "环世全鉴 · 异环 Wiki", "author": "Matsuzaka Yuki",
            "license": "CC BY-NC-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "raw_snapshot": RAW.relative_to(ROOT).as_posix(),
            "modifications": "按本地 HTML 快照逐项提取、结构化并改用本地图像；说明、数值和角色强化条件保留来源表述。"
        },
        "cycles": [],
    }
    coverage = [result["title"], result["subtitle"], result["system_heading"], result["system_description"]]
    for node in cycle_nodes:
        details = first(node, lambda n: n.tag == "details")
        summary = first(details, lambda n: n.tag == "summary")
        description = first(details, lambda n: n.tag == "div" and has_class(n, "leading-relaxed"))
        require(description is not None, "Missing base description.")
        attributes = [{"name": clean(image.parent.text()), "image": asset_map[image.attrs["src"]]} for image in summary.descendants("img")]
        cycle = {
            "id": details.attrs["data-collapse-id"], "name": node.attrs["data-cycle-name"],
            "attributes": attributes, "description": text_content(description).strip(), "enhancements": [],
            "source_url": SOURCE, "source_collapse_id": details.attrs["data-collapse-id"]
        }
        coverage.extend([cycle["name"], *[a["name"] for a in attributes], cycle["description"]])
        passive_heading = first(details, lambda n: n.tag == "h3")
        if passive_heading:
            cycle["enhancement_heading"] = clean(passive_heading.text())
            coverage.append(cycle["enhancement_heading"])
        for image in details.descendants("img"):
            if image in list(summary.descendants("img")):
                continue
            card = image.parent
            name_node = first(card, lambda n: n.tag == "span" and has_class(n, "font-semibold"))
            description_node = first(card, lambda n: n.tag == "p")
            require(name_node is not None and description_node is not None, "Unexpected passive card.")
            character_id = Path(image.attrs["src"]).stem.removesuffix("-icon")
            enhancement = {
                "character_id": character_id, "character_name": clean(name_node.text()),
                "label": "被动技能", "description": text_content(description_node).strip(),
                "image": asset_map[image.attrs["src"]]
            }
            cycle["enhancements"].append(enhancement)
            coverage.extend([enhancement["character_name"], enhancement["label"], enhancement["description"]])
        result["cycles"].append(cycle)
    actual = normalized(text_content(main))
    reconstructed = normalized("".join(coverage))
    require(actual == reconstructed, "Text coverage mismatch: article contains omitted or altered text.")
    passive_count = sum(len(c["enhancements"]) for c in result["cycles"])
    require(passive_count == 20, "Passive roster changed; inspect all source cards.")
    require(len(assets) == 26, "Image count changed; inspect source assets.")
    require("CC BY-NC-SA 4.0" in raw and "Matsuzaka Yuki" in raw, "Source attribution missing.")
    previous = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    timestamp = previous.get("captured_at") if not refresh else None
    timestamp = timestamp or datetime.now(timezone.utc).isoformat()
    result["source"]["captured_at"] = timestamp
    snapshot_hash = hashlib.sha256(RAW.read_bytes()).hexdigest()
    result["source"]["snapshot_sha256"] = snapshot_hash
    result["coverage"] = {
        "reaction_count": len(result["cycles"]), "enhancement_count": passive_count, "image_count": len(assets),
        "article_text_complete": True, "source_text_sha256": hashlib.sha256(actual.encode()).hexdigest(),
        "numeric_tokens": re.findall(r"\d+(?:\.\d+)?%?", actual),
        "tables": len(list(main.descendants("table"))),
    }
    manifest = {"source_url": SOURCE, "captured_at": timestamp, "raw_snapshot": result["source"]["raw_snapshot"], "snapshot_sha256": snapshot_hash, "assets": assets, "coverage": result["coverage"]}
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT.with_suffix(".js").write_text("window.esperCycleKnowledge = " + json.dumps(result, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Complete article imported: 8 reactions, {passive_count} passives, {len(assets)} local images; text coverage exact; tables={result['coverage']['tables']}.")
    for cycle in result["cycles"]:
        print(json.dumps({"name": cycle["name"], "attributes": [a["name"] for a in cycle["attributes"]], "passives": len(cycle["enhancements"])}, ensure_ascii=True))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download missing article images.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the page and every article image.")
    arguments = parser.parse_args()
    build(arguments.download, arguments.refresh)
