# SuMeMe 项目状态

- **采集时间：** 2026-07-30T22:24:23+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployment_behind_main`
- **线上版本：** `fe9e4a37401cdda1288226990236536cba85288b`
- **main 最新版本：** `94d639b2fbb180f681d823931782be21b834ef0c`
- **线上与 main 同步：** 否
- **开放 PR：** 2
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`83.4%`，剩余 4.8 GiB
- 内存使用：`55.3%`，可用 1.6 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| letta | running | healthy | Up 6 hours (healthy) |
| lobe | running | - | Up 33 hours |
| memory-gateway | running | healthy | Up 6 hours (healthy) |
| postgresql | running | healthy | Up 34 hours (healthy) |
| qdrant | running | healthy | Up 34 hours (healthy) |
| redis | running | healthy | Up 34 hours (healthy) |
| rustfs | running | healthy | Up 10 hours (healthy) |
| searxng | running | - | Up 34 hours |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-30T14:24:01Z |
| CI | pending | main | 2026-07-30T14:23:54Z |
| CI | success | agent/object-reservation-cleanup | 2026-07-30T14:22:48Z |
| CI | failure | agent/object-reservation-cleanup | 2026-07-30T14:21:05Z |
| CI | cancelled | main | 2026-07-30T14:23:55Z |
| CI | success | agent/scoped-object-access-api | 2026-07-30T14:09:45Z |
| CI | success | agent/scoped-object-access-api | 2026-07-30T14:09:53Z |
| CI | failure | agent/scoped-object-access-api | 2026-07-30T14:07:14Z |

## 开放 PR

- #47 Add cross-scope object isolation negative matrix (`agent/isolation-negative-matrix` → `agent/letta-agent-ownership`)
- #46 Fail closed on Letta agent ownership collisions (`agent/letta-agent-ownership` → `agent/object-reservation-cleanup`)

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
