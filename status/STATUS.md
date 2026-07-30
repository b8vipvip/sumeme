# SuMeMe 项目状态

- **采集时间：** 2026-07-30T15:08:25+08:00
- **总体状态：** `unhealthy`
- **开发阶段：** `deployed_unhealthy`
- **线上版本：** `fe9e4a37401cdda1288226990236536cba85288b`
- **main 最新版本：** `9827490cd183a74d9fa33b66b489bf507f1d1045`
- **线上与 main 同步：** 否
- **开放 PR：** 0
- **开放 Issue：** 3

## 需要关注

- 缺少关键服务: letta
- 本地 memory-gateway 健康检查失败
- 公网健康检查失败

## 健康检查

- 本地网关：`failed`
- 公网入口：`failed`
- 磁盘使用：`82.6%`，剩余 5.1 GiB
- 内存使用：`41.7%`，可用 2.1 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| lobe | running | - | Up 26 hours |
| memory-gateway | running | - | Up 3 minutes (healthy) |
| postgresql | running | healthy | Up 27 hours (healthy) |
| qdrant | running | healthy | Up 27 hours (healthy) |
| redis | running | healthy | Up 27 hours (healthy) |
| rustfs | running | healthy | Up 2 hours (healthy) |
| searxng | running | - | Up 27 hours |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-30T07:07:59Z |
| CI | in_progress | main | 2026-07-30T07:00:30Z |
| Plugin CI | success | main | 2026-07-30T07:00:44Z |
| CI | success | agent/sync-vsr-ghs-modes | 2026-07-30T06:59:28Z |
| Plugin CI | success | agent/sync-vsr-ghs-modes | 2026-07-30T06:59:31Z |
| CI | success | agent/sync-vsr-ghs-modes | 2026-07-30T06:59:07Z |
| Plugin CI | success | agent/sync-vsr-ghs-modes | 2026-07-30T06:59:10Z |
| CI | success | agent/sync-vsr-ghs-modes | 2026-07-30T06:59:08Z |

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
- 磁盘保护级别：`warning`
- 最近 smoke test：`failure`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
