# Account、Vault 与系统身份隔离

## 目的

SuMeMe 的记忆不能只用一个客户端可填写的 `user_id` 区分。所有原文、附件、向量、结构化事实、缓存、导出和备份都必须绑定同一个服务端作用域：

```text
principal_type + account_id + vault_id
```

- `principal_type=account`：真实登录账户；
- `principal_type=service`：smoke test、迁移、后台任务等系统身份；
- `account_id`：由登录令牌的受验证主体映射，正式模式下客户端不可指定；
- `vault_id`：账户内独立记忆库，例如 personal、work、family；
- `device_id`：设备审计信息，不参与数据所有权判断。

## 统一作用域

代码使用 `MemoryScope` 表示隔离边界：

```text
account:alice/personal
account:alice/work
account:bob/personal
service:sumeme-smoke/production-smoke
```

四个作用域必须映射到四套不同的：

- MemPalace wing；
- Letta Agent；
- Supermemory containerTag；
- 对象存储前缀；
- 后续 PostgreSQL RLS 条件和加密密钥。

账户相同但 Vault 不同也不能共享记忆；服务身份与同名真实账户同样不能共享。

## 当前兼容阶段

本阶段先统一数据模型和 Provider 作用域。网关仍兼容 LobeHub 现有请求：

- `x-sumeme-account-id`；
- 旧 `x-sumeme-user-id`；
- OpenAI 请求体 `user`；
- `metadata.vault_id`；
- `x-sumeme-vault-id`。

这些值当前仍属于客户端声明，所以 `/health` 会报告：

```text
identity_enforcement=legacy-client-asserted
```

这不是最终安全边界。下一阶段必须验证 JWT/OIDC，并从已验证的 `sub` 生成 `account_id`；届时客户端提供的账户 ID 将被忽略或拒绝。

## 旧数据兼容

### MemPalace

Phase 1 使用：

```text
user_<user_id>
```

新数据使用：

```text
scope_acct.<account_id>.vault.<vault_id>
scope_svc.<service_id>.vault.<vault_id>
```

默认 Vault 在迁移期同时搜索旧 wing 和新 wing，新写入只进入新作用域。非默认 Vault 从创建起完全独立。

### Letta

状态文件升级为 schema 3：

```json
{
  "schema_version": 3,
  "agents": {
    "acct.default.vault.default": "agent-...",
    "svc.sumeme-smoke.vault.production-smoke": "agent-..."
  }
}
```

旧 `{ "agent_id": "..." }` 和 schema 2 用户映射会在加载时迁移到默认 Vault，避免正式记忆与 smoke Agent 混用。

### Supermemory

`containerTag` 包含完整作用域，`customId` 的幂等哈希也包含作用域。同一内容写入不同账户或 Vault 时必须产生不同容器和不同 ID。

## Smoke test

生产 smoke 固定使用：

```text
service:sumeme-smoke/production-smoke
```

聊天写入、管理检索、Letta Agent、MemPalace wing、Supermemory containerTag 和 RustFS 临时对象都使用该作用域，不接触真实账户的默认 Vault。

## 下一阶段：强制身份

1. 验证 LobeHub/OIDC JWT 的签名、issuer、audience、expiry；
2. 从已验证 `sub` 映射内部不可枚举的 `account_id`；
3. 校验账户对 `vault_id` 的所有权和角色；
4. 禁止普通请求设置 `principal_type=service`；
5. PostgreSQL 所有业务表加入 `account_id + vault_id` 并启用 RLS；
6. RustFS 改为私有桶和短时预签名 URL；
7. 增加 A 账户访问 B 账户数据的读取、写入、搜索、删除、导出负向测试。
