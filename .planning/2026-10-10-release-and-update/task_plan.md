# Task Plan: Windows 安装发行与 Gitee 更新方案

## Goal
设计 GitHub 源码/配置维护、独立管理端 EXE、Windows 安装发行、递增版本和 Gitee 程序/公共配置更新的可执行方案。

## Next Step
用户已授权实现联网安装器并同步Gitee下载产物；实施签名清单、版本、配置导出和安装更新。

## Current Phase
Phase 6 - Implementation

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify current code and confirmed startup policy
- [x] Validate hosting and installer constraints (limits verified; real artifact download scheduled for release acceptance)
- **Status:** complete

### Phase 2: 发布与更新架构
- [x] 分离应用版本和配置版本、定义 Gitee 发布内容与清单。
- [x] 定义安装、启动门禁、程序替换和配置缓存。
- **Status:** complete

### Phase 3: 可执行开发计划
- [x] 写入 docs/plans/desktop-release-and-update.md，映射现有模块修改。
- [x] 记录后续真实发布和双电脑验收步骤。
- **Status:** complete

### Phase 4: 方案核对
- [x] 逐项核对六项需求及用户后续纠正。
- [x] 区分已核实限制、未核实下载能力和尚未实现功能。
- **Status:** complete

### Phase 5: Delivery
- [x] 交付方案及实施顺序，说明当前未发布安装包。
- **Status:** complete

## Decisions Made
### 实施阶段（2026-10-11）
- [x] 公共JSON配置导出、签名和版本递增。
- [x] 联网安装器、更新门禁、原子安装与配置回退。
- [x] 管理端发布入口、Gitee白名单附件上传和清单切换。
- [ ] 必要测试、实际构建、Gitee匿名下载检查及GitHub同步。

| Decision | Rationale |
|----------|-----------|
| 程序版本检查严格；配置下载失败可离线 | 用户后续明确纠正，以最后一条为准。 |
| GitHub 与 Gitee 使用完全独立的仓库和发布白名单 | 不同步源码到 Gitee。 |
| 本轮先交付实现方案 | 用户请求“看看怎么实现”；不声称安装和在线更新已实现。 |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| init-session 无法安全更新共享 active_plan 指针 | 新计划三文件已创建；使用 PLAN_ID=2026-10-10-release-and-update 显式解析，未回落其他计划。 |
| Gitee 仓库 web 访问内部错误、PowerShell API TLS 失败 | 不推断仓库私有或不存在；继续核实官方限制，匿名访问能力标为未验收。 |
| 规划完成标记补丁上下文不匹配 | 按已修改后的实际行修正补丁；不修改业务代码。 |
| 沙箱临时目录无法读写 | 正常本机权限执行隔离测试/构建；不改变用户游戏数据。 |
| 系统 Windows PowerShell 签名模块加载失败 | 构建机采用正常工作的 pwsh，验证微软签名后才分发运行库。 |
| Gitee 没有保存的写入凭据 | 已提供单EXE管理端的本机DPAPI令牌入口，等待用户配置；不索取聊天令牌。 |
