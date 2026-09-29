# Findings & Decisions

## Requirements
- 交付一份美观的“可可助手” UI，但产品角色是“配队知识管理后台”，不是通用聊天助手。
- 维护者不应通过阅读或修改求解器代码来维护角色能力标签。
- 管理界面必须表达游戏事实、受控能力标签、反应强化、槽位适配、影响分析和发布状态。
- 新增普通角色应主要录入能力与证据，由系统自动推导适配槽位和阵容影响。
- 修改上线前需要看到即时校验、双版本影响分析，并支持草稿、审核、发布、回滚语义。
- 当前工作区没有实际应用代码，因此交付一个零依赖、可直接打开的高完成度 UI 概念实现。

## Background Findings
- 项目核心领域是游戏配队知识：游戏事实、能力标签、反应强化、体系、槽位、阵容模板、候选阵容、可行性规则、评价维度、选择策略、证据、知识变更集、知识发布包。
- 维护者最有价值的反馈不是原始 JSON，而是“系统理解”“适配槽位”“影响阵容”和“黄金测试状态”。
- 参考概念稿采用左侧领域导航、中央角色编辑、右侧即时校验与发布影响；本 UI 延续这一信息架构。
- 当前 MVP 聚焦角色管理，包含角色事实、标签、反应强化、站场模式、解锁条件和证据；反应体系与规则中心先做导航入口。

## Animation Vocabulary
- **Stagger** — Animate several items one after another with a small delay between each, creating a cascade.
- **Scale in** — Element grows from smaller to full size as it appears, often paired with a fade.
- **Crossfade** — One element fades out as another fades in, in the same spot.
- **Layout animation** — When an element's size or position changes, it animates to the new spot instead of snapping.
- **Origin-aware animation** — An element animates out of its trigger, like a popover growing from the button that opened it instead of from its own center which is the default in CSS.
- **Press / Tap feedback** — A subtle scale-down when an element is clicked, so it feels physical.
- **Reduced motion** — Respecting the user's prefers-reduced-motion setting by toning down or removing motion.

## Technical Decisions
| Decision | Rationale |
|---|---|
| Vanilla HTML/CSS/JS | 空仓库直接提供可预览成品，避免引入安装步骤 |
| CSS custom easing | 使用 `cubic-bezier(0.23, 1, 0.32, 1)` 的强 ease-out，入口/反馈更灵敏 |
| CSS transitions for dynamic UI | 角色卡、标签、校验状态和 toast 可能快速触发，transition 可从当前状态重新定向 |
| transform + opacity only for movement | 避免布局抖动与 layout thrashing |
| reduced-motion + hover gate | 满足动效可访问性与触屏设备误触规范 |
| No scale(0) / no transition: all | 保证入口有物理起点且审计可通过 |

## Issues Encountered
| Issue | Resolution |
|---|---|
| 当前无现成组件 | 从品牌基础、领域导航、角色表单和解释型反馈组件一起建立最小系统 |
| 之前未读取用户附上的三份背景文件 | 已暂停原方案，完整读取并将主题改为配队知识管理后台 |

## Resources
- README.md
- 用户附上的 findings.md / progress.md / task_plan.md
- animation-vocabulary/SKILL.md
- emil-design-eng/SKILL.md
- review-animations/SKILL.md + STANDARDS.md
- webapp-testing/SKILL.md
## Canonical Plan Consolidation

- 当前项目唯一主计划目录为 .planning/2026-09-28-cocoa-assistant-ui-overhaul/。
- 之前新增的 2026-09-28-cassette-recommendation-and-terminal/ 是本计划中的一个功能阶段，不是独立项目。
- 本次已把该阶段的需求、数据决策、实现结果、验证结果和错误记录合并到本主计划。
- 后续不再按功能创建同级计划目录，所有新发现继续追加到本 findings.md。

## Current Role Data Findings

- 真红知识数据位于 data/knowledge/characters/zhenhong.json 和 data/knowledge/characters/zhenhong.js。
- 角色基础资料由维护者编辑，用户公开预览从维护后的资料同步生成。
- 技能目标等级必须按不同技能分别维护，并汇总对应养成材料。
- 卡带的 main_affix_pool 与 sub_affix_pool 表示原始可能出现属性；recommended_main_affixes 与 recommended_sub_affixes 表示维护者推荐属性。
- 推荐属性结构为 name + priority；priority 越大越优先，同值用“≈”。
- 卡带终端放在 recommended.cassette.terminal，并标记为用户截图补录来源。
- 角色资源已迁移到 data/resources/characters/zhenhong/，抓取快照仍保留在 data/mysqil/characters/zhenhong/raw/。

## Other Character Expansion — 2026-09-29

- User requested downloading all other character data locally and integrating it into the role management system, using Zhenhong's data structure as the template.
- Scope follows the existing canonical plan's next step. This phase should first establish the complete character roster and available source coverage; unknown facts must retain provenance or remain explicitly incomplete rather than being invented.
- The existing source of truth is the community-maintained 异环 Wiki at `https://wiki.mysqil.com/`, which already supplied Zhenhong's raw page snapshot and asset paths. Search results expose individual pages at `/characters/<id>` and a roster on the site home page. Use this source consistently and preserve per-field source attribution.
- The Mysqil home page is current as of 2026-09-29 and lists 25 characters: 卡厄斯、神塔吉多、娜娜莉、安魂曲、法帝娅、浔、真红、九原、伊洛伊、早雾、零、哈尼娅、阿德勒、哈索尔、小吱、白藏、达芙蒂尔、翳、薄荷、埃德嘉、海月、明音凛、残虹、灵可、黑羽. The request therefore covers the 24 entries other than 真红 in the current roster.
- The source site identifies itself as a player-maintained, unofficial guide, with content based on game data and community contributions, and states CC BY-NC-SA 4.0 at the footer. Preserve attribution and source URLs. Avoid publishing redistributed guide text or assets into the public remote until licensing and commercial use are addressed.
- The roster page's direct URL fetch timed out in the web reader, while the home page rendered and supplied the current roster. Use its character links or sitemap for programmatic collection.
- `robots.txt` permits crawling and points to `https://wiki.mysqil.com/sitemap-index.xml`; `/sitemap.xml` itself returns 404. Use the declared sitemap index to enumerate pages rather than guessing character slugs.
- Mysqil's declared sitemap index resolves to `sitemap-0.xml`, which lists 25 character detail pages (including 真红). Slugs: `adeler`, `anhunqu`, `baizang`, `bohe`, `canhong`, `dafutier`, `edjia`, `fadiya`, `haiyue`, `haniya`, `hasuoer`, `heiyu`, `jiuyuan`, `kaesi`, `ling`, `lingke`, `mingyin`, `nanali`, `tajiduo`, `xiaozhi`, `xun`, `yi`, `yiluoyi`, `zaowu`, `zhenhong`. The directory therefore supports a deterministic 24-character download; verify display names from each page rather than inferring slugs.
- A representative detail page (`kaesi`) is server-rendered Astro HTML and can be saved directly; the raw snapshot is 121 KB. It contains standard field text, localizable image paths, per-stat JSON in `data-json`, skill parameter arrays in `data-skill-params`, and cultivation JSON in `data-upgrade`. The page labels skills, six awakenings, recommended equipment, team compositions, and calculator data; the project scope still excludes importing team recommendations.
- The management UI hardcodes its roster in `index.html` and only hydrates the Zhenhong entry from `window.characterKnowledge.zhenhong`; its list/search controls therefore need to become data-driven before 24 more records are actually manageable.
- Mysqil character pages expose core facts in an `<aside>` card, five stat curves in a JSON attribute, one skill card per skill with `data-skill-params`, and a calculator JSON attribute containing ascension, skill costs, and item catalog. The app's existing renderer can consume normalized versions of these structures after small genericity fixes.
- The side panel markup identifies role metadata as label/value rows (`dl > div`), and recommendation URLs are available on the weapon and cassette card anchors. Each skill card contains one `data-skill-params` select and its surrounding skill text; level-cap values can be inferred from the parameter arrays. The `data-upgrade` object has `ascension`, `skills`, and `materials`; `materials` is the source equivalent of our `cultivation.material_catalog`.
- The Mysqil detail page's six metadata rows directly provide rarity, element, cassette type, role, position, and tier rating; the adjacent paragraph is the character summary. Weapon and cassette cards provide the exact item slug and display text via their links. Awakening and resonance entries are separate cards in the same section; terminal name, description, and effects have their own card.
- Page asset URLs cover portraits, elemental/stat UI, weapon/cassette icons, and awakening icons. The HTML references related team portraits too; those must be excluded from role asset imports because team recommendations are outside this phase.
- A stdlib `html.parser` DOM walk can extract the local Mysqil snapshots without third-party runtime dependencies. Preserve optional or source-missing values as empty/unknown with manual-review status rather than creating fake recommendations.
- Character-linked weapon and cassette detail pages are available at `/weapons/<slug>/` and `/cassettes/<slug>/`. The cassette detail page exposes exact 2/4-piece effects, main/sub affix pools, quality tiers, item icon URLs, and a set overview; weapon pages expose description and level/stat detail. A sample `/images/items/<icon-id>.webp` endpoint responds with a WebP asset. These pages support filling the existing recommendation schema rather than leaving every non-Zhenhong cassette blank.
- Bulk source collection completed from the Mysqil sitemap: 24 non-Zhenhong role snapshots plus 28 unique linked equipment detail snapshots. Of 639 role-specific image URLs, 615 downloaded; 24 referenced awakening WebP URLs return 404. Keep those source facts, mark the missing assets for review, and render a non-broken placeholder rather than inventing replacement imagery.
- Role title lives in the sidebar `h2`; source pages do not have a content `h1`, so normalized names must come from `aside h2`.
- Tower character 塔吉多 (`tajiduo`) uses a legacy/different page layout: skill names are headed by descriptive `h4`s, recommendation labels are 推荐弧盘 / 推荐空幕, and the page has no char-stats `data-json` or `data-upgrade` data attributes. The current import leaves that record incomplete; recover details from its raw page and mark source omissions for human review.
- Some equipment slugs use Unicode accented letters. Equipment URL extraction and path generation must preserve these slugs and percent-encode them for HTTP requests.
- Phase 6 import completion: all 24 non-Zhenhong role snapshots and 30 linked item snapshots (20 weapons, 10 cassettes) are local; the two accented cassette slugs are now downloaded as well. The normalized collection is 25 characters total, with per-character source URLs, source license, raw snapshots, and pending manual-review status.
- The management view now builds the roster from `window.characterKnowledge`, displays source data for every character, and renders separate resonance, awakening, stats, skills, cultivation, recommendation, and local-asset sections. Missing source fields/assets render an explicit empty state; no team recommendations enter normalized character data.
- Mysqil currently returns 404 for 24 awakening image references across 残虹、黑羽、灵可、伊洛伊. Their awakening descriptions stay available and the UI uses a local placeholder for the missing icons.
- Source coverage exceptions: 塔吉多 has four legacy prose skill entries but no structured stats/upgrade/recommended equipment; 明音凛's source page currently exposes two skill entries and no cassette recommendation. These gaps remain visible for follow-up review.
- Additional source gaps are recorded in each character's `manual_review`: 残虹 currently has no importable weapon/cassette recommendation; 黑羽 and 灵可 have no cassette recommendation; 明音凛 also omits its source position. The editor shows empty states for absent recommendations rather than carrying data over from another role.
- `scripts/download_mysqil_sources.ps1` now resolves the repository root relative to itself and can parse/download percent-encoded Unicode equipment paths; `scripts/import_mysqil_characters.py --offline` regenerates the normalized records and shared JS bundle from local snapshots.
- Source site license is stated as CC BY-NC-SA 4.0. The data is stored locally with attribution; confirm license compatibility before public or commercial redistribution.


## Terminal and Drive Layout Review — 2026-09-29

- The identical 5×4 dark-square graphic was generated by shared UI markup. Mysqil has no terminal `<img>` files, but its terminal diagram is drawn with a 7×7 inline grid and role-specific active-slot coordinates. The earlier audit looked only for `<img>` and missed those HTML-rendered diagrams. Across the 24 source terminal sections there are four distinct layouts and 11 effect variants; 塔吉多's page has no terminal section.
- The temporary change that placed a recommended cassette icon in the terminal card was incorrect and has been removed. The card now renders the exact 7×7 terminal slot pattern parsed from each role source; the cassette icon remains only in the cassette summary. White/empty cells and 20 active slots match the Mysqil source layout.
- All 25 normalized character JSON records carry root-level `terminal` and `drive_layout_image` fields. The importer records each terminal layout as `rows`, `columns`, and `active_slots` with per-field Mysqil provenance. Current coverage is 24/25 terminal records; all 24 have 20 active positions in a 7×7 grid, represented by four distinct arrangements and 11 effect variants. The Zhenhong user-supplied terminal text keeps its original provenance while its diagram uses the role source snapshot.
- Added a PNG/JPG/WebP upload slot. Current static app stores uploaded images in browser IndexedDB per character (with a small localStorage fallback), not in repository files or GitHub. The user-facing preview remains hidden and empty until an image is available; uploaded image data is local to the browser profile.
- `node --check` passed for `app.js` and both character data bundles. A structured scan found all 25 JSON files have both canonical fields and all recommended cassette icon paths resolve.
- Browser interaction verification could not run: the available Playwright Python package and Chromium binary are absent. The in-app browser also rejected the local `file://` page and explicitly prohibited using a local HTTP server as a workaround. The upload / role-switch / remove flow remains unverified in a live browser.


## Repository-backed Drive Layout Upload Plan — 2026-09-29

- The current site is a static `index.html` app with no backend. IndexedDB/localStorage uploads are private to one browser and cannot become team data or GitHub source of truth.
- Recommended default: a small loopback-only local admin service that serves the app and writes images/metadata into the selected repository checkout. The image path belongs in the role JSON `drive_layout_image`; generated JS bundles should be rebuilt from JSON. Normal Git review/commit/push remains a separate explicit step; never place a GitHub personal access token in frontend code.
- A remotely hosted admin uploader would require a separately designed authenticated backend or GitHub App and is outside the static-site capability. Confirm this deployment requirement before implementation.
- Existing source archive states Mysqil material is CC BY-NC-SA 4.0 and asks to verify compatibility before redistribution, especially in commercial use. Source-derived role text and downloaded artwork are currently untracked local files; review repository license/visibility and scope before publishing them.
- Current `main` is aligned with `origin/main` at `ba208f7`; prior local changes are uncommitted and include the app/data expansion, terminal diagram fix, and optional browser-local layout upload.


### Sync Preflight Errors
- Direct GitHub page fetch returned a cache miss; repository visibility/license could not be confirmed through web search.
- `git fetch origin main` failed before contacting the remote because the sandbox marks `.git/FETCH_HEAD` read-only. Git fetch/commit/push requires an approved filesystem escalation.

## Session: 2026-09-29 — Encyclopedia Management and Arc Drive Catalog

### Starting Point
- Synced project state is clean at `origin/main`; no new implementation changes have been made yet.
- The previous user request asks for a sibling 图鉴 area with 弧盘、空幕、驱动块 categories, then a complete local copy of the guide site's 弧盘 data.
- The existing source downloader only follows equipment linked from character pages, so its 20 role-linked weapon pages do not establish complete catalog coverage.

### Discovery Notes
- The guide's global navigation groups 弧盘、空幕、驱动块 under 图鉴, and the item detail pages link back to a separate 弧盘 index. The guide page footer identifies CC BY-NC-SA 4.0 and credits Matsuzaka Yuki; preserve attribution in local files and user-facing source links.
- The web search reader can retrieve individual item pages but times out on the likely category listing URL. Direct PowerShell HTTP access is blocked by the workspace's network policy; do not treat a partial search result list as a complete source inventory.
- Existing app navigation is a left sidebar with placeholder click handlers, whereas the supplied reference depicts a hierarchical top navigation. Implementation must add a clear hierarchy without breaking the existing role-management workspace.
- Existing imported role JSON already contains source-linked recommended weapons and raw snapshots, but no standalone weapon/arc-drive collection is loaded by the UI.

### Current Status
- **Phase:** 9 — Encyclopedia Management and Arc Drive Catalog
- **Status:** discovery; complete listing acquisition is the current blocker to claiming a complete catalog.

#### Arc-drive source inventory update
- Browser navigation successfully opened the authoritative `/weapons/` index. It explicitly reports **51 items** and exposes all 51 detail-page links in a single list. The current inventory comprises S/A/B grades and five types; this full index supersedes the earlier limitation from the web reader.
- A detail page contains the weapon image, grade/type, display name, level-80 base attributes, description, rank-dependent effect text, overview, and page scripts carrying level and rank values. The item icon path follows `/images/weapons/<slug>.webp` on the sampled page.
- Source detail footers identify © 2026 Matsuzaka Yuki and CC BY-NC-SA 4.0. Keep a visible attribution/source link in the app and preserve page snapshots.

## Phase 10 — Sky Curtain Catalog — 2026-09-29

- Canonical Phase 9 conventions confirmed before source investigation: raw index at `data/mysqil/weapons/raw/index.html`; each raw detail snapshot at `data/mysqil/weapons/<slug>/raw/page.html`; item roster and retrieval/source metadata at `data/mysqil/weapons/roster.json`; imported knowledge at `data/knowledge/encyclopedia/arc_drives.json` plus generated `.js`; item-specific images under `data/resources/encyclopedia/weapons/<slug>/`; repeatable collection/import scripts are `scripts/download_mysqil_weapons.ps1` and `scripts/import_mysqil_weapons.py`. The importer checks the index-declared count and attaches source/license/author/URL/snapshot provenance to each record.
- The source's authoritative 空幕 index is `https://wiki.mysqil.com/cassettes/` (also reachable without the trailing slash). It declares **12 套卡带**, split into six 属性专属 and six 泛用功能 entries. Names listed by the index: 失落光芒、恶魔之血·诅咒、森林萤火之心、真红双生蝶、街头拳王、迪亚波罗斯、守卫王国、小小大冒险、影之信条、缇娅的夜间酒馆、静谧山庄、音速蓝刺猬. The index footer credits Matsuzaka Yuki and states CC BY-NC-SA 4.0.
- The index distinguishes 卡带 from 驱动块 as separate entities. This phase imports only the 12 空幕卡带 entries; the 驱动块 UI/category remains empty.
- Each of the 12 detail pages and its referenced item artwork still needs direct inspection and local snapshot/resource reconciliation. Do not treat search snippets as complete item data.

### Detail page inventory and retrieval notes
- The listing links to these 12 stable detail slugs: `shiluo-guangmang`, `emozhixie-zuzhou`, `senlin-yinghuozhixin`, `zhenhong-shuangshengdie`, `jietou-quanwang`, `diyabolosi`, `shouwei-wangguo`, `xiaoxiao-damaoxian`, `yingzhi-xintiao`, `tiyà-yèjianjiuguan`, `jingmi-shanzhuang`, and `yinsu-lancìwei`. Preserve and URL-encode the two accent-bearing paths when fetching.
- The four detail pages retrieved by the web reader expose the same core layout: set classification and elemental affinity where applicable; 2-piece/4-piece effects; acquisition text; main/sub affix possibility pools; Gold/Purple/Blue quality notes; an editorial overview; and one item image. Each footer repeats Matsuzaka Yuki and CC BY-NC-SA 4.0. The source's prose overview may include editorial recommendations, so keep source facts distinct and preserve its URL/provenance if normalized.
- Web reader retrieval failed for eight detail pages (cache miss or timeout). Direct raw download and offline parsing are required before claiming all page fields or assets are reconciled.

### Local integration findings
- Ten of the 12 listed card sets already have raw snapshots under `data/mysqil/cassettes/<slug>/raw/page.html` because character imports downloaded role-recommended gear. The source index entries `yingzhi-xintiao` and `jingmi-shanzhuang` have no snapshot yet.
- `data/knowledge/encyclopedia/cassettes/` does not exist: there is no complete standalone 空幕 knowledge package. The app already has a dedicated 空幕 sub-navigation button, but `showEncyclopediaCategory` routes it to the generic empty-state panel.
- A lookup of the absent knowledge directory emitted a path-not-found message and made no changes; this confirms the planned data gap.

### Image asset findings
- All inspected cached cassette pages reference three quality-specific item images (Gold, Purple, Blue), each hosted under an English asset slug at `/images/cassettes/<asset-slug>/<quality>.webp`. The page-detail slug and image-directory slug are not reliably identical, so collect each page's exact image URLs instead of deriving names.
- The complete expected image set is 36 item-specific WebP files for the 12 listed entries. Preserve all three tiers locally; the UI can default to Gold and allow selecting the other two images.

### Normalization fields confirmed from cached detail HTML
- The primary page content is server-rendered under `<main>`. The item header contains the `h1`, category label, and (for attribute-specific sets) element label. The set-effects section holds separate 2-piece and 4-piece cards; acquisition is a separate labeled section.
- The affix mechanism section presents main-affix and sub-affix pools as individual chips, followed by a quality-difference panel; the final `套装概述` section contains source overview prose. Parse each field from its own section and leave missing values empty rather than falling back to generic explanatory copy.
- The header includes three `<img data-tier-img="gold|purple|blue">` elements. These expose all quality image variants in one raw page; the app can provide an image-tier selector.

### Index link parsing correction
- The 13th `/cassettes/<slug>` link is `/cassettes/drivers`, labeled “查看驱动块详解 →”; it is a guide link, not a card entry. The 12 actual catalog links are card anchors carrying `bg-card` and `overflow-hidden` classes. The downloader now restricts enumeration to those catalog-card anchors and retains the index-declared count check.

### Source collection complete
- `scripts/download_mysqil_cassettes.ps1 -Refresh` fetched the declared 12 entries, all 12 detail pages, and all 36 Gold/Purple/Blue WebP files with no failures. The downloader saved `data/mysqil/cassettes/raw/index.html`, each `data/mysqil/cassettes/<slug>/raw/page.html`, image files under `data/resources/encyclopedia/cassettes/<slug>/<quality>.webp`, and the root `roster.json` with author, license, source URLs, local paths, SHA-256 hashes, and retrieval time.
- The web reader had failed to retrieve eight detail URLs, but the local downloader fetched all eight. All 12 pages have been refreshed rather than relying on role-link discovery coverage.

### Parser implementation notes
- On a representative local snapshot, the header has the exact `属性专属`/`泛用功能` marker and optional elemental affinity; the set-effects cards are inside their own section; acquisition has a labeled value; each main/sub-affix card has an individual heading, explanatory paragraph, and chip container; and the quality-difference card contains the shared Gold/Purple/Blue notes.
- The category index itself also summarizes both set effects for each item, but detail-page content remains the canonical normalized source. The index is retained separately for completeness and provenance.
- The diagnostic printed the required structure successfully before its final chip-only step hit an undefined helper method. This affected no source data; importer code will use the parser's children list directly.

### Normalized knowledge package
- `scripts/import_mysqil_cassettes.py` reads only the local source roster and snapshots. It validates the declared 12-item count, uniqueness, exact page-title match, required two-/four-piece effects, all three source image variants and URL/path mapping, then writes `data/knowledge/encyclopedia/sky_curtains.json` and `sky_curtains.js`.
- Each record preserves category, optional element, both set effects, acquisition, separate main/sub-affix pools and notes, quality differences, source overview, Gold/Purple/Blue local image paths and hashes, source URL, raw snapshot path, author, license, and pending human review status. Missing optional source values remain empty.
- Import completed with 12 records and 36 locally mapped quality images.


### UI integration and scope review
- Added `sky_curtains.js` to the page load order. 空幕 now has its own searchable listing, category and element filters, detail panel, source links/attribution, 2/4-piece effects, acquisition, main/sub-affix pools, quality differences, and a Gold/Purple/Blue image selector. The 驱动块 category remains on the existing empty-state panel.
- Source coverage reconciles 12 source entries to 12 unique normalized records, 12 detail snapshots, and 36 WebP images. All 12 records contain both set effects, acquisition, overview, main/sub-affix pools, three quality notes, and all three quality image mappings. Categories are 6 属性专属 / 6 泛用功能; the six elemental sets have one affinity each.
- A first coverage pass found quality-tier prose was not being parsed (0/12); source DOM showed the label in a nested `div` and description in a `p`. The importer was corrected and rerun; the final coverage pass confirms 金/紫/蓝 notes on all 12 records.
- Static checks passed: `node --check app.js`, `node --check data/knowledge/encyclopedia/arc_drives.js`, and `node --check data/knowledge/encyclopedia/sky_curtains.js`; roster/count, raw-page footer, title, quality assets, SHA-256, provenance, and JSON/JS bundle matching checks passed. Browser interaction and responsive verification were not run.


### Attribution and license review
- Mysqil's index/detail pages identify Matsuzaka Yuki and CC BY-NC-SA 4.0. The official Creative Commons deed says sharing/adaptation is allowed under conditions including appropriate credit, a link to the license, an indication of changes, noncommercial use, and same-license sharing for adapted material: https://creativecommons.org/licenses/by-nc-sa/4.0/ .
- The raw pages remain preserved; normalized knowledge is a structured extraction from those snapshots. The UI, README, and attribution file will link the license and identify the imported data as normalized. Commercial reuse remains outside the source license grant.
- The official deed page opened from its legal-code URL timed out in the web reader. The checklist above comes from the official CC deed summary, not a claim that the full legal code was reviewed.


### Attribution implementation
- Added the official CC BY-NC-SA 4.0 license URL to the cassette raw roster and to collection/record provenance; each normalized item identifies the source-page extraction and structure normalization while its exact HTML page remains preserved.
- Both arc-drive and sky-curtain attribution footers now link to the source index and the Creative Commons license, name Matsuzaka Yuki, and state that the catalog was extracted and structured. README and `data/mysqil/ATTRIBUTION.md` describe the 12-set update workflow, snapshot/resource locations, attribution, license link, and modification status.


### Final page-field reconciliation
- A final raw-page pass found two quality-panel fields present on every item page that were not yet in the normalized record: the grade-role note (`data-tier-field="role"`) and grade-source note (`data-tier-field="source"`). They supplement the separate acquisition field and Gold/Purple/Blue quality differences. Import both exactly as shown, expose them in the item detail, and include them in final coverage checks.


### Final source-field reconciliation complete
- The normalized quality object now includes the raw page's `data-tier-field="role"` (quality grade guidance) and `data-tier-field="source"` (quality source conditions) alongside the Gold/Purple/Blue tier notes. The detail page shows both additional values, and search includes them.
- Reimported all 12 records. Final audit confirms both additional fields are present on 12/12 records, with the earlier source/count/page/image/provenance/quality checks still passing.


### Git delivery attempt
- Refreshed `origin/main` immediately before delivery; local `HEAD` and `origin/main` both matched `b4e560e`. Created local feature commit `b190533 feat: add complete sky curtain catalog` (52 files, including 12 records and 36 images).
- The direct `git push origin main` was rejected by automatic review. The reviewer cited direct mutation of the repository's default branch as high risk and said it did not recognize trusted explicit authorization for this destination/side effect. No push succeeded: the post-attempt check shows `origin/main` remains `b4e560e`, local `main` is ahead by one, and the working tree is clean. Do not retry via another route; require direct user approval.
