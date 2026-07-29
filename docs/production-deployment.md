# SuMeMe 生产发布链路

## 自动发布

生产部署是 `CI` 工作流中的后置任务，不再通过另一个工作流监听
`workflow_run`。

```text
push main
   │
   ├── gateway
   ├── reliability
   └── compose
          │ 三组全部成功
          ▼
   deploy-production
          │ self-hosted: sumeme-production
          ▼
       /opt/sumeme
```

`deploy-production` 同时满足以下条件才会运行：

- 事件是 `push`；
- Git ref 是 `refs/heads/main`；
- `gateway`、`reliability`、`compose` 三个前置任务全部成功。

部署任务检出 `${{ github.sha }}`，随后比较实际 `git rev-parse HEAD` 与
`GITHUB_SHA`。不一致时立即停止。部署脚本也接收相同 SHA，并把成功版本写入：

```text
/opt/sumeme/.deploy/current_sha
```

因此测试通过的提交、检出的提交、部署脚本收到的提交和运行状态记录必须是同一个
SHA。

## PR 与开发分支

`pull_request` 和 `agent/**` push 仍运行完整检查，但生产部署任务会跳过。开发分支
不能占用生产 Runner，也不能修改线上 `/opt/sumeme`。

## 人工发布

`.github/workflows/deploy-production.yml` 只保留 `workflow_dispatch`，用于重新发布
当前 main。必须在 GitHub Actions 页面选择 `main` 才能运行；其他 ref 会被任务级
条件拒绝。

人工发布不会接受用户输入的任意 SHA，也不会从 PR 分支检出代码。

## 并发与回滚

自动发布和人工发布共用：

```text
concurrency group: sumeme-production
cancel-in-progress: false
```

同一时间只允许一个生产发布，新任务排队而不是取消正在执行的部署。

`scripts/deploy-production.sh` 继续负责：

- 磁盘预检与安全清理；
- 当前代码快照；
- 精确同步代码并保留服务器 `.env`；
- Docker Compose 校验、拉取、构建和启动；
- HTTP 健康检查；
- Provider 感知的生产 smoke；
- 失败时恢复上一份代码快照；
- 记录 `current_sha`、`previous_sha` 和历史。

代码回滚不逆转数据库迁移。任何会修改数据库结构的后续版本必须先实现可前向兼容
迁移和独立备份。

## 验收

成功自动发布后应同时满足：

```bash
cat /opt/sumeme/.deploy/current_sha
tail -n 20 /opt/sumeme/.deploy/history.log
curl -fsS http://127.0.0.1:8010/health
curl -fsS https://sumeme.mv3.cn/sumeme-health
```

状态镜像中的 `deployment.current_sha` 应与 GitHub `main` 最新 SHA 一致，
`deployment_in_sync` 应为 `true`。
