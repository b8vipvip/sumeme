# SuMeMe 使用 ADOB GitHub-hosted SSH 部署

SuMeMe 支持两条互斥的生产发布路径：

```text
默认迁移回退：self-hosted Runner on VPS
目标路径：GitHub-hosted Runner → ADOB reusable workflow → SSH/rsync → VPS
```

通过仓库变量选择：

```text
SUMEME_DEPLOY_TRANSPORT=github-hosted-ssh
```

未设置或使用其他值时，继续使用现有 `sumeme-production` self-hosted Runner。两个部署 Job 不会在同一提交中同时运行。

## 固定的 ADOB 版本

SuMeMe 调用经过审查的 ADOB 提交：

```text
621a5fc3d0876a5a33560468ae6073ec3ac640a4
```

不要改为未固定的 `@main`。升级 ADOB 时应通过 PR 更新固定 SHA，并重新运行 SuMeMe CI。

## VPS 账户

迁移阶段复用现有：

```text
sumeme-runner
```

这样不会更改 `/opt/sumeme` 的既有所有权，也不会影响当前 self-hosted 回退路径。SSH 验证成功前不要停止 Runner 服务。

在 VPS 生成项目专用密钥：

```bash
set -euo pipefail

SSH_HOST="VPS_PUBLIC_IP_OR_SSH_HOST"
SSH_PORT="22"
KEY_DIR="/root/sumeme-adob-deploy-key"

install -d -m 700 "${KEY_DIR}"
ssh-keygen \
  -t ed25519 \
  -C "github-actions:b8vipvip/sumeme" \
  -f "${KEY_DIR}/id_ed25519" \
  -N ""
```

从 ADOB 的固定版本下载并校验安装器，或在可信 ADOB checkout 中运行：

```bash
curl -fsSL \
  https://raw.githubusercontent.com/b8vipvip/ADOB/621a5fc3d0876a5a33560468ae6073ec3ac640a4/installer/install-ssh-deploy.sh \
  -o /root/install-adob-ssh-deploy.sh

chmod 700 /root/install-adob-ssh-deploy.sh

SSH_PUBLIC_KEY="$(cat /root/sumeme-adob-deploy-key/id_ed25519.pub)" \
DEPLOY_USER="sumeme-runner" \
DEPLOY_DIR="/opt/sumeme" \
SSH_HOST="${SSH_HOST}" \
SSH_PORT="${SSH_PORT}" \
CREATE_USER="false" \
bash /root/install-adob-ssh-deploy.sh
```

脚本会把公钥写入：

```text
/home/sumeme-runner/.ssh/authorized_keys
```

并准备独立 staging：

```text
/opt/sumeme.adob/incoming/<git-sha>
```

staging 位于 `/opt/sumeme` 外部，避免部署脚本的 `rsync --delete` 删除当前上传源。

## GitHub Secrets

在 `b8vipvip/sumeme` 的 Actions secrets 添加：

```text
SUMEME_SSH_PRIVATE_KEY
SUMEME_SSH_HOST_KEY
```

`SUMEME_SSH_PRIVATE_KEY` 是完整 OpenSSH 私钥。

`SUMEME_SSH_HOST_KEY` 是安装器输出的完整 known_hosts 行，来源必须是 VPS 本机 `/etc/ssh/ssh_host_ed25519_key.pub`。

私钥不得放进 Issue、PR、聊天、代码或 Actions Variable。

## GitHub Variables

添加：

```text
SUMEME_VPS_HOST=<VPS 公网 IP 或 SSH 域名>
SUMEME_VPS_PORT=22
SUMEME_VPS_USER=sumeme-runner
```

首次测试前不要设置 `SUMEME_DEPLOY_TRANSPORT`。

## 首次切换

1. 确认 SSH 端口可被 GitHub-hosted Runner 访问。
2. 添加两个 Secrets 和三个 Variables。
3. 设置：

```text
SUMEME_DEPLOY_TRANSPORT=github-hosted-ssh
```

4. 在 `Deploy production` 工作流对 `main` 执行一次手动发布。
5. 验证：

```bash
cat /opt/sumeme/.deploy/current_sha
tail -n 20 /opt/sumeme/.deploy/history.log
curl -fsS http://127.0.0.1:8080/health; echo
curl -fsS https://sumeme.mv3.cn/health; echo
```

6. 重新读取 `ops-status`，确认 deployed SHA、容器和 smoke 结果。

手动 SSH 发布成功后，后续每次 main CI 通过都会自动走 ADOB SSH 路径。

## 回退

只需把变量改为：

```text
SUMEME_DEPLOY_TRANSPORT=self-hosted
```

或删除该变量，下一次 main 发布就恢复使用现有 self-hosted Runner。

不要在 SSH 发布进行中切换变量。部署脚本自身通过 `/opt/sumeme/.deploy/deploy.lock` 防止并发修改。

## 停止旧 Runner 的条件

当前只迁移部署工作流。`publish-status`、`diagnose`、`rollback` 和部分维护任务仍使用 self-hosted Runner，所以暂时不能停止：

```text
actions.runner.b8vipvip-sumeme.sumeme-vps.service
```

后续把这些维护操作迁移到 ADOB SSH transport 后，才能完全移除 VPS 常驻 Runner。
