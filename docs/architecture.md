# SuMeMe 系统架构

## 1. 设计原则

SuMeMe 将“对话入口”“模型能力”“原文记忆”“结构化记忆”拆开：

1. LobeHub 负责多端 UI、账号、会话和附件；
2. memory-gateway 负责统一身份、记忆召回、上下文注入与模型转发；
3. AI 中转站负责文字、图片、视频和文档理解；
4. MemPalace 保存逐字原始内容；
5. Letta 维护会变化的用户画像、人物、项目、偏好与事件关系。

上游组件不直接互相耦合，全部通过稳定接口连接。

## 2. 一次对话的数据流

```text
用户在 LobeHub 发送消息/附件
  ↓
LobeHub 调用 memory-gateway /v1/chat/completions
  ↓
网关识别当前用户和最后一条 user 消息
  ↓
并行召回：
  ├─ MemPalace：语义检索原始历史片段
  └─ Letta：返回相关事实与关系
  ↓
网关生成一条不可见 system memory context
  ↓
原请求 + memory context 转发到中转站
  ↓
中转站返回流式或非流式回答
  ↓
后台写入：
  ├─ MemPalace：本轮 user/assistant 原文和附件元数据
  └─ Letta：让 Agent 更新长期结构化记忆
```

## 3. 身份隔离

第一阶段是个人单用户系统，默认使用 `SUMEME_USER_ID=default`。网关也支持以下优先级：

1. `X-SuMeMe-User-Id` 请求头；
2. OpenAI 请求体 `user` 字段；
3. `.env` 中的 `SUMEME_USER_ID`。

MemPalace 使用 `user_<id>` 作为 wing。后续多用户版需要把 LobeHub 的真实用户 ID 通过自定义 provider header 传给网关，并为每个用户维护独立 Letta Agent。

## 4. 原始附件

LobeHub 将原始文件保存在 RustFS。当前网关会保存 OpenAI 消息体中出现的：

- 文本；
- 图片 URL 或 data URL 标识；
- 音频输入标识；
- 文件名、file_id、MIME 类型等元数据；
- 模型实际收到的文档上下文。

第二阶段增加 `attachment-worker`：

1. 监听 LobeHub 新附件记录；
2. 从 RustFS 获取原始文件；
3. 图片调用中转站视觉模型；
4. 视频执行音轨转写、关键帧抽取和时间轴总结；
5. Office/PDF 执行文本与页面视觉解析；
6. 把原始文件永久 URL、详细描述和时间轴写入 MemPalace；
7. 把人物、事件和关系写入 Letta。

## 5. “不限上下文”的实现

系统并不把全部历史一次性塞入模型。每轮只取：

- MemPalace 前 N 条高相关原文；
- Letta 返回的高相关结构化事实；
- 当前会话原有上下文。

`MEMORY_CONTEXT_MAX_CHARS` 控制注入长度，避免召回结果挤占主模型上下文。

## 6. 失败降级

- MemPalace 故障：仅使用 Letta；
- Letta 故障：仅使用 MemPalace；
- 两者均故障：直接调用中转站；
- 中转站故障：按 OpenAI 格式返回上游错误；
- 后台记忆写入失败：不影响用户已收到的回答。

## 7. 路线图

### 阶段 1：基础闭环

- OpenAI compatible proxy；
- 双记忆召回；
- 原文存储；
- Letta 结构化记忆；
- VPS/宝塔部署。

### 阶段 2：完整多模态摄取

- 附件 worker；
- 图片、视频、音频、PDF、Office 统一解析；
- 后台任务队列；
- 处理状态和失败重试；
- 历史附件补录。

### 阶段 3：记忆管理 UI

- 查看、搜索、编辑、删除记忆；
- 时间线、人物、项目和关系图；
- 原文与结构化事实双向溯源；
- 敏感内容排除和保留期限。

### 阶段 4：原生客户端

- Android TWA/PWA 封装；
- Windows 桌面封装；
- 分享到 SuMeMe；
- 相册、文件、网页一键投喂。
