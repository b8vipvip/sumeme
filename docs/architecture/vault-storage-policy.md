# Vault 所有权与三种存储模式

## 目标

SuMeMe 的每一份长期记忆都必须属于一个不可跨越的作用域：

```text
principal_type + account_id + vault_id
```

- `principal_type=account`：真实用户账户；
- `principal_type=service`：smoke、迁移、后台任务等系统身份；
- `account_id`：由可信身份派生，客户端不能覆盖；
- `vault_id`：账户下的个人、工作、家庭、项目等独立记忆库。

服务身份即使使用与真实账户相同的文本 ID，也不能进入账户命名空间。

## 服务端 Vault 注册表

memory-gateway 在持久卷中维护 SQLite 注册表：

```text
/data/gateway/vaults.sqlite3
```

主键是：

```text
(principal_type, account_id, vault_id)
```

注册表只保存作用域、存储模式和时间，不保存原文、附件、模型密钥或外部身份 subject。

### 自动注册规则

- service identity：允许自动注册独立 service vault；
- 已验证 JWT：token 中获授权的 vault 允许自动注册；
- legacy 兼容模式：为现有部署允许自动注册，但不视为正式安全边界；
- LobeHub `trusted-openai-user`：只自动注册 `default`；具名 vault 必须先由受信任管理流程创建。

这避免浏览器仅修改 `metadata.vault_id` 就无限创建未治理的记忆库。

## 存储模式

### `local-only`

含义是**资料持久化在用户设备**，不是本地运行 AI 模型。

服务端行为：

- 聊天仍可按用户选择调用中转站或官方 API；
- 不从服务端记忆 Provider 召回；
- 不向 MemPalace、Letta 或 Supermemory 写入；
- 管理 checkpoint 拒绝云端写入。

本地客户端未来负责本地加密 Vault、索引和最小上下文选择。

### `cloud`

默认兼容模式：

- 允许服务端召回；
- 正常聊天后自动写入；
- 当前默认 Provider 为 MemPalace + Letta；
- 可通过显式服务端配置切换到 SuMeMe 维护的 Supermemory 兼容方案；
- 不允许静默双写或自动故障切换。

### `hybrid`

敏感原文保留本地，云端只保存用户设备产生的脱敏记忆：

- 允许召回已经存在的云端脱敏记忆；
- 普通聊天请求和助手原文不会自动写入云端；
- 云端 checkpoint 必须显式声明 `sanitized_for_cloud=true`；
- 声明只表示客户端已执行隐私流程，服务端不把它当作语义脱敏证明；
- 后续客户端隐私路由器必须先脱敏文本，再生成上传云端的 Embedding。

服务端不会把敏感原文生成的向量当成“已脱敏”。

## AI 出口约束

三种存储模式都遵守同一规则：

- 生成、Embedding、视觉、OCR、转写、重排和记忆提取只调用用户配置的中转站或厂商官方 API；
- 禁止 Ollama、llama.cpp、LocalAI、vLLM、本地 Whisper、本地模型权重及任何隐式本地模型回退；
- 本地允许执行文件读取、哈希、加密、压缩、原生文本提取和确定性规则等非 AI 操作。

所以“完全本地”准确表示数据持久化位置，而不是模型推理位置。

## 管理接口

管理员令牌保护：

```http
PUT /api/vaults/policy
POST /api/vaults/list
```

创建或更新策略示例：

```json
{
  "principal_type": "account",
  "account_id": "acct-example",
  "vault_id": "personal",
  "storage_mode": "hybrid"
}
```

混合模式的显式脱敏写入：

```json
{
  "principal_type": "account",
  "account_id": "acct-example",
  "vault_id": "personal",
  "sanitized_for_cloud": true,
  "request_payload": {
    "messages": [
      {"role": "user", "content": "已经在设备上完成脱敏的内容"}
    ]
  },
  "assistant_text": "已经在设备上完成脱敏的结果"
}
```

管理接口不是最终用户 UI。后续 Android、Windows 和 Web 客户端必须通过正式账户授权流程管理自己的 Vault，不能获得全局管理员令牌。

## 当前边界与后续工作

本阶段完成：

- 持久化 Vault 注册表；
- 账户、Vault 和 service principal 的复合隔离；
- 三种模式在网关读写层的安全默认行为；
- 管理策略接口和自动测试。

后续仍需：

1. PostgreSQL RLS 与对象存储私有路径；
2. 账户自助 Vault 管理 API；
3. 本地加密 Vault 与同步协议；
4. 混合模式客户端隐私分类、脱敏和冲突解决；
5. 每条资料对默认 Vault 模式的覆盖规则；
6. 导出、删除、密钥轮换和审计记录。
