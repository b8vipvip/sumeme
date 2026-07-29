# SuMeMe

SuMeMe 是一个面向个人长期记忆的多模态 AI 系统。它使用 LobeHub 作为 Android / Web / Windows 的统一入口，通过 OpenAI 兼容的 `memory-gateway` 调用你的 AI 中转站，并同时维护两类记忆：

- **MemPalace**：逐字保存原始对话和附件描述，避免细节被摘要丢失。
- **Letta**：提取人物、项目、偏好、事件、关系和时间变化，形成可持续更新的结构化记忆。

```text
Android PWA / Web / Windows
            │
            ▼
         LobeHub
   对话、附件、账号、同步
            │ OpenAI-compatible
            ▼
      memory-gateway
       ├─ 召回 MemPalace 原文
       ├─ 召回 Letta 结构化记忆
       ├─ 注入当前请求
       └─ 转发至 AI 中转站
            │
            ▼
        多模态模型
```

## 当前阶段

本分支提供第一阶段可部署骨架：

- LobeHub、PostgreSQL、Redis、RustFS、Qdrant、Letta、memory-gateway 的 Docker Compose 编排；
- OpenAI 兼容的 `/v1/models` 与 `/v1/chat/completions` 网关；
- 非流式和流式对话转发；
- 从本轮消息召回双记忆并注入系统上下文；
- 将本轮原始消息写入 MemPalace；
- 通过 Letta Agent 维护结构化个人记忆；
- 宝塔 Nginx 反向代理模板；
- `/opt/sumeme` 部署、更新、备份脚本；
- 基础单元测试和 GitHub Actions。

## 重要限制

1. **当前版本不修改 LobeHub 上游源码。** LobeHub 只需把 OpenAI Base URL 指向 `memory-gateway`，因此后续可独立升级。
2. **原始附件由 LobeHub/RustFS 保存。** 当前网关保存附件元数据、URL和模型可见描述；直接读取 LobeHub 数据库并对历史附件做离线解析属于第二阶段。
3. **MemPalace 当前使用其官方本地 embedding 模型。** 这不是本地聊天大模型，但仍会占用约数百 MB。若你要求 embedding 也必须走中转站，需要在第二阶段实现 OpenAI-compatible embedding provider。
4. **Letta 适配器默认容错降级。** Letta 未完成 Agent 初始化时，对话仍可走中转站，日志会记录跳过原因。
5. 仓库是公开的。任何 API Key、密码、JWKS、证书私钥都只能写入服务器上的 `.env`，不能提交到 GitHub。

## 快速部署

服务器需要 Docker、Docker Compose v2、Git、OpenSSL。建议在宝塔终端以 root 执行：

```bash
cd /opt
git clone git@github.com:b8vipvip/sumeme.git
cd sumeme
git checkout agent/bootstrap-sumeme

cp .env.example .env
bash scripts/generate-secrets.sh
nano .env
```

至少填写：

```dotenv
OPENAI_RELAY_BASE_URL=https://你的中转站地址/v1
OPENAI_RELAY_API_KEY=你的中转站密钥
OPENAI_CHAT_MODEL=你的主对话模型
OPENAI_MEMORY_MODEL=用于记忆整理的模型
OPENAI_EMBEDDING_MODEL=中转站支持的 embedding 模型
S3_ENDPOINT=https://s3.sumeme.mv3.cn
```

启动：

```bash
docker compose pull
docker compose build memory-gateway
docker compose up -d
docker compose ps
curl http://127.0.0.1:8010/health
```

然后在宝塔网站 `sumeme.mv3.cn` 中导入 `deploy/baota-nginx.conf` 的反代配置。

附件上传建议增加一个独立域名 `s3.sumeme.mv3.cn`，解析到同一 VPS，并在宝塔申请证书后使用 `deploy/baota-s3-nginx.conf`。官方 LobeHub 的对象存储端点需要浏览器可访问，否则聊天附件上传会失败。

完整步骤见 [宝塔部署文档](docs/deployment-baota.md)。

## 开发

```bash
cd services/memory-gateway
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload --port 8000
```

## 上游项目策略

本仓库不复制三个上游仓库的完整源码，而是通过镜像和 Python 包依赖接入，并在 `.env` 中允许固定版本。这样可以：

- 保留清晰的许可证边界；
- 独立升级 LobeHub、MemPalace、Letta；
- 避免把几十万行无关上游代码塞入本仓库；
- 将我们的核心改动集中在 `memory-gateway` 与部署编排层。

详情见 [上游与许可证](docs/upstreams.md) 和 [系统架构](docs/architecture.md)。
