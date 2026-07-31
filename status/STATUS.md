# SuMeMe 项目状态

- **采集时间：** 2026-07-31T20:17:16+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployment_in_progress`
- **线上版本：** `4a88ed68344be6778b4acbdd484fca8dd89a5d48`
- **main 最新版本：** `7fec9c27f5570bca44ebad70fb20c7577a4ea86a`
- **线上与 main 同步：** 否
- **开放 PR：** 0
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`72.3%`，剩余 9.1 GiB
- 内存使用：`56.6%`，可用 1.6 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up About a minute (healthy) |
| letta | running | healthy | Up 9 hours (healthy) |
| lobe | running | - | Up 2 hours |
| memory-gateway | running | healthy | Up About a minute (healthy) |
| postgresql | running | healthy | Up 9 hours (healthy) |
| qdrant | running | healthy | Up 9 hours (healthy) |
| redis | running | healthy | Up 9 hours (healthy) |
| rustfs | running | healthy | Up 9 hours (healthy) |
| searxng | running | - | Up 9 hours |
| sumeme-web | running | healthy | Up About a minute (healthy) |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-31T12:16:58Z |
| CI | in_progress | main | 2026-07-31T12:15:17Z |
| Server UI check | success | main | 2026-07-31T12:14:41Z |
| Files manager check | success | main | 2026-07-31T12:14:43Z |
| Public UI smoke | skipped | main | 2026-07-31T12:14:06Z |
| CI | success | agent/lobehub-files-manager | 2026-07-31T12:14:02Z |
| Files manager check | success | agent/lobehub-files-manager | 2026-07-31T12:13:25Z |
| Server UI check | success | agent/lobehub-files-manager | 2026-07-31T12:13:30Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-31T19:28:50+08:00 4a88ed68344be6778b4acbdd484fca8dd89a5d48`
- `2026-07-31T19:20:51+08:00 9621f00a6ff32e996229c8b3f490ae98dcfd0a96`
- `2026-07-31T19:10:53+08:00 adddeac3918de48859647db5a8b0e90ec1259196`
- `2026-07-31T18:54:35+08:00 556007b956d06ca04857be3a817a09bba6aa2065`
- `2026-07-31T18:32:38+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=626f41b285a6ef4ee328fb4cba1c274ced733d39 reason=snapshot_restore_failed`
- `2026-07-31T18:32:38+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=626f41b285a6ef4ee328fb4cba1c274ced733d39 reason=snapshot_restore_failed`
- `2026-07-31T18:23:32+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=1b09d1a909116950acd5ad9c7309d6be23a8ac17 reason=snapshot_restore_failed`
- `2026-07-31T18:23:31+08:00 rollback_failed target=d090da52d3dfd06711d173949473ac5a514f82a4 failed=1b09d1a909116950acd5ad9c7309d6be23a8ac17 reason=snapshot_restore_failed`
- `2026-07-31T18:11:46+08:00 d090da52d3dfd06711d173949473ac5a514f82a4`
- `2026-07-31T18:04:11+08:00 530a1175b64a219d8771218616a5dbd7abf0233b`

## 可靠性信号

- 状态快照发布时年龄：`0s`
- 状态快照过期：`no`（阈值 2100s）
- 部署状态：`in_progress`
- 当前版本与 main 一致：`no`
- deploying SHA：`7fec9c27f5570bca44ebad70fb20c7577a4ea86a`
- 最近发布结果：`success`
- 磁盘保护级别：`ok`
- Letta 必需：`no`
- Letta 可用：`yes`
- 最近 smoke test：`degraded`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
