# SuMeMe 项目状态

- **采集时间：** 2026-07-31T11:10:07+08:00
- **总体状态：** `degraded`
- **开发阶段：** `deployed_degraded`
- **线上版本：** `8077ba1627b5cb68c306cb762c636e6742a42701`
- **main 最新版本：** `8077ba1627b5cb68c306cb762c636e6742a42701`
- **线上与 main 同步：** 是
- **开放 PR：** 0
- **开放 Issue：** 3

## 需要关注

- 磁盘使用率达到 80% 警戒线

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`83.8%`，剩余 4.6 GiB
- 内存使用：`62.5%`，可用 1.4 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up 56 seconds (healthy) |
| letta | running | healthy | Up 8 minutes (healthy) |
| lobe | running | - | Up 20 minutes |
| memory-gateway | running | healthy | Up 50 seconds (healthy) |
| postgresql | running | healthy | Up 20 minutes (healthy) |
| qdrant | running | healthy | Up 20 minutes (healthy) |
| redis | running | healthy | Up 20 minutes (healthy) |
| rustfs | running | healthy | Up 20 minutes (healthy) |
| searxng | running | - | Up 20 minutes |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-31T03:09:48Z |
| CI | success | main | 2026-07-31T03:09:38Z |
| CI | success | agent/optional-letta-status | 2026-07-31T03:07:38Z |
| CI | failure | agent/optional-letta-status | 2026-07-31T03:06:47Z |
| Publish project status | success | main | 2026-07-31T03:02:28Z |
| CI | success | main | 2026-07-31T03:01:40Z |
| CI | success | agent/authenticate-letta-healthcheck | 2026-07-31T02:59:37Z |
| Publish project status | success | main | 2026-07-31T02:56:57Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-31T11:09:27+08:00 8077ba1627b5cb68c306cb762c636e6742a42701`
- `2026-07-31T11:01:29+08:00 12adbf02d85c101098cb772587540700b20ec644`
- `2026-07-31T10:56:07+08:00 aa09d1274c8918baa866e6448d7e713047805553`
- `2026-07-31T10:51:34+08:00 73eb76fa6d6f0e1fc5bc4aa192e587870d051315`
- `2026-07-31T10:49:41+08:00 421dbe47d8f8096f41572d2f89221b1c8870d5a3`
- `2026-07-31T10:41:36+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=a7789e85a59277b609eed3b3f89dc14502e7f245`
- `2026-07-31T10:22:08+08:00 rollback_failed target=fe9e4a37401cdda1288226990236536cba85288b failed=01892424ec7418e0f712334adb168144797c6d4a reason=runtime_recovery_failed`
- `2026-07-30T23:41:07+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=f8de54d84553526c9a10b79cc21ea0f01b1bb0fc`
- `2026-07-30T22:33:25+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=d80e539434df8d6f89a198a45a067b332addcb3b`
- `2026-07-29T15:03:24+08:00 fe9e4a37401cdda1288226990236536cba85288b`

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
