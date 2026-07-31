# SuMeMe

SuMeMe 是一个面向个人长期记忆的多端、多模态 AI 系统。产品由两个独立部分组成：

- **SuMeMe 原生客户端**：Android 与 Windows 共用 Flutter 代码，负责对话、记忆检索、资料、Vault、同步和本地设置；
- **SuMeMe 服务端**：部署在用户自己的服务器，通过 `sumeme.mv3.cn` 提供 Web 管理后台、模型网关、记忆、对象存储和运维能力。

客户端不再使用 WebView 承载主界面，也不打包第三方聊天产品的页面。服务端根入口由 SuMeMe 自己的 `sumeme-web` 提供。

所有生成式 AI、Embedding、OCR、视觉、转写和记忆提取只允许使用 OpenAI-compatible 中转站或明确批准的厂商官方 API。项目禁止加载本地 AI 模型和模型权重。

## 当前架构

```text
Android / Windows 原生 Flutter 客户端
                     │ HTTPS
                     ▼
          https://sumeme.mv3.cn
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
   sumeme-web              memory-gateway
 服务端管理后台       身份、Vault、记忆、对象、聊天
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
          MemPalace           Letta          RustFS / Qdrant
          原文记忆          结构化记忆       对象与向量索引
                                │
                                ▼
                       ai-provider-proxy
                                │
                                ▼
                    OpenAI-compatible 中转站
```

LobeHub 容器目前仅作为历史数据迁移兼容服务保留，不提供公网入口，也不再承担产品 UI。完成会话与账户数据迁移后可以从运行架构中移除。

持久化组件：

- PostgreSQL：历史应用数据和迁移来源；
- Redis：缓存与任务辅助；
- RustFS：附件与私有 Vault 对象；
- SQLite：MemPalace 原文 drawer 与 Vault Registry；
- Qdrant：向量、drawer ID 和服务端作用域元数据；
- Letta：结构化长期记忆。

完整说明见 [`docs/architecture.md`](docs/architecture.md)，原生 UI 设计见 [`docs/ui-native-redesign.md`](docs/ui-native-redesign.md)，当前进度见 [`docs/development-progress.md`](docs/development-progress.md)。

## 原生客户端

客户端源码位于 [`clients/sumeme_app`](clients/sumeme_app)。当前 0.3 信息架构：

1. 首页：服务连接、记忆引擎、当前 Vault、最近对话；
2. 对话：本机会话列表、模型选择、流式回答、长期记忆开关；
3. 记忆：自然语言检索与作用域结果；
4. 资料库：私有对象列表、类型和处理状态；
5. Vault：`local-only`、`cloud`、`hybrid` 策略；
6. 同步：设备、任务、冲突和可信身份状态；
7. 设置：服务器、凭据、账户、模型、隐私和外观。

Windows 使用侧边导航与宽屏多栏布局；Android 使用底部导航、抽屉和窄屏路由。敏感凭据保存到 Android Keystore 或 Windows Credential Manager，本机会话索引与界面设置保存在设备上。

生成和测试：

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

## 服务端 Web 管理后台

`web/server-ui` 是独立 Nginx 服务，绑定服务器本机 `127.0.0.1:3210`，由宝塔/Nginx 反向代理到 `sumeme.mv3.cn`。

页面包含：

- 服务与记忆能力总览；
- 记忆检索；
- 私有对象列表；
- Vault 策略；
- 模型与中转站状态；
- 安全的运维摘要；
- 当前浏览器会话凭据设置。

浏览器凭据只进入 `sessionStorage`，关闭标签页后清除。服务器 `.env`、中转站密钥、Docker 凭据和对象存储密钥不会下发到页面。容器重启、回滚、备份恢复和删除操作在管理员身份、二次确认与审计日志完成前不开放。

公开入口：

```text
/                   SuMeMe 服务端管理后台
/sumeme-health      公开健康状态
/api/gateway/*      经过同源反向代理的受保护 API
```

## 当前服务能力

- OpenAI-compatible `/v1/models` 与 `/v1/chat/completions`；
- 流式和非流式聊天；
- 每轮对话前并发召回 MemPalace 原文与 Letta 结构化记忆；
- 成功回答后写入 MemPalace，并尝试更新 Letta；
- `account_id + vault_id + principal_type` 服务端作用域；
- `local-only`、`cloud`、`hybrid` 三种 Vault 策略；
- 私有对象预签名上传、完整性校验、短时下载与安全删除协议；
- GHS 自动部署、磁盘预检、健康检查、业务 smoke、快照和回滚；
- 受限日志读取与流式密钥脱敏；
- Flutter、Python、Shell、Compose、容器和公网 UI 自动测试。

## 记忆实现

### MemPalace 原文记忆

- 完整原文保存到 `gateway-data` 中的 SQLite；
- Qdrant payload 不保存用户原文；
- Qdrant 查询强制匹配服务端 `scope_key`；
- SQLite 读取再次校验账户与 Vault；
- UUIDv5 point ID 使重复 checkpoint 幂等；
- Embedding 通过内部 `ai-provider-proxy` 获取。

当前生产使用：

```dotenv
EMBEDDING_PROVIDER_MODE=remote-semantic-hash
```

远程模型提取规范化语义标签，本地只执行确定性 feature hashing，不加载任何机器学习模型。

### Letta 结构化记忆

```dotenv
LETTA_IMAGE_PIN=letta/letta:0.16.8
LETTA_REQUIRED=false
```

MemPalace 是当前必需的持久原文组件；Letta 保持可观测但可选。Letta 失败会产生稳定错误码和 degraded 状态，不阻止聊天入口启动。

默认 Provider：

```dotenv
MEMORY_PROVIDER=mempalace-letta
```

备用 Provider：

```dotenv
MEMORY_PROVIDER=supermemory
```

切换必须显式进行。禁止自动 Provider failover 和 dual-write，以免产生不可审计的记忆分叉。

## 身份与 Vault

支持的身份模式：

```text
legacy-client-asserted
trusted-openai-user
jwt-preferred
jwt-required
```

正式多账户部署应使用 `trusted-openai-user` 或经过验证的 JWT。JWT 模式从签名后的 `issuer + sub` 派生内部 `account_id`，客户端不能自行指定真实账户边界。

Vault 策略：

- `local-only`：网关可以代理聊天，但不从服务端记忆召回或自动写入；
- `cloud`：服务端正常召回和自动持久化；
- `hybrid`：允许云端召回，但原始聊天不自动持久化，只接受显式脱敏 checkpoint。

加密本地 Vault、本地全文索引、混合脱敏同步和冲突解决仍在开发队列中。

## 配置与启动

服务器需要 Docker、Docker Compose v2、Git、rsync、curl、Python 3 和 OpenSSL。

```bash
cd /opt
git clone git@github.com:b8vipvip/sumeme.git
cd sumeme
git checkout main
cp .env.example .env
bash scripts/generate-secrets.sh
nano .env
```

至少配置：

```dotenv
OPENAI_RELAY_BASE_URL=https://你的中转站地址/v1
OPENAI_RELAY_API_KEY=你的中转站密钥
OPENAI_CHAT_MODEL=你的主对话模型
OPENAI_MEMORY_MODEL=用于语义提取和记忆整理的模型
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
GATEWAY_API_KEY=随机高强度密钥
GATEWAY_ADMIN_TOKEN=随机高强度密钥
GATEWAY_SERVICE_TOKEN=仅供可信后台任务使用的随机密钥
S3_ENDPOINT=https://你的对象存储域名
```

不要把 `.env`、密钥、密码、私钥或真实用户内容提交到 GitHub。

本地启动：

```bash
docker compose config
docker compose pull
docker compose build sumeme-web memory-gateway ai-provider-proxy
docker compose up -d
docker compose ps
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:3210/healthz
```

宝塔与 Nginx 配置见 [`docs/deployment-baota.md`](docs/deployment-baota.md)。

## 自动部署

正式生产模式为 **GHS — GitHub-hosted SSH**。GitHub-hosted Runner 检出经过 CI 的精确提交，通过固定 Host Key 的 SSH/rsync 上传 staging，并调用受审查的 `scripts/deploy-production-v2.sh`。

`.env`、数据库、对象存储、Docker volumes 和备份只保留在 VPS。VSR 仅作为显式备用流程，禁止在一次发布中静默切换。

生产发布包含：

- 部署互斥锁；
- 磁盘空间预检与安全清理；
- 精确提交和代码快照；
- 本地运行时镜像构建；
- 容器、HTTP 和原生 SuMeMe UI 健康检查；
- 隔离 service identity 的业务 smoke；
- 失败诊断、自动回滚和发布历史。

## 开发与测试

```bash
# memory-gateway
cd services/memory-gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check app tests
PYTHONPATH=. pytest -q
python -m compileall app

# 运维契约与 Compose
cd ../..
python -m compileall scripts tests
python -m unittest discover -s tests -v
bash -n scripts/*.sh
cp .env.example .env
docker compose config
```

## 尚未完成

当前原生 UI 和可用 API 已经建立，但以下功能不会伪装成完成：

- 正式可信账户登录与设备令牌；
- 本地加密 Vault 和离线全文索引；
- attachment-worker、分片上传与异步解析；
- 图片、音频、视频、PDF、Office 的远程 AI 解析；
- 逐条记忆来源、查看、编辑、删除、时间线和关系图；
- Hybrid 增量同步、冲突解决与后台任务；
- Android 系统分享入口、Windows 文件投递；
- Android 正式签名、Windows Authenticode 和自动更新。
