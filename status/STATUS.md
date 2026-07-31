# SuMeMe 项目状态

- **采集时间：** 2026-07-31T10:53:13+08:00
- **总体状态：** `unhealthy`
- **开发阶段：** `deployed_unhealthy`
- **线上版本：** `73eb76fa6d6f0e1fc5bc4aa192e587870d051315`
- **main 最新版本：** `73eb76fa6d6f0e1fc5bc4aa192e587870d051315`
- **线上与 main 同步：** 是
- **开放 PR：** 0
- **开放 Issue：** 3

## 需要关注

- 关键服务异常: letta(running/starting)

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`83.8%`，剩余 4.6 GiB
- 内存使用：`62.4%`，可用 1.4 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up About a minute (healthy) |
| letta | running | starting | Up 3 minutes (health: starting) |
| lobe | running | - | Up 3 minutes |
| memory-gateway | running | healthy | Up About a minute (healthy) |
| postgresql | running | healthy | Up 4 minutes (healthy) |
| qdrant | running | healthy | Up 4 minutes (healthy) |
| redis | running | healthy | Up 4 minutes (healthy) |
| rustfs | running | healthy | Up 4 minutes (healthy) |
| searxng | running | - | Up 4 minutes |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-31T02:52:56Z |
| Publish project status | success | main | 2026-07-31T02:51:38Z |
| CI | failure | main | 2026-07-31T02:52:45Z |
| Build Android and Windows clients | in_progress | main | 2026-07-31T02:50:29Z |
| CI | failure | main | 2026-07-31T02:50:52Z |
| CI | success | agent/capture-expected-smoke-failures | 2026-07-31T02:47:32Z |
| CI | success | agent/first-flutter-clients | 2026-07-31T02:44:14Z |
| Build Android and Windows clients | success | agent/first-flutter-clients | 2026-07-31T02:49:14Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-31T10:51:34+08:00 73eb76fa6d6f0e1fc5bc4aa192e587870d051315`
- `2026-07-31T10:49:41+08:00 421dbe47d8f8096f41572d2f89221b1c8870d5a3`
- `2026-07-31T10:41:36+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=a7789e85a59277b609eed3b3f89dc14502e7f245`
- `2026-07-31T10:22:08+08:00 rollback_failed target=fe9e4a37401cdda1288226990236536cba85288b failed=01892424ec7418e0f712334adb168144797c6d4a reason=runtime_recovery_failed`
- `2026-07-30T23:41:07+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=f8de54d84553526c9a10b79cc21ea0f01b1bb0fc`
- `2026-07-30T22:33:25+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=d80e539434df8d6f89a198a45a067b332addcb3b`
- `2026-07-29T15:03:24+08:00 fe9e4a37401cdda1288226990236536cba85288b`
- `2026-07-29T15:01:16+08:00 985f62c95ecff62417e9f515c3a683e369fdaf8d`
- `2026-07-29T15:00:27+08:00 efe5b594b0b0d05509a1e7717f2eadc95adabf84`
- `2026-07-29T14:35:43+08:00 b2b0ab82a712af7e2a1aeda930989f368522caf7`

## 可靠性信号

- 状态快照发布时年龄：`0s`
- 状态快照过期：`no`（阈值 2100s）
- 部署状态：`idle`
- 当前版本与 main 一致：`yes`
- deploying SHA：`none`
- 最近发布结果：`success`
- 磁盘保护级别：`warning`
- 最近 smoke test：`degraded`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
