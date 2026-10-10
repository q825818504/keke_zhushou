# 联网安装与更新

GitHub：`https://github.com/q825818504/keke_zhushou.git`，维护完整源码、知识 JSON、图片与发行记录。

Gitee：`https://gitee.com/Alime17/koko-assistant-update.git`，只维护 `README.md`、`channels/*.json`、`metadata/**/*.json` 和许可说明。安装器、程序分块、公共配置分块和运行库分块使用发行附件。不能把主仓库镜像或源码目录上传到 Gitee。

## 使用规则

- 用户运行 `KokoAssistantSetup-v1.0-<hash>.exe` 联网安装，无需 Python、Node 或原版计算器。安装到 `%LOCALAPPDATA%/Programs/KekeAssistant`，建立开始菜单入口。
- 每次启动先验证 Gitee 程序清单的 Ed25519 签名。网络或验证失败只显示重试/退出，不打开主界面。有新版时必须先完成更新。
- 程序门禁通过后检查公共配置。配置下载或验证失败，使用完整缓存或安装包内置配置，并在主界面提示。
- 程序安装到独立版本目录，完整校验后原子切换入口。更新不改动 `%LOCALAPPDATA%/KekeAssistant` 中的个人设置、背包、截图或账号标签。
- 缺少 WebView2/VC++ x64 时从同一签名清单指定的 Gitee 附件下载微软安装文件；VC++ 安装可能需要 Windows 权限提示。游戏插件部署仍由用户在读取页面主动选择。
- 程序版本始于 1.0，成功正式发行后下一候选版本增加次版本号，如 1.1、1.2。配置使用独立 r1/r2；相同内容不重复发布。

## 构建与发布

在维护工作副本中安装 `desktop/requirements.txt` 以及现有 OCR 构建依赖，执行：

```powershell
.venv-ocr/Scripts/python.exe desktop/check_update.py
.venv-ocr/Scripts/python.exe desktop/build_release.py
.venv-ocr/Scripts/python.exe desktop/build.py admin --dist-dir dist/windows/admin
```

完整发行产物位于 `dist/windows/releases/v1.0`，文件清单为 `release-artifacts.json`。首次构建会下载官方 WebView2 x64 完整安装文件及 VC++ x64 安装文件，验证微软 Authenticode 签名后分块。每块 90 MiB，适应 Gitee 每个附件 100 MB 限制。附件总配额有限，发布历史不能无限保留；当前工具不会自动删除线上版本，Gitee 拒绝上传时不会切换最新清单。相同哈希内容在后续发行中复用已核验附件。

打开 `dist/windows/admin/KekeAssistantAdmin.exe`，选择本项目资料库。在“资料同步”中配置具有指定 Gitee 仓库发布权限的个人访问令牌。输入框内容不会写入日志、Git 或用户安装包；发布令牌和 Ed25519 私钥使用维护电脑当前 Windows 用户的 DPAPI 加密保存。

首版及后续程序发行使用：

```powershell
.venv-ocr/Scripts/python.exe desktop/release_publish.py dist/windows/releases/v1.0
```

日常改配置后使用管理端“同步并发布公共配置”：先同步维护资料到 GitHub，然后导出白名单 JSON/引用图片，再发布到 Gitee。导出不执行远端 JavaScript，不包含玩家快照或截图。仅源码/配置树在 GitHub；发行包包含正常运行必需的已编译程序和界面资源，Gitee 不提供开发源码树、管理工具或发布凭据。

发布顺序：上传附件 → 不携带令牌匿名下载并核验全部哈希 → 提交签名 latest 清单 → 匿名核验清单 → 更新本地 `desktop/release-state.json`。成功后应将该发行记录同步 GitHub；中断重试不会提前消耗正式版本号。

`desktop/update-trust.json` 是公开验证密钥，可提交 GitHub。私钥不在源码目录，切勿重生成已有发行身份。换维护电脑需要安全恢复同一个发布私钥；现阶段尚无密钥导入/备份 UI，原维护电脑的 DPAPI 文件不能直接跨电脑使用。

## 当前验收状态（2026-10-11）

已通过17项更新/发布故障路径测试和令牌保存界面测试；最终管理端EXE与正式用户端界面验收均通过。v1.0安装器约15 MiB，首批下载产物约444 MiB。

Gitee首版v1.0已上线，9个下载附件全部经过不携带令牌的完整下载和SHA256校验。当前配置r2；已真实验证匿名签名清单、配置/815图片加载，以及正式打包用户端通过在线门禁并正常显示功能。仓库只包含README、channels与metadata JSON；发行附件包含安装器、程序、公共配置、微软运行库。

可分发联网安装器为 `dist/windows/final/KokoAssistantSetup-v1.0.exe`；线上下载入口：[Gitee发行版](https://gitee.com/Alime17/koko-assistant-update/releases)。管理端仍为 `dist/windows/admin/KekeAssistantAdmin.exe`。

第二台干净Windows从安装器首次安装、真实v1.0→v1.1强制升级仍待跨电脑实机验收；本次没有提前发行v1.1。程序未配置Windows代码签名；清单签名保证更新来源，不能替代Windows发行证书。

微软运行环境说明：[WebView2 分发](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)、[VC++ 运行库](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)。
