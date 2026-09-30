# 可可助手 · 角色资料与养成指南

零依赖的本地角色资料与图鉴页面。页面默认进入面向用户的 Apple 风格角色指南：可以搜索角色、浏览基础定位、技能、推荐配装和养成材料；通过右上角“进入管理端”可切回维护者编辑工作台。角色资料从 `data/knowledge/characters/` 加载，目前包含真红和 Mysqil 页面中列出的其他 24 名角色；图鉴接入完整的 51 件弧盘、12 套空幕和 12 种驱动块形状。源页面未提供的数据会标记待补充。

## 用户端与管理端

默认打开的是用户端，适合查角色和做养成规划；维护者点击右上角“进入管理端”后，可使用原有的角色资料编辑、来源快照、审核状态和图鉴维护能力。用户端不会展示草稿、审核、编辑表单和原始快照入口。

## 打开页面

直接打开 [index.html](./index.html)。页面由 `index.html`、`styles.css`、`app.js` 和本地知识数据组成，不需要构建步骤。

## 更新角色来源数据

更新来源需要 PowerShell 7 和 Python 3.10+（仅使用标准库）。从项目目录运行：

```powershell
.\scripts\download_mysqil_sources.ps1
python .\scripts\import_mysqil_characters.py --offline
```

下载器会缓存角色页、相关武器/卡带页和图片；离线导入器从快照生成对应的角色 JSON 与 `other_characters.js`。如果要重新抓取已有来源，可在下载脚本后加 `-Refresh`，并在重新生成时去掉 `--offline`（仅在导入器可直连来源站的环境中使用）。

## 更新弧盘来源数据

在项目目录使用 PowerShell 7 和 Python 3.10+ 运行：

```powershell
.\scripts\download_mysqil_weapons.ps1 -Refresh
python .\scripts\import_mysqil_weapons.py
```

下载器按来源站弧盘目录校验 51 项清单，保存目录页、每件详情页和独立本地图标；导入器将等级成长曲线及 R1–R5 调弧效果生成到图鉴知识包。日常增量下载可省略 `-Refresh`。

## 更新空幕来源数据

在项目目录使用 PowerShell 7 和 Python 3.10+ 运行：

```powershell
.\scripts\download_mysqil_cassettes.ps1 -Refresh
python .\scripts\import_mysqil_cassettes.py
```

下载器按来源站空幕目录校验 12 套清单，保存目录页、每套详情页和金/紫/蓝三种品质图片；离线导入器从本地快照生成 `sky_curtains.json` 与 `sky_curtains.js`。日常增量下载可省略 `-Refresh`。

## 更新驱动块来源数据

在项目目录使用 PowerShell 7 和 Python 3.10+ 运行：

```powershell
.\scripts\download_mysqil_driver_blocks.ps1 -Refresh
python .\scripts\import_mysqil_driver_blocks.py
```

下载器核对 Mysqil 驱动块目录中的 12 种形状、36 个品质详情页及其引用图片，并保存驱动块机制说明页；离线导入器从本地快照生成 `driver_blocks.json` 与 `driver_blocks.js`，每种形状包含金/紫/蓝品质、+0 至 +20 主属性成长、11 种候选副词条和来源记录。日常增量下载可省略 `-Refresh`。

## 自动配队 1.0

用户端自动配队只需选择持有角色即可生成，助手会比较可用主C及其阵容并推荐主C与队友。也可按顺序手动锁定最多两名主C作为偏好，填写每名角色共鸣 0–6 与专属弧盘持有标记、查看多套候选，以及从第一队剩余角色生成第二队。持有与养成输入保存在当前浏览器，不会上传。共鸣与专属弧盘只作为候选排序偏好，不代表伤害模拟。

可见的攻略站阵容单独保存在 data/knowledge/team_templates.json，浏览器读取由 team_templates.js 提供。更新 JSON 后运行：
python .\scripts\build_team_templates_bundle.py

当前保存了会火攻略站公开界面实际展示的 27 条候选、覆盖 9 个主C组；站点没有结构化阵容导出，数据来自可见界面的人工整理，不能视为完整阵容库。来源未显示复用许可，发布或再分发前需复核授权。记录还预留了本地审核和编辑字段，后续可由管理端维护。

运行 `node .\scripts\smoke_check_app.js` 可检查页面脚本引用、JavaScript 语法、本地角色与图鉴数据、阵容角色 ID、角色头像映射及其重复文件，以及角色推荐与空幕图鉴获取方式的一致性。该检查不替代浏览器交互回归。

运行 `node .\scripts\check_team_recommendations.js` 可回归自动推荐主C、手动锁定、两队角色互斥、偏好选择、空池与不足人数，以及本地规则候选回退。

## 数据与来源

- 结构化角色知识：`data/knowledge/characters/<角色 ID>.json`
- 结构化弧盘图鉴：`data/knowledge/encyclopedia/arc_drives.json` 与 `arc_drives.js`
- 结构化空幕图鉴：`data/knowledge/encyclopedia/sky_curtains.json` 与 `sky_curtains.js`
- 结构化驱动块图鉴：`data/knowledge/encyclopedia/driver_blocks.json` 与 `driver_blocks.js`
- 原始页面快照与清单：`data/mysqil/`
- 空幕目录页、详情快照与清单：`data/mysqil/cassettes/`
- 驱动块目录页、36 个品质详情快照、机制说明与清单：`data/mysqil/driver-blocks/`
- 角色本地图片：`data/resources/characters/<角色 ID>/`
- 弧盘本地图标：`data/resources/encyclopedia/weapons/<弧盘 ID>/`
- 空幕品质图片：`data/resources/encyclopedia/cassettes/<套装 ID>/`
- 驱动块形状图和词条图标：`data/resources/encyclopedia/driver_blocks/site/`
- 来源及许可说明：[`data/mysqil/ATTRIBUTION.md`](./data/mysqil/ATTRIBUTION.md)
- 唯一项目计划与进度：`.planning/2026-09-28-cocoa-assistant-ui-overhaul/`

来源站 [Mysqil · 环世全鉴](https://wiki.mysqil.com/) 为社区维护的非官方资料，页面注明 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，并署名 Matsuzaka Yuki。原始 HTML 快照保留在本地，结构化图鉴记录说明了来源和规范化整理；分享导入或改编的资料时应保留署名与许可链接、说明修改，并遵守非商业和相同方式共享条件。配队推荐不进入标准化角色数据。

## 可视化攻略阵容管理
进入管理端后选择侧栏「攻略阵容」。从角色库拖入四个位置，或选中位置后点击角色；队内拖动会交换位置。选择主C、填写阵容名称与攻略说明，点击「保存阵容」即可纳入用户端攻略候选。已有阵容可搜索、编辑、复制、停用、删除及撤销删除。

保存使用当前浏览器的本地存储；不同浏览器或设备不会自动同步。可导出 JSON 备份并在另一浏览器导入。导入按阵容编号合并，校验失败不会部分写入。若要将导出内容发布到仓库，将导出的 team_templates.json 替换 data/knowledge/team_templates.json，再运行 scripts/build_team_templates_bundle.py 生成发布包。页面保存本身不会修改仓库文件。
## 反应体系 · 异能环合
管理端「反应体系」可浏览、搜索和按属性筛选全部 8 种环合及 20 条角色强化被动。用户端预览在所有管理端页面常驻；资料与配队使用同一份环合定义，属性组合表示可形成的反应，实际触发还需满足资料中的条件。

资料来源：[环世全鉴 · 异能环合](https://wiki.mysqil.com/esper-cycles)，作者 Matsuzaka Yuki，许可 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)。原始 HTML 保存在 data/mysqil/esper-cycles/raw/page.html，26 张正文图片及 SHA-256 校验清单保存在同目录 assets/ 和 roster.json。结构化资料及浏览器包位于 data/knowledge/esper_cycles.json 和 esper_cycles.js。本地版本调整展示与分类，保留来源文字、数值、角色强化条件与图片；派生资料按同一许可使用。

更新：运行 python scripts/import_mysqil_esper_cycles.py --refresh 下载并重建；无网络时运行不带参数的同一命令，从快照重建。导入器检查正文逐字覆盖、8 项清单、20 条被动和全部图片。运行 node scripts/check_esper_cycles.js 独立核对正文、全部数值、资源哈希和 JSON/JS 一致性。