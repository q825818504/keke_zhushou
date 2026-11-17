# 用户端代码审计与优化记录（2026-11-15）

范围：`可可助手用户端` 全仓（根目录页面与业务模块、`desktop/` 桌面层）。目标：**只做不改变现有功能与界面表现的优化**，并用可复跑的差分证据证明「行为一致」。

## 一、审计方法与证据链

| 环节 | 做法 |
| --- | --- |
| 并行只读审计 | 四条独立线：`app.js`+`index.html`、业务模块 `.js`、`styles.css`、`desktop/` Python；各线按「位置 / 问题 / 证据 / 等价改法 / 收益」回报，不直接改码 |
| 黄金快照差分 | `_tmp/audit/golden.js` 固定 28 组输入（4 种角色池 × 2 种养成 × 锁定/未锁定），产出 8,357,241 字节的推荐结果快照；改造前后 **sha256 完全相同** |
| 真实浏览器 A/B | Playwright + Chromium，同一份数据、同一交互序列，比较**生成耗时**与 `#userTeamRoute` 的 `textContent` 是否逐字符相同 |
| HTTP 层 A/B | 同一 `config.json` 固定夹具，比较响应体字节、`Content-Type`/`Cache-Control`/`Content-Encoding`/`Content-Length`/状态码 |
| 既有检查回归 | `scripts/check_*` 11 项全绿；`desktop/check_*` 中原本为绿的项目改动前后同绿，原本为红的项目改动前后**同一处报错**（见第五节） |

## 二、已落地的改动

### 1. 自动配队：消除 762 条模板的重复深拷贝（收益最大）

**问题**：`teamGuideStore.all()` 每次调用都会 `filter + map(copy)`，`copy` 是 `JSON.parse(JSON.stringify(...))`，把 762 条维护阵容（2.32 MB）整体深拷贝一遍，实测 **3.0 ms/次**。而推荐链路在**一次点击**里就调用了上百次：

- `userTeamRankedMainCNames` 的 `sort` 比较器里调 2 次 → 27 人排名共 **167 次**；
- 第 2290 行的 `userTeamCanPin` 每人 1 次；
- `userTeamCollectPlans` 每个主 C 的默认参数里再 1 次。

112 个核心角色 × 反复调用叠加后，单队「生成候选」实测 **533 ms**，界面在此期间是冻结的。

**改动**：

| 位置 | 改动 |
| --- | --- |
| `app.js:87-118` | 新增 `teamTemplateRecords()` / `teamTemplateCoreCounts()` / `invalidateTeamTemplateCache()`；缓存键 = `store` 对象标识 + `store.revision()` |
| `team_manager.js:37,47` | store 增加 `revision()` 代数计数器，`commit()` 内自增；缓存失效不再依赖 `guide-lineups-changed` 是否真的派发到（测试桩/无监听者环境同样正确） |
| `app.js:2362-2370` | 主 C 排名的来源阵容计数改为预建 `Map<角色id, 条数>`，与原 `all().filter(...).length` 等价（同样不过滤 `active`） |
| `app.js:2321-2326` | `userTeamCanPin` 改为查同一张计数表 |
| `app.js:2453-2480` | `userTeamCollectPlans` 改为「先按启用 + 核心 id 廉价筛选，再为命中项解析成员名」，原实现是 762 条先 `map` 出数组再 `filter` |
| `app.js:2547-2585` | 双队组合：`cores.indexOf()` → 排名 `Map`；冲突检测由「每次 `filter` 新建数组」改为计数（仅在需要记录 `closestConflicts` 时才建数组）；成员 key 与投资分按 plan/角色预计算 |

**等价性**：黄金快照 28 组输出 **逐字节相同**（8,357,241 B，sha256 `6360fec3…`）；真实浏览器里 `#userTeamRoute` 文本 `sha256` 前后相同（单队 `0fbf8f6d…`、双队 `f258350f…`）；`check_team_recommendations` / `check_dual_team_recommendations.cjs` / `check_guide_manager` 全绿。

**收益（真实 Chromium，同一构建产物）**：

| 场景 | 改造前 | 改造后 |
| --- | --- | --- |
| 完整页（管理端，含 `team_manager.js`）单队生成 | 306 ms | **10 ms** |
| 完整页 双队生成 | 257 ms | **144 ms** |
| 用户包 单队生成 | 31 ms | **11 ms** |
| 用户包 双队生成 | 220 ms | **132 ms** |
| Node 纯逻辑 单队（`all()` 调用次数） | 533 ms（184 次） | **26 ms（1 次）** |

> 注：用户包里 `team_manager.js` 属禁止模块（`prepare_public.py` 会拦截），`window.teamGuideStore` 不存在，走 `teamTemplateKnowledge.teams` 回退——这条路径也已单独验证（结果一致、20 ms/10 ms），因此该优化对用户包与管理端都成立。

**残余风险**：缓存返回的是同一批记录对象，`plan.sourceRecord` 现在指向共享对象（原实现每次都是新副本）。已核对全部消费点只读（`app.js:2448-2449、2584-2585、2638、2656-2657`），无写入。将来若有人对 `sourceRecord` 赋值，需要重新评估。

### 2. `/public-config.js`：缓存 + gzip

**问题**：`desktop/runtime.py` 每次请求都 `load_config()`（解析 6.65 MiB 的 `config.json`）再 `json.dumps` 两遍，产出 **7.39 MiB** 脚本，且响应头固定 `Cache-Control: no-store`。实测 **76-78 ms CPU/次**，每次刷新都重来。

**改动**：`desktop/runtime.py:97-127` 增加按 `(st_mtime_ns, size)` 命中的 payload 缓存，并同时缓存一份 gzip 副本；`runtime.py:199-207` 仅当客户端声明 `Accept-Encoding: gzip` 时改发压缩体；`:224-227` 增补 `Content-Encoding` 与 `Vary`。

**等价性（HTTP 层 A/B）**：

- 不发 `Accept-Encoding`：状态 200、`Content-Type: application/javascript`、`Cache-Control: no-store`、**无** `Content-Encoding`、`Content-Length: 7744329`，响应体与改造前**逐字节相同**；
- 发 `Accept-Encoding: gzip`：`Content-Encoding: gzip`、`Content-Length: 457619`，`gzip.decompress` 后与原始字节**完全相同**；
- 真实 Chromium 端到端：页面加载 27 角色 / 762 阵容 / 10 个导航项正常，`pageerror` 0、`requestfailed` 0，`public-config` 实际传输 **0.44 MiB（gzip）**；
- 其他路径（`/index.html`、`/styles.css`、`/local-data-version`）仍为 identity，不受影响。

**收益**：首屏传输 **7.39 MiB → 0.44 MiB（约 17×）**，重复请求 CPU 从 78 ms 降到 0（`load_config` 调用次数 2 → 1）。

**残余风险**：缓存判据是 `(mtime_ns, size)`，理论上「同一 100 ns 内等长改写」会命中旧值；`stat` 失败时降级为不缓存（与旧行为一致）。缓存不跨进程。

### 3. 桌面层清理与 IO 收敛

| 位置 | 改动 | 证据 |
| --- | --- | --- |
| `desktop/installer_entry.py:100-131` | `install()` 正文包 `try`，失败时清掉 `.stage-*` 与 `download-*.zip` 后重抛 | 失败路径残留由 `[".stage-HEX/", ".stage-HEX/partial.bin", "download-HEX.zip"]` 变为 `[]`；成功路径 `installation.json`/`active-version.json`/文件树**逐字节相同** |
| `desktop/installer_entry.py:11` | 删除未使用的 `import time` | 全文件无 `time.` 引用 |
| `desktop/release_lifecycle.py:88-92` | `release-seen.json` 只解析一次 | 9 种文件状态 + `acknowledge` 前后输出 `diff` 为空 |
| `desktop/prerequisites.py:43-49` | 组件安装包 `finally` 删除 | 失败后残留 `['MicrosoftEdgeWebView2Setup.exe']` → `[]`，异常类型与文案不变 |
| `desktop/diagnostics.py:112-129` | 导出包按 mtime 只留最近 5 个（仅匹配 `可可助手诊断-*.zip`） | 7 次导出后剩 5 个、最新保留、用户自建文件不动 |

### 4. 业务模块索引化

| 位置 | 改动 | 差分证据 | 收益 |
| --- | --- | --- | --- |
| `role_build_standard.js:426-451` | `load()` 循环前取一次 `roles()`，建 `roleIndexById` / `roleIndexByKey` / `characterIndex`；用「两个首次命中位置取较小者」保持原 `find` 的语义 | 4 种库存（空/单件/混合/1009 件）`snapshot` **逐字节相同** | `roles()` 调用 674 → 1 次 |
| `role_build.js:90-103` | `equippedFor` 改为 `owner` 分桶索引（按 items 引用 + 长度失效） | 4 种库存 + 2 条失效路径（换新数组、原地 push）下 `equippedFor`/`assessment` 输出全等 | 单次 paint `1.602 ms → 0.003 ms` |
| `drive_layout_solver.js:139-171` | 盘面几何（`index` + 每个形状的落子表）按 `cells` 签名缓存，`placementsFor` 只做剩余量过滤与 `choices` 拼装 | 1080 组「盘面 × 形状数 × limit × maxNodes」中 870 组逐字节一致、210 组两侧同样抛错同文案；plan piece 键仍为 `{id,shape_id,row,column}`，改写返回值不影响缓存 | `placementsFor` 0.225 → 0.027 ms（≈8×），`generateCandidates` 1.29 → 1.08 ms |
| `inventory_management.js:166-183` | 套装名表提到模块级；目录归一化索引按 `items` 引用缓存 | 17 种行（数字/字符串/大小写/无套装/含书名号等）digest 逐字节相同 | 200 张卡带渲染 0.313 → 0.251 ms |

## 三、明确不建议改动的部分（安全边界，保持原样）

这些点「看着能简化、实际会开洞」或会改变外部可见行为，本次一律不动，仅登记：

1. `update_protocol.verify_envelope`（Ed25519 + `product/schema` 校验）、`checked_url` 域名白名单与重定向拦截、`download_package` 的 size+sha256 双校验——发行信任链核心。
2. `release_lifecycle` 删除前的四重守卫（`recognized_install` / 指针指向 / 符号链接 / junction）。
3. `runtime.do_GET` 的 `Host` 精确匹配（防 DNS rebinding）与 `do_POST` 的 `Origin` + `X-Keke-Inventory` 双校验。
4. `guarded()` 在 `--startup-check` 失败时仍返回 0（门禁语义，改动会改变失败表现）。
5. `safe_extract` 的字节上限、`highest-version.json` 容错、云端更新说明是否延后、`allow_reuse_address` ——都涉及更新/启动时序，需要单独一轮带真机演练。
6. `os.replace(staging → folder)` 与 `active-version.json` 的写入顺序（原子安装切换）。

## 四、未落地、建议排期的优化（按收益/风险排序）

### 值得做

1. **用户包裁掉管理端 CSS**：`prepare_public.py:48` 原样复制 197.6 KB 的 `styles.css`，其中约 **128.7 KB** 只服务管理端/浏览器预览（`body:not(.desktop-mode)` 整族 19.1 KB、`user-cassette-*`/`rb-candidate-*`/`publish-*`/`evidence-*` 等成簇死区约 31 KB）。按「编译后 app.js + index.html 用户段」做白名单裁剪即可，用户端视觉零变化。
2. **`[hidden]` 冗余与死声明清理**：`styles.css:211` 的 `[hidden]{display:none !important}` 已覆盖 7 处同类规则；另有 6 组「后段完全覆盖前段」的死声明（如 `.user-team-controls` 8 次定义里 5 次恒死）。纯 CSS 清理，零视觉风险。
3. **用户端搜索框焦点丢失（缺陷，非优化）**：`整块 innerHTML` 重建时把搜索框本身也换掉了，`#userArcDriveSearch`/`#userSkyCurtainSearch`/`#userDriverBlockSearch` 只能输入 1 个字符（`renderUserTeamRoute:2650-2700` 有完整的焦点/滚动恢复逻辑，这三处没有）。修法：外壳只渲染一次、只重建列表与详情；或重建后用 `requestAnimationFrame` 复焦并 `setSelectionRange`。
4. **轮播拖动去掉强制同步布局**：`userCarouselSetPosition` 每次 `pointermove` 都读 `firstCard.offsetWidth` + `getComputedStyle(track).gap`（`app.js:1986-2000`）。改为 `requestAnimationFrame` 合帧 + 指标缓存（`resize` 时失效），最终位置不变。
5. **`roleLocks()` 每次 paint 读 27 次 `localStorage`**（`role_build.js:307`）：改模块级缓存 + `storage` 事件失效。
6. **`cassette_scoring.js` 的 `recommendationMap` / `legalSubAffixes` WeakMap 缓存**：千件库存省 10-15 ms，键必须用对象引用（不能按 id，避免跨账号/卡带串味）。
7. **启动期隐藏面板预渲染**（仅影响完整页）：`initArcDriveCatalog` 等把 53+12+12 张卡片渲染进 `hidden` 容器，加 `renderCharacterCards` 的 27 张卡，首屏约 105 个无谓图片请求；改为首次进入该视图时再渲染。
8. **`src=""` 兜底**：资源路径非法时 `importedAssetUrl` 返回 `""`，模板仍写出 `<img src="">`，会对当前文档地址多发一次请求（`app.js:289、294、617、626、851、1156、1282`）。
9. **`styles.css` 只有 2 处图片缺固有尺寸**（`.drive-layout-public img`、`.vision-evidence`），补 `aspect-ratio` 可消除 CLS。

### 需要产品/数据确认

- `styles.css:202-205` 的 `element-fire/violet/teal/blue/light` 从未生效：`app.js:1237` 用 `className = "element-badge"` 整串覆盖，元素徽标恒为紫色。
- `styles.css:1186/1271/1296/1334` 的窄屏导航宽度策略互相覆盖，620px 下按 `64vw` 而非 `100vw-112px`。
- 三处百分数口径不同（DLL 存分数、OCR 存百分点、`adapter==='nte-native-v1'` 决定是否 ×100），权威口径需回查 `desktop/inventory/equipment.py`。
- `role_build_standard.js:91` 的 `Object.entries(SOURCE_SHAPES).find(...)` 实为属性查表，`record.shape` 若为 `constructor`/`toString` 会取到原型链函数；建议改 `Object.hasOwn`。
- `team_manager.js:367/374/385` 的 `records.find(...)` 可能返回 `undefined`（另一窗口已删除该记录时）→ 直接抛 `Cannot read properties of undefined`。

## 五、验证清单（本次实跑）

```
node scripts/smoke_check_app.js                        PASS  27 角色 / 762 模板 / 827 资源
node scripts/check_cassette_scoring.js                 PASS
node scripts/check_loadout_optimizer.js                PASS
node scripts/check_terminal_puzzle.cjs                 PASS
node scripts/check_drive_layout_solver.cjs             PASS
node scripts/check_team_recommendations.js             PASS
node scripts/check_dual_team_recommendations.cjs       PASS
node scripts/check_unified_save.js                     PASS
node scripts/check_guide_manager.js                    PASS
node scripts/check_native_assembly_planner.cjs         PASS
node scripts/check_esper_cycles.js                     PASS
node scripts/check_role_build_standard_browser.cjs     PASS  真实 Chromium
node scripts/check_inventory_browser.cjs               PASS  真实 Chromium
node desktop/compile_user.cjs <out>                    PASS  143 声明，无管理端依赖
prepare_public(app_version='1.8', app_revision=0)      PASS  851 文件 / 44 资源
py_compile desktop/{runtime,installer_entry,release_lifecycle,prerequisites,diagnostics}.py  OK
.venv-ocr python desktop/check_v1_2.py                 PASS  6 tests
.venv-ocr python desktop/check_v1_3.py                 PASS  7 tests
.venv-ocr python desktop/check_release_history.py      PASS  3 tests
.venv-ocr python desktop/check_v1_7_diagnostics.py     PASS  4 tests
```

**改动前后同为红（与本次改动无关，已定位）**：

| 检查 | 原因 |
| --- | --- |
| `desktop/check_local_data.py` | 断言 `POST /api/characters/save` 返回 405，而 `runtime.py` 在 `Origin` 校验处返回 403（全仓无 `send_error(405)`）——测试与实现口径过期 |
| `desktop/check_v1_1.py` | `from build_release import prepare`：`build_release` 属管理端仓，本仓拆分后不存在 |
| `scripts/check_dual_team_browser.cjs` | 断言「所有双队组合都存在角色冲突」，但维护阵容已增至 762 条，该场景现在存在 306 组可行双队——断言过期（用 HEAD 源码复跑，同样在此处失败） |
| `scripts/check_cassette_scoring_ui.js` / `check_terminal_browser.cjs` / `check_character_recommendations.js` | 模块解析（`playwright` 未装在根目录）或脚本内写死旧仓目录名 `keke_zhushou` |
| `scripts/check_native_assembly_browser.cjs` | 等待 `[data-equipment="inspect"]`，该按钮当前页面不渲染（用基线副本对比，两侧一致） |
| `scripts/check_role_build_refresh_browser.cjs` | `releaseNotesDialog` 遮挡点击导致 `TimeoutError`（改动前后同一报错） |

## 六、复跑审计脚本

差分与 A/B 脚本未进仓，留在 `D:\可可助手\_tmp\`：

- `_tmp/audit/golden.js`、`bench_rec.js`、`bench_nostore.js` —— 黄金快照与纯逻辑基准
- `_tmp/audit/hdr_ab.py` —— `/public-config.js` 的 HTTP 层 A/B（含 gzip 解码比对）
- `_tmp/audit/browser_dom_ab.js`、`browser_fullpage_ab.js` —— 真实浏览器耗时 + DOM 文本一致性
- `_tmp/mod/diff_01..04*.js` —— 四个模块的等价性差分
- `build/_audit_step2/` —— 桌面层 A/B 夹具（gitignored，可随时删除）
