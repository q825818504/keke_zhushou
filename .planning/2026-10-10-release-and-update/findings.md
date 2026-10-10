# Findings & Decisions

## Requirements
- GitHub 继续维护应用源码与管理配置；管理端维持独立 EXE，可从本机维护并远程发布公共配置。
- 用户端改成 Windows 安装发行，安装后展开程序、依赖和公共配置。
- 首次正式版本 v1.0，每次重新正式发行增加 minor：v1.1、v1.2；配置独立版本。
- Gitee 指定仓库 https://gitee.com/Alime17/koko-assistant-update.git 仅放发布元数据、公共配置、图片、安装/更新产物，不放应用源码。
- 每次启动检查版本：检查失败或检测到新版本未安装，禁止进入主界面。
- 每次启动更新公共配置：更新失败允许使用上次完整缓存或随安装包提供的配置。此条替代用户此前要求全部严格联网的回复。

## Research Findings
- desktop/build.py 当前 user/admin 均为 PyInstaller onefile，未做 installer 或启动联网更新。
- prepare_public.py 将配置 .js 与程序 .js 及图片一起打包，public-manifest 全资源散列但版本硬编码 0.1.0；程序/公共数据需拆分。
- user_entry.py 目前直接进入窗口，runtime.py 优先读取本机 admin-workspace.json 指向的 Git 工作副本，否则读取内置 public。
- 当前最终 EXE 172694591 字节（约165 MiB）。Gitee 官方社区版 Git 单文件50MB、仓库500MB；附件单文件100MB、单仓库附件1GB，不能承诺整个离线安装包直接作为一份附件上传。
- 未检测到已安装的 Inno Setup 编译器；installer 技术方案需独立准备。
- 匿名Git读取指定Gitee仓库成功（禁用credential helper和终端提示），退出0且无refs；仓库当前为空，Raw版本和附件的匿名下载尚不能验证。
- Inno Setup官方文档确认DiskSliceSize配合DiskSpanning控制分卷大小；PrivilegesRequired=lowest支持非管理员安装模式。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 发布成功后才推进版本，失败重建不增加 | 避免测试构建和失败构建消耗版本；版本使用整数分段比较。 |
| 公共配置 JSON 与图片数据包 | 不把动态下载的配置作为任意 JS 执行，不上传源码配置 .js 到 Gitee。 |
| 独立更新入口与签名发布清单 | 程序需要退出后替换，不能自覆盖运行中的 EXE；仅SHA256不足以认证发布来源。 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Gitee匿名版本接口/附件下载未验证 | 后续真实发布前验证；不得内置仓库写入令牌到用户端。 |

## Resources
- https://help.gitee.com/questions/Gitee%E4%BA%A7%E5%93%81%E9%85%8D%E9%A2%9D%E8%AF%B4%E6%98%8E （本次已打开并核实）
- desktop/build.py、desktop/prepare_public.py、desktop/runtime.py、desktop/user_entry.py、desktop/admin_entry.py。
