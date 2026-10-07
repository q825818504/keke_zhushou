# 可可助手 Windows 桌面版

双击 dist/windows/KekeAssistant.exe 使用用户端；双击 dist/windows/KekeAssistantAdmin.exe 维护资料。
当前正式发行版位于 dist/windows/：KekeAssistant.exe 为用户端，KekeAssistantAdmin.exe 为管理端。重建会更新这两个正式入口；若管理程序正在运行，应先正常退出以便清理旧暂存副本。
保存404修复后，两目录中的常用EXE已统一为新版；此前旧二进制另存为pre-save-fix.exe用于恢复，不要用备份文件日常管理。接口能力会在保存前核对，后台过旧时明确提示更新而不发送无效请求。
它们显示独立 Windows 应用窗口，没有浏览器地址栏或浏览器标签页。界面采用现有资料与交互代码，在 WebView2 中呈现桌面侧栏和工具栏；不是全套 Windows 原生控件重写。

用户版首次打开自动配队。侧栏提供角色、弧盘、空幕、驱动块；Ctrl+1 至 Ctrl+5 切换功能。用户发行资源不包含管理 DOM、资料写入接口、Git 模块、管理脚本或原始来源快照。

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

## 第一版边界

这是未签名的 Windows 桌面预览版。本机用户版优先只读管理版所选资料库的公共知识包与图片，管理版保存后，用户版无需重建或先同步GitHub；已打开的用户版会自动检测变化并刷新，保留个人设置。资料库选择保存在本机应用数据目录，管理版不必保持运行。没有本机管理资料库的普通用户仍读取EXE内置资料；跨电脑在线资料更新尚未配置。小程序后续适配。

顶栏「保存」保存当前角色所有可编辑资料：基础字段、推荐弧盘、卡带、主/副属性及1–5优先级；基础与推荐在同一文件事务中更新。摆放图选择/移除即时写入，保存会等待尚在进行的写入。攻略阵容页面顶栏保存与「保存阵容」共用表单校验和重复确认。养成计算目标、搜索和筛选不是维护资料，不发布给其他用户。

图鉴资料的来源与 CC BY-NC-SA 4.0 许可在用户包 ABOUT.txt 和应用“关于”菜单保留。对外发行仍须按项目记录核对图像与攻略的许可。
