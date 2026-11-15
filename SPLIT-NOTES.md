# 可可助手 · 用户端源码仓

来源：`D:\keke_zhushou` 单仓工作树快照（HEAD `4237d1d`，含当时未提交改动），2026-11-15 拆分。
本仓只承载**用户端**（Windows 用户安装包 / `KekeAssistant.exe`）所需的源码与构建链。

## 边界（依据源码，不是约定俗成）

| 依据 | 内容 |
|---|---|
| `desktop/build.py:38-65` | 用户包取用的根文件清单（由 `prepare_public` 显式复制，不是整仓打包） |
| `desktop/prepare_public.py:25-110` | 用户页面重建：裁剪 `#userExperienceView`、重写脚本顺序、只收被引用的本地图片 |
| `desktop/compile_user.cjs:55-57` | 用户端 `app.js` 闭包编译，出现 `KekeAdminBridge/showRoleManagement/bindSave/guideCanLeave` 即构建失败 |
| `desktop/build.py:99-104` | 用户 EXE 禁止包含 `admin_server/admin_entry/build_*_bundle/release_*/build_release` 模块与 `admin_bridge/team_manager/.git` |

**本仓不含**（在 `keke-manage` 私有仓）：`desktop/admin_entry.py`、`scripts/admin_server.py`、`scripts/start_admin.ps1`、`desktop/release_credentials.py`、`release_publish.py`、`release_lifecycle.py`、`build_release.py`、`scripts/build_character_overrides_bundle.py`、`scripts/build_team_templates_bundle.py`、`scripts/check_admin_*`、`scripts/check_release_*`、`desktop/releases/v*.md`（维护备案）、`.planning/`、`skills/`。

`admin_bridge.js`、`team_manager.js`、`index.html` 保留在此：它们被 `index.html` 引用，是页面的一部分；管理桥只在 `127.0.0.1` 管理服务下才 `ready`（`admin_bridge.js:4-5`），用户包构建时不会进入 `app.js` 闭包。

## 构建用户端

```powershell
# 依赖（一次性）
py -3.12 -m venv .venv-ocr
.venv-ocr\Scripts\python.exe -m pip install -r desktop/requirements-ocr.txt
npm.cmd --prefix desktop ci
.venv-ocr\Scripts\python.exe scripts/prepare_vision_models.py     # OCR 权重，不进 Git
.venv-ocr\Scripts\python.exe scripts/prepare_native_components.py # 第三方 Core/DLL，不进 Git

# 构建
.venv-ocr\Scripts\python.exe desktop/build.py user --dist-dir dist/windows/final
```

## 检查

```powershell
node scripts/smoke_check_app.js                 # 已知红：Exe 缺专属图标（资料站无素材）
node scripts/check_team_recommendations.js      # 已知红：纯辅助池编出主C
node scripts/check_dual_team_recommendations.cjs
node scripts/check_esper_cycles.js              # 已知红：强化被动 23 断言写死 20
node scripts/check_unified_save.js
```

Python 检查一律用 `.venv-ocr\Scripts\python.exe`（系统 3.13 缺 `mss`/`cv2`，会把检查伪装成全红）。

## 发行通道

程序与配置不发本仓：Gitee `Alime17/koko-assistant-update` 只维护 `README.md`、`channels/*.json`、`metadata/**` 与许可说明，二进制走发行附件。发布工具在 `keke-manage`。

## 认证方式（不走账号登录）

远端统一用令牌，不弹账号密码框：

```powershell
git remote set-url origin https://x-access-token:<PAT>@github.com/q825818504/keke_zhushou.git
git config credential.helper ""      # 禁止凭据管理器接管/弹窗
$env:GIT_TERMINAL_PROMPT = "0"       # 认证失败即报错，不阻塞
```

PAT 需要 `Contents: Read and write`，且本仓库要被勾进该 token 的 `Repository access`。令牌明文只存在于本机 `.git/config`，不要把带令牌的目录打包外发。

## 数据纪律

改 `data/knowledge/*.json` 后，浏览器用的 `*.js` bundle 需在管理端仓用 `scripts/build_*_bundle.py` 重建；未知游戏数值一律保留「待补充」，不跨来源合并（原生 UID / OCR 批次 / 本机手动补录三者身份不同）。
