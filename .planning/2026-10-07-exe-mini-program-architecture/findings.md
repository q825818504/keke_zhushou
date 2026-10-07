# 架构调研发现

## 阶段10：404验收补充
- 编译归档只读提取确认：dist/windows旧管理EXE未包含characters/save，windows-updated新版包含该路由。旧EXE读取外部项目新UI，因此出现界面更新但服务API缺失的版本错配；本轮无助手进程/8765监听，不能直接证明用户截图时打开的具体文件。
- 上轮只完成真实EXE导航烟测、独立JS保存绑定和独立Python存储回归，未完成真实发行EXE点击保存端到端，明确是测试覆盖缺口。
- 增加ping capability和客户端兼容校验；旧后台不再发起404保存。失败保持脏状态是正确行为，不通过隐藏关闭提醒掩盖未写入。
- check_exe_save.py标记隔离工作副本，用真实EXE点击主词条灵伤5/副词条暴击率4并保存，随后新进程读取；两个报告均ok=true，noUnsavedAfterTest=true、JS错误为空。测试专用模式限制标记目录和smoke-report，不开放正常项目自动写入。
- 已在确认无运行进程后将旧windows入口替换为新版；两份管理EXE哈希一致，旧二进制另存pre-save-fix.exe，未删除项目资料或浏览器缓存。

## 阶段9实施
- 统一角色保存通过新characters/save接口原子写入basic/recommended，保留未知覆盖字段、其他角色和图片；独立保存推荐复用顶栏；阵容顶栏走现有表单和重复确认。
- 用户桌面UI仍使用独立内置纯用户模块；公共只读服务优先读取本机admin-workspace配置下已知知识JS与图片，不开放JSON源、管理脚本、Git接口；版本轮询后刷新并保留浏览器个人设置。
- 单角色项目保存成功后只清理该角色的legacy覆盖，其他未写入编辑保留；基础保存失败不会将角色编辑标成已保存。

## 2026-10-07 娜娜莉推荐优先级丢失诊断
- 顶栏 bindSave() 只保存基础资料：调用 saveCharacterBasics，不调用 CharacterRecommendations.save 或 persistCharacterRecommendations。词条编辑仅修改内存；独立“保存推荐”按钮才会持久化推荐。这与用户对“保存草稿”的理解不符，是保存范围缺陷。
- Node VM 抽取真实 bindSave 隔离复现：内存已有主属性优先级5、副属性4，点击顶栏保存后请求只有 basic，没有推荐持久化；不访问实际API、不修改真实资料。
- 本机 character_overrides.json 的 nanali 仅含 name/basic，无 recommended；原始 nanali.json 的主/副推荐均为空，重启回退到空默认，不是已保存推荐被 Git 覆盖的证据。
- origin = https://github.com/q825818504/keke_zhushou.git，main 最新提交7755f47（2026-10-07 16:39:15 +0800）；只读 ls-remote 验证远端main与本地HEAD相同。提交含character_overrides JSON/JS和team_overrides JSON/team_templates JS，不含娜娜莉推荐属性。
- 两份项目写前备份均没有 nanali.recommended；只检查专属desktop-admin的Local Storage leveldb中推荐键存在性（1个可读文件、0命中），未输出或更改浏览器资料。尚未找到可恢复的这次优先级配置，不能凭空恢复。
- 用户 EXE 固定打包旧快照，build/desktop/public的character_overrides仍为空；未实现在线资料更新，重启用户EXE/同步私有Git不刷新其内置资料。
- 修复建议：顶栏保存同时保存推荐、按真正完成的持久化范围反馈成功、失败保留编辑；同步面板明确仓库/分支/提交与待保存编辑；隔离覆盖重启读取及发布快照验收。用户本轮询问原因，未擅自修改应用/角色数据或推送Git。

## Windows 桌面实施补充
- 本机 Windows PowerShell 5.1 有效策略 Restricted，PowerShell 7 为 RemoteSigned；Python 3.13.14、Node 24.18、npm 12 和 WebView2 154 已安装。无需修改执行策略。
- 采用 pywebview 独立 Windows 窗口与 PyInstaller 单文件发行，复用界面内容，桌面布局使用清晰侧栏与紧凑工具栏；不是全套原生控件重写。
- 用户发行资源由 HTML 提取、Acorn 顶层声明依赖闭包与图片引用白名单生成：125 项用户声明、25 名角色、815 张引用图像；不复制管理 DOM、桥接/阵容管理脚本、原始快照、Git 或项目全目录。
- 管理程序读写选定外部工作副本，公共用户程序只提供只读资源服务；两者资料与程序维护边界分开。
- 官方 API 核实：pywebview.start 支持独立 storage_path 与 private_mode；Windows 使用 WebView2，PyInstaller 可封装窗口及所需 DLL。https://pywebview.flowrl.com/api/ ，https://pywebview.flowrl.com/guide/freezing.html 。
- 源码窗口 QA 中管理 API 的公开 window/Path 属性触发递归扫描，改为私有字段后验证通过；关闭回调改用已缓存脏状态避免 UI 线程内同步脚本求值。
- 运行成品需要 WebView2，不需要外部 Python/Node；当前尚无在线更新地址、签名或安装器，首版为离线单文件预览发行。

## 用户已确认
- 当前阶段是公共数据展示，不做玩家账号、库存或跨端个人资料同步。
- Windows EXE 断网可用，但只能显示断网前获取/安装的旧资料；联网时再拿新版本。
- 管理端是本人跨电脑维护的本地程序，通过私有 GitHub 仓库同步，不需要在线网页登录管理。
- 管理源仓库应保持私有；用户端只获取公共图鉴和攻略。
- 未来如接入游戏官方 API，是按需读取，不是个人数据云同步；驱动快读取先限 Windows EXE。
- 接受静态 HTTPS 公共资料发布，但希望先以私有 GitHub 为基础，暂不考虑付费云服务。

## 仓库/应用已知基线
- 工作区：`D:/keke_zhushou`，分支 `main`。
- 本轮开始前已推送 `220fc9c`；本地 `main` 与 `origin/main` 一致。
- 当前项目是静态 Web 入口（`index.html`、`app.js` 等）；公共资料由 JSON/JS 文件组成。
- `app.js` 使用浏览器 `localStorage` 保存部分用户端配置；部分自定义图像使用 IndexedDB，回退时使用 localStorage。
- 历史 NTE 研究 `artifacts/` 仍未跟踪；不属于本架构评估发布源，不移动、不提交。

## 本轮代码盘点
- 根目录未发现 `AGENTS.md`、`package.json`、Electron/Tauri 配置或现成 Web bundler；README 说明当前直接打开 `index.html`，无需构建。
- `index.html` 同时包含用户导航与管理入口（含 `#userAdminButton`），并直接 script-load 本地角色/图鉴/攻略 JS 包。用户版若“不含管理端”，应从发行构建中剔除入口和管理模块，不能只用 CSS 隐藏按钮。
- `app.js` 是用户端和管理端共用的主要脚本；源码检索未发现运行时 `fetch()` 数据更新链路。现状公共数据随本地文件打包，不是从远端动态同步。
- 多类用户/编辑状态保存在浏览器 `localStorage`；自定义驱动摆放图主要存 IndexedDB。README 明确攻略阵容仅保存在当前浏览器，可通过 JSON 导出/导入；管理页保存本身不会修改仓库文件。
- 因而 EXE 化不仅是加一层窗口壳：还需明确数据更新通道、存储目录/迁移、管理工作副本同步及发行包排除规则。
- 基线盘点时尚未运行构建、测试或浏览器交互；随后已进入阶段 6 并实施本地管理数据写回。

## GitHub 官方资料（已核实）
- GitHub 推荐优先考虑 GitHub App；单页网页应用/用户设备上的公共客户端无法保密客户端密钥，不应把个人访问令牌或 App 私钥嵌入应用。在线网页登录管理需要可信的 token 处理路径；本地 Git 同步可以由 Git 客户端处理授权。
  - [GitHub OAuth app best practices](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/best-practices-for-creating-an-oauth-app)
  - [Keeping API credentials secure](https://docs.github.com/en/rest/authentication/keeping-your-api-credentials-secure)
- GitHub Pages 发布结果公开可访问，即使源仓库为私有；私有仓库使用 Pages 有套餐限制。
  - [Creating a GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)

## 微信官方资料访问状态
- 已定位官方网络能力页：[Mini Program Network](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html)。网页抓取和桌面浏览器辅助工具无法展开正文；确定发布主机前需重新核实服务域名、备案、TLS、请求限制等当前条款。
- 已定位官方登录页：[Mini Program Login](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/login.html) 与 [code2Session](https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/login/auth.code2Session.html)。小程序身份登录与游戏账号/API 登录是不同身份体系。
- 本轮检索继续以官方页面为准；未读取的搜索摘要不视作政策结论。

## 初步架构约束（待评估）
- 私有 GitHub 可作为角色/图鉴/攻略与管理程序的版本化源。
- 用户端不能持有私有仓库令牌；须将私有源与公开只读发布物分开。
- 无在线托管时，资料随客户端发布，但内容更新会受客户端发布/审核节奏约束。
- 独立静态发布目标可能避免自建数据库/VPS；能否满足小程序网络配置要求需先查官方规则和开发者账号状态。
- EXE 程序更新与资料更新应分开评估：前者走安装包/发行流程，后者走数据版本和本地缓存。

## 待核实
- 当前 `localStorage` 依赖及迁移到 Windows WebView/EXE 的数据目录。
- 单管理员场景下，管理端通过本地 Git 凭据拉取/提交；快进拉取按路径比较，重叠时拒绝，不强制覆盖。
- 用户资料包体积、图像托管、缓存失效与回滚。
- 小程序分包/包体、域名、隐私、备案和主体要求的最新官方口径。
- Windows 运行时选型需结合当前代码依赖和驱动快读取能力，不提前定 Electron/Tauri 等方案。

## 官方文档补充核查（2026-10-07）
- GitHub Pages 的官方文档说明：免费个人/组织计划下 Pages 源仓库需要公开；页面本身默认公开，即使源仓库私有（私有发布能力受计划限制）。因此适合的零后端候选是“私有源仓库 + 独立、仅含获准公开资料的发布仓库/目录”，而不是把私有主仓库直接开放给客户端。公开资料仓库需要严格白名单生成，不能复制整个源仓库。
  - [Creating a GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)
  - [Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- Electron 官方资料支持将 HTML/CSS/JS 与运行时封装为 Windows 可分发应用，并有 autoUpdater；官方建议签名发行包。可用性好、共享当前前端容易，但运行时体积通常高于系统 WebView 路线。签名与自动更新会带来额外发行配置，不建议当作首版前置。
  - [Electron distribution overview](https://www.electronjs.org/docs/latest/tutorial/distribution-overview)
  - [Electron application packaging](https://www.electronjs.org/docs/latest/tutorial/application-distribution/)
  - [Electron updating applications](https://www.electronjs.org/docs/latest/tutorial/updates)
- Tauri 官方 Windows 安装文档显示其使用 WebView2；可以选择捆绑运行时以应对机器未安装/离线环境，但需要引入 Rust/Tauri 工具链。是否比 Electron 更适合应通过小型打包与本地能力验证，而不是仅按包体大小决定。
  - [Tauri Windows installer](https://v2.tauri.app/distribute/windows-installer/)
- 微信官方网络、登录与 `code2Session` 页面均已定位，但当前 web 抓取失败，桌面浏览器 CUA 初始化亦失败。没有将网络域名、备案、隐私、包体、分包、审核等内容写成已核实结论；需使用开发者工具和账号在实施前验证。
  - [Mini Program Network](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html)
  - [Mini Program Login](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/login.html)
  - [code2Session](https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/login/auth.code2Session.html)

## 推荐的数据/发布边界
- 私有主仓库存放唯一权威源数据、管理端源代码、来源快照/许可信息和构建脚本；多电脑维护用本机 Git 凭据走 pull/commit/push。当前 README 显示管理阵容保存到浏览器存储，并不能自动写入工作区文件，故必须先做写回/导出确认与Git同步闭环。
- 用户 EXE 与小程序只获取公共数据快照。JSON 清单包含数据版本、最低客户端兼容版本、资源列表和哈希。客户端只在全部文件下载并验证成功后切换到新快照，保留上一版；超时/断网/哈希不符时继续使用已安装或上次成功的资料。
- EXE首版可随安装包带完整静态知识包，先人工下载安装程序更新；等数据静态发布目标和校验流程稳定后再启用“资料独立更新”。小程序默认按同一数据schema但独立界面适配；若网络域名/主体要求不满足，就只能随小程序版本发布资料并经历平台发布流程。
- Mysqil 数据遵循当前仓库记录的 CC BY-NC-SA 4.0 署名和相同方式共享义务；对外发行前检查商业使用边界以及每项资源的来源许可，不能因为托管免费就默认可再分发。
- Windows 框架建议暂不锁定：Electron 倾向最少改变前端/JS并简化桥接，代价是包体与签名发行；Tauri 倾向较小壳并能提供原生能力边界，代价是引入 Rust/WebView2 与额外工具链。先用驱动快读取的真实技术接口做 POC 再定。

## 管理端持久化现状（实现阶段补充）
- `bindSave()` 中的“保存草稿”目前只更新标签和 toast，没有序列化或写盘；基础资料表单会影响预览状态，但刷新后不构成可靠保存。
- 角色推荐（弧盘、卡带及推荐词条）覆盖保存在 `localStorage` 的 `keke-role-recommendations-v2`；默认知识仍来自 `data/knowledge/characters/*.json` 生成的浏览器知识包。
- 攻略阵容的编辑/删除覆盖在 `localStorage` 的 `keke-guide-lineups-v1`，通过 overlay 避免修改来源阵容；阵容页当前提示“保存至当前浏览器”。
- 驱动摆放图保存在 IndexedDB `keke-drive-layouts`；不支持时走 localStorage data URL 回退。当前文件注释明确提示不会同步 GitHub。
- `keke-user-team-v1` 是用户自己的持有角色、偏好主C、共鸣/专属弧盘与队伍数量，应继续留作本机用户设置，不能写入公共知识目录或 Git 同步。
- 因此不能仅增加 Git 按钮：至少需处理角色基础资料、推荐配置/词条、攻略阵容、摆放图片四类管理资料，并为旧浏览器存储提供可确认的迁移路径。建议同步桥只接受明确的文件/字段白名单。
- 风险：角色 JSON 由 `import_mysqil_characters.py` 从来源快照生成；若手工覆盖后重新导入会不会覆盖维护者编辑，需要继续核对生成器并设计分离的 override 层或合并方式。

## 阶段 6 实施结果（2026-10-07）
- 管理员从 `scripts/start_admin.ps1` 启动 loopback 服务，默认固定在 `127.0.0.1:8765`，避免随机端口导致浏览器本地设置每次都落入新来源；服务不暴露到局域网，不携带 GitHub token。
- 角色基础资料与推荐（含词条优先级）使用 `data/knowledge/character_overrides.json` + 生成包 `character_overrides.js`；来源导入角色 JSON 不被直接覆盖。
- 攻略阵容使用 `team_overrides.json` 覆盖原始 `team_templates.json`；构建后的 `team_templates.js` 合并展示，保持来源目录清单不变。
- 驱动摆放图可写入角色资源目录；覆盖 JSON、JS bundle 和图像在单次文件事务中更新，变更前的文件另存到 `%LOCALAPPDATA%/KekeAssistant/repo-write-backups/`。
- 从旧 `file://` 页面可导出管理数据并在本地服务导入。导入合并当前浏览器维护数据与备份，重复编号优先所选备份；源备份与旧来源数据保留，只有成功写入后才清理已迁移的当前浏览器管理覆盖/摆放图缓存。持有角色、共鸣及个人偏好不进入迁移包或 Git。
- Git 面板只暂存管理资料白名单与驱动摆放图；提交说明由用户确认按钮发起；凭据使用本机 Git Credential Manager。拉取仅允许 fast-forward，先比较本地/远端改动路径，重叠时停止，不执行 reset/force。
- 已通过现有 JavaScript smoke/自动配队/异能环合检查、隔离临时目录的服务端写入与备份测试，以及本地临时 bare remote 的快进冲突和白名单提交测试；没有对真实 GitHub 执行 fetch、commit 或 push。
- 未完成的验收：Playwright 模块在当前 Python 环境不存在，备用 CUA 运行时连续重置；需用户本机启动页面确认可视 UI、导出旧浏览器数据，并使用自己的 Git 凭据验证首次同步。
