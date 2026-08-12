# SuMeMe 项目状态

- **采集时间：** 2026-08-13T04:33:14+08:00
- **总体状态：** `healthy`
- **开发阶段：** `deployed_and_stable`
- **线上版本：** `e6d9007524633325b7005aa2751a9e97364f5432`
- **main 最新版本：** `e6d9007524633325b7005aa2751a9e97364f5432`
- **线上与 main 同步：** 是
- **开放 PR：** 0
- **开放 Issue：** 3

## 健康检查

- 本地网关：`ok`
- 公网入口：`ok`
- 磁盘使用：`77.8%`，剩余 7.0 GiB
- 内存使用：`46.2%`，可用 2.0 GiB

## 容器服务

| 服务 | 状态 | 健康 | 说明 |
|---|---|---|---|
| ai-provider-proxy | running | healthy | Up 11 days (healthy) |
| letta | running | healthy | Up 12 days (healthy) |
| lobe | running | - | Up 12 days |
| memory-gateway | running | healthy | Up 11 days (healthy) |
| postgresql | running | healthy | Up 12 days (healthy) |
| qdrant | running | healthy | Up 12 days (healthy) |
| redis | running | healthy | Up 12 days (healthy) |
| rustfs | running | healthy | Up 12 days (healthy) |
| searxng | running | - | Up 11 days |
| sumeme-web | running | healthy | Up 11 days (healthy) |

## 最近工作流

| 工作流 | 结果 | 分支 | 时间 |
|---|---|---|---|
| Publish project status | in_progress | main | 2026-08-12T20:32:54Z |
| Publish project status | success | main | 2026-08-12T19:46:41Z |
| Publish project status | success | main | 2026-08-12T19:19:04Z |
| Smoke production | success | main | 2026-08-12T19:18:15Z |
| Publish project status | success | main | 2026-08-12T18:34:04Z |
| Publish project status | success | main | 2026-08-12T17:39:48Z |
| Publish project status | success | main | 2026-08-12T16:34:06Z |
| Publish project status | success | main | 2026-08-12T15:36:16Z |

## 开放 PR

- 无

## 开放 Issue

- #10 备用方案：维护 SuMeMe Supermemory Fork 并统一远程 AI 出口
- #7 基础架构：严格账户隔离与本地/云端/混合三种记忆存储模式
- #4 Phase 1.5：端到端验证、状态新鲜度与磁盘保护

## 最近部署

- `2026-08-01T09:28:26+08:00 e6d9007524633325b7005aa2751a9e97364f5432`
- `2026-08-01T08:51:02+08:00 549e8beddc921ec4f5cef69bef6748c2bf2af22f`
- `2026-07-31T22:10:19+08:00 ddddf2ee60fa08dbda449942b276dff2fc28e18e`
- `2026-07-31T22:06:14+08:00 2fd8e6aa85fd2048443029be322d9e14e557a9b4`
- `2026-07-31T20:26:00+08:00 1858ee28dacc133f737b8e7028f4bfba05c13a7b`
- `2026-07-31T20:17:25+08:00 7fec9c27f5570bca44ebad70fb20c7577a4ea86a`
- `2026-07-31T19:28:50+08:00 4a88ed68344be6778b4acbdd484fca8dd89a5d48`
- `2026-07-31T19:20:51+08:00 9621f00a6ff32e996229c8b3f490ae98dcfd0a96`
- `2026-07-31T19:10:53+08:00 adddeac3918de48859647db5a8b0e90ec1259196`
- `2026-07-31T18:54:35+08:00 556007b956d06ca04857be3a817a09bba6aa2065`

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
