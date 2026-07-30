# 私有 Vault 对象存储

## 当前问题

现有 LobeHub 附件桶 `RUSTFS_LOBE_BUCKET` 使用匿名读取策略，以便浏览器直接加载附件。它属于早期快速验证方案，不适合作为身份证、私人照片、音视频和完整文档等长期个人资料的正式存储边界。

直接把该桶改成私有会立即破坏现有 LobeHub 附件 URL，因此迁移必须分阶段完成。

## 第一阶段：独立私有桶

新增：

```text
RUSTFS_PRIVATE_BUCKET=sumeme-vaults
```

`rustfs-init` 每次部署都会：

1. 创建私有桶；
2. 执行 `mc anonymous set none`；
3. 如果设置私有策略失败，初始化容器失败，从而阻止依赖它的应用发布；
4. 不修改已有 LobeHub 桶的兼容策略。

新桶用于：

- attachment-worker 的原始附件；
- cloud 模式的账户/Vault 私有对象；
- hybrid 模式允许上传的脱敏派生物；
- 导入、导出和临时处理对象；
- 后续预签名 URL 下载。

## 对象键

正式对象键必须包含不可跨越的作用域，禁止只使用用户提供的文件名：

```text
accounts/<account_id>/vaults/<vault_id>/objects/<object_id>/<safe_filename>
services/<service_id>/vaults/<vault_id>/objects/<object_id>/<safe_filename>
```

要求：

- `account_id` 来自已验证身份；
- `vault_id` 必须通过 Vault 注册表授权；
- `object_id` 由服务端生成；
- 原始文件名只作为显示信息，不能决定权限或目录；
- 禁止 `..`、绝对路径、反斜杠和控制字符；
- 列表、读取、删除、复制和预签名都必须重新检查作用域，不能只依赖对象键难以猜测。

## 三种存储模式

### local-only

- 原始对象不上传私有桶；
- 云端只可保存不含用户资料的设备/同步状态；
- 用户主动发送给远程 AI 的临时内容不等于允许长期云端持久化。

### cloud

- 原始附件写入私有桶；
- 数据库只保存 scoped object key、哈希、MIME、大小、状态和来源；
- 客户端通过短时预签名 URL 上传或下载。

### hybrid

- 原始附件保留本地；
- 云端只能接收客户端明确允许的脱敏文本、缩略图或派生文件；
- 派生对象与本地原件使用不相同的对象 ID；
- 云端记录本地引用 ID，但不能假设可以读取本地原件。

## 预签名 URL

后续对象 API 必须满足：

- URL 有短期有效期；
- 默认只授权单个对象和单一动作；
- 上传前限制最大大小和 MIME；
- 下载响应使用安全的 Content-Disposition；
- 日志不记录签名查询参数；
- 删除或撤销设备后，未使用的上传授权应失效或自然快速过期。

## LobeHub 迁移

在确认当前 LobeHub 版本能够使用私有 S3 对象或 SuMeMe 代理签名 URL 前：

- 保留 legacy `lobe` 桶；
- 不把新的敏感原始资料写入 legacy 桶；
- UI 明确区分“旧聊天附件”和“私有 Vault 资料”；
- 完成附件迁移和引用替换后，才能撤销 legacy 匿名策略。

## 后续任务

1. 新增 scoped object metadata 表；
2. 新增预签名上传、完成确认、下载和删除 API；
3. 接入 Vault storage mode；
4. 实现哈希去重，但去重索引不能跨账户暴露对象存在性；
5. attachment-worker 只读取已授权对象；
6. 增加匿名访问负向 smoke test；
7. 迁移 LobeHub legacy 附件并最终关闭匿名桶。
