# SuMeMe

SuMeMe 是一个面向个人长期记忆的多端、多模态 AI 系统。它以 LobeHub 作为 Android PWA、Web 和 Windows 的统一入口，通过 OpenAI-compatible `memory-gateway` 调用配置的 AI 中转站，并维护两类互补记忆：

- **MemPalace 语义兼容层**：逐字保存原始对话、附件元数据和模型可见描述，避免细节被摘要丢失；
- **Letta**：维护人物、项目、偏好、事件、关系和时间变化等结构化记忆。

所有生成式 AI、Embedding、OCR、视觉、转写和记忆提取只允许使用 OpenAI-compatible 中转站或明确批准的厂商官方 API。项目禁止加载本地 AI 模型和模型权重。

## 当前架构

```text
Android PWA / Web / Windows
            │
            ▼
         LobeHub
  对话、账号、会话、附件
            │ OpenAI-compatible
            ▼
      memory-gateway
      ├─ 身份与 Vault 授权
      ├─ 召回 MemPalace 原文
      ├─ 召回 Letta 结构化记忆
      ├─ 注入受控 memory context
      └─ 转发聊天请求
            │
            ▼
    ai-provider-proxy
    ├─ models / chat / responses
    └─ remote-only embeddings
            │
            ▼
    OpenAI-compatible 中转站
```

持久化组件：

- PostgreSQL：LobeHub 数据；
- Redis：缓存和会话辅助；
- RustFS：附件与私有 Vault 对象；
- SQLite：MemPalace 原文 drawer 和 Vault Registry；
- Qdrant：只保存向量、drawer ID 和服务端作用域元数据；
- Letta：结构化长期记忆。

完整说明见 [`docs/architecture.md`](docs/architecture.md)。当前开发状态、阻塞和下一步队列见 [`docs/development-progress.md`](docs/development-progress.md)。

## 当前能力

- Docker Compose 编排 LobeHub、PostgreSQL、Redis、RustFS、Qdrant、Letta、memory-gateway、ai-provider-proxy 和 SearXNG；
- OpenAI-compatible `/v1/models` 与 `/v1/chat/completions`；
- 流式和非流式聊天转发；
- 每轮对话前并发召回原文与结构化记忆；
- 召回超时按组件快速降级，不让可选记忆无限阻塞聊天；
- 成功回答后写入 MemPalace，并尝试更新 Letta；
- JWT、LobeHub trusted user、service identity 和兼容模式；
- `account_id + vault_id + principal_type` 服务端作用域；
- `local-only`、`cloud`、`hybrid` 三种服务端 Vault 策略语义；
- GHS 自动部署、磁盘预检、健康检查、业务 smoke、快照和回滚；
- 受限生产日志读取与流式密钥脱敏；
- 基础单元测试、Compose 校验、容器构建和 GitHub Actions。

## 记忆实现

### MemPalace 原文记忆

运行时不再依赖 MemPalace 官方本地 ONNX Embedding：

- 完整原文保存到 `gateway-data` 中的 SQLite；
- Qdrant payload 不保存用户原文；
- Qdrant 查询强制匹配服务端 `scope_key`；
- SQLite 读取再次校验账户和 Vault；
- UUIDv5 point ID 使重复 checkpoint 幂等；
- Embedding 通过内部 `ai-provider-proxy` 获取。

当前生产使用：

```dotenv
EMBEDDING_PROVIDER_MODE=remote-semantic-hash
```

远程模型提取规范化语义标签，本地只执行确定性 feature hashing，不加载任何机器学习模型。

### Letta 结构化记忆

当前固定：

```dotenv
LETTA_IMAGE_PIN=letta/letta:0.16.8
LETTA_REQUIRED=false
```

Python SDK 固定为 `letta-client==1.12.1`。MemPalace 是当前必需的持久原文组件；Letta 在生产验收完成前保持可观测但可选。Letta 失败会返回稳定 `letta_*` 错误码和 degraded 状态，不应阻止聊天入口启动。

### Provider 选择

默认：

```dotenv
MEMORY_PROVIDER=mempalace-letta
```

备用：

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

后台 smoke、迁移和任务使用独立 service identity，不与真实用户账户共享作用域。

Vault 存储策略：

- `local-only`：网关可以代理聊天，但不从服务端记忆召回或自动写入；
- `cloud`：服务端正常召回和自动持久化；
- `hybrid`：允许云端召回，但原始聊天不自动持久化，只接受显式脱敏 checkpoint。

目前这是服务端策略基础。加密本地 Vault、本地检索、混合脱敏同步和冲突解决仍在后续开发队列中。

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
docker compose build memory-gateway ai-provider-proxy
docker compose up -d
docker compose ps
curl http://127.0.0.1:8010/health
```

宝塔与 Nginx 配置见 [`docs/deployment-baota.md`](docs/deployment-baota.md)。

## 自动部署

正式生产模式：

> **GHS — GitHub-hosted SSH**

GitHub-hosted Runner 检出经过 CI 的精确提交，通过固定 Host Key 的 SSH/rsync 上传 staging，并调用受审查的 `scripts/deploy-production.sh`。`.env`、数据库、对象存储、Docker volumes 和备份保留在 VPS。

VSR 只作为显式备用工作流存在，禁止在一次发布中静默从 GHS 切换到 VSR。详细协议见 [`ADOB/docs/DEPLOYMENT_MODES.md`](ADOB/docs/DEPLOYMENT_MODES.md)。

生产脚本包括：

- 部署互斥锁；
- 磁盘空间预检与安全清理；
- 精确提交和代码快照；
- 本地运行时镜像构建；
- 容器与 HTTP 健康检查；
- 隔离 service identity 的业务 smoke；
- 失败诊断、自动回滚和发布历史。

## 开发与测试

memory-gateway：

```bash
cd services/memory-gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check app tests
PYTHONPATH=. pytest -q
python -m compileall app
```

Provider Proxy：

```bash
cd services/ai-provider-proxy
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check app tests
PYTHONPATH=. pytest -q
python -m compileall app
docker build -t sumeme-ai-provider-proxy:test .
```

运维契约：

```bash
python -m compileall scripts tests
python -m unittest discover -s tests -v
bash -n scripts/*.sh
cp .env.example .env
docker compose config
```

## 当前限制与路线图

当前正在完成 Phase 1.5：生产闭环、状态新鲜度、磁盘保护、真实记忆写入召回和严格隔离验收。

在进入大规模多模态摄取前，还必须完成：

- 正式账户身份接入；
- Letta Agent 所有权校验；
- RustFS 对象按账户和 Vault 分区及短时签名访问；
- 跨账户读取、搜索、修改、删除、导出和恢复负向测试；
- 完整本地 Vault 与 Hybrid 同步。

后续阶段：

1. attachment-worker 和异步队列；
2. 图片、音频、视频、PDF、Office 的远程 AI 解析；
3. 记忆查看、搜索、编辑、删除、时间线和关系图；
4. Android、Windows 原生封装及系统分享入口。
