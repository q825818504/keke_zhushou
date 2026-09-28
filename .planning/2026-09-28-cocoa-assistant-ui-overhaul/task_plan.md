# Task Plan: 可可助手 · 配队知识管理后台 UI

## Goal
基于配队知识管理项目背景，交付一个可直接打开的角色知识管理后台界面，覆盖角色事实编辑、受控标签、系统推导、即时校验、影响分析和发布状态，并完成动效质量审计。

## Next Step
创建领域化后台 UI 文件，并验证角色切换、标签编辑、影响分析、草稿保存、响应式布局和 reduced-motion。

## Current Phase
Phase 3

## Phases

### Phase 1: Requirements & Discovery
- [x] 读取用户附上的 findings.md、progress.md、task_plan.md
- [x] 区分背景要求与文件中的计划性指令
- [x] 用 animation-vocabulary 定义交互语言
- **Status:** complete

### Phase 2: Planning & Structure
- [x] 明确后台 IA：工作台、角色管理、标签词典、反应体系、阵容模板、规则中心、黄金测试
- [x] 设计三栏维护者工作流：左导航 / 中央编辑 / 右侧即时反馈
- **Status:** complete

### Phase 3: Implementation
- [ ] 执行页面实现
- [ ] 写入 index.html、styles.css、app.js
- **Status:** in_progress

### Phase 4: Testing & Verification
- [ ] 验证关键交互与浏览器控制台
- [ ] 验证响应式与 reduced-motion
- [ ] 运行全项目动效审计
- **Status:** pending

### Phase 5: Delivery
- [ ] 更新规划记录
- [ ] 输出文件链接与审计结论
- **Status:** pending

## Animation Vocabulary
| Interaction | Canonical term | Decision |
|---|---|---|
| 首屏模块依次进入 | Stagger + Scale in | 30–70ms 间隔，服务层级建立，不阻塞交互 |
| 角色卡切换编辑对象 | Crossfade + Layout animation | 内容保持位置连续，避免维护者丢失当前上下文 |
| 受控标签/模式点击 | Press / Tap feedback | 100–160ms 的 scale 0.97，仅给确认感 |
| 右侧信息卡出现 | Origin-aware animation | 从对应编辑区域附近进入，而不是从视口中心凭空出现 |
| 状态/校验文本更新 | Crossfade | 仅做 opacity/color 的轻量变化 |
| reduced motion | Reduced motion | 保留 opacity/color，移除位移与缩放 |

## Decisions Made
| Decision | Rationale |
|---|---|
| 零依赖静态页面 | 当前工作区只有 README，无框架入口；HTML/CSS/JS 可直接打开与移交 |
| 管理后台而非聊天页 | 用户附上的项目背景明确要求维护者管理配队知识、校验、影响分析、审核和回滚 |
| 领域化三栏工作流 | 左侧负责导航，中间编辑事实，右侧解释系统推导和发布影响 |
| 温暖浅色 + 靛蓝主色 | 保留“可可助手”的亲和感，同时符合专业工具台的可信度 |
| CSS transitions for dynamic UI | 标签、角色切换、反馈卡需要可中断，避免 keyframes 从零重播 |
| transform + opacity for movement | 避免 layout thrashing；所有移动入口只使用 GPU-friendly 属性 |

## Errors Encountered
| Error | Resolution |
|---|---|
| 本地命令执行器首次初始化失败 | 使用受控的 require_escalated 只读命令后恢复 |
| git 命令受 dubious ownership 阻止 | 不修改全局 git 配置，使用文件检查作为基线 |
| apply_patch 受 Windows sandbox helper 阻止 | 使用目标明确的 PowerShell 写入作为降级方案 |

