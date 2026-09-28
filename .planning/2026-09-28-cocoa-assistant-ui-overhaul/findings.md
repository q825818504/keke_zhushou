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
