# SuMeMe 可信身份与 Vault 授权

## 目标

记忆作用域不能继续由客户端自由填写的 `user`、`X-SuMeMe-User-Id` 或
`X-SuMeMe-Account-Id` 决定。可信模式下，memory-gateway 必须先验证由受信任
身份系统签发的 JWT，再从经过验证的声明生成账户和 Vault 作用域。

当前生产部署仍保持 `IDENTITY_MODE=legacy-client-asserted`，因为现有 LobeHub
容器尚未把服务端会话转换成 `X-SuMeMe-Identity-Token`。在身份桥接完成前，
不得把健康状态描述为“严格多账户隔离”。

## 运行模式

| 模式 | 有 JWT | 无 JWT | 用途 |
|---|---|---|---|
| `legacy-client-asserted` | 拒绝未配置的身份令牌 | 使用旧客户端声明 | 现有生产兼容 |
| `jwt-preferred` | 必须验证，失败不降级 | 暂时回退旧作用域 | 灰度迁移 |
| `jwt-required` | 必须验证 | 返回 401 | 最终严格模式 |

在 `jwt-preferred` 模式中，只有完全没有身份令牌时才允许兼容回退。已提供但
无效、过期、受众错误或签名错误的令牌永远不会回退到客户端声明身份。

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

外部 `sub` 不直接进入存储路径。网关使用：

```text
oidc-<sha256(issuer + NUL + subject) 前 32 个十六进制字符>
```

这样可以：

- 避免 `a/b` 与 `a_b` 等字符归一化碰撞；
- 避免不同身份发行方使用相同 `sub` 时发生冲突；
- 不在 Qdrant、Letta、Supermemory 或对象路径中暴露原始身份标识。

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

1. 生产继续保持 `legacy-client-asserted`；
2. 在 LobeHub 服务端模型请求路径加入可信身份桥接；
3. 身份桥只从已验证服务端会话读取用户 ID，不接受浏览器自报账户 ID；
4. 身份桥签发或转发符合本文件契约的短期 JWT；
5. 切换为 `jwt-preferred`，观察账户和 Vault 映射；
6. 验证生产 smoke 使用独立 service identity；
7. 完成旧默认账户记忆迁移；
8. 切换为 `jwt-required`；
9. 停止读取所有客户端声明账户字段。

## 管理接口

`/api/memory/search` 和 `/api/memory/checkpoint` 使用独立
`GATEWAY_ADMIN_TOKEN`。管理员可以显式选择账户或 service scope，这是受信任运维
能力，不等同于普通聊天请求的用户身份。管理接口响应不得返回 JWT、密钥、用户
原文或 Provider 原始异常。
