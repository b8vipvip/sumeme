# SuMeMe 开发计划

> 最后更新：2026-07-30  
> 当前阶段：Phase 1 已完成；Phase 1.5 生产验收与 Phase 1.6/1.7 基础架构并行推进

## 1. 产品目标

SuMeMe 是面向个人长期记忆的多模态 AI 系统。用户可以从 Android、Web、Windows 持续发送文本、图片、音频、视频、文档和网页；系统保存可追溯原文，并提取人物、项目、事件、偏好、关系和时间变化，在后续对话中按相关性召回。

不可变原则：

1. 原始资料与 AI 提取记忆分层保存，摘要不能替代原文；
2. 所有生成、Embedding、视觉、OCR、转写、重排和记忆提取只允许调用用户配置的中转站或厂商官方 API；
3. 禁止 Ollama、llama.cpp、LocalAI、vLLM、本地 Whisper、本地模型权重和隐式本地模型回退；
4. `LobeHub + MemPalace + Letta` 是默认云端组合，Supermemory 是可显式切换的备用方案；
5. 每个账户、Vault 和系统身份必须强隔离，客户端不能自行声明另一个账户；
6. 支持 `local-only`、`cloud`、`hybrid` 三种数据持久化模式；
7. 每个阶段必须具备自动测试、健康检查、脱敏状态、可审计发布和回滚边界。

## 2. 默认架构

```text
Android / Windows / Web / LobeHub
                  │
                  ▼
         身份认证与 Vault 授权
   principal_type + account_id + vault_id
                  │
                  ▼
          Privacy / Storage Router
        local-only / cloud / hybrid
             │                 │
             ▼                 ▼
        本地客户端栈       SuMeMe 云端记忆栈
                              │
                   ┌──────────┴──────────┐
                   ▼                     ▼
              MemPalace                Letta
             原文与细节          事实、人物、项目、关系
                   └──────────┬──────────┘
                              ▼
                    中转站或官方 AI API
```

备用服务端方案：

```text
MEMORY_PROVIDER=supermemory
```

备用方案不与默认方案静默双写，也不自动故障切换。切换、迁移、回滚和删除必须显式执行。

## 3. 三种存储模式

### `local-only`

- 原文、附件、索引和长期记忆持久化在用户设备；
- 云端 memory-gateway 不读取或写入长期记忆；
- 用户仍可选择把当前问题所需的最小内容发送到中转站或官方 API；
- “本地”表示数据位置，不表示使用本地 AI 模型。

### `cloud`

- 数据和记忆保存在 SuMeMe 服务端；
- 默认使用 MemPalace + Letta；
- 每条数据库记录、对象、向量、Agent、缓存、导出和备份都必须受账户与 Vault 边界约束。

### `hybrid`

- 敏感原文和原始附件保存在本地；
- 云端只接收客户端产生的脱敏摘要、事实和由脱敏文本生成的向量；
- 普通聊天原文不能自动写入云端记忆；
- 云端可以召回已有脱敏记忆；
- 客户端必须承担隐私分类、脱敏和本地/云端合并职责。

## 4. 阶段状态

| 阶段 | 状态 | 完成目标 |
|---|---|---|
| Phase 1 基础闭环 | 已完成 | LobeHub、OpenAI-compatible 网关、MemPalace + Letta、RustFS、自动 CI/部署 |
| Phase 1.5 可靠性 | 生产验收中 | 真实聊天、记忆写入/召回、RustFS、磁盘保护、状态新鲜度、稳定发布 |
| Phase 1.6 可信身份与隔离 | 进行中 | JWT/OIDC、LobeHub 可信用户、service identity、账户/Vault 所有权、负向越权测试 |
| Phase 1.7 存储策略与隐私路由 | 进行中 | local-only/cloud/hybrid、持久 Vault policy、本地/云端同步契约 |
| Phase 2 多模态摄取 | 未开始 | 图片、PDF、音频、视频、Office 异步解析和历史补录 |
| Phase 3 记忆管理 | 未开始 | 搜索、查看、编辑、删除、时间线、关系、原文溯源、审计 |
| Phase 4 多端产品化 | 未开始 | Android、Windows、Web、本地 Vault、系统分享与同步 |
| Phase 5 产品安全与运营 | 未开始 | 配额、密钥轮换、导出删除、灾难恢复、容量和成本治理 |

## 5. Phase 1.5：可靠性与真实闭环

### 工作项

- `/v1/models` 调用真实中转站；
- `/v1/chat/completions` 完成最小真实聊天；
- 隔离 service vault 执行同步 memory checkpoint；
- 分别确认 MemPalace 与 Letta 写入结果；
- 轮询语义召回并区分最终一致延迟与关键失败；
- RustFS 临时对象上传、读回、校验、删除；
- 状态快照记录生成时间、过期阈值、磁盘和 smoke 结果；
- 磁盘 80% 安全清理，90% 或低于 3 GiB 阻止大型发布；
- 永不执行 `docker volume prune`，永不自动删除用户数据卷；
- Docker 构建缓存、依赖下载和发布锁具备慢链路容错。

### 完成标准

1. 生产 SHA 与 main 同步；
2. 中转站模型和聊天成功；
3. MemPalace、Letta 同步写入成功；
4. RustFS 测试成功；
5. smoke 不接触真实账户 Vault；
6. 日志、状态和 CI 不包含密钥或用户原文；
7. 冷构建、并发部署和下载抖动不会破坏现有线上版本。

## 6. Phase 1.6：可信身份与 Vault 隔离

### 已完成基础

- `principal_type + account_id + vault_id + device_id` 统一作用域；
- JWT/OIDC 签名、issuer、audience、subject、时间和 vault claim 验证；
- LobeHub 服务端注入的 OpenAI `user` 派生账户；
- service identity 与真实账户命名空间隔离；
- MemPalace、Letta、Supermemory 使用同一 storage key；
- 外部 subject 通过不可逆哈希派生账户键。

### 当前工作

- SQLite Vault 注册表；
- LobeHub 默认 Vault 自动注册，具名 Vault 由可信管理流程创建；
- JWT claim 授权 Vault 自动注册；
- 管理接口和跨账户负向测试；
- 后续将附件路径、PostgreSQL RLS 和对象权限接入同一边界。

### 完成标准

即使账户 A 修改请求参数、猜测 Vault 名称或附件路径，也不能读取、搜索、写入、删除、导出或恢复账户 B 的任何数据。

## 7. Phase 1.7：存储策略与隐私路由

### 当前工作

- 每个 Vault 持久保存 `local-only / cloud / hybrid`；
- cloud 保持现有自动召回和写入；
- local-only 禁用服务端长期记忆读写；
- hybrid 允许云端脱敏记忆召回，但原始聊天不自动持久化；
- 混合模式显式写入必须标记为客户端已脱敏；
- 健康接口和响应头报告实际策略。

### 后续工作

- Android/Windows 加密本地 Vault；
- 同步游标、冲突解决、离线队列和设备撤销；
- 资料级覆盖策略；
- 敏感字段策略、脱敏规则和本地密钥管理；
- 云端向量只从脱敏文本生成；
- 删除和导出的本地/云端一致性。

## 8. Phase 2：多模态摄取

新增独立 attachment-worker，不阻塞聊天：

```text
附件进入本地或 RustFS
        ↓
账户/Vault/存储策略校验
        ↓
Redis 队列 + 幂等任务
        ↓
非 AI 原生解析 / 远程 AI Provider
        ↓
原文引用 + 结构化记忆
```

优先顺序：

1. 图片：远程视觉/OCR、描述和引用；
2. PDF：原生文本、页面渲染、扫描件远程 OCR、页码引用；
3. 音频：远程转写、时间戳、说话人信息；
4. 视频：音轨、关键帧、时间轴和长视频分段；
5. Word、PPT、Excel；
6. 历史附件补录、暂停、恢复、限速和重试。

所有 AI 任务都必须经过统一 RemoteAIProvider，禁止本地模型。

## 9. Phase 3：记忆管理

- 全局搜索原文和结构化记忆；
- 按人物、项目、时间、来源、文件类型和 Vault 筛选；
- 查看原文与结构化事实关联；
- 修改、确认、合并、软删除和彻底删除；
- 标记“不要记住”“仅本地”“混合脱敏”“临时资料”；
- 记忆来源、置信度、冲突和审计记录；
- 时间线、人物页、项目页和关系图；
- 导出及账户删除。

## 10. Phase 4：客户端

### Android

- PWA/TWA 或原生壳；
- 系统分享到 SuMeMe；
- 相册、相机、录音和文件选择；
- 本地加密 Vault；
- 后台上传、弱网续传和处理通知。

### Windows

- 桌面封装或 PWA；
- 文件右键发送、剪贴板和浏览器剪藏；
- 本地加密 Vault 和后台同步；
- 不默认采集屏幕或文件夹。

### Web

- cloud 模式完整支持；
- 上传队列、处理状态、记忆引用和管理 UI；
- 浏览器本地模式只作为受能力限制的实现，不承诺替代原生本地 Vault。

## 11. 发布与运维

```text
开发分支
→ 测试与静态检查
→ Pull Request
→ GitHub-hosted CI
→ 合并 main
→ ADOB GitHub-hosted Runner 通过固定 Host Key SSH 部署
→ VPS 项目脚本执行磁盘保护、Compose、健康和 smoke
→ 更新 ops-status
→ 验证生产 SHA
```

迁移期间保留 self-hosted Runner 用于状态、诊断和回滚；在这些工作流全部迁移到 ADOB SSH 后再停用。

发布规则：

- ADOB 调用固定提交 SHA，不使用浮动 `@main`；
- GitHub concurrency 与 VPS `flock` 双层串行；
- `.env`、密钥和数据卷不上传 GitHub；
- 应用代码可回滚，数据库迁移必须有向前修复或明确反向迁移；
- 未通过生产 smoke 的版本不能标记为稳定。

## 12. 当前执行顺序

1. 完成慢链路 Docker 构建并让生产 SHA 追上 main；
2. 完成 Vault 注册表和三种存储策略；
3. 把生产身份从 legacy 切到 `trusted-openai-user`，执行跨账户负向测试；
4. 将 RustFS 改为私有对象访问，并接入账户/Vault 路径；
5. 设计本地 Vault 与混合同步协议；
6. 开始 attachment-worker，先图片和 PDF；
7. 完成音频、视频和历史补录；
8. 进入记忆管理 UI 和多端客户端。
