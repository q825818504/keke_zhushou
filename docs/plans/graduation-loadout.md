# 毕业配装：V1.5 本地实现

- [x] 驱动按整块外轮廓同品质微光，不逐格发光。
- [x] 使用共享评分，按总分优先枚举形状数量并验证摆放；计算放到 Worker，搜索受限时明确标记未证实最优。
- [x] 默认排除其他角色持有的驱动与空幕，本角色装备始终参与。
- [x] 按账号与原生角色实例保存，装备引用跨刷新解析并校验；不持久化临时选择句柄。
- [x] 游戏页展示已保存方案，预览装备变化；含空幕和驱动的整套方案走原生一键接口，拆卸和单件操作逐件核验。
- [x] 纯求解、存储/身份失效、原生模拟装配/拆卸、源码浏览器全流程测试。
- [x] 最终重建、837 项资源与新增脚本 hash/PYZ 模块审计、生成包 UI 验收；覆盖唯一 V1.5 测试包，不发布。

总分口径沿用：空幕 100（主60/副40）＋盘面 100；盘面按 Σ（单块评分×格数）÷盘面可用格数折算（20 格盘面分母为 20）。金色用柔金、紫色用浅紫、蓝色用冰蓝描边。每角色每账号保留一个可覆盖方案；读取或账号变化清理计算中状态。所有实装写入仍由后端检查实时来源和状态完成。

## 实现与验收记录（2026-10-17）

- `role_build.js` 从每块 cells 的外侧边生成 SVG 线段，共享格边不描线；柔金/浅紫/冰蓝描边配轻微 drop-shadow，不修改驱动原图。
- `loadout_optimizer.js` 为纯模块，由 `loadout_worker.js` 运行。空幕按角色图鉴推荐 ID 锁定；不会被更高词条分的其他套装替代，并强制包含图鉴维护的四种套装驱动形状。使用 `DriveLayoutSolver.generateCandidates` 枚举库存允许的形状数量组合，按实际总分优先排序，逐一验证是否能在角色盘面合法摆放；最高分可行组合即为结果。相同形状数量的坐标位置不会改变属性分，因此每种组合验证一个合法位置即可。评分枚举或高分候选的摆放验证未完成时 `complete=false`，界面明确未证实最优。默认排除其他角色的空幕和驱动，本角色装备仍参与。
- `equipment_plans.py` 在本机 inventory/build-plans 以账号 hash 文件保存每原生角色一个方案。保存 uid/kind 稳定引用和排除装备状态字段的属性签名，刷新后重新映射句柄；角色实例变化、装备消失或属性变化、保护限制下被其他角色占用都会使方案失效。保存时校验摆放，saved-preview 再解析，执行仍使用有期限预览 token 和原生逐件核验。
- 修复 `equipment.py` 的 preview_assembly 中 resolve_request 因缩进不可达的问题。UI 提供计算/保存、已保存方案、装配/拆卸清单预览、再次确认、运行/停止和完成刷新。状态请求失败保留 unknown/running 锁，保留停止及手动重查，有限退避重试，并以 pollGeneration 丢弃旧响应；不能将断连当作操作已停止。
- 已通过：纯优化器与 10 组独立 brute-force 最优对照、归属/形状/预算用例；7 个模拟 Core 的真实 service 测试和 HTTP 验证，覆盖保存/重载/重启、归属保护、失效、过期、转移/拆卸/再装、live revision 变化不派发、停止仅在已核验步骤后结束；共享评分、smoke、源码 1440/390 Worker 全流程和状态断连恢复。
- 独立 `/root/graduation_finish_review` 完整复核的唯一 material 问题为状态断连错误解锁，已修复并验证；结论 resolved/ship，最终包核验条件已满足。837 项资源审计通过，worker/optimizer/scorer/role JS 与源码 hash 一致，PYZ 中确认 `inventory.equipment_plans`。生成包用自身 config 通过 Worker 全流程、过滤、保存、游戏预览不派发、确认、断连保持 running/取消按钮、手动恢复及拆卸请求验证。
- 最终唯一包 `dist/windows/test-v1.5/KekeAssistant.exe`，180281107 字节；SHA-256 `0778D257B4520226AF2D3E574D93E92F565FC825D2B48E1FE6B153ED40A8A02C`。主代理确认构建、包内 UI 及唯一 EXE 审计通过。
- 全部游戏写入验证使用模拟 Core；未操作真实游戏、未启动真实 EXE、未发布，release 保持 1.4。延续既有暗色界面，不创建全局 DESIGN.md，也不重跑已失败的上下文加载器。

## 用户纠正与最终验收（2026-10-17）

- [x] 计算结果直接切换既有盘面、空幕/驱动装备行、属性汇总、页头和选中角色卡分数，统一使用 `assessment(role, plan)`；仅一个盘面，无独立 `rb-proposed-plan`。游戏页已保存方案复用同一展示，无效方案提示重算，不用当前装备冒充。
- [x] 游戏页只列当前账号 `saved_plans` 已有键对应的持有角色，搜索与计数同步；没有方案时提示先计算保存。无效方案仍可见其失效原因。
- [x] 真实第 0 步误拦已定位并修复：inventory 与 control 的 domainKey 分属两域，refresh 会改变 snapshot/revision。`state.context` 统一使用库存 header 的 pid/providerId/domainKey，`control_context` 独立冻结 equipment.status 身份；完整 fingerprint 保留。verify_operation/verify_unequipped 同时校验 control_context。执行初始完整状态匹配后不再比较跨 refresh 的旧 revision，只核对 session pid；包括第 0 步的每条命令前核对 control 域及最新 observation.header 字符串 revision，无法使用 revision 时完整 capture 回退。
- 证据为主代理只读检查本机最新 equipment-operations 审计、对应账号快照及 NteAdapter 原生 read：saved/live 角色 uid、装备 rows 和补丁后 fingerprint 一致，两个 domainKey 确属不同域，最新 revision guard 通过，装备派发为 0。此轮有真实原生只读核验，没有 equip/unequip 写入；此前「未操作真实游戏」仅为较早轮次记录。
- 9/9 service 测试通过，新增双域不同/refresh revision 变化/字符串 revision 正常装配，以及 dirty 第 0 步拦截；真实装备字段变化仍 0 派发。scorer/optimizer/smoke、源码与生成包自身 config UI 均通过。UI 验证单盘面、外部空幕实际替换装备行和页头（fixture 总分 133.5）、2 个持有角色仅 1 个保存角色可见、未保存游戏空状态及断连恢复；fixture 分数不代表真实账号配装结果。
- 新截图 `artifacts/role-build/desktop-game-source.png`、`mobile-game-source.png`，既有源码/包截图同步更新。独立全新 `/root/single_display_finish_review` 完整复核 disposition ship，无 material 问题，独立运行 9 个 service 测试通过。
- 唯一测试 EXE 已覆盖重建：`dist/windows/test-v1.5/KekeAssistant.exe`，180280263 字节，SHA-256 `FADD0F69E5F9005B122032B2DFED3CD8F2D9E04974300BD1AC41E55E5C6C81EA`。837 项资源、PYZ 模块及生成包 UI 审计通过；上一节包大小/hash 为历史记录。本轮未启动 EXE、未发布，release 仍为 1.4。

## 自动装配性能优化（2026-10-17）

- 对照 NTE Drive Calculator 固定提交 `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1` 的 `equipment_plan_execution.py`、`fast_equipment_execution.py` 和 `nte_core.py`：有空幕的完整配装通过 `equipment.equip_one_key` 一次提交空幕及驱动位置；计算器快速路径随后依靠更新的装备观测确认结果。这个接口也在可可助手固定的 Core 0.4.4 协议中。
- 可可助手之前每件装备后都刷新并分页读取整份装备快照，因此6件方案至少产生多次完整游戏状态读取。当前完整方案改为一次批量 RPC，等待快照修订变化后整体读取核验，必要时有限重读；不重新发送超时或结果不明的写操作。跨角色物品仍由预览展示，最终全库存指纹核对每一件装备归属、位置及其他字段。
- 批量 RPC 已派发时不能安全中断，因此界面明确提示并隐藏停止按钮；停止仍可阻止尚未派发的逐件操作。没有空幕的方案和拆卸保留逐件路径。
- 本次完成源码调整和本地 V1.5 测试包构建；真实游戏中的耗时与卡顿改善仍需用户在游戏里实测。发布版本继续保持 V1.4。
