# 上游项目与许可证策略

## FDEX 前端来源

- 来源仓库：`b8vipvip/fdex`
- 读取基线：`ecb0e41cb7a5f4f3ad69398f4bb33edfde0a7068`
- 使用范围：Android Jetpack Compose 的信息架构、导航与组件样式，以及 FastAPI 管理后台的侧边栏、卡片、表单和响应式视觉体系
- 落地位置：改造后的代码只提交到 `b8vipvip/sumeme`
- 上游保护：SuMeMe 的自动化和部署流程不得向 `b8vipvip/fdex` 写入提交、分支、标签或 Release

FDEX 当前仓库没有提供单独的 `LICENSE` 文件。两个仓库均由同一所有者维护，但在将相关代码用于其他所有者或商业发行前，仍应补充明确许可证。

SuMeMe 不直接照搬 FDEX 的业务模型。FDEX 的“消息、工作、发现、我的”结构会映射为 SuMeMe 的“对话、记忆、资料、Vault、同步和设置”，数据层全部替换为 SuMeMe 与 LobeHub 接口。

## LobeHub

- 上游：`lobehub/lobehub`
- 固定版本：`v2.2.11`
- 接入方式：从固定 tag 构建受审查的 Docker 镜像
- 保留作用：账户与 Better Auth、会话、消息、附件、知识库、用户设置、PostgreSQL/Redis 数据模型和应用 API
- 替换范围：只替换用户可见前端，不删除或迁移掉上述后端能力
- 许可证：当前上游使用 LobeHub Community License

公网入口由 `sumeme-web` 提供 FDEX 风格的 SuMeMe 页面；`/api/auth/*`、`/trpc/*`、通用 `/api/*`、OIDC 路由以及兼容静态资源反向代理到内部 LobeHub 服务。LobeHub 不直接暴露宿主机端口。

部署者需要自行确认上游许可证是否适合实际用途。

## MemPalace

- 上游：`MemPalace/mempalace`
- 接入方式：保留 MemPalace 语义，通过 memory-gateway、SQLite、Qdrant 和远程 embedding 实现
- 作用：原文逐字保存与语义检索
- 许可证：MIT

SuMeMe 不加载 MemPalace 的本地 ONNX 模型；生成式 AI 和 embedding 均走远程中转站或明确批准的官方 API。

## Letta

- 上游：`letta-ai/letta`
- 接入方式：固定 Docker 镜像和 `letta-client`
- 作用：状态化 Agent、长期结构化记忆、用户画像和关系更新
- 许可证：Apache-2.0

## 边界原则

- FDEX 仓库只读，适配代码保留在 SuMeMe；
- LobeHub 保留为核心后端，不再使用其原生视觉界面；
- SuMeMe 维护前端适配、反向代理、记忆网关和部署编排；
- 上游升级必须固定版本、经过 CI，并验证账户、会话、附件和数据兼容性。
