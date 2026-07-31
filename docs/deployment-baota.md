# 宝塔面板部署指南

## 1. 产品入口

SuMeMe 服务端由独立的 `sumeme-web` 容器提供 Web 管理后台，并通过宝塔 Nginx 暴露为：

```text
https://sumeme.mv3.cn
```

Android/Windows 客户端是独立的 Flutter 原生应用，通过同一域名的 `/api/gateway` 调用服务端 API，不会加载这个网页作为客户端主界面。

服务器内部监听：

- `127.0.0.1:3210`：`sumeme-web`；
- `127.0.0.1:8010`：`memory-gateway`；
- `127.0.0.1:9000/9001`：RustFS。

这些端口不得直接开放到公网。

## 2. 安装目录

```bash
cd /opt
git clone git@github.com:b8vipvip/sumeme.git
cd /opt/sumeme
git checkout main
cp .env.example .env
bash scripts/generate-secrets.sh
chmod 600 .env
```

仓库可以公开，但 `.env`、数据库、对象、备份和任何用户内容只保存在 VPS。

## 3. 填写中转站和模型

编辑 `/opt/sumeme/.env`：

```dotenv
APP_DOMAIN=sumeme.mv3.cn
APP_URL=https://sumeme.mv3.cn
WEB_PORT=3210
GATEWAY_PORT=8010

OPENAI_RELAY_BASE_URL=https://你的中转站/v1
OPENAI_RELAY_API_KEY=你的Key
OPENAI_CHAT_MODEL=主对话模型真实名称
OPENAI_MEMORY_MODEL=用于记忆整理的模型真实名称
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MODEL_LIST=+主对话模型真实名称

GATEWAY_API_KEY=高强度随机密钥
GATEWAY_ADMIN_TOKEN=高强度随机密钥
GATEWAY_SERVICE_TOKEN=高强度随机密钥
```

不要给值加多余引号。Docker `env_file` 会把引号当成值的一部分。

客户端只需要服务器地址，以及经过授权的客户端 Gateway 凭据。不要把中转站 Key、对象存储密钥或 service token 放进客户端。

## 4. 对象存储域名

浏览器或客户端下载对象时需要可访问的 S3 端点。建议：

1. 新增 DNS：`s3.sumeme.mv3.cn` 指向 VPS；
2. 宝塔新增网站 `s3.sumeme.mv3.cn`；
3. 申请 SSL；
4. 使用 `deploy/baota-s3-nginx.conf`；
5. `.env` 设置：

```dotenv
S3_ENDPOINT=https://s3.sumeme.mv3.cn
```

RustFS 仅监听回环地址，公网只能经过宝塔 Nginx。

## 5. 首次启动

```bash
cd /opt/sumeme
docker compose config
docker compose pull
docker compose build sumeme-web memory-gateway ai-provider-proxy
docker compose up -d
docker compose ps
```

检查服务端 UI 和网关：

```bash
curl http://127.0.0.1:3210/healthz
curl http://127.0.0.1:3210/ | grep 'SuMeMe · 服务端'
curl http://127.0.0.1:8010/health
curl -H "Authorization: Bearer $(grep '^GATEWAY_API_KEY=' .env | cut -d= -f2-)" \
  http://127.0.0.1:8010/v1/models
```

正式环境优先使用仓库 GHS 自动部署，而不是长期手动运行这些命令。

## 6. 宝塔主站反向代理

宝塔中新建或打开 `sumeme.mv3.cn`：

1. PHP 版本选择纯静态；
2. 开启 SSL 和强制 HTTPS；
3. 将 `deploy/baota-nginx.conf` 中的 `location` 配置放入该网站的 `server {}`；
4. 重载 Nginx。

主站只需反代到：

```text
http://127.0.0.1:3210
```

`sumeme-web` 会在容器网络内将：

- `/sumeme-health` 转到 `memory-gateway:/health`；
- `/api/gateway/*` 转到受保护的网关 API；
- 其他路径返回 SuMeMe 服务端管理后台。

访问：

```text
https://sumeme.mv3.cn
```

页面标题应为：

```text
SuMeMe · 服务端
```

## 7. 服务端管理后台凭据

管理后台不会内置服务器密钥。需要模型、记忆或 Vault 操作时，在“安全凭据”中临时输入：

- Gateway 凭据；
- 管理员凭据。

凭据只进入当前标签页的 `sessionStorage`，关闭标签页后清除。

当前面板允许：

- 查看公开健康；
- 读取模型列表；
- 作用域记忆检索；
- 私有对象列表；
- 读取和修改 Vault 策略。

容器重启、回滚、数据库操作、密钥修改和备份恢复不会直接暴露给浏览器，必须走受审查的服务器流程。

## 8. Letta

当前固定：

```dotenv
LETTA_IMAGE_PIN=letta/letta:0.16.8
LETTA_REQUIRED=false
```

MemPalace 是必需的原文记忆组件；Letta 是可观测但可选的结构化记忆组件。检查：

```bash
docker compose ps letta
docker compose logs --tail=200 letta memory-gateway
```

即使 Letta 降级，只要 MemPalace、网关、数据库和对象链路正常，服务端仍可工作。

## 9. LobeHub 历史容器

当前 Compose 暂时保留内部 `lobe` 容器，目的是迁移历史账户、会话和附件数据。它：

- 没有宿主机端口；
- 不作为公网入口；
- 不作为 Android/Windows 客户端 UI；
- 不作为 SuMeMe 服务端管理后台。

迁移完成并验证数据完整后，可以在单独的迁移 PR 中移除该容器和 PostgreSQL 中不再需要的旧表。

## 10. 自动部署

正式模式：

```text
GHS — GitHub-hosted SSH
```

GitHub Runner 完成 CI 后，通过固定 Host Key 上传经过验证的精确提交，并执行 `scripts/deploy-production-v2.sh`。自动部署会：

- 检查磁盘空间；
- 保护 `.env` 与数据卷；
- 构建本地服务镜像；
- 收敛 Compose；
- 验证容器、网关和原生 SuMeMe 公网页面；
- 执行业务 smoke；
- 失败时回滚到上一快照。

不要在自动部署过程中手动修改 `/opt/sumeme`，避免与部署锁冲突。

## 11. 防火墙

公网只需要：

- 80；
- 443；
- SSH 管理端口；
- 宝塔管理端口（建议限制来源 IP）。

不要将以下端口直接开放到公网：

```text
3210 8010 8283 6333 5432 6379 9000 9001
```

## 12. 备份

```bash
cd /opt/sumeme
bash scripts/backup.sh
```

至少备份：

- PostgreSQL；
- Redis（如有关键任务状态）；
- RustFS 数据卷；
- Qdrant 数据卷；
- `gateway-data`、`mempalace-data`、`letta-data`；
- `.env` 的离线加密副本；
- `.deploy` 发布历史与快照元数据。

备份应同步到另一台服务器或独立对象存储，并定期做恢复演练。
