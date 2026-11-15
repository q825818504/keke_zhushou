# 原生分解发送模块

当前目录包含Windows x64发送模块、独立测试桥接DLL和Windows加载器。助手端加载、检测、单件材料确认及库存回读入口已接入源码，尚未实机验证。加载不会自动分解。原发送DLL仍仅导出 `KekeSubmitNativeDecomposition`；测试桥接额外导出 `KekeBridgeHook`。

## 测试桥接

- `loader.cpp`：核对游戏版本和桥接DLL哈希，创建限当前用户/SYSTEM的会话文件，通过Windows线程消息钩子加载独立桥接；安装后向目标游戏窗口句柄及线程队列投递 `WM_NULL` 唤醒消息；不修改现有第三方插件或签名规则。
- `bridge.cpp`：使用现有宿主导出的OpenOwner/ProcessEvents::Observe接口观察真实ReceiveTick，仅在确认其线程与游戏窗口线程一致后启用派发。接口缺失或拒绝时不就绪，不绕过拒绝。
- 游戏Tick或已确认线程的消息泵处理单件请求。单独的私有命名管道使用当前用户ACL、随机会话密钥和游戏服务器PID核验；管道工作线程不发送游戏请求。
- 游戏分解页必须只选中同一个UID。助手端另做最新完整库存、游戏账号、锁定/装备和保存方案引用检查。不是OCR点击分解。
- DLL在游戏进程内固定至游戏退出，避免回调悬空。出现加载/会话异常后应重启游戏再测试，不支持热替换。

## 给用户的测试步骤

1. 使用独立测试EXE，开启风险模式，完整读取当前账号的DLL库存。
2. 背包管理点击“加载分解桥接”，确认UAC，然后“检测桥接”。若等待Tick，回到游戏场景活动几秒再检测。
3. 当前诊断包只检查桥接，不需要在助手或游戏里选物品。桥接未显示就绪时停止操作，不选择物品，也不点击任何分解按钮。
4. 只有桥接通过游戏环境核验后，才安排单件测试；测试目标和材料去向须在操作前明确确认。
5. 只有单件流程经过用户明确批准后，才记录装备消失及全物品数量变化。尚未确认材料定义ID，不会把无关材料增加或发送返回当作产物结算成功。出现结果不明时不重发，保留日志。

入口为 `dist/windows/test-v1.7/KekeAssistant.exe`。加载日志位于助手数据目录 `player-inventory/native-decomposition/<组件版本>/` 的loader.log及bridge-PID.log；操作审计在库存目录decomposition-operations。实际库存根目录以接口返回audit_path/log_directory为准。

`SubmitOnGameThread`包含实际游戏消息构造与发送调用，因此不得用于只读诊断。只有宿主接入完成、用户明确批准具体测试物品和材料去向后才可调用。本次研究仅编写源码，没有调用。

## 已实现

- 显式经验/倒带枚举，缺少或无效值拒绝执行。现场对照：经验=true、倒带=false。
- 当前游戏可执行文件SHA256与五个运行时代码段完整字节校验；不接受旧版本偏移。
- 游戏分配器创建8字节UID数组，真实构造器消费数组，真实ServerComposeRPC包装器派发，按游戏代码释放消息参数。
- 初始只接受单件。请求ID在调用前消耗且不自动回收，结果不明不自动重发。
- 仅返回“已派发、结果未确认”，不会把函数返回当成分解成功。

## 桥接职责

1. 在可信游戏线程上下文调度；实现真实线程检查，不得恒返回true。
2. 根据最新账号/快照修订重新核对UID，拒绝已装备、已锁定、方案引用或状态未知的物品；风险模式须开启。
3. 返回经引擎类型及当前账号核实的PlayerState实例，不能用类默认对象。
4. 处理服务端回执、库存删除及材料增量；处理未确认状态，禁用自动重试。
5. 在UI呈现实际目标和“分解为经验材料/倒带材料”的不可逆确认；获得用户批准后才交给此模块。
6. 采用可维护的授权组件构建/装载方式。不得修改现有第三方签名校验来加载本模块。

`MessageContractChanged`要求停止当前会话排查，不能继续请求；该异常路径故意不猜测未知布局的释放方式。模块不是跨版本SDK。

## 构建

需要Windows x64 C++17工具链、Windows SDK、CMake 3.24+。在VS x64开发环境运行：

```powershell
cmake -S native/decomposition -B build/native-decomposition -A x64
cmake --build build/native-decomposition --config Release
```

版本指纹由`scripts/export_cleanup_native_profile.py`从已核实的只读报告生成，导出不连接游戏、不执行函数。构建不会加载进游戏。

本机使用从官方ziglang.org下载并核对官方SHA256的便携Zig 0.14.1，依赖和缓存均位于忽略提交的build目录。运行 `py -3 scripts/build_cleanup_native.py` 可重新生成版本指纹、编译Windows x64 DLL并离线核对导出表。产物在 `build/native-decomposition/KekeNativeDecomposition.dll`，编译记录为同目录 `build-report.json`。

当前已完成编译和助手端源码接入，没有加载DLL、调用导出函数或实机验证。独立DLL采用C链接导出，跨工具链宿主应使用相同头文件、Win64布局和不抛异常的回调；不要传递STL对象。现有第三方Core/签名插件未改动。

完整独立测试包使用 `.venv-ocr/Scripts/python.exe scripts/build_decomposition_test.py` 构建，保留现有OCR依赖。普通build默认不带分解测试组件，只有显式native_decomposition=True才打入桥接及加载器。

## 2026-10-22：独立内存路线与桥接验证边界

用户要求不依赖 Calculator 的既有白名单。当前可控的自有路径已经存在：助手本地 `DecompositionService` 接收显式材料和单件 UID，`KekeNativeDecomposition.dll` 按当前游戏版本构造 `EquipDecompose_Request` 并调用游戏内 `ServerComposeRPC`；因此无需把 `equipment.set_item_decompose` 加进第三方 Core 白名单。后者只是另一个客户端 RPC 名称，不能自行创建后让未修改的 Core 接受。

剩下的接入点是让这个版本校验过的发送器在正确的游戏线程运行。当前诊断包用 `WH_GETMESSAGE` 加载桥接 DLL，并把唤醒消息投递给目标 HWND 和线程队列。Codex 隔离桌面的离线探针得到 `mapped=0 callback=0 post=1 retrieved=1 received=1`，最小控制 DLL 也未映射；这说明隔离桌面不能验证跨进程 hook，既不能证明普通桌面或游戏必然失败，也不能宣称桥接已修好。没有发起游戏请求。

公开 Anomaly SDK 额外提供 `anomaly.nte.ui-buttons`，由其宿主在游戏 tick 调用控件自身点击处理器；这是一个非 OCR 的原生 UI 流程候选，但不暴露 `UFunction` / `ServerComposeRPC`，所以不替代当前直发 RPC 路线。该项目 README 也明确说明内存读写/hook/patch 的风险及公平游戏限制。没有把 UI 点击服务或未授权加载方式悄悄替换进当前功能。

当前构建仍是桥接诊断包，不是已验证可用的分解版本。用户已在游戏中实测：加载器安装钩子并成功投递 HWND 与线程 `WM_NULL` 后，等待10秒仍未观察到桥接模块或回调日志。`SetWindowsHookEx` 返回钩子句柄不等于目标 DLL 已加载；当前证据无法区分目标线程未触发钩子与目标侧未完成映射。不得点击分解。需要受支持的游戏内宿主/插件调用入口，或进一步取得能区分这两种状态的非侵入式证据；不能把换一种加载器说成已修复。
