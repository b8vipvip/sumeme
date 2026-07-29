# 远程 AI 与可插拔数据连接器架构约束

> 状态：Accepted  
> 日期：2026-07-29

## 1. 决策

SuMeMe 的所有 AI 能力只允许通过以下两类远程接口调用：

1. 用户配置的 OpenAI-compatible 中转站；
2. 模型厂商官方 API。

项目禁止捆绑、下载、启动或调用任何本地部署 AI 模型及本地模型服务，包括但不限于 Ollama、llama.cpp、LocalAI、vLLM、本地 Whisper、本地 OCR 模型、本地视觉模型和本地 Embedding 模型。

该限制覆盖：

- 对话生成；
- Embedding；
- 视觉理解；
- OCR；
- 语音识别和转写；
- 视频关键帧理解；
- 摘要、脱敏、分类和实体提取；
- 记忆提取、冲突判断和记忆压缩；
- 重排序及其他由模型完成的语义处理。

非 AI 的确定性本地处理允许保留，例如文件哈希、加解密、压缩、格式读取、规则匹配、正则脱敏、音视频切片和数据库查询。

## 2. “完全本地”模式的定义

完全本地只表示：

- 原文、附件、解析结果、结构化记忆、向量索引和元数据持久保存在用户设备；
- SuMeMe 云端不持久保存这些内容；
- 本地 Vault 和本地密钥不上传。

完全本地不表示 AI 推理在设备上执行。需要 AI 时，客户端通过隐私策略选择最小必要内容，再调用中转站或官方 API。

若用户要求某条内容绝不离开设备，则该内容不得调用远程 AI，只能使用非 AI 的本地确定性处理，或跳过相应 AI 功能。

## 3. AI Provider 抽象

所有组件必须通过统一的 `AIProvider` 层访问模型，不得直接写死厂商 SDK：

```text
AIProvider
├── OpenAICompatibleRelayProvider
├── OpenAIOfficialProvider
├── AnthropicOfficialProvider
├── GoogleOfficialProvider
└── OtherOfficialProvider
```

Provider 必须声明能力：

- chat
- embedding
- vision
- ocr
- transcription
- rerank
- structured_output

调用前执行能力探测、模型白名单、数据策略检查和账户成本限制。

## 4. Supermemory 连接器的定位

Google Drive、Gmail、Notion、OneDrive、GitHub、S3 和网页爬虫只是 Supermemory 提供的可选数据同步入口，不是使用 Supermemory 的前置条件。

SuMeMe 可以完全不启用这些官方连接器，直接把以下内容通过 Supermemory 的文档、文件、会话和记忆 API 写入：

- LobeHub 对话；
- SuMeMe 客户端上传的文件；
- 本地脱敏后的事实；
- 自己解析或采集的数据；
- 自定义数据源同步结果。

## 5. 自定义连接器

SuMeMe 自己维护统一的 `SourceConnector` 接口：

```text
SourceConnector
├── LobeHubConnector
├── LocalFolderConnector
├── AndroidShareConnector
├── WindowsFileConnector
├── BrowserClipperConnector
├── WeChatExportConnector
├── EmailImportConnector
├── WebCrawlerConnector
└── CustomConnector
```

每个连接器只负责：

1. 获取源数据；
2. 生成稳定的 `source_id` 和 `revision`；
3. 标注 `account_id`、`vault_id`、来源和隐私级别；
4. 将标准化内容交给 SuMeMe 摄取管线。

摄取管线再按用户选择把内容发送到 MemPalace、Letta 或 Supermemory。这样连接器不会与具体记忆引擎绑定。

## 6. Supermemory 的二次开发边界

允许三种扩展方式：

1. 在 SuMeMe 内开发自定义连接器，然后调用 Supermemory 通用文档/文件 API；
2. 在自托管 Supermemory 代码中增加新的 provider/connector；
3. 完全绕过 Supermemory 连接器模块，只使用其记忆、搜索、文档和 Profile 能力。

优先选择第 1 种，因为升级 Supermemory 时冲突最少，也便于同一个连接器同时支持 MemPalace、Letta 和 Supermemory。

只有在需要 Supermemory 内部统一处理 OAuth、Webhook、增量游标和定时同步时，才考虑第 2 种。

## 7. 隐私与存储模式

### Local-only

数据本地持久化；AI 请求仍只走中转站或官方 API；发送前执行最小化和隐私策略。

### Cloud

数据在 SuMeMe 服务端按 `account_id + vault_id` 强隔离；AI 请求由服务端通过中转站或官方 API 发起。

### Hybrid

敏感原文和附件留在本地；云端只接收脱敏结果；AI 调用前由客户端或可信隐私层再次检查，禁止把本地敏感原文意外发送给远程 API。

## 8. 强制检查

CI 和运行时必须逐步加入以下保护：

- 禁止依赖常见本地模型运行库和本地推理服务；
- 禁止配置 localhost/内网模型端点作为 AI Provider；
- 模型端点必须来自允许的中转站或官方域名列表；
- 所有模型调用记录 provider、模型、能力类型、账户和数据策略结果，但不记录敏感正文；
- 对“仅本地且禁止外发”的资料，任何远程 AI 调用都必须被阻止并留下审计事件。

## 9. 结果

SuMeMe 的“本地、云端、混合”描述的是数据存储和隐私路由，而不是模型部署位置。记忆引擎可本地或云端部署，但其内部需要模型能力时，也必须统一调用中转站或厂商官方 API。