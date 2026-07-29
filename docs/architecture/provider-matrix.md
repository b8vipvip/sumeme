# Provider 与连接器职责矩阵

| 模块 | 允许 | 禁止 |
|---|---|---|
| AI Provider | OpenAI-compatible 中转站、OpenAI/Anthropic/Google 等官方 API | Ollama、llama.cpp、LocalAI、vLLM、本地 Whisper、本地 OCR/视觉/Embedding 模型 |
| 默认记忆引擎 | MemPalace 保存原文与情景记忆，Letta 保存结构化记忆 | 绕过身份、Vault、隐私策略直接访问数据 |
| 备用记忆引擎 | SuMeMe 二次开发的 Supermemory，全部 AI 出口指向中转站或官方 API | 使用不可审计的内置模型出口、与默认方案静默双写 |
| 数据连接器 | 官方连接器、自研连接器、文件/API 导入 | 把连接器与单一记忆引擎写死 |
| Local-only | 数据持久化在本地，按策略调用远程 API | 默认上传原文、在云端持久化、静默外发敏感资料 |
| Cloud | 服务端强隔离、远程 API 推理 | 客户端自行指定账户身份、公开附件桶 |
| Hybrid | 本地保存敏感原文，云端保存脱敏内容 | 上传未脱敏向量或原始敏感附件 |

## 服务端选择规则

- `MEMORY_PROVIDER=mempalace-letta`：默认方案；
- `MEMORY_PROVIDER=supermemory`：备用方案；
- 一次只启用一套记忆 Provider；
- 禁止运行时自动降级到另一套 Provider；
- 禁止默认双写，避免重复记忆、删除不一致和隐私策略分叉；
- 切换 Provider 不代表自动迁移历史数据，迁移必须通过独立、可审计、可回滚的任务完成；
- `/health`、管理检索接口、smoke test 和状态快照必须报告当前实际 Provider。

连接器负责采集和标准化，隐私路由负责判断数据去向，记忆 Provider 负责保存与召回，AI Provider 负责远程推理。Supermemory 的官方连接器只是可选实现，自研连接器可以通过统一的 `SourceConnector` 接口接入任一记忆 Provider。
