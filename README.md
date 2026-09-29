# 可可助手 · 角色与图鉴管理

零依赖的本地角色与图鉴管理页面。角色资料从 `data/knowledge/characters/` 加载，目前包含真红和 Mysqil 页面中列出的其他 24 名角色；图鉴接入完整的 51 件弧盘、12 套空幕和 12 种驱动块形状。选择角色可查看已导入的基础资料、技能、属性成长、觉醒、共鸣、养成材料、推荐装备及本地图片；弧盘可按稀有度、类型和关键字筛选，并查看成长属性与各调弧等级效果；空幕可按套装类别、属性和关键字筛选，并查看套装效果、可能词条和三种品质图片；驱动块可按型号和关键字筛选，比较金/紫/蓝三档、查看 +0 至 +20 主属性成长、随机词条池与机制说明。源页面未提供的数据会标记待补充。

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
