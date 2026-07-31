# SuMeMe 项目状态

- **采集时间：** 2026-07-31T17:16:36+08:00
- **总体状态：** `unhealthy`
- **开发阶段：** `deployed_unhealthy`
- **线上版本：** `8077ba1627b5cb68c306cb762c636e6742a42701`
- **main 最新版本：** `abfba0110a4e17ce86745a333314b4964a4695c0`
- **线上与 main 同步：** 否
- **开放 PR：** 0
- **开放 Issue：** 3

## 需要关注

- 缺少关键服务: sumeme-web
- 磁盘使用率达到 80% 警戒线

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`84.4%`，剩余 4.4 GiB
- 内存使用：`63.3%`，可用 1.3 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up 6 hours (healthy) |
| letta | running | healthy | Up 6 hours (healthy) |
| lobe | running | - | Up 6 hours |
| memory-gateway | running | healthy | Up 6 hours (healthy) |
| postgresql | running | healthy | Up 6 hours (healthy) |
| qdrant | running | healthy | Up 6 hours (healthy) |
| redis | running | healthy | Up 6 hours (healthy) |
| rustfs | running | healthy | Up 6 hours (healthy) |
| searxng | running | - | Up 6 hours |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-31T09:16:17Z |
| Smoke production | success | main | 2026-07-31T09:16:11Z |
| Publish project status | success | main | 2026-07-31T07:55:38Z |
| Public UI smoke | skipped | main | 2026-07-31T07:54:51Z |
| Publish project status | success | main | 2026-07-31T07:33:13Z |
| CI | cancelled | main | 2026-07-31T07:54:47Z |
| Server UI check | success | main | 2026-07-31T06:54:13Z |
| Build Android and Windows clients | success | main | 2026-07-31T06:58:52Z |

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
- 当前版本与 main 一致：`no`
- deploying SHA：`none`
- 最近发布结果：`success`
- 磁盘保护级别：`warning`
- Letta 必需：`no`
- Letta 可用：`yes`
- 最近 smoke test：`degraded`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
