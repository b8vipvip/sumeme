# SuMeMe 项目状态

- **采集时间：** 2026-07-30T11:47:14+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployment_behind_main`
- **线上版本：** `fe9e4a37401cdda1288226990236536cba85288b`
- **main 最新版本：** `43bdbd14851ce74bd6ece93a9f0d3259aaeac8f9`
- **线上与 main 同步：** 否
- **开放 PR：** 1
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`81.3%`，剩余 5.6 GiB
- 内存使用：`42.8%`，可用 2.1 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| letta | running | healthy | Up 23 hours (healthy) |
| lobe | running | - | Up 23 hours |
| memory-gateway | running | healthy | Up 25 seconds (healthy) |
| postgresql | running | healthy | Up 24 hours (healthy) |
| qdrant | running | healthy | Up 24 hours (healthy) |
| redis | running | healthy | Up 24 hours (healthy) |
| rustfs | running | healthy | Up 49 minutes (healthy) |
| searxng | running | - | Up 24 hours |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-30T03:47:03Z |
| CI | in_progress | agent/scoped-object-metadata | 2026-07-30T03:46:41Z |
| CI | success | agent/scoped-object-metadata | 2026-07-30T03:46:47Z |
| CI | success | agent/scoped-object-metadata | 2026-07-30T03:46:10Z |
| CI | success | agent/scoped-object-metadata | 2026-07-30T03:45:39Z |
| CI | success | agent/scoped-object-metadata | 2026-07-30T03:44:56Z |
| CI | failure | main | 2026-07-30T03:46:57Z |
| CI | success | agent/align-smoke-relay-timeouts | 2026-07-30T03:42:49Z |

## 开放 PR

- #27 Add scoped object metadata and lifecycle rules (`agent/scoped-object-metadata` → `main`)

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-29T15:03:24+08:00 fe9e4a37401cdda1288226990236536cba85288b`
- `2026-07-29T15:01:16+08:00 985f62c95ecff62417e9f515c3a683e369fdaf8d`
- `2026-07-29T15:00:27+08:00 efe5b594b0b0d05509a1e7717f2eadc95adabf84`
- `2026-07-29T14:35:43+08:00 b2b0ab82a712af7e2a1aeda930989f368522caf7`

## 可靠性信号

- 状态快照发布时年龄：`0s`
- 状态快照过期：`no`（阈值 2100s）
- 磁盘保护级别：`warning`
- 最近 smoke test：`failure`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
