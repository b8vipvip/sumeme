# SuMeMe 项目状态

- **采集时间：** 2026-07-31T18:12:29+08:00
- **总体状态：** `degraded`
- **开发阶段：** `deployed_degraded`
- **线上版本：** `d090da52d3dfd06711d173949473ac5a514f82a4`
- **main 最新版本：** `d090da52d3dfd06711d173949473ac5a514f82a4`
- **线上与 main 同步：** 是
- **开放 PR：** 0
- **开放 Issue：** 3

## 需要关注

- 磁盘使用率达到 80% 警戒线

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`85.1%`，剩余 4.1 GiB
- 内存使用：`60.4%`，可用 1.4 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up 2 minutes (healthy) |
| letta | running | healthy | Up 7 hours (healthy) |
| lobe | running | - | Up 9 minutes |
| memory-gateway | running | healthy | Up 2 minutes (healthy) |
| postgresql | running | healthy | Up 7 hours (healthy) |
| qdrant | running | healthy | Up 7 hours (healthy) |
| redis | running | healthy | Up 7 hours (healthy) |
| rustfs | running | healthy | Up 7 hours (healthy) |
| searxng | running | - | Up 7 hours |
| sumeme-web | running | healthy | Up About a minute (healthy) |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-31T10:12:10Z |
| Public UI smoke | in_progress | main | 2026-07-31T10:12:04Z |
| CI | success | main | 2026-07-31T10:11:59Z |
| Server UI check | success | main | 2026-07-31T10:09:29Z |
| Public UI smoke | skipped | main | 2026-07-31T10:08:23Z |
| CI | success | agent/update-public-ui-smoke | 2026-07-31T10:08:20Z |
| Server UI check | success | agent/update-public-ui-smoke | 2026-07-31T10:08:01Z |
| Publish project status | success | main | 2026-07-31T10:05:20Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-31T18:11:46+08:00 d090da52d3dfd06711d173949473ac5a514f82a4`
- `2026-07-31T18:04:11+08:00 530a1175b64a219d8771218616a5dbd7abf0233b`
- `2026-07-31T17:55:52+08:00 rollback target=8077ba1627b5cb68c306cb762c636e6742a42701 failed=4a8f255c0306ceac8bd38470525c6e1cee180738`
- `2026-07-31T17:48:37+08:00 rollback target=8077ba1627b5cb68c306cb762c636e6742a42701 failed=8dfeb2f0293a6fa38602200be92cdefce7d42b2d`
- `2026-07-31T11:09:27+08:00 8077ba1627b5cb68c306cb762c636e6742a42701`
- `2026-07-31T11:01:29+08:00 12adbf02d85c101098cb772587540700b20ec644`
- `2026-07-31T10:56:07+08:00 aa09d1274c8918baa866e6448d7e713047805553`
- `2026-07-31T10:51:34+08:00 73eb76fa6d6f0e1fc5bc4aa192e587870d051315`
- `2026-07-31T10:49:41+08:00 421dbe47d8f8096f41572d2f89221b1c8870d5a3`
- `2026-07-31T10:41:36+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=a7789e85a59277b609eed3b3f89dc14502e7f245`

## 可靠性信号

- 状态快照发布时年龄：`0s`
- 状态快照过期：`no`（阈值 2100s）
- 部署状态：`idle`
- 当前版本与 main 一致：`yes`
- deploying SHA：`none`
- 最近发布结果：`success`
- 磁盘保护级别：`warning`
- Letta 必需：`no`
- Letta 可用：`yes`
- 最近 smoke test：`degraded`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
