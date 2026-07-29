# 宝塔面板部署指南

## 1. 目录

```bash
cd /opt
git clone git@github.com:b8vipvip/sumeme.git
cd /opt/sumeme
git checkout agent/bootstrap-sumeme
cp .env.example .env
bash scripts/generate-secrets.sh
```

仓库公开，`.env` 只保存在 VPS，权限应为 `600`。

## 2. 填写中转站

编辑 `/opt/sumeme/.env`：

```dotenv
OPENAI_RELAY_BASE_URL=https://你的中转站/v1
OPENAI_RELAY_API_KEY=你的Key
OPENAI_CHAT_MODEL=主对话模型真实名称
OPENAI_MEMORY_MODEL=便宜且支持工具/结构化输出的模型
OPENAI_EMBEDDING_MODEL=中转站真实 embedding 模型名称
OPENAI_MODEL_LIST=+主对话模型真实名称
LETTA_MODEL=openai/主对话模型真实名称
LETTA_EMBEDDING=openai/embedding模型真实名称
```

不要给值加引号。Docker `env_file` 会把引号当成值的一部分。

## 3. 对象存储域名

LobeHub 的聊天附件需要浏览器可访问的 S3 端点。建议：

1. 新增 DNS：`s3.sumeme.mv3.cn` 指向 VPS；
2. 宝塔新增网站 `s3.sumeme.mv3.cn`；
3. 申请 SSL；
4. 使用 `deploy/baota-s3-nginx.conf`；
5. `.env` 设置：

```dotenv
S3_ENDPOINT=https://s3.sumeme.mv3.cn
```

RustFS 仅监听 `127.0.0.1:9000`，公网只能经过宝塔 Nginx。

## 4. 启动

```bash
cd /opt/sumeme
bash scripts/deploy.sh
```

检查：

```bash
docker compose ps
docker compose logs --tail=200 memory-gateway
curl http://127.0.0.1:8010/health
curl -H "Authorization: Bearer $(grep '^GATEWAY_API_KEY=' .env | cut -d= -f2-)" \
  http://127.0.0.1:8010/v1/models
```

MemPalace 第一次启动可能下载 embedding 模型，网关健康检查需要更久。

## 5. 宝塔主站反代

宝塔中新建或打开 `sumeme.mv3.cn`：

1. PHP 版本选择纯静态；
2. 开启 SSL 和强制 HTTPS；
3. 将 `deploy/baota-nginx.conf` 中的 `location` 配置放入该网站的 `server {}`；
4. 重载 Nginx。

访问：

```text
https://sumeme.mv3.cn
```

## 6. 初始化 Letta

第一版网关支持在 `LETTA_AGENT_ID` 为空时自动创建个人记忆 Agent，并把 ID 保存到 `gateway-data` 卷。检查日志：

```bash
docker compose logs -f memory-gateway
```

若中转站不兼容 Letta 的 provider 探测，可先设置：

```dotenv
LETTA_ENABLED=false
```

此时 MemPalace 和记忆增强对话仍可运行，之后再单独调通 Letta。

## 7. 更新

```bash
cd /opt/sumeme
bash scripts/backup.sh
bash scripts/update.sh
```

生产环境建议把 `latest` 改成验证过的具体镜像 tag，再执行更新。

## 8. 防火墙

公网只需要：

- 80；
- 443；
- SSH 管理端口；
- 宝塔管理端口（建议限制 IP）。

不要把 3210、8010、8283、6333、5432、6379、9000、9001 直接开放到公网。

## 9. 备份

```bash
cd /opt/sumeme
bash scripts/backup.sh
```

备份位于 `/opt/sumeme/backups/<时间>/`。至少还应把该目录同步到另一台服务器或对象存储。
