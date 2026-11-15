# 内存分解调用契约研究

## 当前实现进度

后续进度：已增加独立Windows加载器、测试桥接及助手UI/后端源码。加载通过用户显式启动的线程消息钩子；桥接使用现有宿主的公开观察接口验证真实Tick线程，工作线程仅接收私有管道请求，实际发送在验证后的游戏线程进行。若接口缺失、拒绝或线程无法验证则保持未就绪，不绕过签名/接口拒绝。游戏分解页单件UID必须与冻结请求相同。

助手现在支持加载/检测、经验/倒带显式选择、单件不可逆确认、完整库存及账号/锁定/装备/保存方案保护复核、发送后的库存和全材料数量回读。材料ID尚未证实，因此只报告装备移除与材料差分，不宣称材料结算已成功；未知结果不重发。原生加载与分解没有实机运行，测试交给用户。独立测试包使用完整OCR环境，普通正式包默认不携带测试加载器。

以下“宿主未实现”的段落是此前阶段记录，现以本段和native/decomposition/README.md所列实现进度为准。

2026-10-22已为SHA256为032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788的当前游戏重新跟踪发送路径，生成 `current-decompose-sender.json`。真实构造器为0x148d23b80，发送包装器为0x14947b780，仍查找ServerComposeRPC；不是沿用旧地址。

新增 `native/decomposition/` 原生模块和 `scripts/export_cleanup_native_profile.py` / `scripts/build_cleanup_native.py`。五个实际引用的构造、发送、分配、析构、释放函数具备完整字节指纹，文件哈希也会在调用前核对。模块使用游戏数组分配和消息释放路径；显式经验/倒带选项，单件限制、请求ID去重、执行互斥、异常停用及“派发但未确认”返回值已写入源码。

使用核对官方包哈希的Zig 0.14.1编译成功，未产生编译警告。产物是 `build/native-decomposition/KekeNativeDecomposition.dll`（424960字节），仅导出KekeSubmitNativeDecomposition；编译记录明确 application_integrated=false、runtime_verified=false、loaded_into_game=false。未加载或调用DLL，没有实机分解，也未运行自动测试。

真实宿主桥接仍未实现：必须提供游戏线程检查/调度、当前PlayerState、风险模式和最新库存/方案保护校验。现有第三方Core没有此接口，其签名插件未改动；独立DLL不能直接塞进该签名插件目录就视为集成。UI按钮仍未接通。

完成通知另有证据：当前静态注册表ENotifyItemType共75项，NOTIFY_DECOMPOSE_FINISH值51。该数字只证明通知枚举存在，不证明请求关联、成功状态或材料结算载荷。回执与库存/材料回读仍待实现。

状态：2026-10-22，已生成含独立桥接/加载器的V1.7测试EXE，助手端单件材料确认与回读已接入。尚未加载组件或发送分解请求，实机测试由用户进行；编译和打包成功不代表游戏内验证成功。

## 版本和证据

仅适用于游戏可执行文件 SHA256 `303e82a2d85833f2a780424ca3650dc5b64d2793c3d88806818a54630ad961bf`。下述地址是该文件的静态 VA，运行时必须按匹配模块基址换算，不得跨版本套用。

本机报告保存在忽略提交的 `build/cleanup-research-current/`：

- `runtime-request-path-readonly.json`：完整包装器搜索失败，但保留分解确认界面的有效局部代码。该报告不能整体称为成功。
- `runtime-code-readonly-v7.json`：成功读取3568字节代码及发送函数 FName。包含只读权限、进程身份、游戏哈希、每段字节哈希及函数边界来源。
- `static-cleanup-contract.json`：静态枚举、函数及结构注册表；与上述运行时代码结合使用。

工具只使用读取权限，不注入、不挂钩、不写游戏内存、不调用游戏函数。运行时代码和物品数据不作为公开发布资源。

## 已确认的请求路径

1. 分解确认界面从所选装备对象读取8字节 UID，形成游戏 TArray。
2. 传入 `ECommonRPCMsgCToS::EquipDecompose_Request`（本版本值99）、材料布尔值和 UID 数组，调用 `0x148d23d40`。
3. 构造器返回32字节 `HottaRpcMessage`；反射属性 Type 位于偏移24。消息前24字节为原生载荷，不能直接凭反射表猜测。
4. 界面将此消息交给 `0x14947b980`。完整287字节函数通过 PE 链式 unwind 片段恢复，第一段7字节不是完整函数。
5. 包装器读取 `0x14fe134c8` 的 FName。只读名称池解码为 **ServerComposeRPC**，number=0；它查找 UFunction 后经对象事件分发。
6. 静态 `ServerComposeRPC` 注册表确认参数仅 `InMessage`，总大小32，结构类型为已核实的 HottaRpcMessage。函数标志0x220cc0。

值99是游戏内部消息枚举，不能单独当作网络包编号。`ServerCommonFunRPC` 的40字节参数包含额外 Actor，属于另一入口。客户端服务端实现为空，直接调用它不能发送请求。

## 内存所有权

构造器的观察调用约定：RCX 为返回消息缓冲，EDX 为请求类型，R8B 为材料布尔值，R9 为 UID TArray 地址。这里只记录观察结果，尚未提供可调用的外部 ABI。

- 构造器接管输入数组：读取数据及长度后清零源数组，复制并释放其数据。
- 不得把 Python 缓冲、普通宿主堆、std::vector 内存作为拥有所有权的游戏 TArray 传入。
- 数组分配候选 `0x141485150`、消息参数复制 `0x144c67040`、参数析构 `0x141535720`、游戏 Free `0x141514700` 已获得代码；必须连同线程约束和 ABI 核实后才能调用。
- 消息参数以32字节步长复制及析构，每条记录含独立缓冲。调用发送包装器后，原消息仍由调用方按游戏路径析构；不能仅释放外层数组。

## 材料去向

现场切换对照已完成：经验材料=true，倒带材料=false。报告 `material-mode-comparison.json` 对照同一个挂在 W_OverallUILayout_C 下的实际UI实例，从true切换为false，两次选中数均0。另一资产Widget实例保持true，所以倒带快照的“全部实例一致”结果为false；这里通过同一实际实例的差分消除了歧义，不能把所有同名对象都当作当前界面。没有调用游戏函数或发送分解。

2026-10-22现场进度：游戏文件已更新为SHA256 `032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788`。旧代码校验失败后，从当前UI类CDO重新定位并反汇编材料控件绑定/回调，确认字段布局。用户选择经验材料、未选物品时，两个候选UI实例标志一致为true，选中数0。经验材料对应true得到现场支持；倒带材料仍待切换对照。此验证只覆盖材料UI，本文旧版本请求地址不因此自动适用于新版本。

原生 UI 绑定与回调已经对上：

| 控件字段 | UI对象偏移 | 选择后的标志 |
| --- | --- | --- |
| RadioBox_Mat | 0x1368 | true |
| RadioBox_Capital | 0x1370 | false |

当前标志位于 UI对象偏移0x1390。中文“经验材料/倒带材料”与上述控件的关系尚未现场核实，不从英文变量名推断。待用户打开分解页、明确选择经验材料后，使用 `probe_cleanup_material_mode_readonly.py` 观察；随后切换倒带材料做对照。观察不需要选中物品或点击分解。

## 接入前剩余工作

1. 完成两种中文材料选项与布尔标志的对照。
2. 实现匹配版本的原生组件入口、游戏线程派发、UID数组分配与消息析构；现有固定版 Core 没有分解方法，不能在 Python 层凭空增加方法名就认为接通。维持现有插件信任规则。
3. 确认服务器完成/失败通知，结合新库存及材料变化核对结果；ProcessEvent 返回不代表服务端分解成功。
4. 接入现有 UI 时必须显式选择产物，并显示“将分解 N 个空幕，分解为【经验材料】/【倒带材料】”。冻结 UID、账号、版本与保护条件；发送前重核装备/锁定/方案引用状态。
5. 首次真实试验由用户指定可销毁的一件物品和产物，明确批准后再进行。结果不明停止，禁止自动重发。UI观察到100件上限，未证明原生协议批次上限；首测限定单件。

OCR 分解安排在后续阶段。

## 2026-10-22：受支持的调用入口检索

用户要求继续内存路线，但只接入受支持的进程内接口；因此本轮只核对公开项目文档、本机固定组件调用面和公开插件框架说明，没有加载游戏组件、调用内部函数或发送分解请求。

- 已找到的游戏内函数是分解界面使用的 `HottaRpcMessage` 构造路径和反射发送包装器 `ServerComposeRPC`。这是游戏客户端内部调用证据，不是可可助手可直接调用的外部 API。现有 `KekeNativeDecomposition.dll` 包含按该版本静态证据编写的发送代码，但仍未在游戏内加载或运行；它本身不能解决可信的游戏线程入口。
- 本机固定版 NTE Calculator Core/插件对外是受限 JSON-RPC。可核实的装备操作包括装备/卸下、锁定、弃置和保存方案装配；无任意 RPC 转发或分解方法。`desktop/native/NOTICE.md` 明确说明没有 arbitrary RPC、签名绕过或 live injection loader。
- NTE Drive Calculator 当前公开的集成文档列出捕获、库存、仓库状态写回与极速装配等能力，并说明通信契约由组件维护仓库定义；公开仓库不带私有 DLL 源码、SDK 或实现规范。公开 README 的“驱动处理”也只列锁定/弃置。已核对的公开资料没有提供自定义原生调用插件或 `ServerComposeRPC` 扩展入口。
- NTE DPS Toolkit 文档列出的 User 插件能力是角色/背包快照及锁定、弃置、穿戴。它能说明同类工具的既有能力范围，但没有提供分解 RPC 的公开契约。
- 检索到 Anomaly 是另一套社区插件平台，确有公开 C ABI 插件 SDK；但它不是游戏官方接口，也不是 NTE Calculator 的扩展 API。其公开 README 明示第三方插件未签名，并把实时进程读写、hook、patch、alloc/free 限定于自有测试进程，同时禁止外挂用途，因此不将它作为调用游戏分解函数的接入路线。

结论：分解函数及游戏 UI 的内部发送路径已经定位；仍未找到受支持的外部调用入口。实现可行性依赖组件维护者提供或授权兼容的插件入口/SDK（包括游戏线程调度和当前玩家对象访问），并在该受支持入口中明确暴露单件分解操作。现有游戏进程钩子加载失败不是调用参数问题，不能通过替换成未授权加载器来当作修复。取得此接口前维持内存路线研究状态，不接 OCR，不执行分解。

本轮公开来源：

- https://github.com/hxwd94666/NTE-Drive-Calculator/blob/main/docs/integrations.md
- https://github.com/hxwd94666/NTE-Drive-Calculator/blob/main/README.md
- https://github.com/kongbaiz/nte-dps-toolkit
- https://github.com/AnomalyNTE/Anomaly

### 版本证据更正

再次核对本机报告后发现，`runtime-code-readonly-v7.json`、`static-cleanup-contract.json` 和旧“已确认的请求路径”小节对应 SHA256 `303e82a2…961bf`；当前 `current-decompose-sender.json` 对应 SHA256 `032eb661…cd788`。当前报告重新定位了 UI 提交代码、消息构造器、发送包装器和玩家对象 getter，发送入口的名字解析为 `ServerComposeRPC`。因此，旧小节中的数值、参数布局和函数地址不能直接套到当前版本；当前报告只证明这些函数和 UI 路径已重新找到，不补足 Core 的受支持调用入口，也不证明真实请求已派发。

## 2026-10-22：Anomaly NTE API 对照

用户指定核对 `AnomalyNTE/Anomaly` 后，修正上一节“Anomaly 不作为调用路线”的过宽表述：Anomaly 确实公开了 `anomaly.nte.ui-buttons` 服务。它能枚举并查找 UMG、CommonUI、HTGame 按钮/单选框/复选框/列表项，并由 Host 在后续 Game tick 调用控件自身的点击处理函数；请求有 generation handle 和状态快照。这给出了一个**语义化游戏 UI 操作**入口，若分解页面控件可被该服务发现，理论上可尝试沿游戏自己的分解页面流程完成选择与提交，不需要 OCR，也无需自行合成鼠标输入。具体页面控件是否被目录收录、实际分解步骤能否完整覆盖，文档没有证明，本机也未加载或操作游戏核验。

它**不是** `ServerComposeRPC` 的直接调用入口：文档明确不向插件暴露 UE 对象指针、UFunction 或 Profile 偏移；Interop 文档列出的是签名解析、Hook、Patch 和受 capability 限制的原始内存读写，并没有通用 UFunction/RPC invoke 服务。WebSocket 只允许插件广播文本，服务本身不分发外部发来的应用消息，不能直接当作可可助手→游戏的命令通道。插件间 IPC 虽在 API 索引中列出，但此轮未核实其可否作为外部桌面应用的命令入口，不据此承诺可以接通。

因此，当前“内存直发分解 RPC”仍缺少公开、受支持的调用契约；新发现的是另一种非 OCR、经游戏 UI 控件处理器提交的候选路线，不能把它描述成已经找到或修复了直发接口。Anomaly README 将自身定义为社区插件平台，并提示第三方工具可能违反公平游戏要求及带来账号风险；若以后评估 UI 路线，需单独确认其是否符合用户愿意承担的风险边界。现阶段按用户先前决定保持内存路线研究，不加载 Anomaly 插件、不调用分解、不切换 OCR。

本节来源：

- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/nte-services.md
- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/interop-and-memory.md
- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/websocket.md
- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/README.md
- https://github.com/AnomalyNTE/Anomaly

### `equipment.set_item_*` 命名边界补充

用户指出 `equipment.set_item_locked` / `equipment.set_item_discarded` 是组件自行定义的白名单，因此不能由“公开列表没有分解”推导出“不能新增分解端点”。这一点成立；前次表述应限定为**当前固定版 Calculator 插件没有公开该端点**，而不是该功能不可自行实现。

静态 token 报告中，当前随包的 `NTE_PluginUser.dll` 可见的是 `equipment.set_item_locked`、`equipment.set_item_discarded` 与 `equipment.set_item_states` 等精确方法名；没有发现 `set_item_decompose`、`set_item_recycle` 等同类名字。字符串扫描缺失不是不存在的绝对证明，但命名空间也没有通配机制证据。可可助手的状态操作表将批量 `set_item_states` 限定为 `locked` / `discarded` 两种字段，不能把它视为任意 `set_item_*` 写接口。

此外，可可助手仓库已经有独立的 `native/decomposition/decomposition.cpp` 发送实现：按当前匹配版本构造游戏自己的分解请求，再走 `ServerComposeRPC`。它不是 Calculator 插件提供的 `equipment.set_item_*` endpoint。当前用户看到的桥接失败说明该自定义发送路径尚未成功连入游戏进程，因此实际阻塞点是可信的进程内派发/桥接，而不是“还没给分解起一个 set_item 方法名”。此代码仍未通过真实派发与结果确认，不能称为可用分解功能。

### 桥接唤醒差异与修正

旧版 `loader.cpp` 安装 `WH_GETMESSAGE` 钩子后只向目标线程发无窗口句柄的 `WM_NULL`；仓库内的隔离验证器则向目标游戏窗体 HWND 使用 `PostMessageW`。因此曾假设线程消息可能被目标消息泵过滤，并将唤醒改为同时投递目标 HWND 与线程队列，也给桥接请求增加同样唤醒及 HWND PID/线程归属核验。用户提供的游戏实测截图显示两处都 `posted`，等待10秒仍未观察到桥接模块或回调日志；诊断显示目标为 x64、同会话、高完整性，原始 protection 字段为 `4294967294`。`SetWindowsHookEx` 返回钩子句柄只证明调用返回了有效句柄，不证明目标线程执行钩子或映射 DLL（见 Microsoft `SetWindowsHookEx` 文档）。所以“只补发 HWND 消息”不是修复，先前假设被实测否定。现有结果无法区分目标线程未触发 hook 与目标侧未完成 DLL 映射；没有调用发送器，也没有发出分解请求。不要继续宣称桥接已修复或把失败归因于一个已证实的 Windows 策略。

参考：[Microsoft SetWindowsHookEx](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowshookexa)。

Codex 隔离桌面离线探针同样得到 `mapped=0 callback=0 post=1 retrieved=1 received=1`，最小控制 DLL 也未映射。该离线结果不能代替游戏结论；用户截图进一步确认当前游戏测试也失败。下一步是取得受支持的游戏内宿主/插件调用入口，或评估 Anomaly 的 `nte-ui-buttons` 服务是否覆盖完整分解 UI 流程。该服务能通过游戏控件自身处理函数执行 UI 点击，但不提供 `ServerComposeRPC` 直调接口；它属于路线变更，尚未接入或实测。

### 2026-10-22：继续只查直发 RPC

用户明确要求继续寻找直发 RPC 入口，不切换到 UI 操作或 OCR。本轮复核 Anomaly API 索引、Interop 头文件、插件开发约定及 NTE 服务定义：

- API 索引将 v1 描述为完整公开参考，服务类别包括签名解析、函数 Hook、Patch、插件间 IPC、UI、UE5 与语义 NTE 服务；没有通用 `UFunction` / 任意 RPC 调用服务。
- `anomaly.interop.hook` 的 `create` 参数是目标地址和 detour，返回 original trampoline 与句柄；它提供安装/撤销 Hook，不提供“按函数地址和参数主动调用”的 API。
- 唯一名称带 `invocation` 的 NTE 服务是 `anomaly.nte.skill-invocation`。它只接受当前 combat/skills 快照中的 world、character、skill handle，并固定走已经验证的 `HTTryActivateAbilityByClass`。文档明确不接受任意路径、UFunction、参数缓冲、目标或位置，因此不能用于 `ServerComposeRPC`。
- `anomaly.ipc` 是 API 索引列出的插件间 IPC；公开插件 ABI 的入口只交付生命周期回调与 `query_service`。没有找到桌面程序可向插件动态注册/调用任意游戏函数的公开接口。`anomaly.websocket` 只允许插件向本地客户端广播文本，不处理外部应用消息，因此也不是命令直达通道。
- Anomaly 插件指南明确要求常见语义功能由 Host 服务执行，并禁止插件在拾取/UI 类流程自行调用 UE `ProcessEvent`；UI 服务则通过控件自身处理器完成真实 UI 操作。用户已选择不走 UI 流程，所以本轮不以该路线替代直发。

结论收窄为：游戏的 `ServerComposeRPC` 及消息构造器已定位，但目前没有找到 Anomaly 或固定版 Calculator 提供的受支持“主动直调任意 RPC”入口。Hook、ProcessEvent 调用点和函数包装器是不同概念；现有 Keke 发送器需要一个在受信任 Game-thread 上的进程内执行入口。自建 Anomaly 插件理论上提供受支持的加载生命周期和 Game Update 回调，但其公开 ABI 没有任意函数调用服务，按游戏私有 ABI 从插件直接调用该 RPC 仍属于自定义、未受文档支持的调用路径，不能称为已找到的官方/宿主 RPC 接口。当前加载器仍未在目标游戏中观察到模块或回调，不再据现有失败诊断推定是某种 Windows 限制，也不尝试替换成另一种进程注入手段。

当前状态：直发函数地址已找到；可用的受支持直接调用入口仍未找到；没有分解请求发送；UI/OCR 均未切换。后续只有发现公开的函数调用契约或组件维护者提供/授权的插件扩展接口，才能继续把“直发”称为受支持集成。Anomaly 公开说明也限定其实时进程读写/Hook 等开发用途，并提示不得用于作弊及相关账号风险。

### 2026-10-22：对游戏调用点做离线倒推

用户要求继续遍历、倒推直发入口。本机当前版本报告含 `decompose_submit_current` 的完整运行时代码字节；用 Capstone 解码后，确认提交函数 `0x148d3dda0` 在 `0x148d3e18f` 直接调用 `0x14947b780`。发送器的 ABI 与现有实现一致：`PlayerState*` + 32 字节 `HottaRpcMessage*`；UI 端先经 `0x148d23b80` 构造消息，再调用该发送包装器。因此，**游戏内部的直接调用协议已经被找到，且 Keke 的 `decomposition.cpp` 已实现这次调用**；它不是缺少新的 `equipment.set_item_*` 方法名。

进一步的通用调用点遍历受限于目标版本的代码状态：磁盘 EXE 对应运行时函数的代码偏移读到零字节，与之前只读采集到的有效运行时代码不同；这说明磁盘镜像不能直接用于该段的普通 xref 扫描，代码由何种加载/展开机制恢复仍未确认。REA/Ghidra 对 273 MB EXE 的导入与分析超过 330 秒启动期限。新增 `scripts/probe_cleanup_current_callers_readonly.py` 仅申请 `PROCESS_QUERY_INFORMATION | PROCESS_VM_READ`，按当前 EXE 哈希遍历运行时代码找 E8/E9 直接引用；普通执行及 Codex 提权执行都在 `OpenProcess` 阶段返回 WinError 5。Windows UAC 启动本身又返回 `0xc0000142`，扫描器没有在管理员上下文中运行。因此未读取代码页、未执行游戏代码、未注入/写内存。该扫描只覆盖直接相对调用，本身也不会证明 RPC 成功。

本轮能确定：**直发函数与 UI 调用点已确认；当前阻塞是让已写好的 sender 在匹配的游戏进程与 Game-thread 上运行的桥接入口。** 当前没有找到另一个受支持的通用直调 API；不得把未成功的 DLL 加载器说成已修复，也不得用驱动/绕过式加载替代。当前 EXE 仍未具备已验证可用的自动分解功能。

验证引用：当前游戏 SHA256 `032eb661ce65e0669fb643a2e87e727d5574bba832cd6fe34ff0ab1d134cd788`；对报告中的11段当前版本运行时代码字节做相对 `E8` call 扫描，唯一命中为 `decompose_submit_current` 的 `0x148d3e18f → 0x14947b780`。覆盖仅限这些已采集片段，不能推断整个可执行文件只存在这一调用者。运行时全节扫描状态保存在 `build/cleanup-research-current/current-rpc-callers-readonly.json`，结果为 `OpenProcess` WinError 5，零代码读取。

本轮来源：

- 追加一次 `xrefs(0x14947b780)` 查询仍在 Ghidra 导入阶段超时（330 秒），没有产生完整调用者图；不能把 UI 的单个已确认调用点说成全部调用点。
- 复核 Anomaly 当前公开 SDK：Interop 暴露签名解析、Hook、Patch，不提供按地址或 `UFunction` 执行任意函数的服务；`nte.skill-invocation` 明确限定到经校验的 `HTTryActivateAbilityByClass`。插件开发指南在 UI/交互场景要求使用语义服务，并明确不应直接调用 UE `ProcessEvent`。这确认公开 SDK 没有可直接替代 `ServerComposeRPC` 的通用调用入口，但不否定游戏本身已有的私有调用包装器。
- 找到一个仍保持直发路线的桥接候选：Anomaly 插件 `on_update` 明确运行在 Game 域，可接收桌面端排队的请求，并在该回调内调用现有发送器；这只是线程调度入口，不是 RPC 服务。私有 ABI/`ProcessEvent` 调用仍不属于 Anomaly 支持的语义接口，且插件开发指南明确反对插件直接调用 `ProcessEvent`。本机常见应用目录和 NTE 游戏目录中未发现 Anomaly 安装/插件目录，故目前没有可直接接入的本机宿主，候选方案也未实现或验证。
- 公开参考：[API 总览](https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/README.md)、[Interop 与内存](https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/interop-and-memory.md)、[NTE 服务](https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/nte-services.md)、[插件开发](https://github.com/AnomalyNTE/Anomaly/blob/main/docs/developer-guide/plugin-development.md)。

- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/README.md
- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/interop-and-memory.md
- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/api-reference/nte-services.md
- https://github.com/AnomalyNTE/Anomaly/blob/main/docs/developer-guide/plugin-development.md
- https://github.com/AnomalyNTE/Anomaly

### 2026-10-22：用户游戏进程只读连通性检查

- 当前进程列表中 `HTGame` PID 32164 与 `KekeDecompositionLoader` PID 33680 均仍在运行。对 `BridgeClient.status(32164)` 做了一次实机状态查询；协议 `op=1` 只返回状态，不进入发送分支。结果为 `ready=false`，命名管道 `KekeDecompose-32164` 未连接。
- 当前加载日志确认加载器匹配 x64、同会话、高完整性目标；`SetWindowsHookExW` 返回 hook 句柄，并成功向游戏 HWND/线程投递 WM_NULL。10 秒后模块快照正常（226 个模块），但没有观察到 `KekeDecompositionBridge.dll`，也没有桥接日志。因此请求没有进入游戏线程，分解发送器未调用。
- 最近 12 小时的 Code Integrity、Defender 和 AppLocker 日志中未找到包含 `HTGame`、`KekeDecompositionBridge`、PID 32164 或 PID 33680 的记录。现有证据不能断言是代码完整性策略拦截，也不能判断目标线程为何没有加载 hook DLL。
- 没有发现名为 Anomaly 的运行进程；本机公开 SDK 调查仍未发现支持任意 `ServerComposeRPC` 直接调用的服务。
- 本轮未发送 `op=2`，没有分解任何物品。直发 RPC 仍未能在当前游戏进程中实际运行；原因未知，不能称为修复完成。
### 2026-10-22：自建直发路线判断

复核后找到一条保留直发 RPC 的可维护实现方向：扩展 Anomaly NTE Adapter，由 Anomaly Host 提供版本/Profile 校验过的 inventory/decompose 语义服务。桌面助手传入冻结的单件 UID、经验/倒带模式和库存修订；Host 在 Game 域排队执行，并在结果确认阶段核对库存与材料变化。这样调用执行仍由游戏进程内宿主负责，Keke 不需要另行加载自有 DLL。

此路线需要 Anomaly Host 维护者增加服务，或维护者授权的 Host fork；不是当前公开 SDK 已有的任意 RPC 调用功能。SDK 文档说明插件 `on_update` 在 Game 域执行，但也明确插件不应直接调用 UE `ProcessEvent`、扫描对象或直接调用 UI 按钮函数。单独写 Anomaly 插件并从中调用私有 RPC 仍不属于受支持接口，不能作为已解决方案。另一条上游路线是让 NTE Calculator Core 正式增加带显式材料模式的分解动作并更新签名插件。

对目前 Windows `WH_GETMESSAGE` 桥接，现场只证明 hook 注册/消息投递成功、目标模块未观察到；源码审阅无法确定具体根因。当前不再以其他注入/映射办法绕过，也没有加载或发出分解请求。该设计尚未提交给上游、实现或实测，因此不代表现在已有可用分解功能。

### 用户纠正：以可可助手为产品边界（2026-10-22）

用户明确不再考虑 Calculator 路线。上一节把外部 Host/计算器支持放在主路线，是偏离当前目标；这里修正：可可助手自己的分解 sender 已经构造游戏请求并调用已定位的 `ServerComposeRPC`，因此不能说“无法实现”或把缺少第三方 `set_item_decompose` 端点当成根本障碍。用户可见的装卸、锁定和弃置均属于可可助手功能，但当前装卸通过内置原生组件端点执行；它不等于自有 raw sender 已经有一个可运行的游戏线程执行器。

当前真正未解决的点是：可可助手自有 `KekeDecompositionBridge.dll` 尚未被游戏模块快照观察到，sender 因而没有运行。源码和日志还不能确定 DLL 未映射的唯一根因。后续分析以 Keke 自有 sender/bridge 和可验证执行宿主为范围，不再把 Calculator 当作解决方案；也不以换一种未授权加载/映射方式绕过当前失败。当前没有向游戏发送分解请求。
