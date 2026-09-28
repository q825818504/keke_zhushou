# Findings & Decisions

## Requirements

- 卡带攻略站的“主属性/副属性”目前表示可能出现的词条池；本系统需要把用户展示改为维护者配置的“推荐主属性”和“推荐副属性”。
- 维护者通过点击属性选项进行选择，并为每个选中属性填写优先级。
- 优先级数字越大越优先；例如暴击=2、暴伤=4，用户看到“暴伤＞暴击”；同优先级显示“暴伤≈暴击”。
- 卡带终端必须进入角色资料的卡带展示。
- 本地资源画廊独立保存到资源目录，便于后续其他实体快速引用。
- 这些功能完成后，需要规划文件完整、全项目文件和进度进入 Git，并推送到现有远程仓库。

## Research Findings

- 当前样板卡带为“失落光芒”，知识文件为 data/knowledge/characters/zhenhong.json，展示函数为 renderCassette，当前把 main_affix_pool / sub_affix_pool 直接渲染成“主属性池/副属性池”。
- 当前资源位于 data/mysqil/characters/zhenhong/assets/，资源引用由 importedAssetUrl 拼接角色抓取目录。
- 当前卡带原始快照为 data/mysqil/characters/zhenhong/raw/cassette-shiluo-guangmang.html；其中明确说明卡带是 1 个主属性 + 4 个副属性，并且词条不可洗练。快照还说明主/副词条是随机池，副词条优先级因角色定位而异，这正是“原始池”和“维护者推荐”必须分开的依据。
- 用户截图补充了卡带终端公开展示：标题为“终端”，示例效果为“[卡带] 属性”，每装配一个亚型驱动，使暴击伤害增加 16%，展示标签为“暴击伤害 +16%”。
- 原始快照中没有直接检索到“终端”字段，因此该字段暂按用户截图确认，并在数据来源中标记为用户补充。

## Technical Decisions

| Decision | Rationale |
|---|---|
| possible_affixes 仍保留原始随机池；新增 recommended_main_affixes 与 recommended_sub_affixes | 明确事实与维护者判断的边界 |
| 每项推荐属性结构为 { name, priority } | 既能表达选择，也能表达排序 |
| 用户文案由优先级排序生成，最大值在前；同值使用“≈”连接 | 直接满足用户示例并支持任意数量属性 |
| 资源统一复制/迁移到 data/resources/characters/zhenhong/ | 资源引用不再绑定抓取快照目录 |
| 终端结构放在 recommended.cassette.terminal | 终端是卡带的展示组成，而不是独立实体 |
| 维护者编辑区使用原始属性池作为可选项 | 避免手输造成词条名称漂移，同时允许未来扩展 |

## Issues Encountered

| Issue | Resolution |
|---|---|
| 项目当前没有安全目录 Git 配置 | 使用每条 Git 命令的 -c safe.directory=D:/keke_zhushou 参数 |
| 用户截图提供终端字段但本地快照未提供 | 标记为用户补充来源，不假装来自网页抓取 |

## Resources

- 本地角色知识：data/knowledge/characters/zhenhong.json
- 本地卡带快照：data/mysqil/characters/zhenhong/raw/cassette-shiluo-guangmang.html
- 来源卡带页面：https://wiki.mysqil.com/cassettes/shiluo-guangmang/

## Visual/Browser Findings

- 截图 1 的卡带区域显示的是一张卡带、2/4 件套效果和主/副属性词条池；系统需要把这两组池改成维护者推荐结果。
- 截图 2 的卡带终端独立展示在卡带区域下方，包含终端图片、终端名称、描述和一条效果标签。
## Implementation Findings

- 推荐主属性与副属性已分别加入维护者编辑器。维护者点击词条后可启用 1–9 的优先级输入。
- 用户展示按 priority 降序生成；相同 priority 使用“≈”，不同 priority 使用“＞”。
- 当前真红样板默认主属性为暴击伤害 > 暴击率；副属性为暴击伤害 > 攻击力（%） > 暴击率。
- 终端没有在本地卡带快照中出现，已按用户截图补录为结构化数据，并用 CSS 网格生成本地可读的终端视觉。
- 资源已从 data/mysqil/characters/zhenhong/assets/ 迁移到 data/resources/characters/zhenhong/，知识 JSON 中的推荐配置、觉醒和画廊资源均已更新为新路径。