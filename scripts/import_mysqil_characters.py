#!/usr/bin/env python3
"""Import Mysqil role pages and assets into the local character schema.

Mysqil labels its community-maintained content CC BY-NC-SA 4.0. Keep attribution
and check license compatibility before redistributing imported content.
"""
from __future__ import annotations
import hashlib, json, re, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://wiki.mysqil.com"
SOURCE = "Mysqil · 环世全鉴"
LICENSE = "CC BY-NC-SA 4.0"
UA = "Mozilla/5.0 (compatible; KekeZhushouLocalImporter/1.0)"
VOID = {"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
LAST_REQUEST = 0.0
HTTP_CACHE = {}

class Element:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []
    def text(self):
        return "".join(x.text() if isinstance(x, Element) else x for x in self.children)
    def descendants(self, tag=None):
        for child in self.children:
            if isinstance(child, Element):
                if tag is None or child.tag == tag: yield child
                yield from child.descendants(tag)
    def classes(self):
        return set((self.attrs.get("class") or "").split())
    def direct(self):
        return [x for x in self.children if isinstance(x, Element)]

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.root=Element("root",[]); self.stack=[self.root]
    def handle_starttag(self, tag, attrs):
        node=Element(tag,attrs,self.stack[-1]); self.stack[-1].children.append(node)
        if tag not in VOID: self.stack.append(node)
    def handle_startendtag(self, tag, attrs): self.stack[-1].children.append(Element(tag,attrs,self.stack[-1]))
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag: self.stack=self.stack[:i]; break
    def handle_data(self, value):
        if value: self.stack[-1].children.append(value)

def clean(value): return re.sub(r"\s+"," ",value).strip()
def parse(raw):
    p=Parser(); p.feed(raw); return p.root
def find_heading(root, label):
    return next((n for n in root.descendants() if n.tag in {"h1","h2","h3","h4"} and clean(n.text())==label),None)
def parent_where(node, predicate):
    node=node.parent
    while node:
        if predicate(node): return node
        node=node.parent
    return None
def is_card(node): return node.tag=="div" and {"rounded-lg","border"} <= node.classes()
def after_heading(node):
    if not node.parent: return None
    siblings=node.parent.direct()
    try: i=siblings.index(node)
    except ValueError: return None
    return next((x for x in siblings[i+1:] if x.tag=="div"),None)

def get(url, timeout=30, retries=4):
    global LAST_REQUEST
    if url in HTTP_CACHE: return HTTP_CACHE[url]
    for attempt in range(retries):
        delay=.2-(time.monotonic()-LAST_REQUEST)
        if delay>0: time.sleep(delay)
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,image/webp,*/*"})
        try:
            with urllib.request.urlopen(req,timeout=timeout) as response:
                result=(response.read(),response.headers.get("Content-Type",""),response.status)
            LAST_REQUEST=time.monotonic(); HTTP_CACHE[url]=result; return result
        except urllib.error.HTTPError as err:
            LAST_REQUEST=time.monotonic()
            if err.code in {429,500,502,503,504} and attempt+1<retries:
                time.sleep(1+attempt*1.5); continue
            raise
        except (urllib.error.URLError,TimeoutError):
            LAST_REQUEST=time.monotonic()
            if attempt+1==retries: raise
            time.sleep(1+attempt*1.5)
    raise RuntimeError("Unable to fetch "+url)

def html_text(payload, content_type):
    match=re.search(r"charset\s*=\s*['\"]?([\w-]+)",content_type,re.I)
    try: return payload.decode(match.group(1) if match else "utf-8")
    except (LookupError,UnicodeDecodeError): return payload.decode("utf-8",errors="replace")
def save_page(url,path,refresh,offline=False):
    if path.exists() and not refresh: return path.read_text(encoding="utf-8-sig"),200,"text/html"
    if offline: raise FileNotFoundError("Missing local snapshot: "+str(path))
    payload,ctype,status=get(url)
    if not ctype.lower().startswith("text/html"): raise ValueError(f"Expected HTML: {url} ({ctype})")
    raw=html_text(payload,ctype); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(raw,encoding="utf-8",newline="")
    return raw,status,ctype
def character_pages(offline=False):
    roster=ROOT/"data"/"mysqil"/"characters"/"roster.json"
    if offline:
        items=json.loads(roster.read_text(encoding="utf-8-sig"))
        return sorted((item["slug"],item["source_url"]) for item in items)
    ns={"s":"http://www.sitemaps.org/schemas/sitemap/0.9"}
    payload,_,_=get(ORIGIN+"/sitemap-index.xml")
    index=ET.fromstring(payload); pages={}
    for item in index.findall(".//s:loc",ns):
        sitemap,_,_=get(item.text)
        for loc in ET.fromstring(sitemap).findall(".//s:loc",ns):
            path=urllib.parse.urlparse(loc.text or "").path.rstrip("/")
            if path.startswith("/characters/") and path!="/characters":
                slug=path.rsplit("/",1)[-1]
                if re.fullmatch(r"[a-z0-9-]+",slug): pages[slug]=ORIGIN+path+"/"
    return sorted(pages.items())
def image_type(path,slug):
    parts=PurePosixPath(urllib.parse.urlparse(path).path).parts
    if len(parts)<3 or parts[1]!="images": return None
    cat,name=parts[2],parts[-1]; stem=PurePosixPath(name).stem
    if cat=="characters":
        if stem in {slug,slug+"-icon"}: return "character_icon" if stem.endswith("-icon") else "character_portrait"
        return None
    return {"weapons":"weapon","cassettes":"cassette","awaken":"awakening_icon","items":"material",
            "ui":"element_icon" if name.startswith("element-") else "stat_icon" if name.startswith("stat-") else "ui_icon"}.get(cat)
def local_asset(slug,url):
    path=urllib.parse.urlparse(url).path
    return "data/resources/characters/"+slug+"/"+path.split("/images/",1)[1]
def download_assets(slug,page,upgrade,skip,refresh,offline):
    if skip: return [],{},[]
    candidates={}
    for node in page.descendants("img"):
        src=node.attrs.get("src") or ""
        if src.startswith("/") and image_type(src,slug): candidates[urllib.parse.urljoin(ORIGIN,src)]=image_type(src,slug)
    for material in (upgrade.get("materials") or {}).values():
        icon=str(material.get("icon") or ""); file=PurePosixPath(icon).name
        if file: candidates.setdefault(f"{ORIGIN}/images/items/{urllib.parse.quote(file)}.webp","material")
    records,local,failures={},{},[]
    for url,kind in candidates.items():
        dest=local_asset(slug,url); file=ROOT/Path(dest)
        try:
            if file.exists() and not refresh: payload=file.read_bytes()
            elif offline: raise FileNotFoundError("Missing local asset: "+str(file))
            else:
                payload,ctype,status=get(url)
                if status!=200 or not ctype.lower().startswith("image/"): raise ValueError(f"{status} {ctype}")
                file.parent.mkdir(parents=True,exist_ok=True); file.write_bytes(payload)
            records[dest]={"type":kind,"source_url":url,"local_path":dest,"sha256":hashlib.sha256(payload).hexdigest()}
            local[url]=dest
        except Exception as err:
            failures.append(url)
            print(f"  ASSET pending review: {url} ({err})")
    return list(records.values()),local,failures
def metadata_rows(dl):
    result={}
    for row in dl.direct():
        key=next((clean(x.text()) for x in row.descendants("dt")),"")
        value=next((clean(x.text()) for x in row.descendants("dd")),"")
        if key: result[key]=value
    return result
def skill_parameters(card,name):
    result=[]; cap=1
    rows=[n for n in card.descendants() if "data-param-row" in n.attrs]
    for select in card.descendants("select"):
        raw=select.attrs.get("data-skill-params")
        if not raw: continue
        try: matrix=json.loads(raw)
        except json.JSONDecodeError: continue
        for i,values in enumerate(matrix):
            if not isinstance(values,list): continue
            row=rows[i] if i<len(rows) else None
            labels=[clean(x.text()) for x in row.parent.direct() if x.tag=="span"] if row and row.parent else []
            label=next((x for x in labels if x!=clean(row.text())),"") if row else ""
            values=[str(x) for x in values]; cap=max(cap,len(values))
            result.append({"label":label or f"参数 {i+1}","source_key":row.attrs.get("data-param-row",name) if row else name,"values":values,"current_value":values[0] if values else ""})
    return result,cap
def skills(page):
    h=find_heading(page,"技能"); section=parent_where(h,lambda n:n.tag=="section") if h else None
    if not section and h:
        siblings=h.parent.direct() if h.parent else []
        try: index=siblings.index(h)+1
        except ValueError: return []
        output=[]
        while index<len(siblings) and siblings[index].tag not in {"h1","h2"}:
            node=siblings[index]
            if node.tag!="h3": index+=1; continue
            title=clean(node.text()); index+=1; descriptions=[]; raw_parts=[title]
            while index<len(siblings) and siblings[index].tag not in {"h1","h2","h3"}:
                block=siblings[index]; value=clean(block.text())
                if value:
                    raw_parts.append(value)
                    if block.tag in {"p","blockquote"}: descriptions.append({"name":title,"text":value})
                index+=1
            prefix=title.split("·",1)[0].strip()
            category={"普攻":"Melee","E 技能":"Skill","Q 大招":"UltraSkill","被动":"Passive"}.get(prefix,prefix or "Skill")
            output.append({"id":title,"name":title,"category":category,"description_parts":descriptions,"raw_text":" ".join(raw_parts),"level_cap":1,"parameters":[]})
        return output
    if not section: return []
    cards=[]
    for h4 in section.descendants("h4"):
        card=parent_where(h4,is_card)
        if card and card not in cards: cards.append(card)
    output=[]
    for card in cards:
        name=next((clean(x.text()) for x in card.descendants("h4")),"")
        if not name: continue
        params,cap=skill_parameters(card,name); prefix=card.text().split(name,1)[0]; category="Skill"
        for value in ("Melee","UltraSkill","Skill","QTE","City"):
            if value in card.text(): category=value; break
        descriptions=[]
        for p in card.descendants("p"):
            value=clean(p.text())
            if value:
                label=next((clean(x.text()) for x in p.descendants() if x.tag in {"b","strong"} and clean(x.text())),name)
                descriptions.append({"name":label,"text":value})
        output.append({"id":name,"name":name,"category":category,"description_parts":descriptions,"raw_text":clean(card.text()),"level_cap":cap,"parameters":params})
    return output
def cards_after(h):
    grid=after_heading(h) if h else None
    return [x for x in grid.direct() if is_card(x)] if grid else []
def awakenings(page,label,resonance=False):
    output=[]
    for card in cards_after(find_heading(page,label)):
        if resonance:
            title=next((x for x in card.descendants("div") if any("Lv." in clean(s.text()) for s in x.descendants("span"))),None)
            raw=clean(title.text()) if title else ""; match=re.search(r"Lv\.?\s*(\d+)\s*(.*)",raw)
            level=int(match.group(1)) if match else None; name=match.group(2).strip() if match else raw
        else:
            title=next(iter(card.descendants("h5")),None); level=None; name=clean(title.text()) if title else ""
        p=next(iter(card.descendants("p")),None); img=next((x for x in card.descendants("img") if x.attrs.get("src")),None)
        entry={"name":name,"description":clean(p.text()) if p else "","asset":img.attrs.get("src","") if img else ""}
        if level is not None: entry["level"]=level
        output.append(entry)
    return output
def terminal(page):
    h=find_heading(page,"终端"); section=parent_where(h,lambda x:x.tag=="section") if h else None
    card=next((x for x in section.descendants() if x.tag=="div" and {"rounded-lg","border"}<=x.classes()),None) if section else None
    if not card: return None
    title=next((clean(x.text()) for x in card.descendants("h4")),"")
    desc=next((clean(x.text()) for x in card.descendants("p")),"")
    effects=[]
    for box in card.descendants("div"):
        if "flex-wrap" in box.classes() and "gap-2" in box.classes():
            effects=[clean(x.text()) for x in box.direct() if clean(x.text())]; break
    result={"id":"terminal","name":title,"description":desc,"effects":effects,"source_type":"mysqil_page"}
    grid=next((x for x in card.descendants("div") if "inline-grid" in x.classes()),None)
    if grid:
        style=grid.attrs.get("style","")
        row_match=re.search(r"grid-template-rows\s*:\s*repeat\(\s*(\d+)",style)
        column_match=re.search(r"grid-template-columns\s*:\s*repeat\(\s*(\d+)",style)
        cells=grid.direct()
        rows=int(row_match.group(1)) if row_match else 0
        columns=int(column_match.group(1)) if column_match else 0
        if not rows or not columns:
            side=int(len(cells)**.5)
            if side*side==len(cells): rows=columns=side
        active_slots=[]
        for cell in cells:
            match=re.fullmatch(r"槽位\s*\[(\d+),(\d+)\]",cell.attrs.get("title",""))
            if match and "bg-[var(--color-accent)]" in cell.classes():
                active_slots.append({"row":int(match.group(1)),"column":int(match.group(2))})
        if rows and columns and active_slots:
            result["layout"]={"rows":rows,"columns":columns,"active_slots":active_slots,"source_type":"mysqil_page"}
    return result
def voice_actors(page):
    h=find_heading(page,"配音演员"); section=parent_where(h,lambda x:x.tag=="section") if h else None
    source=clean(section.text()) if section else ""; result={}
    for match in re.finditer(r"(日文|英文|中文|韩文)\s*[:：]\s*([^:：]+?)(?=(?:日文|英文|中文|韩文)\s*[:：]|$)",source):
        result[match.group(1)]=match.group(2).strip()
    return result
def import_character(slug,raw,timestamp,skip_assets,refresh,offline):
    page=parse(raw); aside=next(iter(page.descendants("aside")),None)
    title_node=next(iter(aside.descendants("h2")),None) if aside else None
    name=clean(title_node.text()) if title_node else slug
    dl=next((x for x in aside.descendants("dl")),None) if aside else None
    rows=metadata_rows(dl) if dl else {}
    fields={"稀有度":"rarity","属性":"element","弧盘类型":"cassette_type","定位":"role","站位":"position","强度评级":"rating"}
    basic={v:rows.get(k,"") for k,v in fields.items()}
    basic["summary"]=next((clean(x.text()) for x in aside.descendants("p") if clean(x.text())),"") if aside else ""
    stats_node=next((x for x in page.descendants() if x.attrs.get("data-component")=="char-stats" and x.attrs.get("data-json")),None)
    stats=json.loads(stats_node.attrs["data-json"]) if stats_node else []
    up_node=next((x for x in page.descendants() if x.attrs.get("data-upgrade")),None)
    up=json.loads(up_node.attrs["data-upgrade"]) if up_node else {"ascension":[],"skills":[],"materials":{}}
    detail=terminal(page); rec={"weapon":None,"cassette":None}
    for h3 in aside.descendants("h3") if aside else []:
        label=clean(h3.text())
        if label not in {"推荐武器","推荐卡带","推荐弧盘","推荐空幕"}: continue
        card=h3.parent; link=next((x for x in card.descendants("a") if x.attrs.get("href")),None) if card else None
        if not link: continue
        url=urllib.parse.urljoin(ORIGIN,link.attrs["href"]); parts=urllib.parse.urlsplit(url)
        ident=urllib.parse.unquote(parts.path.rstrip("/").rsplit("/",1)[-1])
        url=urllib.parse.urlunsplit((parts.scheme,parts.netloc,urllib.parse.quote(parts.path,safe="/%"),parts.query,parts.fragment))
        img=next((x for x in link.descendants("img") if x.attrs.get("src")),None); title=(img.attrs.get("alt") if img else "") or clean(link.text())
        item={"id":ident,"name":title,"source_url":url}
        if label in {"推荐武器","推荐弧盘"}:
            rank=re.search(r"([SAB])\s*$",clean(link.text())); item.update({"rating":rank.group(1) if rank else "","asset":""}); rec["weapon"]=item
        else:
            item.update({"category":"","cassette_type":"空幕卡带","element":basic["element"],"icon":"","description":"","set_effects":[],"acquisition":"","main_affix_pool":[],"sub_affix_pool":[],"quality":[],"structure":{"main_affix_count":1,"sub_affix_count":4,"rerollable":False},"recommended_main_affixes":[],"recommended_sub_affixes":[],"terminal":detail})
            rec["cassette"]=item
    assets,source_local,asset_failures=download_assets(slug,page,up,skip_assets,refresh,offline)
    for kind,item in rec.items():
        if not item: continue
        link=next((x for x in aside.descendants("a") if urllib.parse.unquote(urllib.parse.urlparse(x.attrs.get("href","")).path).rstrip("/").endswith("/"+item["id"])),None)
        img=next((x for x in link.descendants("img") if x.attrs.get("src")),None) if link else None
        src=urllib.parse.urljoin(ORIGIN,img.attrs["src"]) if img else ""
        local=source_local.get(src,"")
        item["asset" if kind=="weapon" else "icon"]=local
    awakening_data=awakenings(page,"觉醒")
    resonance=awakenings(page,"共鸣",True)
    for item in awakening_data+resonance:
        if item["asset"].startswith("/"): item["asset"]=source_local.get(urllib.parse.urljoin(ORIGIN,item["asset"]),"")
    knowledge={
        "schema_version":"0.3","entity_type":"character","id":slug,"name":name,"review_status":"draft",
        "basic":basic,"recommended":rec,"terminal":detail,"drive_layout_image":"",
        "base_stats":{"level_cap":max((len(x.get("values",[])) for x in stats),default=0),"stats":stats},
        "skills":skills(page),"awakenings":awakening_data,"resonance":resonance,"voice_actors":voice_actors(page),
        "cultivation":{"ascension":up.get("ascension",[]),"skills":up.get("skills",[]),"material_catalog":up.get("materials") or {}},
        "assets":assets,
        "provenance":{"source":"mysqil","source_name":SOURCE,"source_url":f"{ORIGIN}/characters/{slug}/","imported_at":timestamp,"raw_snapshot":f"data/mysqil/characters/{slug}/raw/page.html","source_license":LICENSE,"user_supplied_sources":[]},
        "scope":{"included":["基础资料","推荐武器","推荐卡带","基础属性成长","技能描述与倍率","觉醒","共鸣","突破材料","技能升级材料","卡带词条机制","终端"],"excluded":["配队推荐"],"note":"社区维护页面导入；配队推荐只保留在原始快照中。"},
        "manual_review":[{"field":"source_review","value":"社区源导入，待人工核验","source_type":"community_source","status":"pending"}]
    }
    for field in ("rarity","element","cassette_type","role","position","rating"):
        if not basic[field]: knowledge["manual_review"].append({"field":"basic."+field,"value":"来源页未提供","source_type":"import_validation","status":"pending"})
    if not stats or not knowledge["skills"] or not up_node:
        if not stats: knowledge["manual_review"].append({"field":"base_stats","value":"来源页结构未解析","source_type":"import_validation","status":"pending"})
        if not knowledge["skills"]: knowledge["manual_review"].append({"field":"skills","value":"来源页结构未解析","source_type":"import_validation","status":"pending"})
        if not up_node: knowledge["manual_review"].append({"field":"cultivation","value":"来源页未提供结构化养成数据","source_type":"import_validation","status":"pending"})
    for key in ("weapon","cassette"):
        if not rec[key]: knowledge["manual_review"].append({"field":"recommended."+key,"value":"来源页未提供可导入的推荐项","source_type":"import_validation","status":"pending"})
    if not detail: knowledge["manual_review"].append({"field":"terminal","value":"来源页未提供终端资料","source_type":"import_validation","status":"pending"})
    elif not detail.get("layout"): knowledge["manual_review"].append({"field":"terminal.layout","value":"来源页未提供终端槽位布局","source_type":"import_validation","status":"pending"})
    if asset_failures: knowledge["manual_review"].append({"field":"assets","value":f"{len(asset_failures)} 个资源下载失败","source_type":"import_validation","status":"pending"})
    return knowledge,up

def parse_cassette(raw,item):
    page=parse(raw); over=find_heading(page,"套装概述")
    section=parent_where(over,lambda x:x.tag=="section") if over else None
    summary=clean(section.text()).replace("套装概述","",1).strip() if section else ""
    item["description"]=summary; item["category"]="属性专属" if "属性专属" in summary else "通用"
    h=find_heading(page,"套装效果"); section=parent_where(h,lambda x:x.tag=="section") if h else None
    for card in section.descendants() if section else []:
        if card.tag!="div" or not is_card(card): continue
        piece=next((clean(x.text()) for x in card.descendants("span") if re.fullmatch(r"\d+件套",clean(x.text()))),"")
        desc=next((clean(x.text()) for x in card.descendants("p") if clean(x.text())),"")
        if piece and desc: item["set_effects"].append({"pieces":int(piece[:-2]),"description":desc})
    for h3 in page.descendants("h3"):
        label=clean(h3.text())
        if label not in {"卡带主属性 · 可能出现的词条","可能出现的副词条"}: continue
        card=parent_where(h3,is_card); chips=next((x for x in card.descendants("div") if "flex-wrap" in x.classes()),None) if card else None
        values=[clean(x.text()) for x in chips.direct() if x.tag=="span" and clean(x.text())] if chips else []
        item["main_affix_pool" if label.startswith("卡带主属性") else "sub_affix_pool"]=values
    h=next((x for x in page.descendants("h3") if clean(x.text()).startswith("品质差异")),None)
    card=parent_where(h,is_card) if h else None; grid=next((x for x in card.descendants("div") if "grid" in x.classes()),None) if card else None
    if grid:
        item["quality"]=[]
        for node in grid.direct():
            raw_text=clean(node.text()); tier=next((x for x in ("金","紫","蓝") if x in raw_text),"")
            desc=next((clean(x.text()) for x in node.descendants("p") if clean(x.text())),"")
            if tier: item["quality"].append({"tier":tier,"description":desc})
        raw_text=clean(card.text())
        item["structure"]={"main_affix_count":1 if "1 主属性" in raw_text else None,"sub_affix_count":4 if "4 副属性" in raw_text else None,"rerollable":False if "不可洗练" in raw_text else None}
    item["detail_source_url"]=item["source_url"]
def parse_weapon(raw,item):
    page=parse(raw); h=find_heading(page,"概述"); section=parent_where(h,lambda x:x.tag=="section") if h else None
    item["description"]=" ".join(clean(x.text()) for x in section.descendants("p") if clean(x.text())) if section else ""
    item["detail_source_url"]=item["source_url"]
def source_path(kind,slug): return ROOT/"data"/"mysqil"/kind/slug/"raw"/"page.html"
def write_manifest(kind,slug,url,timestamp,status,ctype,count=0):
    path=source_path(kind,slug); path.parent.mkdir(parents=True,exist_ok=True)
    value={"source":"mysqil","source_name":SOURCE,"source_url":url,"canonical_url":url,"fetched_at":timestamp,"http_status":status,"content_type":ctype,"raw_html":"raw/page.html","image_count":count,"source_license":LICENSE,"note":"社区维护的非官方来源快照；导入知识待人工核验。"}
    (path.parent/"manifest.json").write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def main():
    import argparse
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--refresh",action="store_true",help="refetch cached pages and assets")
    cli.add_argument("--skip-assets",action="store_true",help="import page data without downloading images")
    cli.add_argument("--offline",action="store_true",help="only read pages and assets already present locally")
    args=cli.parse_args()
    if args.offline and args.refresh: cli.error("--offline cannot be combined with --refresh")
    pages=[(s,u) for s,u in character_pages(args.offline) if s!="zhenhong"]
    timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    records=[]; equipment={"weapons":{},"cassettes":{}}
    for slug,url in pages:
        path=source_path("characters",slug)
        try:
            raw,status,ctype=save_page(url,path,args.refresh,args.offline)
            data,up=import_character(slug,raw,timestamp,args.skip_assets,args.refresh,args.offline)
            for group,key in (("weapons","weapon"),("cassettes","cassette")):
                item=data["recommended"].get(key)
                if item and item.get("source_url"): equipment[group][item["id"]]=item["source_url"]
            write_manifest("characters",slug,url,timestamp,status,ctype,len(data["assets"]))
            records.append(data); print(f"PAGE {slug}: {data['name']} · 技能 {len(data['skills'])} · 资源 {len(data['assets'])}")
        except Exception as err:
            print(f"ERROR page {slug}: {err}"); raise
    for group,items in equipment.items():
        for ident,url in sorted(items.items()):
            try:
                raw,status,ctype=save_page(url,source_path(group,ident),args.refresh,args.offline)
                for data in records:
                    item=data["recommended"].get("cassette" if group=="cassettes" else "weapon")
                    if item and item["id"]==ident: (parse_cassette if group=="cassettes" else parse_weapon)(raw,item)
                write_manifest(group,ident,url,timestamp,status,ctype); print(f"ITEM {group}/{ident}: saved")
            except Exception as err:
                print(f"ERROR item {group}/{ident}: {err}")
                for data in records:
                    item=data["recommended"].get("cassette" if group=="cassettes" else "weapon")
                    if item and item["id"]==ident: data["manual_review"].append({"field":"recommended."+group,"value":"详情页下载失败","source_type":"import_validation","status":"pending"})
    directory=ROOT/"data"/"knowledge"/"characters"; directory.mkdir(parents=True,exist_ok=True)
    for data in records:
        (directory/(data["id"]+".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        resource=ROOT/"data"/"resources"/"characters"/data["id"]; resource.mkdir(parents=True,exist_ok=True)
        manifest={"resource_root":f"data/resources/characters/{data['id']}","entity_type":"character","entity_id":data["id"],"asset_count":len(data["assets"]),"source_snapshot":data["provenance"]["raw_snapshot"],"source_license":LICENSE,"updated_at":timestamp[:10]}
        (resource/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    all_data={}
    for path in sorted(directory.glob("*.json")):
        data=json.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("id")!="zhenhong": all_data[data["id"]]=data
    (directory/"other_characters.js").write_text("window.characterKnowledge = Object.assign(window.characterKnowledge || {}, "+json.dumps(all_data,ensure_ascii=False,separators=(",",":"))+");\n",encoding="utf-8",newline="")
    attribution=ROOT/"data"/"mysqil"/"ATTRIBUTION.md"
    attribution.write_text(f"# {SOURCE} source attribution\n\n- Source: [{SOURCE}]({ORIGIN}/)\n- Stated source license: {LICENSE}.\n- Character and linked equipment snapshots are stored under data/mysqil/.\n- Each imported record retains its source URL and a pending human-review entry.\n- Team recommendations remain in raw snapshots and are excluded from normalized knowledge.\n\nCheck license compatibility before redistributing imported descriptions or images, especially in commercial use.\n",encoding="utf-8",newline="")
    print(f"SUMMARY characters={len(records)}/{len(pages)} weapons={len(equipment['weapons'])} cassettes={len(equipment['cassettes'])}")
if __name__=="__main__": main()
