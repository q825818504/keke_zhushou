# 可可助手 · 角色知识管理后台

零依赖的本地角色知识管理页面。角色资料从 `data/knowledge/characters/` 加载，目前包含真红和 Mysqil 页面中列出的其他 24 名角色。选择角色可查看已导入的基础资料、技能、属性成长、觉醒、共鸣、养成材料、推荐装备及本地图片；源页面未提供的数据会标记待补充。

## 打开页面

直接打开 [index.html](./index.html)。页面由 `index.html`、`styles.css`、`app.js` 和本地知识数据组成，不需要构建步骤。

## 更新角色来源数据

更新来源需要 PowerShell 7 和 Python 3.10+（仅使用标准库）。从项目目录运行：

```powershell
.\scripts\download_mysqil_sources.ps1
python .\scripts\import_mysqil_characters.py --offline
```

下载器会缓存角色页、相关武器/卡带页和图片；离线导入器从快照生成对应的角色 JSON 与 `other_characters.js`。如果要重新抓取已有来源，可在下载脚本后加 `-Refresh`，并在重新生成时去掉 `--offline`（仅在导入器可直连来源站的环境中使用）。

## 数据与来源

- 结构化角色知识：`data/knowledge/characters/<角色 ID>.json`
- 原始页面快照与清单：`data/mysqil/`
- 角色本地图片：`data/resources/characters/<角色 ID>/`
- 来源及许可说明：[`data/mysqil/ATTRIBUTION.md`](./data/mysqil/ATTRIBUTION.md)
- 唯一项目计划与进度：`.planning/2026-09-28-cocoa-assistant-ui-overhaul/`

来源站 [Mysqil · 环世全鉴](https://wiki.mysqil.com/) 为社区维护的非官方资料，页面注明 CC BY-NC-SA 4.0。导入记录保留来源链接和人工核验状态；商业或公开再分发前需确认许可兼容。配队推荐不进入标准化角色数据。
