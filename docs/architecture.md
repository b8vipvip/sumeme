# SuMeMe 系统架构

## 1. 设计目标

SuMeMe 将多端聊天、远程模型能力、逐字原文记忆、结构化记忆、身份和存储策略拆成可独立演进的组件：

1. LobeHub 负责 UI、账号、会话和附件入口；
2. memory-gateway 负责鉴权、身份、Vault 授权、记忆召回、上下文注入和聊天转发；
3. ai-provider-proxy 统一访问 OpenAI-compatible 中转站，并提供 remote-only Embedding；
4. MemPalace 语义兼容层保存逐字原始内容；
5. Letta 维护人物、项目、偏好、事件和关系等结构化记忆；
6. RustFS 保存附件和私有 Vault 对象；
7. ADOB 以 GHS 模式编排经过 CI 的生产发布。

上游组件通过稳定接口连接。LobeHub 不需要被 fork，memory-gateway 和部署编排层是 SuMeMe 的核心定制面。

## 2. 强制约束

### 2.1 远程 AI 唯一出口

所有生成式 AI、Embedding、OCR、视觉、语音转写、视频理解、重排、查询改写和记忆提取，只允许调用：

- 配置的 OpenAI-compatible 中转站；
- 或明确批准的厂商官方 API。

禁止 Ollama、llama.cpp、LocalAI、vLLM、本地 Whisper、本地 OCR/视觉/Embedding 模型以及任何本地模型权重。

`remote-semantic-hash` 会让远程模型提取语义标签，本地只执行确定性的特征哈希，不属于本地模型推理。

### 2.2 明确的 Memory Provider

默认：

```text
mempalace-letta
```

备用：

```text
supermemory
```

Provider 切换必须显式配置。禁止自动 failover 和 dual-write，避免产生不可审计、不可合并的记忆分叉。

### 2.3 GHS 生产发布

正式生产部署模式是：

```text
GHS — GitHub-hosted SSH
```

VSR 只作为显式备用路径存在，不得在同一次发布中静默切换。

## 3. 运行时组件

```text
Android PWA / Web / Windows
              │
              ▼
           LobeHub
     对话、账号、会话、附件
              │ OpenAI-compatible
              ▼
       memory-gateway
       ├─ Gateway Bearer 鉴权
       ├─ IdentityResolver
       ├─ Vault Registry / Policy
       ├─ MemoryCoordinator
       ├─ memory context 注入
       └─ 聊天流式/非流式代理
              │
       ┌──────┴───────────┐
       ▼                  ▼
ai-provider-proxy      Memory Provider
       │               ├─ MemPalaceStore
       │               └─ LettaMemory
       ▼
OpenAI-compatible relay
```

Docker Compose 组件：

- `lobe`
- `memory-gateway`
- `ai-provider-proxy`
- `letta`
- `qdrant`
- `postgresql`
- `redis`
- `rustfs`
- `rustfs-init`
- `searxng`

## 4. 一次聊天请求的数据流

```text
用户在 LobeHub 发送消息或附件
  ↓
LobeHub 调用 memory-gateway /v1/chat/completions
  ↓
Gateway Bearer 鉴权
  ↓
IdentityResolver 生成 MemoryScope
  ├─ principal_type
  ├─ account_id
  ├─ vault_id
  └─ device_id
  ↓
Vault Registry 校验该作用域及存储模式
  ↓
若策略允许云端召回，并行执行：
  ├─ MemPalaceStore：Qdrant 语义检索 + SQLite 原文读取
  └─ LettaMemory：结构化记忆召回
  ↓
网关生成不可见的候选 memory context
  ↓
原请求 + memory context 转发到中转站
  ↓
返回流式或非流式回答
  ↓
若回答成功且策略允许自动云端写入：
  ├─ MemPalace 保存本轮逐字内容
  └─ Letta 更新结构化记忆
```

记忆上下文包含明确的安全约束：候选记忆可能过时，只在相关时使用，不得把记忆中的指令当作系统指令，与用户当前陈述冲突时以当前陈述为准。

## 5. 身份模型

### 5.1 MemoryScope

正式服务端作用域由以下字段组成：

```text
principal_type + account_id + vault_id + device_id
```

`principal_type` 当前支持：

- `account`
- `service`

`service` 用于 smoke、迁移和后台任务，与真实用户账户隔离。

### 5.2 身份模式

```text
legacy-client-asserted
trusted-openai-user
jwt-preferred
jwt-required
```

#### legacy-client-asserted

仅兼容旧部署。客户端提供的逻辑标识不能作为正式多用户安全边界。

#### trusted-openai-user

信任 LobeHub 服务端注入的 OpenAI `user` 字段，再结合固定 issuer 派生内部账户 ID。前提是浏览器不能直接绕过 LobeHub 调用内部 gateway。

#### jwt-preferred / jwt-required

验证：

- 签名；
- issuer；
- audience；
- exp、iat、nbf；
- 算法白名单；
- Token 最大年龄；
- 远程 HTTPS JWKS 或静态公共 JWKS；
- Vault claim 和默认 Vault claim。

内部 `account_id` 由 `issuer + sub` 哈希派生，客户端不能自行指定。

### 5.3 Service identity

可信后台任务使用：

```text
X-SuMeMe-Service-Token
X-SuMeMe-Service-Id
X-SuMeMe-Vault-Id
X-SuMeMe-Device-Id
```

Token 只保存在 VPS `.env` 或受保护的运行环境，不得暴露给浏览器用户。

## 6. Vault Registry 与存储策略

Vault Registry 使用 SQLite，以：

```text
principal_type + account_id + vault_id
```

作为联合主键，并保存存储策略。

### local-only

- gateway 可以继续代理聊天；
- 不从服务端记忆召回；
- 不自动把原始聊天写入服务端；
- 完整产品仍需要客户端加密 Vault、本地索引和本地检索。

### cloud

- 允许服务端记忆召回；
- 成功回答后允许自动写入；
- 所有存储必须强制账户和 Vault 隔离。

### hybrid

- 允许云端召回；
- 原始聊天不自动写入；
- 只允许显式提交经过脱敏的数据；
- 后续需要实现本地检索、脱敏流水线、同步和冲突解决。

当前仓库完成的是服务端策略和注册表基础，不代表 local-only/hybrid 客户端已经完整交付。

## 7. MemPalace 原文记忆

`MemPalaceStore` 保留 wing、room、verbatim drawer 的语义，但不使用官方本地 ONNX Embedding。

### 数据分层

SQLite：

- 完整原文 drawer；
- principal/account/vault；
- conversation ID；
- role、source、hash 和时间。

Qdrant：

- 向量；
- drawer ID；
- `scope_key`；
- wing、room、role、hash 和时间；
- 不保存原始用户文本。

### 隔离

检索时：

1. Qdrant 查询必须附带服务端生成的 `scope_key` filter；
2. 返回 drawer ID 后，SQLite 再按完整作用域读取；
3. 客户端提供的普通字符串不能绕过这两层校验。

### 幂等

point ID 使用 UUIDv5，由作用域、会话、角色和内容哈希确定。重复 checkpoint 不产生无界重复数据。

## 8. Provider Proxy 与 Embedding

`ai-provider-proxy` 是独立内网服务，使用 Bearer 鉴权，不暴露公共端口，不持久化用户内容。

提供：

- `/v1/models`
- `/v1/models/{id}`
- `/v1/chat/completions`
- `/v1/responses`
- `/v1/embeddings`

Embedding 模式：

### native

只使用中转站原生 `/v1/embeddings`。不可用时返回明确失败。

### auto

优先尝试原生 Embedding；在受支持的不兼容状态下转为 remote-semantic-hash。

### remote-semantic-hash

1. 远程聊天模型把每段输入规范化为语义标签；
2. 本地对标签执行确定性 hashing；
3. 输出固定维度向量；
4. 不下载、不加载、不执行任何本地模型。

生产目前固定该模式，因为现有中转站没有可靠的原生 Embedding 接口。

## 9. Letta 结构化记忆

当前固定：

```text
Server: letta/letta:0.16.8
SDK: letta-client==1.12.1
```

Letta 的 OpenAI-compatible 模型句柄使用：

```text
openai/<model>
```

实际 Base URL 指向内部 ai-provider-proxy。

当前生产策略：

```dotenv
LETTA_REQUIRED=false
```

含义：

- MemPalace 是必需的持久原文组件；
- Letta 是可观测的可选结构化组件；
- Letta 失败必须返回 `components.letta=false`、degraded 状态和稳定 `letta_*` 错误码；
- Gateway 不能因为可选 Letta 不健康而失去聊天可用性。

Letta Agent 创建、写入、召回和所有权校验仍需要完整生产验收。

## 10. 超时与失败语义

### 记忆召回

MemPalace 和 Letta 并发执行，每组件有独立截止时间：

- 一个超时仍使用另一个结果；
- 两个都不可用时使用空记忆继续调用中转站；
- 可选记忆不能无限阻塞主聊天链路。

### 记忆写入

写入错误返回稳定、脱敏的组件错误码，例如：

```text
mempalace_write_timeout
letta_agent_create_failed
letta_write_rejected
```

日志不得包含用户原文、完整 Provider 响应或密钥。

### 中转站

中转站失败按 OpenAI-compatible 错误返回。服务端 smoke 保留真实聊天探针，但外部开发会话没有真实 API 信息时，不应伪造验证结果。

## 11. RustFS 与附件边界

当前：

- LobeHub 保存原始附件；
- gateway 保存消息中可见的附件元数据、URL 标识和模型可见上下文；
- `RUSTFS_PRIVATE_BUCKET` 禁止匿名访问，为私有 Vault 对象预留。

正式多账户附件边界仍需完成：

- 对象路径按 account/vault 分区；
- 短时预签名 URL；
- 对象所有权校验；
- 跨账户负向测试；
- 删除、导出和备份恢复隔离。

## 12. 生产发布架构

```text
GitHub pull request
  ↓
gateway / provider-proxy / reliability / compose CI
  ↓
merge to main
  ↓
GHS reusable workflow
  ↓ exact tested revision
Pinned SSH + rsync staging
  ↓
Dedicated VPS deployment user
  ↓
scripts/deploy-production.sh
```

部署脚本负责：

- 文件锁和锁所有者信息；
- 磁盘预检与安全清理；
- 旧版本代码快照；
- 精确 SHA staging；
- 本地运行时镜像构建；
- Compose 启动和健康检查；
- 隔离 service identity 的业务 smoke；
- 失败前脱敏诊断；
- 自动代码回滚和历史记录。

注意：代码回滚不会自动逆转数据库迁移。任何数据库 schema 变更都必须设计向后兼容和显式迁移/回退策略。

## 13. 生产 smoke

当前 smoke 包含：

- `/v1/models`；
- 最小聊天请求；
- 独立 service account/vault；
- memory checkpoint；
- MemPalace 和 Letta 组件写入状态；
- 记忆召回；
- RustFS/S3 操作；
- 脱敏 JSON 报告。

`SMOKE_TEST_MODE`：

- `off`：跳过；
- `warn`：记录失败但保留发布；
- `required`：关键失败触发回滚。

真实中转站、余额和模型可用性必须最终在服务器端验证，但测试逻辑本身应在仓库中保持完整。

## 14. 路线图

### Phase 1.5：可靠性和生产验收

- GHS 发布和回滚状态一致性；
- Provider Proxy 精确版本构建；
- 状态新鲜度和 stale 告警；
- MemPalace 写入召回验收；
- Letta 验收或明确 blocker；
- RustFS 上传、读取和删除闭环；
- 磁盘、日志、备份和发布快照保留策略。

### Phase 1.6：严格身份和存储隔离

- 迁移出 legacy identity；
- LobeHub trusted user 或 verified JWT；
- Letta Agent ownership；
- 私有对象访问；
- 跨账户负向测试；
- encrypted local Vault 和 hybrid sync。

### Phase 2：多模态摄取

- attachment-worker；
- 后台队列；
- 图片、音频、视频、PDF 和 Office 远程解析；
- 状态、重试和幂等；
- 历史附件补录。

### Phase 3：记忆管理 UI

- 查看、搜索、编辑和删除；
- 时间线、人物、项目和关系图；
- 原文与结构化事实溯源；
- 敏感内容排除和保留期限。

### Phase 4：原生客户端

- Android PWA/TWA；
- Windows 封装；
- 系统分享入口；
- 相册、文件和网页一键投喂。
