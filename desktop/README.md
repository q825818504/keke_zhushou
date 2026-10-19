# 可可助手 Windows 桌面版

正式发行改为联网安装器，构建与发布见 [RELEASE.md](RELEASE.md)。当前用户安装入口为 `dist/windows/final/KokoAssistantSetup-v1.6.exe`，Gitee首版已通过匿名下载验证；管理端保持单EXE。
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

V1.6 本地测试运行 `.venv-ocr/Scripts/python.exe scripts/build_v16_test.py --revision 4`，输出 `dist/windows/test-v1.6-r4/KekeAssistant.exe`；构建并校验成功后仅保留最新测试包。正式发行另用 `desktop/build_release.py` 和 `desktop/release_publish.py`。

角色配装 PLUS 保留 DLL 快照与原生装备操作。v1.6 新增的标准「角色配装」从图鉴列出角色（排除塔吉多），单独选择可选 UID 账号和已保存的 DLL 快照 / OCR 历史读取时间，沿用毕业配装求解与评分规则，只用所选快照计算，并按账号、快照及角色在本机保存方案。其游戏配装从方案生成预览后，通过 OCR 角色识别、游戏内筛选、逐件拖放和画面复核逐步执行；每次输入前检查异环仍在前台，并支持停止后续输入。真实游戏内执行需在用户自己的游戏和显示环境中验收。

## 第一版边界

旧版预览程序优先只读管理端所选的本机资料库。新的正式目录版每次启动按 Gitee 签名清单进行程序门禁和公共配置更新，并保留个人设置；配置网络失败可使用缓存或内置资料。源码开发界面与旧预览模式仍保留用于维护。小程序后续适配。

顶栏「保存」保存当前角色所有可编辑资料：基础字段、推荐弧盘、卡带、主/副属性及1–5优先级；基础与推荐在同一文件事务中更新。摆放图选择/移除即时写入，保存会等待尚在进行的写入。攻略阵容页面顶栏保存与「保存阵容」共用表单校验和重复确认。养成计算目标、搜索和筛选不是维护资料，不发布给其他用户。

图鉴资料的来源与 CC BY-NC-SA 4.0 许可在用户包 ABOUT.txt 中保留。对外发行仍须按项目记录核对图像与攻略的许可。

## 背包数据与读取数据

背包数据显示库存统计、已保存的原生快照或OCR批次、详情、纠错和删除。读取数据提供DLL原生读取、截图导入、鼠标全量、NEW增量与手柄全量，并按方式切换采集内容。角色配装单设入口，分为计算配装方案与游戏配装；游戏装备操作复用背包内已保存的DLL原生快照构建意图，并在执行前核对游戏状态。

构建用户版需要Python3.12及`desktop/requirements-ocr.txt`，运行`scripts/prepare_vision_models.py`恢复固定OCR权重；权重不提交Git。原生组件使用固定清单验证的本地资源包，通过`scripts/prepare_native_components.py`准备，第三方Core/DLL不提交源码仓库。构建命令：

    .venv-ocr/Scripts/python.exe desktop/build.py user --dist-dir dist/windows/final

详见[数据来源](../docs/account-data-sources.md)、[OCR接入](../docs/ocr-integration.md)与[功能计划](../docs/plans/inventory-data-collection.md)。源码同步不包含EXE、真实截图或玩家数据。

V1.6 修订 1 引入独立截图路径队列、增量计数、后台检查点以及运行中轻量进度响应。测试包保留策略现以修订 3 为准。

V1.6 修订 2：使用 `scripts/build_v16_test.py --revision 2` 构建到 `dist/windows/test-v1.6-r2/`。新增末页稳定锚点、每格盘面复检/两轮缺块补装，以及 OCR 百分点单位转换与属性图鉴检查；旧扫描数据通过只读视图校验，原始截图和批次不改写。

V1.6 修订 3：PLUS 按账号保存角色装备保护锁；普通游戏配装使用保存的装备快照展示方案。构建命令 `scripts/build_v16_test.py --revision 3`；构建及审计成功后清理仅包含测试 EXE 的旧测试目录，只保留最新测试包，不影响正式版和账号数据。
