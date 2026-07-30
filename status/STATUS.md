# SuMeMe 项目状态

- **采集时间：** 2026-07-31T00:57:49+08:00
- **总体状态：** `unhealthy`
- **开发阶段：** `deployed_unhealthy`
- **线上版本：** `fe9e4a37401cdda1288226990236536cba85288b`
- **main 最新版本：** `f8de54d84553526c9a10b79cc21ea0f01b1bb0fc`
- **线上与 main 同步：** 否
- **开放 PR：** 0
- **开放 Issue：** 3

## 需要关注

- 缺少关键服务: letta, lobe, memory-gateway, postgresql, qdrant, redis, rustfs, searxng
- 本地 memory-gateway 健康检查失败
- 公网健康检查失败

## 健康检查

- 本地网关：`failed`
- 公网入口：`failed`
- 磁盘使用：`83.4%`，剩余 4.8 GiB
- 内存使用：`32.5%`，可用 2.5 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-07-30T16:57:30Z |
| Publish project status | success | main | 2026-07-30T15:42:13Z |
| Publish project status | success | main | 2026-07-30T15:24:03Z |
| Publish project status | success | main | 2026-07-30T14:34:33Z |
| Publish project status | cancelled | main | 2026-07-30T14:33:45Z |
| CI | failure | main | 2026-07-30T15:41:13Z |
| CI | success | agent/isolation-negative-matrix | 2026-07-30T14:31:09Z |
| Publish project status | success | main | 2026-07-30T14:30:51Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-07-30T23:41:07+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=f8de54d84553526c9a10b79cc21ea0f01b1bb0fc`
- `2026-07-30T22:33:25+08:00 rollback target=fe9e4a37401cdda1288226990236536cba85288b failed=d80e539434df8d6f89a198a45a067b332addcb3b`
- `2026-07-29T15:03:24+08:00 fe9e4a37401cdda1288226990236536cba85288b`
- `2026-07-29T15:01:16+08:00 985f62c95ecff62417e9f515c3a683e369fdaf8d`
- `2026-07-29T15:00:27+08:00 efe5b594b0b0d05509a1e7717f2eadc95adabf84`
- `2026-07-29T14:35:43+08:00 b2b0ab82a712af7e2a1aeda930989f368522caf7`

## 可靠性信号

- 状态快照发布时年龄：`1s`
- 状态快照过期：`no`（阈值 2100s）
- 部署状态：`idle`
- 当前版本与 main 一致：`no`
- deploying SHA：`none`
- 最近发布结果：`rollback`
- 磁盘保护级别：`warning`
- 最近 smoke test：`failure`
- 自动清理不会删除 Docker 数据卷、数据库或用户附件。
