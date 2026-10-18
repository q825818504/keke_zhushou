# 可可助手 Windows 桌面版

正式发行改为联网安装器，构建与发布见 [RELEASE.md](RELEASE.md)。当前用户安装入口为 `dist/windows/final/KokoAssistantSetup-v1.0.exe`，Gitee首版已通过匿名下载验证；管理端保持单EXE。
它们显示独立 Windows 应用窗口，没有浏览器地址栏或浏览器标签页。界面采用现有资料与交互代码，在 WebView2 中呈现桌面侧栏和工具栏；不是全套 Windows 原生控件重写。

用户版首次打开自动配队。侧栏提供角色、弧盘、空幕、驱动块、背包数据和读取数据；Ctrl+1 至 Ctrl+7 切换功能。用户发行资源不包含管理 DOM、资料写入接口、Git 模块、管理脚本或原始来源快照。

管理版维护外部项目工作副本。启动时优先打开上次选择的项目，首次启动查找相邻项目；没有找到时弹出文件夹选择窗口。左下角“切换项目资料库”可换电脑上的工作副本。管理数据保存与 Git 同步仍使用已有服务和本机凭据，不往 EXE 内置仓库令牌。

现有浏览器维护数据不会自动进入桌面版。未写入项目的旧数据请先在原页面导出，进入桌面管理版“资料同步”导入，确认后再同步。已写入项目的数据直接读取，构建用户版时包含这些资料。

本地用户设置存放在 LOCALAPPDATA/KekeAssistant/desktop-user；管理版使用 desktop-admin。退出应用后服务随之停止。正常用户端和管理端分别使用仅本机的 8767、8765 端口；没有监听局域网。

## 重建

Windows 电脑需要 Python 3.10+、Node.js（仅构建用户 JavaScript）和 Edge WebView2 Runtime。成品 EXE 内置 Python，运行成品无需安装 Python 或 Node.js。当前电脑已经有 WebView2。

    py -3 -m venv .venv-desktop
    .venv-desktop\Scripts\python.exe -m pip install -r desktop/requirements.txt
    npm.cmd --prefix desktop ci
    .venv-desktop\Scripts\python.exe desktop/build.py all

只重建用户版或管理版，将 all 改为 user 或 admin。生成的 dist、build、虚拟环境和 node_modules 不提交 Git。依赖清单和构建脚本保留在私有仓库。

V1.5 本地测试统一运行 `.venv-ocr/Scripts/python.exe scripts/build_v15_test.py`，固定覆盖 `dist/windows/test-v1.5/KekeAssistant.exe`。成功构建后清理已知旧测试包和空输出目录；不生成新的功能命名目录，不发布，不触碰正式版、账号数据或非空目录中的其他文件。若旧测试版仍运行导致 Windows 锁定 EXE，关闭旧实例后重试清理。

角色配装的毕业计算在 Worker 中按角色优先级搜索最高加权总分与合法盘面，达到搜索预算时明确显示未证实最优。默认排除其他角色占用的空幕和驱动；本角色装备始终参与。计算后每账号每角色可保存一套方案，本机文件位于库存目录 `build-plans/`，使用原生角色实例与稳定装备引用校验。读取后重新解析临时句柄；装备消失、属性改变或占用限制冲突会使方案失效。游戏配装从保存方案生成操作预览，再确认执行自动装配；含空幕和驱动的完整方案通过一次原生批量指令提交，并用最新完整背包快照整体核验。仅驱动或单件操作继续逐件核对；拆卸只针对所选角色的空幕与驱动，停止仅阻止尚未派发的操作。

## 第一版边界

旧版预览程序优先只读管理端所选的本机资料库。新的正式目录版每次启动按 Gitee 签名清单进行程序门禁和公共配置更新，并保留个人设置；配置网络失败可使用缓存或内置资料。源码开发界面与旧预览模式仍保留用于维护。小程序后续适配。

顶栏「保存」保存当前角色所有可编辑资料：基础字段、推荐弧盘、卡带、主/副属性及1–5优先级；基础与推荐在同一文件事务中更新。摆放图选择/移除即时写入，保存会等待尚在进行的写入。攻略阵容页面顶栏保存与「保存阵容」共用表单校验和重复确认。养成计算目标、搜索和筛选不是维护资料，不发布给其他用户。

图鉴资料的来源与 CC BY-NC-SA 4.0 许可在用户包 ABOUT.txt 中保留。对外发行仍须按项目记录核对图像与攻略的许可。

## 背包数据与读取数据

背包数据显示库存统计、已保存的原生快照或OCR批次、详情、纠错和删除。读取数据提供DLL原生读取、截图导入、鼠标全量、NEW增量与手柄全量，并按方式切换采集内容。角色配装单设入口，分为计算配装方案与游戏配装；游戏装备操作复用背包内已保存的DLL原生快照构建意图，并在执行前核对游戏状态。

构建用户版需要Python3.12及`desktop/requirements-ocr.txt`，运行`scripts/prepare_vision_models.py`恢复固定OCR权重；权重不提交Git。原生组件使用固定清单验证的本地资源包，通过`scripts/prepare_native_components.py`准备，第三方Core/DLL不提交源码仓库。构建命令：

    .venv-ocr/Scripts/python.exe desktop/build.py user --dist-dir dist/windows/final

详见[数据来源](../docs/account-data-sources.md)、[OCR接入](../docs/ocr-integration.md)与[功能计划](../docs/plans/inventory-data-collection.md)。源码同步不包含EXE、真实截图或玩家数据。
