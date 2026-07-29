# Provider 与连接器职责矩阵

| 模块 | 允许 | 禁止 |
|---|---|---|
| AI Provider | OpenAI-compatible 中转站、OpenAI/Anthropic/Google 等官方 API | Ollama、llama.cpp、LocalAI、vLLM、本地 Whisper、本地 OCR/视觉/Embedding 模型 |
| 记忆引擎 | MemPalace、Letta、Supermemory、本地数据库或向量索引 | 绕过身份、Vault、隐私策略直接访问数据 |
| 数据连接器 | 官方连接器、自研连接器、文件/API 导入 | 把连接器与单一记忆引擎写死 |
| Local-only | 数据持久化在本地，按策略调用远程 API | 默认上传原文、在云端持久化、静默外发敏感资料 |
| Cloud | 服务端强隔离、远程 API 推理 | 客户端自行指定账户身份、公开附件桶 |
| Hybrid | 本地保存敏感原文，云端保存脱敏内容 | 上传未脱敏向量或原始敏感附件 |

连接器负责采集和标准化，隐私路由负责判断数据去向，记忆 Provider 负责保存与召回，AI Provider 负责远程推理。