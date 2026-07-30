# SuMeMe 项目状态

- **采集时间：** 2026-07-30T11:27:35+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployment_behind_main`
- **线上版本：** `fe9e4a37401cdda1288226990236536cba85288b`
- **main 最新版本：** `7e0eb3a682f83919030b5e164198a68fe63ce8ff`
- **线上与 main 同步：** 否
- **开放 PR：** 0
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`79.9%`，剩余 6.2 GiB
- 内存使用：`43.7%`，可用 2.0 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| letta | running | healthy | Up 23 hours (healthy) |
| lobe | running | - | Up 22 hours |
| memory-gateway | running | healthy | Up 34 seconds (healthy) |
| postgresql | running | healthy | Up 23 hours (healthy) |
| qdrant | running | healthy | Up 23 hours (healthy) |
| redis | running | healthy | Up 23 hours (healthy) |
| rustfs | running | healthy | Up 29 minutes (healthy) |
| searxng | running | - | Up 23 hours |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| CI | queued | agent/private-vault-object-bucket | 2026-07-30T03:27:25Z |
| Publish project status | in_progress | main | 2026-07-30T03:27:23Z |
| Publish project status | cancelled | main | 2026-07-30T03:27:19Z |
| CI | in_progress | agent/private-vault-object-bucket | 2026-07-30T03:27:02Z |
| CI | success | agent/private-vault-object-bucket | 2026-07-30T03:26:56Z |
| Smoke production | success | main | 2026-07-30T03:27:04Z |
| CI | success | agent/private-vault-object-bucket | 2026-07-30T03:25:26Z |
| Publish project status | success | main | 2026-07-30T03:18:56Z |

## 开放 PR

- 无

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
- 磁盘保护级别：`ok`
- 最近 smoke test：`failure`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
