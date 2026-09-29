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

Phase 9 图鉴与弧盘目录已完成本地实现；当前按本计划核对变更范围、刷新远端状态并提交推送至 GitHub。之后再继续处理 Phase 8 仓库持久化驱动摆放图上传。

## Current Phase

Phase 9 - Encyclopedia Management and Arc Drive Catalog；implementation complete, GitHub delivery in progress.

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
- [ ] Commit the complete Phase 9 feature and push it to `origin/main`.
- [ ] Browser interaction and responsive visual verification.
- **Status:** implementation complete; GitHub delivery in progress; visual verification not run.
