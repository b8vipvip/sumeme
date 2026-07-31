# SuMeMe Android / Windows 原生客户端

本目录保存 SuMeMe 第一方 Flutter 客户端源码。Android 和 Windows 平台工程由
`scripts/materialize-flutter-client.py` 在构建时从当前 Flutter stable 模板生成，避免长期提交大量平台模板文件。

## 0.3 产品边界

- Android 与 Windows 共用一套 Flutter 业务代码；
- 主界面全部由 Flutter 原生组件绘制，不使用 WebView 承载产品 UI；
- 不打包 LobeHub 页面、静态资源或本地回环 HTTP 代理；
- 客户端与 `https://sumeme.mv3.cn` 服务端独立部署；
- 模型、聊天、记忆、Vault 和对象请求统一走 `/api/gateway`；
- Gateway 与管理员凭据写入 Android Keystore 或 Windows Credential Manager；
- 本机会话索引与界面设置通过 `shared_preferences` 保存；
- 客户端不包含服务器 `.env`、中转站密钥、Docker 凭据或对象存储密钥。

## 原生界面

当前信息架构包括：

1. 首页：服务状态、记忆引擎、当前 Vault、最近对话；
2. 对话：会话列表、流式消息、模型/Vault 信息、长期记忆开关；
3. 记忆：自然语言检索与作用域结果；
4. 资料库：私有对象列表、类型与状态；
5. Vault：local-only、cloud、hybrid 三种策略；
6. 同步：设备、任务与可信身份迁移状态；
7. 设置：服务器、凭据、账户、模型、隐私和外观。

Windows 使用侧边 NavigationRail 和宽屏多栏布局；Android 使用底部 NavigationBar、抽屉和窄屏页面。

## 当前可用接口

客户端已经接入：

- `GET /sumeme-health`
- `GET /api/gateway/v1/models`
- `POST /api/gateway/v1/chat/completions`（流式）
- `POST /api/gateway/api/memory/search`
- `POST /api/gateway/api/vaults/list`
- `PUT /api/gateway/api/vaults/policy`
- `POST /api/gateway/api/objects/list`

附件选择、分片上传、异步解析、逐条记忆编辑/删除、可信用户登录、本地加密 Vault 和增量同步仍是后续开发阶段；界面已为这些功能预留入口，但不会伪装成已经完成。

## 本地生成

安装当前 Flutter stable SDK、Android 工具链，以及 Windows 上的 Visual Studio 2022 Desktop development with C++ workload。

```bash
python scripts/materialize-flutter-client.py \
  --output .generated/sumeme_app
cd .generated/sumeme_app
flutter analyze
flutter test
```

构建 Android：

```bash
flutter build apk --release
```

构建 Windows：

```powershell
flutter build windows --release
```

## GitHub 构建产物

`.github/workflows/build-clients.yml` 在 Linux 和 Windows Runner 上分别构建：

- `sumeme-android-apk`：开发签名 release APK 与构建来源信息；
- `sumeme-windows-x64`：Windows 安装版 EXE、便携版 ZIP 与构建来源信息。

构建来源文件会明确记录：

```text
ui=native-flutter
webview=false
```

正式公开发行仍需要受保护的 Android release keystore、Windows Authenticode 签名和自动更新签名校验。
