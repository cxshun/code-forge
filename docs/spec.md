# Code Forge - 需求规格说明

> 本文档描述 Code Forge 的功能性与非功能性需求。设计思路、技术选型、关键决策、流程图见 [design.md](./design.md)。

---

## 1. 项目概述

### 1.1 产品定位

Code Forge 是一个云端多租户的 Coding Agent SaaS：

- 以 **飞书 WebSocket** 作为统一交互入口
- 以 **工作空间（Workspace）** 作为一等公民组织 `MCP + Skill + 项目代码`
- 长期目标：对外提供服务

### 1.2 核心创新

| 维度 | 创新点 |
|---|---|
| 工作空间 | 把 MCP（工具协议）+ Skill（能力）+ 多 Repo（代码上下文）打包成可切换、可组合的物理单元 |
| 飞书入口 | 脱离 IDE，1 WS 可绑多个群（开发/测试/...），在飞书移动端/桌面端都能盯 Agent 跑 |
| 广场生态 | Skill / MCP 全局共享，用户上传立即可用（无审核），跨 WS 引用挂载 |
| 按需 invoke | Skill 只把 description 注入 system prompt，触发时才加载完整内容，省 token |
| Chat 级 Memory | 飞书 chat 维度的长期记忆，跨会话持久、跨 chat 隔离 |

### 1.3 MVP 目标

验证 "飞书 → 工作空间 → Agent" 的核心闭环；账号由管理员开通。

---

## 2. 用户角色与典型场景

### 2.1 角色

| 角色 | 职责 | 主要入口 |
|---|---|---|
| 管理员 | 创建/配置 WS、上传 Skill/MCP、绑定飞书 chat、管理 Memory | 管理后台（Web） |
| 使用者 | 在飞书 chat 中 @ 机器人触发 Agent、查看进度、接收结果 | 飞书客户端 |
| Skill/MCP 提供者 | 上传 Skill/MCP 到广场供他人引用 | 管理后台 |

> MVP 阶段角色边界较模糊，同一用户可同时是管理员和使用者。

### 2.2 典型场景

| 场景 | 描述 |
|---|---|
| 配置 WS | 管理员创建 WS，挂载多个 Git repo、Skill、MCP，绑定飞书群 |
| 飞书对话 | 使用者在群里 @ 机器人提需求，Agent 流式反馈进度，最终交付修改 |
| Plan 确认 | Agent 对复杂任务生成 Plan，管理员通过飞书卡片按钮确认/拒绝 |
| Skill 上传 | 开发者将内部最佳实践封装为 Skill，上传到广场供其他 WS 引用 |
| Memory 积累 | Agent 记录用户偏好、项目背景到 chat memory，后续会话自动应用 |
| Memory 管理 | 管理员在后台查看/编辑/删除某个 chat 的 memory |
| 项目指令维护 | 管理员在 WS 级 AGENT.md 写入通用规则；repo 维护者通过源仓库根目录的 AGENT.md 维护 repo 规范，Agent 启动时自动加载 |

---

## 3. 功能性需求

### 3.1 飞书接入

- **F3.1.1** 通过飞书 WebSocket 长连接接收消息（无需对外暴露 HTTP）
- **F3.1.2** 支持群聊场景（MVP 暂不支持私聊）
- **F3.1.3** 群聊场景下识别 @ 机器人触发，回复明确 @ 触发者
- **F3.1.4** 支持流式进度推送，富卡片类型：进度卡片、Plan 确认卡片、diff 预览卡片、TaskList 卡片、**排队状态卡片**
- **F3.1.5** **收到消息即时反馈**：接入层收到用户消息后立即回复"思考中"表情 / 卡片，给用户感知确认（避免 Agent 启动延迟期间用户以为消息丢失）
- **F3.1.6** **多 App 支持**：后端支持注册多个飞书自建应用（`app_id` + `app_secret`），每个 App 维护独立 WebSocket 长连接；同一群可通过添加多个机器人实现"一群绑多 WS"
- **F3.1.7** **消息去重**：接入层以飞书 `message_id` 为幂等键（Redis 短期缓存），断线重连补推的重复消息在进 Run 队列前丢弃，避免重复触发 Run（详见 design D38）
- **F3.1.8** **输入边界（MVP）**：仅支持**纯文本**消息触发 Agent；图片 / 文件 / 语音 / 引用回复等富消息暂不处理（静默忽略或回复"暂不支持该消息类型"）
- **F3.1.9** **流式推送节流**：`text_delta` 按阈值（~500ms 窗口或 ~200 token）合并更新进度卡片，避免触发飞书卡片更新 QPS 限制

### 3.2 工作空间管理

- **F3.2.1** 工作空间（WS）创建、查询、修改、删除
- **F3.2.2** 1 WS 可挂载 N 个 Git Repo（HTTPS clone，可选 token 用于私有仓库）
- **F3.2.3** 1 WS 可绑定 N 个 FeishuChat（FeishuChat 独占：1 FeishuChat 只能绑 1 WS）
- **F3.2.4** FeishuChat 唯一键 = `(app_id, chat_id)`；绑定时管理员选择已注册的飞书 App + 粘贴 chat_id，后端校验合法性 + 机器人是否在群
- **F3.2.5** 删除 WS 前需解绑所有 FeishuChat、解除所有广场引用

### 3.3 Agent 内核

- **F3.3.1** Agentic Loop：调用 LLM → 解析 tool_use → 执行工具 → 反馈结果 → 直到最终回复
- **F3.3.2** 支持流式输出（Token 级推送，封装为进度卡片）
- **F3.3.3** **WS 写锁串行**：同 WS 内的 Run 写操作（`Write` / `Edit` / `Bash`）通过分布式锁串行；读操作并行不受影响（详见 design D20）
- **F3.3.4** **排队反馈**：Run 入队时推送"⏳ 排队中，前面 N 个"，抢到锁时推送"▶️ 开始执行"
- **F3.3.5** **取消 / 中断**：排队中可"取消排队"立即从队列移除；运行中可中断，信号传到 Agent Loop 异步中止
- **F3.3.6** **超时保护**：单 Run 硬超时 10 分钟，超时后强制中止并释放锁
- **F3.3.7** 1 个 Session = 1 个 Run（详见 design D23）
- **F3.3.8** **并行子代理**：主 Agent 可在单 Run 内并行启动多个子代理（独立上下文窗口，仅回最终消息），用于可独立拆分的子任务；只读子代理天然并行，写型子代理复用父 Run 锁（详见 design D33）
- **F3.3.9** **拆分判断责任**：主 Agent 负责判断子任务是否可安全并行（无写冲突 / 无强依赖），system prompt 提供拆分指导；存在冲突时串行（详见 design D33）
- **F3.3.10** **上下文管理（自研分层）**：Agentic Loop 多轮 tool_result 累积，需显式管理。采用**四道防线**逐级处理（按成本从低到高）：L0 工具结果源头节流（Bash/Read 输出截断）→ L1 tool-result clearing（旧结果替换为占位、保留 tool_use 记录、可重取、零推理）→ L2 compaction（旧历史压成结构化摘要）→ L3 memory 联动（compaction 前强信号沉淀 chat memory）→ L4 硬兜底（仍超 limit 95% 则中断告知）。**自研、Provider 无关**（不依赖 Anthropic 一方 context editing beta，规避 Claude 国内封禁），机制本身只要 Provider 给出 token 计数与 context window 即可工作；摘要模型可指定国内模型（如 GLM）。支持 WS 级配置（F3.7.8，详见 design D34）
- **F3.3.11** **循环兜底**：除单 Run 10 min 硬超时外，设最大 tool_use 轮数上限（默认 50，可配置），防 Agent 空转烧 token；触顶中断并告知用户
- **F3.3.12** **错误处理与重试**：工具失败（Bash 退出码非 0 / MCP 不可用 / 路径越界）作为 `tool_result`（is_error）回灌 Agent 自主决策（不一刀切中断）；LLM 调用失败（429/5xx/超时）由 Provider 层指数退避重试（默认 3 次），仍失败则中断 Run（详见 design §6.5）
- **F3.3.13** **中断执行语义**：排队中取消=立即移除无副作用；运行中中断=当前工具完成/被 kill 后停止 Loop，Bash 走 SIGTERM→SIGKILL、子代理级联中断；已落盘改动**保留不回滚**（详见 design §6.6）

### 3.4 工具系统

- **F3.4.1** 内置工具：`Read` / `Write` / `Edit` / `Glob` / `Grep` / `Bash` / `TaskList` / `Plan Mode` / `WebFetch` / `WebSearch` / `Agent`（子代理）
- **F3.4.2** MCP 工具：通过 MCP 客户端连接外部服务（stdio / http）
- **F3.4.3** Skill 工具：每个挂载的 Skill 包装为 `skill__{name}` 工具，按需 invoke（详见 design D16）
  - **F3.4.3.1** 启动时仅把 frontmatter 的 `name + description` 注入 system prompt（元信息层）
  - **F3.4.3.2** Agent 调用 `skill__{name}` 时，后端读取完整 `SKILL.md` 作为 `tool_result` 返回（内容层）
  - **F3.4.3.3** `scripts/` 通过 Bash 执行（不进入上下文），`resources/` 通过 Read 按需读取（依赖层）
- **F3.4.4** **路径安全**：所有文件类工具调用必须限定在当前 WS 的 `repos/` 与 `chats/{feishu_chat_id}/memory/` 子树内；Bash 同样需路径校验，禁止越界
- **F3.4.5** **写锁规则**：`Write` / `Edit` / `Bash` 抢 WS 写锁；`Read` / `Glob` / `Grep` 等只读工具不抢锁（详见 design D20）
- **F3.4.6** **普通工具一轮多并发**：单条 LLM 响应内含多个 tool_use 时，只读工具（`Read`/`Glob`/`Grep`/`WebFetch`/`WebSearch`/`skill__{name}`）`asyncio.gather` 并发执行，写工具串行（与 D33 的子代理并行正交，详见 design §6.5）
- **F3.4.7** **MCP 工具规则**：MCP 工具默认抢 WS 锁（无法静态判断副作用）、不受 D17 路径校验约束（风险自担）；MCP 配置可标 `read_only=true` 豁免抢锁；单次调用默认 60s 超时（详见 design D37）
- **F3.4.8** **Bash git 边界与代码交付**：Bash 允许只读 git 子命令（`status`/`diff`/`log`/`show`/`branch`/`blame`），禁用写 git 与网络 git（`commit`/`push`/`pull`/`fetch`/`merge`/`reset` 等，黑名单拦截）；代码交付 = 改动落 `repos/` 本地工作副本 + diff 预览卡片，**MVP 不自动 commit/push**（详见 design D35）

### 3.5 Skill / MCP 广场

- **F3.5.1** Skill / MCP 是顶层实体，存于全局广场，可被任意 WS 引用
- **F3.5.2** 用户可上传 Skill（无需审核，立即可用）
- **F3.5.3** 用户可注册 MCP（配置 stdio 命令或 http endpoint）
- **F3.5.4** 默认 owner 私有，可设置"全员可见"开关
- **F3.5.5** 被引用的资源禁止删除，必须先解绑
- **F3.5.6** 单 WS 最多挂载 50 个 Skill（防止 system prompt 膨胀）
- **F3.5.7** **SKILL.md 结构规范**（详见 design D15）：
  - frontmatter：`name`（必需，全局唯一）、`description`（必需，注入 system prompt）
  - 正文：`## 何时使用` / `## 工作流程` / `## 脚本说明（如有）` / `## 注意事项`
  - 必须明确告知 Agent 脚本调用路径与资源读取路径，不写脚本源码
- **F3.5.8** **Skill 版本（MVP 无版本管理）**：作者更新 SKILL.md 后对已挂载 WS **即时生效**（下次 Run 注入新 description / 内容）；MVP 不提供版本快照、回滚与"钉版本"能力——挂载方需知悉被引用 Skill 可能被作者随时修改

### 3.6 Memory 系统

- **F3.6.1** Memory 以 FeishuChat 为作用域：跨 session 持久、跨 FeishuChat 隔离
- **F3.6.2** 每个 FeishuChat 维护独立的 memory 目录（`MEMORY.md` 索引 + 分类 `.md` 文件）
- **F3.6.3** Memory 类型分类：`user` / `feedback` / `project` / `reference`（参考 Claude Code）
- **F3.6.4** Agent 通过内置 Write / Edit 工具直接落盘 memory 文件（不提供专门 memory 工具）
- **F3.6.5** Agent Loop 启动时自动加载对应 FeishuChat 的 `MEMORY.md` 索引到上下文
- **F3.6.6** **写入策略 = Agent 自主判断 + 强信号触发**（详见 design D22）：
  - 强信号：显式指令（"记住 X"）/ 纠正型 feedback / 重复偏好 / 强烈情绪 / 主动告知
  - 不写：代码状态、弱信号、敏感信息、临时上下文
  - 防过度：同主题合并、更新优先、写入后告知用户
- **F3.6.7** Memory 陈旧性：Agent 推荐前需校验 memory 引用的文件 / 函数 / 配置是否仍存在
- **F3.6.8** **Memory 并发写入安全**：Run 内并行子代理不直接写 memory，memory 写入由主 Agent 收口（避免子代理间写冲突，详见 design D22）
- **F3.6.9** **群聊归属**：同一 FeishuChat 内多用户共享 memory；写入 `user`/`feedback` 类时标注来源飞书 sender；多人偏好冲突时后写覆盖，用户可在后台修正（详见 design D22）

### 3.7 管理后台

- **F3.7.1** WS CRUD（创建、查询、修改、删除）
- **F3.7.2** WS 详情：repo 管理、FeishuChat 绑定、Skill / MCP 挂载
- **F3.7.3** Skill / MCP 广场：上传、可见性设置、删除
- **F3.7.4** 飞书 App 注册：录入 `app_id` + `app_secret`，维护多 App 列表
- **F3.7.5** 会话历史查看（按 FeishuChat / session 维度）
- **F3.7.6** **Memory 管理**：按 FeishuChat 维度列出 memory 文件，支持查看 / 编辑 / 删除
- **F3.7.7** 用户账号管理：管理员创建 / 停用账号、重置密码、角色分配（自建账号密码体系，详见 design D32）
- **F3.7.8** **WS 级上下文管理配置**：按 WS 配置自动压缩策略（启用开关、clearing/compaction 触发阈值、`clear_keep`/`compact_recent`、摘要模型 provider/model、摘要 instructions、`exclude_tools`）；默认值合理、WS 可覆盖（详见 design D34）

### 3.8 鉴权

- **F3.8.1** 自建账号密码登录管理后台（username + password，详见 design D32）
- **F3.8.2** **管理后台权限校验**：WS 配置 / Skill 上传 / Memory 管理等操作需 owner 校验（与飞书群内使用权解耦）
- **F3.8.3** 广场资源权限校验（owner 才能编辑 / 删除）

> 飞书群内使用权采用无权限模型（拉群即用，详见 design D21），不在本节范围内。

### 3.9 项目指令（AGENT.md）

- **F3.9.1** 支持 **WS 级 AGENT.md**（`/workspaces/{ws_id}/AGENT.md`）：描述工作空间通用规则，1 WS 至多 1 份
- **F3.9.2** 支持 **Repo 级 AGENT.md**（`repos/{repo_id}/AGENT.md`）：随 git clone 进入，每个 repo 根目录 1 份
- **F3.9.3** **自动加载**：Run 启动时后端直接读取并注入 system prompt（不走 Read 工具）
- **F3.9.4** **多 Repo 加载规则**：仅加载 WS 级 + 当前 cwd 所在 repo 的 Repo 级（不拼接所有 repo）
- **F3.9.5** **cwd 默认值**：第一个挂载 repo 的根目录；管理后台可为每个 FeishuChat 配置默认 cwd
- **F3.9.6** **Agent 可写入**：允许 Agent 通过 Write / Edit 修改两份 AGENT.md（路径白名单精确到这两条文件）
- **F3.9.7** **管理后台支持**：WS 级 AGENT.md 支持在线查看 / 编辑；Repo 级 AGENT.md 后台只读（由源仓库维护）
- **F3.9.8** **长度建议**：单份 ≤ 2K token，超长时记录告警但正常加载（不截断）

> 详见 design D24。

### 3.10 可观测性（Observability）

- **F3.10.1** **Trace 采集**：Agent Loop 全流程埋点，包括 Run 起 / 止、每次 Claude API 调用（request / response / usage / stream chunk）、每次 tool_use 执行（input / output / duration / 是否抢锁 / 是否越界拒绝）、skill invoke、子代理调用、中断 / 超时 / 错误 / 路径拒绝
- **F3.10.2** **Span 树结构**：Trace 数据以 span 树组织，**1 Run = 1 trace（根 span）**，下挂 llm / tool / skill / subagent span，支持任意嵌套（子代理内可再嵌套）；span 类型含 run / llm / tool / skill / subagent / interrupt / error
- **F3.10.3** **分层存储**：Span 元数据（token / 延迟 / cost / 状态 / 错误类型 / 工具名）入 PostgreSQL；完整大 payload（prompt / response / tool_result）落本地文件系统，PG 记录存文件路径引用；**Trace payload 与 Agent 会话历史（session JSONL）分离存储**（独立 traces/ 目录），互不污染
- **F3.10.4** **流式响应采集**：支持 Claude API streaming 响应的 token usage 聚合（message_start 取 input / cache token，message_delta 累计 output，message_stop 取 final usage），边推飞书边累计 payload
- **F3.10.5** **后台调试视图**：单 Run 的 span 瀑布图，支持展开 prompt / response / tool I/O（大文件分片流式返回）
- **F3.10.6** **成本与性能聚合视图**：按 WS / FeishuChat / 时间段聚合 token 消耗、cost、延迟分布、工具耗时 TopN、单 Run 成本；cost 基于模型 pricing 表与 cache token 折算
- **F3.10.7** **监控告警视图**：异常 Run 列表（error / timeout / interrupted）；可配置告警规则（错误率 / 超时率 / P95 延迟 / 单 Run cost / WS 日 cost 阈值），**内置默认规则集**，触发飞书通知
- **F3.10.8** **非阻塞采集**：Trace 采集不得阻塞 Agent Loop 与飞书流式推送；采用内存缓冲 + 后台批写策略
- **F3.10.9** **失败降级**：Trace 写入失败时缓冲丢弃 / 转入 fallback 文件，Agent 主流程不感知、不失败

> 详见 design D25~D31 与 §7 可观测性详设。

---

## 4. 非功能性需求

### 4.1 多租户隔离

- **NF4.1.1** 工作空间之间物理隔离（独立目录、独立 DB 记录）
- **NF4.1.2** 工具调用路径强制限定在当前 WS 子树
- **NF4.1.3** FeishuChat 之间 memory 不可互访

### 4.2 安全

- **NF4.2.1** 不使用沙箱，路径校验作为软隔离
- **NF4.2.2** 外部 MCP 服务的风险由用户自挂自负责
- **NF4.2.3** Memory 不应记录敏感信息（密钥、凭证），Agent 写入时需判断
- **NF4.2.4** **敏感凭证静态加密**：git token / 飞书 `app_secret` / Anthropic key 等凭证落盘前经应用层加密（密钥环境变量注入），DB 与日志均不存明文（详见 design D32）
- **NF4.2.5** **传输安全**：生产环境强制 HTTPS；管理后台 Cookie 增加 `Secure` 属性（详见 design D32）
- **NF4.2.6** **CSRF 防护**：Cookie-based session 的写操作（POST/PATCH/DELETE）依赖 `SameSite=Lax` + 自定义请求头校验（详见 design D32）

### 4.3 性能

- **NF4.3.1** Agent 首字节响应 ≤ 3s（LLM API 调用）
- **NF4.3.2** 单 WS 写操作串行（锁约束）；队列可容纳 ≥ 5 个等待 Run
- **NF4.3.3** Skill invoke 加载延迟 ≤ 500ms（本地文件读取）
- **NF4.3.4** AGENT.md 加载延迟 ≤ 200ms（Run 启动时本地文件读取 + 注入）
- **NF4.3.5** 单 Run 并行子代理数默认上限 5（可配置），防 fork 爆炸与成本失控（详见 design D33）

### 4.4 可用性

- **NF4.4.1** 7x24 在线（云端部署）
- **NF4.4.2** 飞书移动端 / 桌面端均可访问
- **NF4.4.3** Run 中断后状态可追溯（不丢失历史）
- **NF4.4.4** **启动恢复**：后端重启 / 崩溃后，启动时清理孤儿 Run（标 interrupted）、强制释放残留 WS 锁、清理半途异步任务残留，避免幽灵 Run / 死锁（详见 design D36）

### 4.5 可扩展性

- **NF4.5.1** LLM 多模型可切换（抽象 Provider 层）
- **NF4.5.2** 模块解耦，工具层 / Agent 内核 / 接入层独立演进

### 4.6 可观测性

- **NF4.6.1** **多租户隔离**：Trace 数据访问边界 = WS 边界，所有查询强制带 `ws_id` 过滤（ORM 层注入）；payload 文件读取必须先校验 WS 归属
- **NF4.6.2** **敏感信息脱敏**：Trace payload 落盘前强制管线化脱敏（API key / token / 密码 / 私钥 / Bearer 等），对齐 NF4.2.3 的安全约束
- **NF4.6.3** **数据保留策略**：Payload 文件默认保留 30 天，PG spans 默认 90 天，可配置；WS 删除时级联清理
- **NF4.6.4** **大 payload 截断**：LLM request ≤ 5MB / response ≤ 10MB / tool 输出 ≤ 1MB，超限截断并标记 `payload_truncated`
- **NF4.6.5** **采集性能开销**：Trace 埋点对单次工具调用的额外延迟 < 1ms（内存入队）；后台批写不与 Agent 抢 event loop
- **NF4.6.6** **字段标准化**：Span 字段对齐 OpenTelemetry GenAI semantic conventions（`gen_ai.*`）和 anthropic usage 结构，预留 OTel 导出能力（未来扩展）

---

## 5. 约束与假设

### 5.1 MVP 范围

- 账号由管理员开通（不做完整计费、审计）
- 仅支持群聊（私聊暂不做）
- **群聊内无权限控制**（拉群即用，详见 design D21）
- 多模型：Claude 为主、GLM 等国内模型备选（Provider 抽象层，design D3）
- 不做沙箱（路径校验作为软隔离）

### 5.2 假设

- 用户自管代码执行风险（详见 design D5）
- 同一 FeishuChat 内多用户共享 memory（接受群聊场景下的偏好融合）
- 用户接受同 WS 写操作串行（同一项目下并发修改需排队，详见 design D20）

### 5.3 不在范围内（MVP）

- 计费、配额、审计日志
- 细粒度 RBAC（管理员 / 使用者二分即可）
- Skill 二阶段召回（embedding 检索）
- 私聊场景
- 跨 WS 数据共享
- AGENT.md 的多 repo 拼接 / 优先级裁剪（MVP 仅加载当前 cwd 那一份）
- 并行子代理的 worktree 隔离（L2，design D33）—— MVP 用 L1 子代理并行 + 主 Agent 拆分判断兜底
- 并行子代理的 Plan DAG 编排（L3，design D33）
- 可观测性的质量评估 / 模型对比 / OTel 导出（P2 预留，字段已对齐 OTel gen_ai.*）
- 图片 / 文件 / 语音 / 引用回复等富消息输入（MVP 仅纯文本触发，F3.1.8）
- 自动 git commit / push / 提 PR（MVP 交付仅本地工作副本 + diff 预览卡片，F3.4.8 / design D35）
- Skill 版本快照 / 回滚 / 钉版本（MVP 作者更新即时生效，F3.5.8）
- 上下文超限后的自动跨 session 续跑（MVP 硬兜底中断，design D34）
