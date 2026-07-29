# SuMeMe 可信身份与 Vault 授权

## 目标

记忆账户不能继续由浏览器自由填写的 `user`、`X-SuMeMe-User-Id` 或
`X-SuMeMe-Account-Id` 决定。memory-gateway 支持两条可信账户来源：

1. LobeHub 服务端在完成 Better Auth/OIDC 验证后注入的 OpenAI `user` 字段；
2. 安卓、Windows、Web 客户端或其他后端提交的已验证 JWT/OIDC `sub`。

生产可以先从 `legacy-client-asserted` 切换到 `trusted-openai-user`，无需维护
LobeHub Fork。外部客户端随后使用 JWT 模式接入。

## LobeHub 当前可信链路

SuMeMe 核对的 LobeHub 上游提交为：

```text
61d8fd4687fd8f73c058a723f82230ed12ee7e5e
```

该版本的聊天路由：

- `src/app/(backend)/middleware/auth/index.ts` 使用 Better Auth session 或 OIDC JWT
  得到服务端 `userId`；
- `src/app/(backend)/webapi/chat/[provider]/route.ts` 把该 `userId` 传给
  `modelRuntime.chat(..., { user: userId })`；
- `packages/model-runtime/src/core/openaiCompatibleFactory/index.ts` 在发送下游请求时，
  先展开清理后的请求体，再写入 `{ user: options?.user }`，因此浏览器提交的同名
  字段会被服务端认证结果覆盖。

因此 `trusted-openai-user` 的安全边界是：

```text
浏览器 session / OIDC
        ↓ LobeHub checkAuth
服务端 userId
        ↓ OpenAI user 字段
GATEWAY_API_KEY + Docker 内网
        ↓
memory-gateway account scope
```

该模式只适用于受信任 LobeHub 服务端。任何持有 `GATEWAY_API_KEY` 的调用方都属于
高权限内部服务，因此该密钥不得发送到浏览器，也不得开放 memory-gateway 端口。

## 运行模式

| 模式 | 账户来源 | 缺失凭据时 | 用途 |
|---|---|---|---|
| `legacy-client-asserted` | 客户端字段 | 使用默认账户 | 旧生产兼容 |
| `trusted-openai-user` | LobeHub 服务端注入的 `user` | 返回 401 | 当前 LobeHub 严格账户隔离 |
| `jwt-preferred` | 有 JWT 时验证 `sub` | 暂时回退旧作用域 | 外部客户端灰度迁移 |
| `jwt-required` | 验证后的 JWT `sub` | 返回 401 | 外部客户端最终模式 |

在 `jwt-preferred` 模式中，只有完全没有身份令牌时才允许兼容回退。已提供但
无效、过期、受众错误或签名错误的令牌永远不会回退到客户端声明身份。

## `trusted-openai-user` 规则

推荐配置：

```env
IDENTITY_MODE=trusted-openai-user
IDENTITY_TRUSTED_UPSTREAM_ISSUER=lobehub-internal
```

规则：

- 请求必须先通过 `GATEWAY_API_KEY`；
- OpenAI 请求体必须含非空字符串 `user`；
- `X-SuMeMe-Account-Id`、`X-SuMeMe-User-Id` 等账户头全部忽略；
- 原始 LobeHub user ID 不写入存储路径；
- Vault 名称位于该账户自己的命名空间内，不能跳到另一个账户；
- `IDENTITY_TRUSTED_UPSTREAM_ISSUER` 必须长期稳定，更改它会创建新的账户命名空间。

当前模式默认使用 `default` Vault。未来由 SuMeMe 的 Vault 数据库维护所有权、共享
和权限时，再把 Vault ID 作为服务端授权结果注入。

## 账户 JWT 契约

请求头：

```http
X-SuMeMe-Identity-Token: <JWT>
X-SuMeMe-Vault-Id: work
X-SuMeMe-Device-Id: phone-a
```

JWT 必须包含：

```json
{
  "iss": "https://identity.example",
  "aud": "sumeme-memory-gateway",
  "sub": "provider-stable-user-id",
  "iat": 1785300000,
  "exp": 1785303600,
  "sumeme_vaults": ["default", "work"],
  "sumeme_default_vault": "default"
}
```

验证规则：

- 签名密钥来自 HTTPS JWKS URL 或只包含公钥的静态 JWKS；
- 必须验证 `iss`、`aud`、`sub`、`iat` 和 `exp`；
- 默认只允许非对称算法，拒绝 `none` 和 HMAC 算法；
- 令牌即使尚未过期，也不能超过 `IDENTITY_MAX_TOKEN_AGE_SECONDS`；
- 请求选择的 Vault 必须出现在 `sumeme_vaults`；
- 未提供 Vault 声明时只允许 `default`；
- 客户端提交的账户 ID 和 OpenAI `user` 字段在 JWT 模式下全部忽略。

## 存储账户键

外部身份标识不直接进入存储路径。两种可信模式统一使用：

```text
acct-<sha256(issuer + NUL + subject) 前 27 个十六进制字符>
```

结果固定为 32 个存储安全字符。这样可以：

- 避免 `a/b` 与 `a_b` 等字符归一化碰撞；
- 避免不同身份发行方使用相同 `sub` 时发生冲突；
- 不在 Qdrant、Letta、Supermemory 或对象路径中暴露原始身份标识；
- 在发行方和 subject 相同时，让 LobeHub assertion 与 JWT 迁移到同一账户键。

## 运维 Service Identity

生产 smoke、迁移和后台任务不应伪装成真实账户。它们使用独立服务令牌：

```http
X-SuMeMe-Service-Token: <GATEWAY_SERVICE_TOKEN>
X-SuMeMe-Service-Id: sumeme-smoke
X-SuMeMe-Vault-Id: production-smoke
```

服务令牌只能生成 `principal_type=service` 的作用域，不能生成账户作用域。请求
同时携带用户 JWT 和服务令牌时会被拒绝。`GATEWAY_SERVICE_TOKEN` 只允许存在
于服务器本地 `.env`、Runner 和受信任后台服务中，禁止发送到浏览器。

## JWKS 配置

推荐使用：

```env
IDENTITY_MODE=jwt-preferred
IDENTITY_ISSUER=https://identity.example
IDENTITY_AUDIENCE=sumeme-memory-gateway
IDENTITY_JWKS_URL=https://identity.example/.well-known/jwks.json
IDENTITY_ALLOWED_ALGORITHMS=RS256,ES256,EdDSA
```

离线或内部部署可以配置一行公钥 JWKS：

```env
IDENTITY_JWKS_JSON={"keys":[{"kty":"RSA","kid":"...","n":"...","e":"AQAB"}]}
```

`IDENTITY_JWKS_JSON` 如果包含 `d`、`p`、`q` 等私钥字段，服务会拒绝启动。
HTTP JWKS 默认也会被拒绝；只有隔离开发环境可以显式设置：

```env
IDENTITY_ALLOW_INSECURE_JWKS_URL=true
```

## 上线顺序

1. 生产保持 `legacy-client-asserted`，部署新代码；
2. 生成服务器本地 `GATEWAY_SERVICE_TOKEN`；
3. 运行新版 smoke，确认 service identity 可用；
4. 固定 `IDENTITY_TRUSTED_UPSTREAM_ISSUER`；
5. 切换为 `trusted-openai-user`；
6. 用两个真实 LobeHub 账户执行交叉负向测试；
7. 迁移旧默认账户记忆到第一个可信账户；
8. 为安卓、Windows 和其他客户端接入 JWT；
9. 建立 Vault 所有权表与 PostgreSQL RLS；
10. 停止读取所有旧客户端声明账户字段。

## 管理接口

`/api/memory/search` 和 `/api/memory/checkpoint` 使用独立
`GATEWAY_ADMIN_TOKEN`。管理员可以显式选择账户或 service scope，这是受信任运维
能力，不等同于普通聊天请求的用户身份。管理接口响应不得返回 JWT、密钥、用户
原文或 Provider 原始异常。
