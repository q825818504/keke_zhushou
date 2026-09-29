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
