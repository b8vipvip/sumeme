# 记忆 Provider 切换与 Supermemory 备用方案

## 决策

SuMeMe 支持两套服务端记忆实现：

1. `mempalace-letta`：默认方案；
2. `supermemory`：备用方案，由 SuMeMe 维护的二次开发版本提供。

服务端通过 `MEMORY_PROVIDER` 显式选择当前方案。任何时刻只允许一套 Provider 承担在线读写。

## 为什么不自动故障切换

记忆系统不是无状态模型代理。一次写入可能生成原文、向量、事实、关系和版本链。自动从 A 切到 B 会造成：

- 同一对话只写入其中一套；
- 两套系统的删除、修改和遗忘状态不同；
- 召回结果随故障状态变化；
- 混合模式的脱敏策略可能不一致；
- 故障恢复后出现重复写入。

因此当前设计只允许运维人员修改配置并重新部署，不做静默自动切换或默认双写。

## 默认方案

```text
MEMORY_PROVIDER=mempalace-letta
```

数据流：

```text
memory-gateway
├── MemPalace：原始对话、完整上下文、可追溯片段
└── Letta：结构化事实、人物、偏好、项目和关系
```

## 备用方案

```text
MEMORY_PROVIDER=supermemory
SUPERMEMORY_BASE_URL=https://memory.example.com
SUPERMEMORY_API_KEY=...
```

memory-gateway 使用兼容接口：

- 写入：`POST /v3/documents`；
- 检索：`POST /v4/search`；
- 用户隔离：`containerTag`；
- 幂等写入：`customId`。

路径均可通过环境变量修改，以适配 SuMeMe 的 Supermemory Fork。

## Supermemory Fork 的强制要求

二次开发版本必须满足：

1. 聊天、Embedding、OCR、视觉、转写、重排、查询改写和记忆提取全部调用中转站或厂商官方 API；
2. 不包含 Ollama、llama.cpp、LocalAI、vLLM 或任何本地模型权重；
3. 所有 AI 出口有统一配置、审计和超时；
4. `account_id + vault_id` 是服务端强制隔离条件，客户端不能自行绕过；
5. 支持 Local-only、Cloud、Hybrid 三种隐私策略；
6. 保留通用 documents/search API，不要求使用 Google Drive、Gmail、Notion 等官方连接器；
7. 支持 SuMeMe 自研 `SourceConnector` 写入标准化数据；
8. 提供导出、删除、迁移和跨账户负向测试。

## 切换流程

```text
备份当前 Provider
→ 停止新写入或进入维护窗口
→ 执行显式迁移任务（可选）
→ 修改 MEMORY_PROVIDER
→ 部署
→ /health 确认 Provider
→ 执行 Provider 感知 smoke test
→ 更新 ops-status
```

切换配置本身不会迁移历史数据。未迁移时，新 Provider 只能召回切换后写入的数据。

## 回滚

回滚时恢复原 `MEMORY_PROVIDER` 和对应密钥，然后重新部署。应用代码回滚不能代替记忆数据迁移回滚；任何迁移任务必须记录批次、来源 ID、目标 ID、校验结果和反向操作。
