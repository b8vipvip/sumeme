# 上游项目与许可证策略

## LobeHub

- 上游：`lobehub/lobehub`
- 接入方式：官方 Docker 镜像
- 作用：Web/PWA/Windows 入口、账号、聊天、附件、知识库
- 许可证：当前上游使用 LobeHub Community License

本仓库不复制或修改 LobeHub 主仓库代码。部署者需要自行确认上游许可证是否适合实际用途。

## MemPalace

- 上游：`MemPalace/mempalace`
- 接入方式：PyPI 包，由 memory-gateway 作为库调用
- 作用：原文逐字保存、语义检索、知识图谱
- 许可证：MIT

第一阶段使用官方 Qdrant backend，但 embedding 仍由 MemPalace 在网关容器中执行。

## Letta

- 上游：`letta-ai/letta`
- 接入方式：官方 Docker 镜像和 `letta-client`
- 作用：状态化 Agent、长期结构化记忆、用户画像和关系更新
- 许可证：Apache-2.0

## 为什么不直接复制源码

直接复制会带来：

- 上游安全修复难以同步；
- Git 历史和许可证边界混乱；
- 仓库体积巨大；
- 三个项目依赖版本互相污染；
- 修改 LobeHub 后每次升级都需要大规模冲突合并。

SuMeMe 只维护编排层、协议适配层和未来的多模态摄取 worker。
