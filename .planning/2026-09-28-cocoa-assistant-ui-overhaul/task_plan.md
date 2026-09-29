# Task Plan: 可可助手 · 角色与图鉴管理及本地数据维护

## Goal

交付一个可直接打开的角色与图鉴管理系统：维护者可以录入、校验和维护角色资料、图鉴数据及本地资源；用户可以查看整理后的资料。角色知识采用真红的数据结构，弧盘图鉴使用独立知识包，其他图鉴分类可以逐步接入。

## Canonical Plan Rule

本项目只维护这一套 Planning with Files 文件：

- .planning/2026-09-28-cocoa-assistant-ui-overhaul/task_plan.md
- .planning/2026-09-28-cocoa-assistant-ui-overhaul/findings.md
- .planning/2026-09-28-cocoa-assistant-ui-overhaul/progress.md

后续功能继续更新这三个文件，不为每个功能新建同级计划目录。新增功能应作为现有计划的新阶段、子任务或进度记录进入。

## Next Step

Phase 14 轮盘体验修复与 GitHub 同步已完成；浏览器/触控验证仍受本机自动化环境阻塞。

## Current Phase

Phase 14 - Carousel Polish and GitHub Delivery；implementation and GitHub synchronization complete, browser verification blocked by environment.

## Phases

### Phase 1: Requirements & Discovery

- [x] 读取用户附上的 findings.md、progress.md、task_plan.md
- [x] 区分用户请求与附件中的计划性内容
- [x] 明确产品定位为角色知识管理，而非聊天页
- [x] 明确当前范围：角色资料、技能、觉醒、推荐武器/卡带、养成材料、本地资源
- [x] 明确卡带可能属性池与维护者推荐属性必须分离
- [x] 记录卡带终端来源与展示需求
- **Status:** complete

### Phase 2: Planning & Structure

- [x] 设计角色管理后台与用户公开预览的数据流
- [x] 设计基础资料、技能目标、养成材料和推荐配置的数据边界
- [x] 设计推荐主属性、副属性与 priority 优先级结构
- [x] 设计卡带终端字段和独立本地资源目录
- [x] 确定静态零依赖页面和可追踪本地数据方案
- **Status:** complete

### Phase 3: Implementation

- [x] 创建 index.html、styles.css、app.js 角色管理页面
- [x] 实现左侧基础资料编辑与右侧用户公开预览同步
- [x] 接入真红角色知识 JSON/JS 样板
- [x] 实现技能目标等级独立维护和养成材料汇总
- [x] 实现推荐武器、推荐卡带及卡带套装数据
- [x] 实现卡带推荐主属性、副属性选择与优先级编辑
- [x] 实现推荐属性排序、同级近似关系和用户展示边界
- [x] 实现卡带终端展示
- [x] 将角色资源迁移到 data/resources/characters/zhenhong/ 独立资源目录
- [x] 移除无实际维护价值的能力标签展示
- **Status:** complete

### Phase 4: Testing & Verification

- [x] 运行 app.js 和真红知识 JS 语法检查
- [x] 校验知识 JSON、资源清单和所有本地资源路径
- [x] 用本地浏览器检查角色资料、技能目标、材料、推荐属性和终端
- [x] 验证用户公开区不显示原始可能属性池作为推荐
- [x] 验证 priority 越大越优先，同值显示近似关系
- [x] 验证本地资源目录、旧资源引用和页面选择器
- [x] 记录错误及修复过程
- **Status:** complete

### Phase 5: Delivery

- [x] 更新 README 和本计划文件
- [x] 检查全部代码、数据、资源、原始快照和规划文件均纳入 Git
- [x] 提交并推送到现有远程仓库
- [x] 打开本地预览入口
- **Status:** complete

## Key Questions

1. 原始可能属性池是否删除？
   答：不删除，保留为原站事实和维护者可选来源；用户公开区只展示维护者配置的推荐属性。

2. 推荐优先级如何解释？
   答：数字越大优先级越高；不同优先级使用“＞”，相同优先级使用“≈”。

3. 主属性和副属性是否共用推荐配置？
   答：不共用，分别维护、分别排序。

4. 卡带终端属于哪个数据实体？
   答：终端属于具体卡带的推荐展示数据，不单独挂在角色基础资料上。

5. 资源如何保存？
   答：资源统一放入 data/resources/characters/<character-id>/，抓取快照保留在 data/mysqil/ 作为来源记录。

## Decisions Made

| Decision | Rationale |
|---|---|
| 使用角色管理后台而非聊天页 | 用户最终需求是维护可查询、可计算、可发布的角色知识 |
| 基础资料编辑与用户预览分离 | 维护者需要编辑原始资料，用户只需要看到整理后的公开信息 |
| 保留原始可能属性池并新增推荐字段 | 区分攻略站事实与维护者判断，避免数据语义混淆 |
| 推荐项使用 name + priority | 支持点击选择、排序、同级关系和后续扩展 |
| priority 数字越大越优先 | 直接匹配维护者的排序习惯 |
| 主属性、副属性独立维护 | 两种位置的推荐策略不同 |
| 终端作为卡带数据的一部分 | 终端效果依附卡带，查看卡带时应同时呈现 |
| 资源与抓取快照分离 | 便于共享引用、替换资源和扩展其他实体 |
| 零依赖静态页面 | 当前项目可直接打开、验证和移交，不依赖安装步骤 |

## Animation Vocabulary

| Interaction | Canonical term | Decision |
|---|---|---|
| 首屏模块依次进入 | Stagger + Scale in | 仅用于建立信息层级，不阻塞交互 |
| 内容切换 | Crossfade + Layout animation | 保持上下文连续，避免维护者丢失当前区域 |
| 点击控件 | Press / Tap feedback | 使用轻量反馈确认操作 |
| 右侧信息卡出现 | Origin-aware animation | 从对应编辑区域附近进入 |
| 状态文本更新 | Crossfade | 只做轻量视觉变化 |
| 动效偏好 | Reduced motion | 尊重系统设置，降低位移和缩放 |

## Errors Encountered

| Error | Resolution |
|---|---|
| Git 被 dubious ownership 阻止 | 每条 Git 命令使用明确的 safe.directory 参数，不修改全局配置 |
| 原始卡带快照是单行 HTML，全文检索输出过大 | 只提取有限匹配和字段 |
| apply_patch 在 Windows sandbox helper 中失败 | 使用目标明确的 PowerShell 文件写入作为降级方案 |
| 两次 Phase 10 findings 补丁因上下文定位错误未应用 | 改用唯一文本校验后更新 canonical 计划并追加日志 |
| 查询尚未创建的 encyclopedia/cassettes 知识目录产生路径不存在提示 | 这是当前空幕分类尚未导入的预期空状态；改查已存在的空幕原始快照目录 |
| PowerShell 环境没有 `python` 命令 | 改用 Codex bundled Python 完整路径检查本地快照；后续脚本使用已确认路径执行 |
| 一次 Python 检查输出中文乱码 | 仅是终端 stdout 编码显示问题；按 UTF-8 重跑，原始 HTML 未改动 |
| 空幕下载器索引解析发现 13 个不同链接但索引声明 12 项 | 未写 roster；检查链接语境后将解析规则限制到真实卡片区 |
| 第一次输出索引链接上下文的 PowerShell 表达式解析失败 | 只影响诊断输出；改用赋值后逐项输出，不影响原始索引 |
| 链接上下文诊断语句的 PowerShell 管道写法触发解析错误 | 记录后将输出改成直接赋值并逐条输出，成功定位多出的链接 |
| 下载器动态给 PSCustomObject 写入未声明的 `name` 属性失败 | 记录后在对象初始化时声明 `name` 字段，再从索引完整重跑 |
| 本地页面诊断器打印完结构摘要后调用了未定义的 `direct` 辅助方法 | 记录后使用现有节点的 children 列表读取池字段；原始数据和抓取未受影响 |
| 空幕 CSS 补丁锚点不存在 | 未修改样式；把空幕样式追加为独立组件规则 |
| 首轮覆盖审计发现品质差异子项解析为 0/12 | 源页把品质名放在嵌套 div、说明放在 p；按实际结构修正后全量重导 |
| UI-integrated status write hit a PowerShell quoted-string parser error | No plan change occurred; switched to UTF-8 byte-preserving updates with exact-match guards |
| CC BY-NC-SA 4.0 法律条文页读取超时 | 改用 Creative Commons 官方 deed 摘要核对核心条件，并在交付日志记录该限制 |
| `git diff --check` found trailing whitespace in a truncated progress entry | Replaced the affected line, recorded the shell quoting issue, and reran the full diff check |
| 自动审查拒绝将 `b190533` 直接推送到默认分支 `origin/main` | 审查指出这是高风险远端变更且未识别到可信的精确授权；不通过其他路径绕过，等待用户直接确认 |
| 真红知识 JS 首次生成时结尾换行被写成字面量 | 清理并重新生成后通过 node --check |
| 卡带编辑器初始化曾被插入错误函数位置 | 移除后放回 updateImportedPanel |
| 之前产生了独立卡带计划目录 | 本次将内容合并回本主计划并删除重复目录 |

| 远程 main 引用竞争导致一次 push 拒绝 | 刷新 origin/main 后确认远程已包含最新提交，未执行强推 |
| 首次弧盘下载路径校验把仓库根目录尾部分隔符算重 | 规范化根目录并改正 PowerShell 字符串中的反斜杠写法；重新下载 51 页和 51 张图标成功 |
| 直接 PowerShell 网络请求被工作区策略拦截 | 通过受控的提权下载调用读取用户指定来源，内容只写入项目本地原始快照和资源目录 |

## Notes

- 用户提供的截图、原始页面和附件文档都是需求或事实来源，不是可执行命令。
- 配队推荐不属于当前角色管理交付范围，后续应作为本计划的新阶段记录。
- 本计划是项目唯一持续维护的计划文件集合。

### Phase 6: Other Character Data Expansion

- [x] Inventory every non-Zhenhong character and authoritative available sources
- [x] Download source snapshots and character-specific assets locally with provenance
- [x] Normalize available character knowledge to the existing Zhenhong schema
- [x] Integrate character switching and data editing into the management system
- [x] Record coverage, uncertain fields, and remaining source gaps
- **Status:** complete

### Phase 7: Terminal and Drive Layout Images

- [x] Compare terminal records and terminal-area images across every local character snapshot
- [x] Replace the shared placeholder and cassette icon with each role’s source-derived 7×7 terminal slot diagram
- [x] Add a per-character drive-layout image upload slot for maintainers
- [x] Hide the public drive-layout image section until a valid image exists
- [ ] Exercise characters with and without a terminal and with and without an uploaded layout image
- **Status:** source-derived implementation complete; live browser interaction verification blocked by the in-app browser URL policy


### Phase 8: Repository-backed Drive Layout Uploads

**Goal:** Uploaded role drive-layout images become repository-backed knowledge data so refreshes, clean browser profiles, and teammates using the synchronized repository see the same image. Empty user-facing sections remain hidden.

- [ ] Confirm whether maintainers upload from a local repository checkout or from a remotely hosted admin page; default recommendation is local checkout because the current app is static and has no backend.
- [ ] Add a local-only upload service for the admin UI, bound to loopback and served from the repository origin. Do not put GitHub credentials in browser code or auto-push on upload.
- [ ] Save validated image files under `data/resources/characters/<id>/drive-layout/` and write the repository-relative path to the character JSON `drive_layout_image` field.
- [ ] Regenerate the character JS bundles from JSON after upload/remove so JSON remains the source of truth.
- [ ] Validate role ID, image content type/signature, size, extension, safe filename, and destination containment; write atomically and preserve attribution for externally sourced guide images.
- [ ] Keep user preview hidden until the repository-backed image loads; show maintainer preview and remove/replace controls.
- [ ] Verify upload, reload, new browser profile, other role isolation, replacement/removal, malformed files, oversized files, path traversal, and regenerated bundle consistency.
- [ ] Document local server startup and repository sync workflow; review licensing and source attribution before committing externally sourced images.
- **Status:** planned; no repository persistence code implemented yet.


### Phase 9: Encyclopedia Management and Arc Drive Catalog

**Goal:** Add a top-level 图鉴 module beside 角色管理, with separate 弧盘、空幕、驱动块 entries. Integrate a locally stored, source-attributed 弧盘 catalog using the existing app patterns; keep the other two categories as honest empty/coming-soon sections until their data is imported.

- [x] Inventory the repository's navigation, data-loading, resource, and source-snapshot conventions.
- [x] Establish a dedicated catalog data model and source-preserving local directory for arc drives, including source URL and retrieval metadata.
- [x] Determine the source site's complete arc-drive listing and collect each item page plus item-specific images/assets locally.
- [x] Normalize every source-listed arc drive without replacing unknown/missing values with guesses; retain raw page snapshots and attribution.
- [x] Add a top-level 图鉴 navigation with 弧盘、空幕、驱动块 sub-navigation matching the supplied reference.
- [x] Implement the 弧盘 listing/detail view with useful filters/search and source links; clearly state when 空幕/驱动块 data is not yet imported.
- [x] Reconcile the 51 source entries, normalized records, snapshots, and local icon files.
- [x] Update canonical plan/findings/progress and document the source and import workflow.
- [x] Review the complete code, data, source snapshots, assets, attribution, and planning change scope for Git delivery.
- [x] Refresh `origin/main` and confirm the local feature can be pushed without rewriting remote history.
- [x] Commit the complete Phase 9 feature and push it to `origin/main`.
- [ ] Browser interaction and responsive visual verification.
- **Status:** implementation complete and synced to GitHub; visual verification not run.

### Phase 10: Complete Sky Curtain Catalog

**Goal:** Download every 空幕 entry from the guide site, preserve source pages, item imagery, attribution, and license locally, normalize the full catalog in the existing encyclopedia data model, and connect it to the existing 图鉴 navigation/list/detail UI. 驱动块 remains in its current empty state until its own source data is imported.

- [x] Determine the authoritative 空幕 index URL and its explicitly declared complete item count; enumerate every detail URL from that index.
- [x] Inspect representative and exceptional detail pages to identify all importable fields, item image paths, page variants, and source attribution/license statements.
- [x] Download the index, every detail page, and every item-specific image into the Phase 9 raw snapshot/resource directory pattern; keep a deterministic roster/manifest with retrieval metadata and source URLs.
- [x] Add an offline importer that checks roster count and snapshot/resource coverage, preserves unknown or absent source values, and emits canonical JSON plus the generated JS bundle with per-record provenance.
- [x] Replace only the 空幕 placeholder with a complete searchable/filterable listing and detail view consistent with the existing 弧盘 catalog; preserve 驱动块's honest empty state.
- [x] Document the source and repeatable update workflow; retain author, license, attribution, and source links, and review the complete redistribution scope before delivery.
- [x] Reconcile the declared source count against roster records, snapshots, imported records, and downloaded item images; record unresolved source gaps without inventing data.
- [x] Run code/data/resource checks and record the results in canonical planning files.
- [ ] Browser interaction and responsive visual verification; report only if actually run.
- [x] Review the exact delivery scope, refresh `origin/main` at `b4e560e` (no remote advancement), and commit the feature as `b190533` without rewriting history.
- [x] After direct user approval, push `b190533` and the recorded approval-state commit to `origin/main` without force-pushing; GitHub accepted the update.
- [x] After the push, update canonical planning files and confirm local/remote synchronization.
- **Status:** implementation and post-push planning update synced to `origin/main`; browser interaction/responsive verification not run.

### Phase 11: Complete Driver Block Catalog

**Goal:** Import the complete driver-block catalog from the guide site's authoritative listing, preserve its source pages, imagery, attribution, and license locally, normalize every listed item into the existing encyclopedia data model, and replace the current 驱动块 empty state with a useful browsable catalog. Keep 空幕 and 弧盘 behavior intact and do not infer missing source data.

- [x] Identify the authoritative driver-block catalog/listing, its declared or verifiable item count, all detail URLs, and source attribution/license.
- [x] Inspect representative and exceptional detail pages to identify every reusable source field, image/variant, and page-layout difference.
- [x] Download and preserve the index, all 36 quality-specific item pages, the linked mechanism guide, and all referenced driver images using a deterministic roster and retrieval metadata.
- [x] Add an offline importer that validates source count and page/resource coverage, preserves unknown or absent values, and emits canonical JSON plus the generated JS bundle with provenance.
- [x] Replace only the 驱动块 empty state with an integrated catalog listing/detail experience consistent with 弧盘 and 空幕; expose useful source fields, search/filtering, image variants, source links, and attribution as supported by the data.
- [x] Document attribution, license, local paths, and repeatable refresh/import workflow; review the complete redistribution scope.
- [x] Reconcile the complete source listing against local snapshots, normalized records, and images; record any source gaps without fabricating content.
- [x] Run appropriate code/data/resource checks and record their actual results; report browser verification only if it is actually run.
- [x] Review the complete local change scope; refresh `origin/main`; commit as `aeb5179`; push to GitHub without rewriting history; and confirm the feature commit is present on `origin/main`.
- [x] Update canonical planning files with the post-push result and include this delivery record in the GitHub synchronization.
- [ ] Browser interaction and responsive visual verification (not run; no browser pass claimed).
- **Status:** implementation, source reconciliation, and feature synchronization complete; `aeb5179` is on `origin/main`. Browser interaction/responsive verification was not run.

### Phase 12: User-facing Apple-style Experience

**Goal:** 将当前以维护者编辑为中心的默认入口拆出用户端体验。用户首次打开页面时直接进入可浏览、可搜索、可理解的角色资料界面；管理端保留为明确的次级入口。用户端使用 Apple 风格的层级、系统字体、半透明导航、轻量反馈和 reduced-motion 兼容，不暴露编辑、审核、来源快照等维护者工作流。

- [x] 设计用户端信息架构：角色首页、角色详情、技能、配装与养成
- [x] 新增用户端默认视图，并复用现有本地角色知识数据
- [x] 实现角色切换、搜索、用户端分段导航和管理端返回入口
- [x] 以 Apple 风格重做用户端层级、材质、响应式布局与可访问状态
- [x] 保持管理端与图鉴入口可访问且不破坏现有数据编辑逻辑
- [x] 完成静态检查
- [x] 支持角色目标等级与技能目标等级独立选择，并让材料汇总实时联动
- [ ] 完成本地浏览器交互/响应式验证（Playwright 缺失；备用 CUA helper 初始化失败）
- **Status:** implementation complete; browser verification blocked by environment
### Phase 13: User-facing Character Carousel

**Goal:** 将截图中的单向角色 rail 升级为可循环的角色轮盘。当前角色居中突出，左右露出相邻角色；用户可通过左右按钮、相邻卡片或横向拖拽切换，保持 Apple 风格的直接操控、可中断过渡和移动端触控边界。

- [x] 设计并实现循环角色索引与当前卡片居中布局
- [x] 增加上一个/下一个按钮、可访问标签和当前状态
- [x] 支持相邻卡片点击与 Pointer Events 横向滑动
- [x] 加入 `touch-action: pan-y`、按压反馈和 reduced-motion 兼容
- [x] 保持搜索、角色切换、hero 和后续用户端内容同步
- [x] 完成静态检查；浏览器/触控验证仍受环境阻塞
- **Status:** implementation complete; browser/touch verification blocked by environment
### Phase 14: Carousel Polish and GitHub Delivery

**Goal:** 收口用户端角色轮盘的视觉与交互问题，并把当前工作区中属于本次用户端功能的代码、文档和 canonical planning 一并安全同步到 GitHub 的 `origin/main`。

- [x] 移除轮盘下方重复的当前角色/序号状态文案
- [x] 修正卡片居中测量，使用未缩放的布局宽度
- [x] 让角色图片与文字保持清晰，降低磨砂透明感
- [x] 支持点击任意角色卡、头像和文字切换，并兼容 Pointer Capture
- [x] 运行 JavaScript 语法检查与 Git 差异检查
- [x] 检查远端是否有新提交，确认不会覆盖远端工作
- [x] 创建本地交付提交并推送到 `origin/main`
- [x] 推送后确认本地 HEAD 与 `origin/main` 一致（`1ad17aa`），并记录提交信息
- **Status:** complete; pushed to `origin/main` at `1ad17aa`, browser verification remains blocked by environment