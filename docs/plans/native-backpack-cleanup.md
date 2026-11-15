# 原生背包清理：状态操作与分解协议研究

## 当前交付状态

用户已将锁定、弃置、分解按钮接入「背包管理」。此前单独放在「背包数据」页的「背包清理预览」卡片已从源码移除，避免入口重复。

锁定/解锁与弃置/取消弃置使用原生状态接口。组件声明 `native_equipment_state_batch_v1` 时按已核实上限每批最多16项状态变更调用 `equipment.set_item_states`；旧组件回退到 `equipment.set_item_locked` / `equipment.set_item_discarded` 单件调用。模仿计算器的规则：把装备设为锁定前先清除弃置标记；把装备设为弃置前先解锁，确认框会列出这些附带变更。背包管理只对完整 DLL 原生库存开放；操作前冻结装备、账号和目标状态，后端核对 UID、进程、快照版本及实例身份，每批/每件派发一次，随后读取新快照核验并保存。状态未知、OCR来源、风险模式关闭或游戏/读取任务繁忙时拒绝操作。分解按钮保持禁用，弃置标记不会被当作分解。

旧的只读清理预览服务和脚本已移除，不再保留 `/inventory/cleanup/*` 接口。

计算器已有基于游戏截图的状态同步方案，细节记录在 `docs/ocr-integration.md`。它属于鼠标/视觉执行流程，不使用原生实例 UID；本轮只核对并记录，没有接入 OCR 点击操作。

## 协议证据与限制

固定组件：Core 0.4.4，nte-core.exe SHA256 `1f875858409ad47eed83ded7991d7a3133eb4afafebf2c2b09cd52802c7b2fed`。

公开调用源码基准 hxwd94666/NTE-Drive-Calculator `0e7a6b4e8e61d7a288e520bbc192a411d68c2fb1`，已读取 `src/integrations/nte_core.py`、`src/services/native_game_session.py`、`src/services/native_inventory_lease.py`，尚未找到分解封装。

Core 与 NTE_PluginUser.dll 静态 token 调查观察到 equip/unequip/move/set_item_locked/set_item_discarded 等名字，未找到 decomposition/recycle/dismantle/salvage 对应协议名。锁定与弃置接口有固定版本公开源码签名作为依据；调查结果存于 build/cleanup-research/static-token-survey.json。字符串缺失不能证明所有运行时路径都不存在；标记丢弃不等于分解。

随包 SOURCE.md 声明公开基础提交不足以重建当前 Core 修改后工作树。因此不能声称修改一个 Python 调用就能补齐 native 分解功能，也不能假设本地有完整 DLL 源码。

## 接通执行所需证据

用户补充正常游戏流程截图：背包点击“空幕分解”→选择物品→明确选择“经验材料”或“倒带材料”→点击“分解”。界面显示已选数量1/100，100仅为观察到的界面批次上限，尚不能证明DLL参数上限。两种返还模式必须作为冻结预览的一部分；缺少模式拒绝生成预览。模式使用应用层标识，不猜测游戏内部枚举值。截图没有展示成功回执，不能据此推断请求名称、参数布局或结算协议。

REA/Ghidra深度分析在330秒初始化期限后超时，已关闭会话；Kuna在当前环境未配置且不支持PE，未重复安装或改客户端配置。这些错误不证明分解路径不存在。普通静态字节调查与REA证据严格区分。

## 用户批准后的只读运行时证据

Windows最初拒绝读取；用户明确允许UAC启动只读诊断。当前游戏与原SHA不符，旧偏移检查停止后，使用既有有界扫描和对象/名称表结构验证。当前SHA256为`303e82a2d85833f2a780424ca3650dc5b64d2793c3d88806818a54630ad961bf`。

读取约61MB名称表，匹配当前462576个对象，0个对象读取失败，没有注入、内存写入或函数调用。确认`/Script/HTGame.HTUI_EquipDecompose`、`HTUI_EquipDecomposeFastSelect`、`HTUI_EquipDecomposeTips`及`DecomposeSelectData`。对应类观察到`OnFastSelectCallback`、`OnItemListViewEntryClick`、`OnInventoryNotifyStatus`、筛选确认及等级/品质/状态选择回调。

特别排除误命中：名称为`Decompose`的UFunction属于`/Script/MeshModelingTools.EditMeshPolygonsToolActions`，不是装备分解函数，不能调用。真实分解请求、返还模式内部枚举、参数和服务端回执仍未核实；这批证据只说明页面/选择相关结构已定位，不代表执行能力已接通。报告位于`build/cleanup-research-current/runtime-cleanup-metadata.json`和`runtime-cleanup-objects.json`。

尝试继续枚举`UFunction/FProperty`签名时，提权读取在当前执行环境仍返回`WinError 5`；备用`runas`启动返回`0xc0000142`，因此没有读取参数字段。辅助脚本`probe_cleanup_reflection_readonly.py`只做内存读取，失败报告保存在`build/cleanup-research-current/runtime-cleanup-reflection.json`。现有Core/DLL仍只观察到装备装卸、移动、锁定/弃置和状态批量操作，没有已验证的分解RPC。不会据此把`set_item_discarded`映射成分解。

1. 待只读访问恢复后核实游戏分解函数/请求、真实实例 UID、参数布局、线程要求、返回错误与批量上限，连同游戏版本及组件能力声明；或者取得组件维护方提供的分解能力和协议。
2. 核实是否存在只读的材料返还预览；不存在时不展示预计材料。
3. 在已有保护预览之上接入冻结清单、UID/修订再核对、执行互斥、单次确认、超时不重发、逐批重读及材料结算核对。
4. 用户批准具体测试实例后才进行单件不可撤销试验；记录前后物品与材料变化，不把本机快照备份称为可恢复物品。

本阶段未执行真实分解，未运行新的自动测试或游戏实测；没有发布或推送。用户确认没有现成分解组件/源码/接口资料。

## 2026-10-22 继续研究的结果

执行顺序为先实现内存分解，再做 OCR。现有组件缺少接口只说明需要扩展组件，不能据此停止游戏侧调用链研究。

已从当前游戏的静态注册表恢复通用请求枚举及 RPC 参数，并通过用户先前批准的管理员只读诊断验证运行时代码。`ServerCommonFunRPC` / `ClientCommonFunRPC` 的参数由32字节 `HottaRpcMessage` 和一个 Actor 参数组成；消息中只有 `Type` 暴露为反射属性，不能据此猜测其原生载荷。客户端虚表中的服务端实现是空函数，不能把直接调用该实现当作发送请求。

更关键的证据来自分解确认界面：界面代码收集物品 UID，传入分解请求枚举成员、材料布尔值及 UID 数组，调用消息构造器，然后经发送包装函数进入对象事件分发。包装函数的完整代码需要结合 PE 链式 unwind 片段恢复，不能把最初7字节的序言误认为全部函数。

材料控件的绑定与回调已对上：`RadioBox_Mat` 选择后写入 true，`RadioBox_Capital` 选择后写入 false。控件名不能直接代替用户看到的“经验材料/倒带材料”；还需要用户在界面选择指定产物，使用只读探针对照实际布尔值。

构造器会移动传入的 UID 数组，并使用游戏自己的释放函数处理其内存。接入时必须使用匹配的游戏分配器、数组布局和析构路径，不能传入 Python 列表、普通进程堆或随便构造的 std::vector 数据指针。

目前新增的工具都只做离线分析或 PROCESS_QUERY_INFORMATION | PROCESS_VM_READ 读取：`probe_cleanup_static_readonly.py`、`probe_cleanup_code_readonly.py`、`probe_cleanup_request_path_readonly.py` 和 `probe_cleanup_material_mode_readonly.py`。报告与工具依赖保存在已忽略的 build 目录，尚未加入可执行的分解服务，也没有发送真实请求。

发送包装函数身份已在只读报告v7中核实：代码加载的 FName 是 `ServerComposeRPC`（number=0）。对应静态 FFunctionParams 只有 `InMessage` 一个参数，总大小32字节，函数标志0x220cc0；结构类型构造器与已核实的 `HottaRpcMessage` 一致。因此分解走此入口，不能把前面40字节的 `ServerCommonFunRPC` 参数误用于分解。包装器复制消息后查找 UFunction，再经对象事件分发；客户端空的服务端实现不能代替发送包装器。

新增代码观察还恢复了数组分配、消息参数复制及析构、游戏释放函数。参数记录按32字节步长复制/析构，其中内嵌缓冲使用游戏分配器。现阶段只读研究没有调用这些函数；函数地址只针对已记录的游戏哈希有效，不能形成跨版本常量。

尚需核实：两个中文材料选项的映射、原生组件接入与游戏线程契约、服务端完成回执和库存/材料结果核对。首次真实试验仍需由用户指定可销毁实例及产物。技术契约见 [native-decomposition-contract.md](native-decomposition-contract.md)。
