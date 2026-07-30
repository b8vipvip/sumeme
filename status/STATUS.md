# SuMeMe 项目状态

- **采集时间：** 2026-07-30T22:30:31+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployment_behind_main`
- **线上版本：** `fe9e4a37401cdda1288226990236536cba85288b`
- **main 最新版本：** `407d1391bd09aab30faf97c8e9818dc399f6b48c`
- **线上与 main 同步：** 否
- **开放 PR：** 1
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`83.4%`，剩余 4.8 GiB
- 内存使用：`55.6%`，可用 1.6 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| letta | running | healthy | Up 6 hours (healthy) |
| lobe | running | - | Up 34 hours |
| memory-gateway | running | healthy | Up 6 hours (healthy) |
| postgresql | running | healthy | Up 34 hours (healthy) |
| qdrant | running | healthy | Up 34 hours (healthy) |
| redis | running | healthy | Up 34 hours (healthy) |
| rustfs | running | healthy | Up 10 hours (healthy) |
| searxng | running | - | Up 34 hours |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-30T14:30:03Z |
| Publish project status | cancelled | main | 2026-07-30T14:29:55Z |
| Smoke production | success | main | 2026-07-30T14:29:49Z |
| CI | pending | main | 2026-07-30T14:29:50Z |
| CI | success | agent/letta-agent-ownership | 2026-07-30T14:28:35Z |
| CI | failure | agent/letta-agent-ownership | 2026-07-30T14:26:54Z |
| Publish project status | success | main | 2026-07-30T14:24:46Z |
| CI | cancelled | main | 2026-07-30T14:29:51Z |

## 开放 PR

- #47 Add cross-scope object isolation negative matrix (`agent/isolation-negative-matrix` → `agent/letta-agent-ownership`)

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
- 部署状态：`in_progress`
- 当前版本与 main 一致：`no`
- deploying SHA：`d80e539434df8d6f89a198a45a067b332addcb3b`
- 最近发布结果：`success`
- 磁盘保护级别：`warning`
- 最近 smoke test：`failure`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
