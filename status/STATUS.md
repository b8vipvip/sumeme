# SuMeMe 项目状态

- **采集时间：** 2026-07-31T19:11:29+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployed_and_stable`
- **线上版本：** `adddeac3918de48859647db5a8b0e90ec1259196`
- **main 最新版本：** `adddeac3918de48859647db5a8b0e90ec1259196`
- **线上与 main 同步：** 是
- **开放 PR：** 0
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`72.5%`，剩余 9.1 GiB
- 内存使用：`55.1%`，可用 1.6 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up 2 minutes (healthy) |
| letta | running | healthy | Up 8 hours (healthy) |
| lobe | running | - | Up About an hour |
| memory-gateway | running | healthy | Up 2 minutes (healthy) |
| postgresql | running | healthy | Up 8 hours (healthy) |
| qdrant | running | healthy | Up 8 hours (healthy) |
| redis | running | healthy | Up 8 hours (healthy) |
| rustfs | running | healthy | Up 8 hours (healthy) |
| searxng | running | - | Up 8 hours |
| sumeme-web | running | healthy | Up 2 minutes (healthy) |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Public UI smoke | in_progress | main | 2026-07-31T11:11:08Z |
| Publish project status | in_progress | main | 2026-07-31T11:11:08Z |
| CI | success | main | 2026-07-31T11:11:03Z |
| Server UI check | success | main | 2026-07-31T11:08:10Z |
| Public UI smoke | skipped | main | 2026-07-31T11:07:21Z |
| CI | success | agent/lobehub-agent-send | 2026-07-31T11:07:18Z |
| Server UI check | success | agent/lobehub-agent-send | 2026-07-31T11:07:01Z |
| Public UI smoke | success | main | 2026-07-31T10:55:16Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-31T19:10:53+08:00 adddeac3918de48859647db5a8b0e90ec1259196`
- `2026-07-31T18:54:35+08:00 556007b956d06ca04857be3a817a09bba6aa2065`
- `2026-07-31T18:32:38+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=626f41b285a6ef4ee328fb4cba1c274ced733d39 reason=snapshot_restore_failed`
- `2026-07-31T18:32:38+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=626f41b285a6ef4ee328fb4cba1c274ced733d39 reason=snapshot_restore_failed`
- `2026-07-31T18:23:32+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=1b09d1a909116950acd5ad9c7309d6be23a8ac17 reason=snapshot_restore_failed`
- `2026-07-31T18:23:31+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=1b09d1a909116950acd5ad9c7309d6be23a8ac17 reason=snapshot_restore_failed`
- `2026-07-31T18:11:46+08:00 d090da52d3dfd06711d173949473ac5a514f82a4`
- `2026-07-31T18:04:11+08:00 530a1175b64a219d8771218616a5dbd7abf0233b`
- `2026-07-31T17:55:52+08:00 rollback target=8077ba1627b5cb68c306cb762c636e6742a42701 failed=4a8f255c0306ceac8bd38470525c6e1cee180738`
- `2026-07-31T17:48:37+08:00 rollback target=8077ba1627b5cb68c306cb762c636e6742a42701 failed=8dfeb2f0293a6fa38602200be92cdefce7d42b2d`

## 可靠性信号

- 状态快照发布时年龄：`0s`
- 状态快照过期：`no`（阈值 2100s）
- 部署状态：`idle`
- 当前版本与 main 一致：`yes`
- deploying SHA：`none`
- 最近发布结果：`success`
- 磁盘保护级别：`ok`
- Letta 必需：`no`
- Letta 可用：`yes`
- 最近 smoke test：`degraded`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
