# Scoped Object Metadata

## 目的

私有 RustFS 桶只解决“对象不能匿名读取”，不能单独证明对象属于谁。SuMeMe 还需要一层服务端元数据，把每个对象绑定到可信作用域：

```text
principal_type + account_id + vault_id + object_id
```

对象权限不能依赖文件名、URL 难猜或客户端提交的路径。

## 对象键

对象键由服务端生成：

```text
accounts/<account_id>/vaults/<vault_id>/objects/<object_id>.<ext>
services/<service_id>/vaults/<vault_id>/objects/<object_id>.<ext>
```

规则：

- `account_id`、`vault_id` 来自已验证身份和 Vault 注册表；
- `object_id` 是服务端生成的随机 128-bit ID；
- 原始文件名不进入权限路径，只保留安全化后的显示名称；
- 仅保留最多 16 个小写字母或数字组成的扩展名；
- 同名文件不会覆盖；
- service principal 与真实账户永远使用不同前缀。

## 元数据状态机

```text
reserved → ready → deleted
```

### reserved

服务端已经：

- 验证账户和 Vault；
- 检查存储模式；
- 生成对象 ID 和对象键；
- 记录预期大小和 SHA-256。

此时对象不能被正常下载或进入 attachment-worker。

### ready

只有实际对象的大小和 SHA-256 与预留值一致，才能标记 ready。后续接入 RustFS 后，完成接口还必须执行 `HEAD` 或受控流式校验，不能仅相信客户端报告。

### deleted

当前实现为软删除元数据状态。后续对象删除任务负责：

1. 撤销下载授权；
2. 删除 RustFS 对象；
3. 删除或作废派生内容、向量和记忆引用；
4. 记录不含用户内容的审计事件；
5. 按保留政策最终清除元数据。

## 三种存储模式

### local-only

禁止创建云端对象记录，返回稳定错误：

```text
object_cloud_storage_disabled
```

本地客户端使用自己的加密对象库和本地引用 ID。

### cloud

允许 `raw`、`thumbnail`、`transcript`、`temporary` 和经处理的派生对象。原始对象写入私有桶。

### hybrid

云端对象必须同时满足：

- `sanitized_for_cloud=true`；
- 对象类型不是 `raw`；
- 原件只保存在本地；
- 云端派生对象使用独立对象 ID；
- 可保存本地引用 ID，但它不能被当作文件路径或权限凭据。

## 哈希与去重

每个对象必须有合法 SHA-256。索引包含完整作用域，因此未来去重查询只能在同一个账户和 Vault 内完成。

禁止向账户 A 返回“账户 B 已经存在同哈希文件”之类的信息，因为这会形成跨账户存在性侧信道。

## 当前实现

`app.objects.ObjectRegistry` 已实现：

- SQLite WAL 持久化；
- scoped object key；
- cloud/local-only/hybrid 策略检查；
- 文件名、MIME、大小、SHA-256 和本地引用校验；
- reserve、complete、list、get、soft-delete；
- 跨账户、跨 Vault 和 account/service 隔离；
- 并发预留唯一对象 ID。

当前模块尚未签发预签名 URL，也不直接访问 RustFS。这是有意的分层：下一阶段会加入 S3 兼容客户端、短时上传授权、服务端对象校验和下载授权；在此之前不会暴露半成品上传接口给客户端。
