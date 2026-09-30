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

### Push approval and completion
- The user explicitly approved pushing the prepared commits to `origin/main` without force. Rechecked that the working tree was clean, local `main` was ahead by exactly two commits, and `origin/main` still pointed to `b4e560e`.
- `git push origin main` succeeded: `b4e560e..9777d32 main -> main`. No force push was used.
- Updated the canonical Phase 10 plan after the push. Browser interaction and responsive verification remain unrun.

## Phase 11 — Driver Block Catalog

- User requested that the full guide-site driver-block dataset be copied into the local repository and integrated into the assistant like the existing 弧盘 and 空幕 catalogs.
- Repository baseline is clean at `1c35cf3`, with `main` aligned to `origin/main`. The current shared encyclopedia navigation already has a dedicated 驱动块 category, which Phase 9 intentionally left empty; Phase 10 imported 空幕 while preserving that empty state.
- Source discovery is in progress; the count, detail routes, license, and representative schemas are being checked against the local snapshots. Keep source-derived web content in this findings file, not in the automatically injected task plan.

### Initial guide-site discovery
- The real catalog is `https://wiki.mysqil.com/drivers` (singular route without a trailing slash). The earlier `/cassettes/drivers` URL does not resolve in the web reader; it was only the cassette-page's “驱动块详解” link label, so do not assume the URL from that label.
- The catalog page declares **12 shapes: Ⅱ型 2 / Ⅲ型 6 / Ⅳ型 4**. Its visible catalog has quality filters (金/紫/蓝), model filters (Ⅱ/Ⅲ/Ⅳ), and three quality-specific detail links per shape, for 36 expected shape-quality records if the raw listing confirms every link.
- Shapes shown in the index: Ⅱ型 horizontal and vertical; Ⅲ型 horizontal, vertical, plus four L orientations; Ⅳ型 horizontal, vertical, plus horizontal and vertical Z shapes. The catalog footer credits Matsuzaka Yuki and CC BY-NC-SA 4.0.
- Search-indexed detail pages expose the shape/model, quality-specific imagery, a level control, main-stat values (at least attack and HP), and quality-specific random-stat values. The observed random-stat families include flat/percent ATK, flat/percent HP, flat/percent DEF, Crit Rate, Crit Damage, universal damage bonus, 环合强度, and 倾陷强度. Confirm exact fields, level scaling, and image variants from all locally downloaded source snapshots before normalization; search results are only discovery evidence.
- A detail result showed a “其他品质” navigation, suggesting adjacent grade routes per shape. Retrieve exact URLs from the actual index rather than constructing a guessed slug pattern.
- The catalog's actual links confirm 36 pages. For the horizontal Ⅱ型 shape, the exact routes are `/drivers/cell2_style1_1_Orange`, `/drivers/cell2_style1_1_Purple`, and `/drivers/cell2_style1_1_Blue`; the source labels grades S/A/B respectively, in addition to gold/purple/blue color.
- The page has a level input showing a `Lv.[input]+20` pattern, two main-stat values (ATK and HP), and four repeated random-stat panels. In the observed Ⅱ型 horizontal sample, each panel lists 11 possible random attributes. Values vary by quality: Gold S main ATK/HP 42/560, Purple A 34/448, Blue B 25/336. Capture the source's actual value table and dynamic level behavior from HTML/embedded data; do not assume +20 is the only supported level.
- The index card's “驱动块机制详解” click points to `/cassettes/drivers`, which timed out/failed in the web reader. That is separate from the accessible `/drivers` 12-shape catalog. Keep researching the guide link and collect the catalog pages from the index itself.
- Repeated web-reader opens of `/cassettes/drivers`, including with and without a trailing slash and a query string, failed with timeout/internal error. Treat this as a web-reader limitation, not a confirmed 404; try the direct source downloader if the mechanism guide is part of scope.
- A full detail page for the horizontal Ⅱ型 lists four equal-looking repeated panels, each with the same 11 random-stat names but tier-specific values. The source page also links B/A/S quality routes. Preserve the pages verbatim and inspect the raw DOM/script to discover whether these are source-declared roll slots before choosing normalized fields.
- Local collection succeeded: the actual index confirms 12 shapes and lists all 36 quality-specific detail links; all 36 pages were saved to `data/mysqil/driver-blocks/<page-id>/raw/page.html`, and the downloader preserved 46 unique referenced `/images/drivers/` and `/images/ui/` image assets with SHA-256 records. The 36 index image references are the 12×3 shape/quality artwork variants.
- The saved detail HTML has data-bearing `#driver-stats-panel` and `#driver-substats` elements, each with embedded JSON consumed by the source page's own slider/substat chooser. The page also uses a `data-lv-slider` input. This should allow importing the full level curves and exact random-stat pool rather than only the visible default values; inspect the JSON field schema and array lengths offline before implementing the importer.
- Exact schema from the first S-grade Ⅱ型 horizontal page: `driver-stats-panel` embeds `id`, `name`, `quality`, `type_id`, `type_geometry`, `ownGridNum`, `set_effect`, `main_stats`, and `sub_stats`. Both main-stat curves have 21 values for slider positions +0 through +20. `sub_stats` declares 4 slots; `driver-substats` contains 11 stat choices with grade-specific value/percent flags and icon URLs. Each page references all three shape artworks (`/images/drivers/gold|purple|blue/...`) and ten shared driver-stat icons. The UI can show the identical roll pool once while retaining the source's `amount_stats: 4`.
- Diagnostic attempt error: the PowerShell `python` command was not recognized, so the offline JSON probe did not run. Discover the configured local Python runtime or another available interpreter before retrying; do not repeat the same command unchanged.
- The follow-up probe used the configured Python path and succeeded with escaped JSON output. The first checked patch did not match the current findings order; a follow-up replacement had an incorrect exact-context precondition, so neither attempt changed files. Corrected the match text before applying this update.
- Schema reconciliation: the driver pool contains 11 options, not 10; the source marks `amount_stats: 4`, and both main-stat curves have exactly 21 entries for +0…+20. The first S-grade horizontal Ⅱ shape maps to `type_id=shard_double_1`, `type_geometry=EquipmentGeometry_Hen2`, and `ownGridNum=2`. Its other quality pages supply the matching quality-specific data.
- The linked mechanism explainer is reachable through direct PowerShell download even though the web reader repeatedly timed out. Saved its complete HTML response (HTTP 200) to `data/mysqil/driver-blocks/raw/mechanism-guide.html` for preservation and offline extraction.
- The explainer adds narrative sections absent from the 36 stat pages: what driver blocks do, model specialization, the cassette-vs-driver affix system, output substat priorities, acquisition/farming, and shape handling. It states each block has fixed ATK+HP main stats and four random substats from 11; blocks are not rerolled, and type/shape compatibility is for completing cassette model combinations. It also cites TapTap, 游侠网, NGA, and 巴哈姆特 as source communities and says in-game values are authoritative; keep this caveat if the article is surfaced in the app.
- Direct download resolved the earlier mechanism-page discovery errors; those were web-reader limitations, not page absence. The downloader should be extended to refresh and manifest this guide snapshot and any guide-specific images so future imports reproduce the full capture.
- The repeatable downloader now reads the guide snapshot (or refreshes it with `-Refresh`), records its URL/status/path in `roster.json`, and scans guide images with the item pages. The guide page has no `/images/drivers/` or `/images/ui/` assets of its own, so no extra guide-only image files were needed.
- `scripts/import_mysqil_driver_blocks.py` successfully imported the corpus into `driver_blocks.json` and `.js`: 12 shape records grouped from 36 pages and 46 SHA-256-verified source images. Its offline reconciliation validates all 36 page titles/quality labels, 12 consistent shape groups, 3 tier artworks per shape, two 21-entry main-stat curves per page, 4 slots, 11 random-stat options, and all six mechanism-guide sections. No source field was invented.

### Integration and final validation
- Added the local driver-block bundle to the existing encyclopedia navigation. Its view supports model filters, search across names/shapes/grades/stats, per-shape gold/purple/blue selection, source-page links, +0…+20 fixed-stat inspection, all 11 random-stat options, and the imported mechanism guide.
- The range control updates its value cells in place so pointer/keyboard interaction keeps the same input element while dragging. Search/filter changes keep the selected detail and highlighted card in sync.
- Added responsive catalog/guide styles and documented the refresh/import workflow, storage paths, author, CC BY-NC-SA 4.0 license, and guide-source caveat. The bundle and raw source remain attributed to Matsuzaka Yuki; the guide says in-game values are authoritative.
- Final offline import reports 12 shapes, 36 quality pages, 46 unique local images, and `guide=imported`. The importer checks source-page labels and IDs, all three image variants, local asset SHA-256 values, 21 levels × 2 main stats, 4 random slots, 11 stat choices, six guide sections, and JSON/JS generation.
- Static checks passed: `node --check app.js`, `node --check data/knowledge/encyclopedia/driver_blocks.js`, PowerShell parser for the downloader, and `git diff --check`. Browser interaction/responsive verification was not run.
- Source and integration scope contains only Phase 11 code, data, documentation, and canonical plan updates. The feature commit `aeb5179` was pushed to `origin/main`; a follow-on planning record captures the post-push confirmation.

## User-facing Apple-style Experience

### Product boundary
- 当前项目已有的角色管理和图鉴页面属于维护者工作台；用户端不应默认看到草稿、审核、编辑表单、来源快照或导入状态。
- 用户端首屏任务是选择角色并快速回答三个问题：这个角色做什么、怎么装、要准备什么。默认入口因此切换为用户端，管理端变成显式的右上角入口。

### Apple-style decisions
- 使用平台系统字体和动态 `clamp()` 字号，标题采用紧 tracking、正文使用更宽松 leading。
- 顶部导航是轻量半透明材质，配合 `backdrop-filter`；大 hero 使用深色渐变承托角色立绘，避免内容卡片堆叠。
- 角色选择使用横向滚动 rail，角色卡保持明确的 active 状态；内容区使用分段控件承载概览、技能、配装和养成，逐层暴露复杂信息。
- 交互反馈使用 pointer/press 状态和短促 transform，不在输入路径加入延迟；用户端仅使用可逆、可打断的普通过渡，不引入不可控的循环动效。
- 加入 reduced-motion、reduced-transparency 和 prefers-contrast 处理；移动端把 hero、卡片和分段控件压缩为单列，并检查横向溢出风险。

### Changed files
- `index.html`：新增用户端结构、用户/管理端模式入口，默认 `body.user-mode`。
- `styles.css`：新增用户端 Apple 风格视觉、材质、响应式和可访问性规则。
- `app.js`：新增用户端数据渲染、角色搜索/切换、四个分段、材料汇总和模式切换。
- `README.md`：更新默认入口和用户端/管理端边界。

### Verification limitation
- 静态检查通过；本轮没有声称浏览器交互或响应式验证通过。Python Playwright 未安装，备用 CUA helper 受到 Windows sandbox 初始化错误影响。
## User cultivation skill-target correction

- 用户端的养成目标不是单一的角色等级问题：角色突破和每项技能升级应分别表达，材料汇总需要同时读取两层目标。
- `userSkillTargets` 以 `角色 ID + 技能索引` 为键保存选择；未做过选择时回退到该技能的最高可用等级，因此不会改变原有默认结果。
- 用户端使用 `data-user-skill-target` 事件委托处理选择变化，直接重新渲染当前养成面板；固定只有一个可用等级的技能节点保持禁用。
- 已完成静态验证；浏览器操作与响应式验证仍未执行，原因与上一轮相同：本地 Playwright 未安装，CUA helper 受 Windows sandbox 初始化错误影响。
## User screenshot — carousel direction

- 截图显示当前角色列表是单向横向 rail：活动卡片在左侧突出，右侧继续露出角色卡，右上角有总数统计；这让用户能浏览，但不够像“选择当前角色”的核心控件。
- 轮盘化的核心应是空间层级而不是自动播放：当前角色居中并突出，左右各露出相邻角色，左右按钮负责明确的上/下一个，首尾通过索引取模循环。
- 交互决策：不做自动旋转，避免用户阅读时被强行切换；支持左右按钮、点击相邻卡片和横向触摸/指针滑动。拖拽时 1:1 跟手，释放后按方向切换并回到稳定位置。
## Character carousel implementation

- 轮盘使用三段重复角色列表，逻辑游标初始位于中段；到达边界时先无动画换到等价副本，再继续做一个方向一致的位移动画，因此首尾不会出现长距离跳跃。
- 中心卡片通过 `is-active` 放大并提高不透明度，前后两张通过 `is-near` 保留空间层级；左右箭头、卡片点击和滑动统一调用 `userCarouselMove` / `userCarouselMoveTo`。
- Pointer Events 仅在轮盘 viewport 内捕获；`touch-action: pan-y` 将横向手势交给轮盘、保留页面纵向滚动。短拖会回到当前位置，超过位移/速度阈值才切换。
- 轮盘不自动旋转，符合用户阅读资料时的控制权和 Apple 风格的低干扰原则。

## Recovery error

- 本轮一次带 `Singleline` 的贪婪正则将 `app.js` 从 `applyCharacter` 后截断；已记录为错误，不再使用跨越函数边界的 `.+` 替换。恢复方式改为 Git 基线后半段追加 + 用户端函数追加，并用函数唯一性、入口接线和 `node --check` 复核。
- 一次批量验证调用因调用编排字符串解析失败，没有修改文件；随后拆成独立验证调用并成功完成，未重复失败调用。
## Carousel polish findings

- 轮盘居中必须按 flex 布局宽度计算，而不是按经过 `transform: scale(...)` 后的视觉包围盒计算；后者会让中心卡片逐步向一侧偏移。
- 轮盘的状态序号属于辅助信息，不应在角色卡片附近重复展示；角色计数保留在搜索区，选择反馈由居中卡片和 hero 内容承担。
- 非当前卡片不需要用低透明度模拟景深；对资料型角色选择器来说，图片、角色名和定位文本应保持可读，层级可以通过轻微缩放、边框和阴影表达。
- 卡片点击使用 `data-user-character` 直接解析角色名称，再把游标放回重复轨道的中段副本；这样点击任意克隆卡都能稳定切换，不依赖点击位置是否恰好落在相邻卡片。
## User-facing navigation direction

- 当前用户端只有角色展示与角色分段资料；顶部“图鉴”按钮直接调用 `showEncyclopediaCategory("arc-drives")`，会移除 `body.user-mode` 并显示管理工作台，这是用户路径与权限边界混淆的根因。
- 用户端主导航应采用轻量胶囊式 segmented navigation：`角色`、`自动配队`、`弧盘`、`空幕`；管理端只保留一个低强调的显式入口，不与用户任务混在同一组导航里。
- 用户端导航切换应只控制 `userExperienceView` 内的 route panels；管理端 `showRoleManagement` 与 `showEncyclopediaCategory` 继续服务维护者侧，不能被用户端详情按钮复用。
- 当前角色知识包的 `scope.excluded` 明确写有“配队推荐”，因此自动配队首版应标记为基于本地角色定位的候选/规则结果，不能把它描述成已导入的官方阵容推荐。
## User-facing navigation initialization failure

- 用户截图中的“载入中”、空 Hero 和无响应顶部按钮由同一个启动错误造成，不是角色知识包缺失。
- showUserExperience() 在启动阶段调用 renderUserRouteView("characters")；该函数读取 userRouteLabels。当 userRouteLabels 仍处于 const 的暂时性死区时，后续用户端绑定和渲染全部被跳过。
- 修复原则：所有被启动调用直接读取的用户端路由常量，必须在启动调用之前初始化；函数声明虽会提升，const 不会提升。
- Chrome CDP 回归确认：初始用户端角色计数为 25/25、Hero 为真红；四个顶部路线均可切换；点击角色卡可切换为白藏；无运行时异常。
## Team solver and catalog synchronization findings

- 参考站点的一键配队页把“拥有角色池”作为输入，把“显式点击生成”作为计算边界，输出 4 人队，并把定位结构与属性环合作为可读的结果依据；这比单纯按稀有度或元素随机取三人更接近用户真正要解决的问题。
- 本项目的角色知识 scope 明确排除配队推荐，所以本地实现采用规则候选而不是抄录外站阵容；后续若导入经过核验的阵容模板，可在同一候选层增加模板优先级。
- 管理端和用户端原本已经共享三份全局 catalog：arcDriveCatalog、skyCurtainCatalog、driverBlockCatalog。用户端不一致的主要原因是展示层只取了部分字段，且没有驱动块路线；修复方向是补齐用户层展示，不建立第二份数据。
- 当前对照结果：弧盘 51 件、空幕 12 套、驱动块 12 种形状，管理端计数和用户端 catalog 完全一致。

## Phase 17 — Automatic Team Builder 1.0 and Source Lineup Discovery

- 用户明确要求现在实现自动配队 1.0，并把 2.0 所需的更深层阵容/强度数据留到后续；若会火攻略站的已录入阵容可稳定公开获取，先本地保存，未来需要可在管理端维护。
- 参考页 `https://sifangshangxia.cn/team.html` 显示 22 名角色，按属性分组；可勾选持有角色、设置共鸣等级和专属弧盘、按顺序锁定最多两个主C，并在候选线路间选择。选中第一队后可使用剩余角色配第二队；不足四人时提示缺人。
- 参考页声明其配队来自已录入的成型阵容及同位置替换；共鸣/专属弧盘只影响方案排序，不改变队伍强度；站点声称计算在本地完成且不上传。后续实现应把站点已核实阵容与本站规则候选分开。
- 当前本地 `app.js` 的 `userTeamBuildPlan` 只返回单个最高分组合；`userTeamGenerated` 仅被赋值但不参与生成条件；角色池初始化为全选，清空后可通过 `userTeamAvailableNames` 回退为全部本地角色。该行为与用户意图和参考交互不符。
- 本地角色知识 scope 明确排除配队推荐；角色数为 25，而参考站角色数为 22。导入前需要匹配角色身份/别名并记录未匹配项，不能把本地规则结果包装成参考站模板。
- 角色知识中 `recommended.weapon` 代表已收录的推荐武器字段，不能在没有来源证明时直接当作“专属弧盘”；缺少记录时应显示未知/未收录。
- 参考站的阵容数据和页面许可条款尚未确认。先调查实际公开页面和数据资源；若只可访问人工渲染结果或无法确认复用条件，保留最小必要的来源记录，不把不确定数据合并进默认公开图鉴。
- 参考页初始角色清单为 22 人；点击“我全都有”后各选中角色卡片出现 0–6 共鸣按钮、专属弧盘开关和“必须用TA”按钮。页面把“零”视作每人固定拥有，因此全选后 UI 显示 23 / 22；角色池导入时需单独表达默认角色，不直接照搬计数。
- 当前可见页面没有阵容下载/导出按钮；页面说明阵容来自已录入成型阵容及同位置替换，但这些记录尚未从 UI 生成结果或静态资源中提取，也未判断能否批量下载。
- 浏览器验证：全选角色、锁定真红并点生成后，页面显示真红的 3 条成型阵容线路；选定一条后还能基于剩余角色展示第二队的多条线路。阵容详情还含定位/反应、队伍操作、共鸣觉醒、专属弧盘和同位替代等区块，证明至少一部分阵容数据可从公开 UI 读到。总阵容数量和批量提取入口仍未知。
- 浏览器拒绝了 `view-source:` URL（仅允许 HTTP/HTTPS 页面导航），并要求不得以其他浏览器、命令或协议绕过取得源码。后续只通过正常公开 UI 或站点本身提供的下载/导出查看阵容；不请求原始页面脚本或隐藏接口。
- 两个“必须用TA”按真红、小吱顺序选中后，参考页生成第一队时把小吱也放进真红队，第二队却改为残虹，并没有保证第二个锁定主C进入第二队。本站 1.0 应用“锁定即占位”的明确约束：第一主C必须进入第一队、第二主C必须进入第二队，且两队成员互斥。
- 通过全选角色、一次锁定一个主C、使用网页正式“生成”交互观察到 10 个主C入口；9 个入口公开展示了 27 条四人候选（真红3、小吱3、娜娜莉3、薄荷2、白藏3、残虹4、安魂曲3、海月3、卡厄斯3）。黑羽没有单独的“以黑羽为首发”的来源阵容组，页面只显示其可替换进残虹队的可见结果。此批是用户可见 UI 结果，不是原始数据库下载；完整性以 UI 实际展示为界。
- 当前没有在页面找到结构化阵容导出，页面所见的导出是阵容图。批量保存的原始源码路径不可用，数据须标明从公开 UI 观察整理、来源许可未披露、仅供当前本地项目评估，不声称完整复制源站数据库。

## Phase 17 implementation outcome — Automatic Team Builder 1.0

- data/knowledge/team_templates.json is the canonical local catalog for the 27 lineup choices visible through the guide site's public UI. It maps all members to stable local character IDs, preserves source order and team labels, and reserves separate editorial status/tags/notes fields for the later management phase.
- data/knowledge/team_templates.js is generated from the JSON by scripts/build_team_templates_bundle.py; index.html loads that bundle before app.js.
- The public page exposed image export but no structured lineup export. The source license was not displayed. Catalog metadata records the source URL, capture date and method, unknown license, observed scope, and incomplete coverage. No hidden source code or API was retrieved.
- The user roster now starts empty, supports selecting all or clearing the pool, and stores owned characters, ordered main-C locks, resonance 0–6, signature-arc ownership, team count, and preference in browser localStorage only.
- Main-C investment inputs are available on locked cores; other owned characters can expand the same controls. The signature-arc checkbox records the user's self-report without inventing an arc name. Resonance and signature-arc ownership affect candidate ranking only.
- The solver prioritizes eligible visible guide-site lineups and fills remaining candidate slots with clearly labeled local rule candidates. It displays up to three choices per team, can plan one or two teams, and blocks the first team's members from the second team. A second locked core is excluded from team one and required in team two.
- Phase 18 remains the planned admin workflow for reviewing and editing these records. Browser interaction and responsive visual review were not run in this implementation pass.

## 2026-09-30 — Startup regression found from user screenshot

- The screenshot's page shell, empty Hero, “载入中” count, and admin topbar match the static initial HTML, indicating that `app.js` did not finish startup.
- The Phase 17 `app.js` diff shows the single-element selector helper `const $ = ...` was accidentally removed. Execution then fails at `const toast = $("#toast")` with `ReferenceError: $ is not defined`, skipping all later rendering and event binding. Restored the helper before `$$`.
- The team route also read an undeclared `userTeamTeamCount`; initialized it from saved `teamCount`, defaulting to one team.
- Added `scripts/smoke_check_app.js` to check HTML script order/existence, script syntax, non-empty local catalogs, valid template character IDs, and the required startup declarations. It passes with 25 characters and 27 templates.
- Browser automation could not run: CUA rejected the local `file://` URL and explicitly prohibited using a local server, another browser surface, or indirect execution to bypass that restriction. This turn verifies source/data contracts only; it does not claim actual click behavior is confirmed.

## 2026-09-30 — Recommended cassette acquisition consistency

- Character recommendations read acquisition from separate character snapshots, while both encyclopedia views read the shared sky curtain catalog. Of 20 character recommendations, 19 snapshots had empty acquisition despite valid catalog IDs.
- Added `resolveRecommendedCassette` to associate acquisition by stable cassette ID. Catalog acquisition takes precedence; unlisted cassettes retain their character-source acquisition. Character-specific recommended affixes and terminal data are preserved without mutating source snapshots.
- Connected the resolver to admin cassette details, user character overview, and user build recommendations. Diabolos now uses the catalog's dark-element Rabbit Hole acquisition in those views.
- Pure data regression checks passed for all 20 character recommendations, canonical precedence, fallback, absent recommendations, and snapshot/affix preservation. Script parsing and diff checks passed; no browser interaction test was performed.

## 2026-09-30 — Automatic main-C selection

- Requiring a core lock prevented users who do not know their main DPS from receiving recommendations. Main-C locks now express optional preferences.
- `userTeamRecommendPlans` compares plans across eligible owned cores when unlocked, prioritizing complete teams, visible source templates, and local scores. Manual locks constrain that same entry point.
- Candidate labels identify their recommended core; selected result titles follow that candidate. Second-team recommendations use the first team's selected member set as an exclusion constraint.
- A sole owned main-C now produces an honest partial candidate. Empty and support-only pools produce no invented main-C. UI instructions no longer ask users to lock a core before generation.
- Pure solver regression passed for unlocked cores, every full-roster first candidate's non-overlapping second team, ordered manual locks, preferences, partial/empty/support-only pools, and rule fallback. Browser interaction was not run.

## 2026-09-30 — Character icon identity mix-up

- The imported 真红 character record contains 11 related-character icon assets in its `assets` array. The generic `.find(type === "character_icon")` selected the first entry, `bohe-icon.webp`, instead of 真红's own `zhenhong-icon.webp`.
- 薄荷's own icon and the mistakenly selected 真红 icon share the same SHA-256 because they are the same file content; the correct 真红 icon was already present in the local bundle.
- Added `findCharacterIcon`, which prefers the filename `<character ID>-icon.*` and only falls back to the first icon when no identity-matched asset exists.
- The smoke check now verifies every character picks its own icon, each file exists, and selected icon image hashes are unique. All 25 character icons passed; app syntax and `git diff --check` passed.

## Visual guide manager
Existing 27 templates are static JSON/JS with editorial metadata. No backend exists. Browser-local overrides plus export/import will share the exact solver catalog, preserve source attribution, and avoid claiming repository writes. Pointer dragging and click/keyboard slot selection provide direct manipulation and accessibility.

### Guide manager verified behavior
- Browser saves overlay the original catalog and are consumed by userTeamBuildPlans; disabling/deleting removes guide eligibility while retaining the local-rule fallback.
- Imports validate all entries before committing, preventing partial updates. Original source bundles are not modified.
- Real browser drag must dispatch mouseMoved with button=left as well as buttons=1; missing button state caused test-only lost capture.
- Chrome tests confirmed four slots, persistence after page reload and no overflow at 390px. Desktop/mobile screenshot review completed.
## 2026-10-01 — Esper cycles discovery
Source: https://wiki.mysqil.com/esper-cycles. Eight native details sections contain six two-attribute reactions and two derived three-attribute reactions, system introduction, and character-specific passives. All article text is server-rendered. Footer credits Matsuzaka Yuki under CC BY-NC-SA 4.0. Inspect parser coverage rather than copying only visible collapsed summaries.

### Esper-cycle full coverage audit
Imported exactly 8 sections: 5/3/4/0/3/3/2/0 passives in source order, totaling 20. All 26 main-article images downloaded. Whitespace-normalized source main text equals reconstructed structured content character-for-character; numeric tokens are retained in coverage metadata. Source contains zero tables. The six two-attribute rules and two three-attribute rules now feed both the reference and user team solver. Existing character IDs from the source are preserved even if source naming differs from local records.

### Reaction view final checks
Independent checker reconstructs all main-body text from structured fields and compares against separately stripped/decoded source HTML, including every numeric token. Offline image hashes and browser decoding cover all 26 unique assets. Both reference view and solver use esper_cycles.js; no second reaction-name/attribute list remains in app.js.
Source defines effect conditions beyond attribute membership; the UI retains those conditions in full rather than describing every attribute combination as an automatically triggered in-battle event.