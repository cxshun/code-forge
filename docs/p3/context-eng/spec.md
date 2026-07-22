# P3 - 上下文工程增强：需求规格

> 子主题：[context-eng](./)。P3 总览见 [../README.md](../README.md)。
> 一期 MVP 上下文管理设计见 [../../mvp/design.md §D34](../../mvp/design.md)（L0-L4 四道防线）。

---

## 1. 背景与目标

### 1.1 问题

MVP 阶段已落地 L0-L4 四道防线（`backend/app/agent/context.py`），在**单 session 内**的上下文压缩工作正常。但随着实际使用深入，暴露出三个关键缺口：

1. **跨 session 上下文断裂**：`load_chat_history` 只加载最近 1 个 completed session 的 JSONL，再往前全丢。用户隔天回来、或连续多轮对话后，早期上下文完全消失。
2. **L2 单次摘要在长对话中静默失败**：前缀超过摘要模型窗口时，`_compact` 捕获异常后直接 skip，导致 L4 频繁触发、Run 报错。
3. **OpenAI 兼容 provider token 计数不准**：`len(content)//4` 估算误差可达 ±30%，L1/L2 触发时机偏离设计阈值。
4. **`context_window` 硬编码**：Anthropic 固定 200K、OpenAI 固定 128K，切换到不同 model（如 claude-opus-4 200K vs glm-4-air 128K vs deepseek-v3 64K）时阈值不自动调整。

### 1.2 目标

在不改动 L0-L4 整体框架的前提下，针对上述四个缺口做增强：

- **跨 session 滑动窗口**：新 Run 启动时加载「最近 N 个 session 的摘要 + 最近 1 个 session 的原文」，N 按 token 预算动态决定
- **L2 递归摘要**：前缀太大时分段摘要再合并，最多递归 3 层，消除静默失败
- **精确 token 计数**：OpenAI 兼容 provider 接入 `tiktoken`，Anthropic 保留 `count_tokens` API
- **per-model context_window**：引入 `ModelRegistry`，按 model_name 查询真实窗口大小

### 1.3 非目标

- **不做嵌入检索 / 向量记忆**：长期记忆仍走 file-based `memory/MEMORY.md`，P4 再考虑嵌入
- **不重写 L0-L4 框架**：保留现有 `ContextManager.manage()` 入口与 L1-L4 编排逻辑
- **不改 1 Session : 1 Run 模型**：D23 的 session/run 结构不变，只改 session 间上下文加载方式
- **不做 max_tokens 可配**：输出长度仍固定 4096，P3 二期再考虑
- **不做跨 session tool 调用保留**：跨 session 仍只传文本摘要，不保留 tool_use/tool_result 原文（配对复杂度高，P4 评估）

---

## 2. 功能性需求

> 编号接续 [direct-chat F2.13](../direct-chat/spec.md)。本子主题范围 F3.1–F3.8。

### 3.1 跨 session 滑动窗口

- **F3.1** Run 完成后（status=completed），异步生成该 session 的摘要并落 DB（`session_summaries` 表），不阻塞用户回复
- **F3.2** 新 Run 启动时，`load_chat_history` 改为加载「最近 N 个 session 摘要 + 最近 1 个 session 原文消息」：
  - 摘要按 session_id 倒序拼接，总 token 不超过 `summary_budget_pct`（默认 25%）的窗口预算
  - 原文消息仍走 JSONL 读取，过滤 tool_result（与现有行为一致）
- **F3.3** 摘要生成失败（LLM 调用异常 / 超时）时降级为「不生成摘要」，不影响 Run 正常完成
- **F3.4** 摘要内容遵循 L2 同款指令（保留代码片段 / 文件路径 / 决策 / TODO / 用户偏好），可被 `ContextConfig.compact_instructions` 覆盖

### 3.2 L2 递归摘要

- **F3.5** L2 compaction 触发时，若前缀 token 超过摘要模型窗口的 60%，分段摘要：
  - 分段边界对齐到完整回合（不切断 tool_use/tool_result 配对）
  - 每段独立调 summary_provider 生成段摘要
  - 段摘要合并为总摘要；若合并后仍超窗口，再递归一层
  - 最多递归 3 层，超过则取前 3 层结果 + 截断提示
- **F3.6** 递归摘要过程中任一段失败时，该段降级为截断（保留首尾 + 中间省略），不整体 skip

### 3.3 精确 token 计数

- **F3.7** OpenAI 兼容 provider 的 `count_tokens` 改用 `tiktoken`（按 model 选 encoding，fallback `cl100k_base`）；未安装 tiktoken 时 fallback 到 `len//4` 估算
- **F3.8** Anthropic provider 的 `count_tokens` 保持现有 `messages.count_tokens` API 不变

### 3.4 per-model context_window

- **F3.9** 新增 `ModelRegistry`：内置常见 model 的 `{context_window, max_output_tokens}` 元数据
- **F3.10** provider 构造时根据 model_name 从 registry 查询；未知 model 走 provider 的 fallback 值
- **F3.11** 支持通过环境变量 `MODEL_OVERRIDES`（JSON）覆盖内置 registry，便于新 model 上线时无需发版

### 3.5 ContextConfig 管理后台 UI

- **F3.12** WorkspaceDetailView 新增「上下文管理」tab，表单化编辑 `ContextConfig`（替代当前 raw JSON textarea）
- **F3.13** 表单字段对应 `ContextConfig` 全部 11 个字段（含 P3 新增 `summary_budget_pct` / `compact_recursive`），控件类型：
  - `enabled` / `compact_recursive`：switch
  - `trigger1` / `trigger2` / `summary_budget_pct`：slider，显示 `% of context_window`
  - `clear_keep` / `compact_recent`：number input（1-20）
  - `summary_provider`：select（anthropic / openai_compatible）
  - `summary_model`：text input，placeholder 显示 provider 默认 model
  - `compact_instructions`：textarea + 「重置默认」按钮
  - `exclude_tools`：tag input（工具名）
- **F3.14** 保存调 `PATCH /workspaces/{id}` 传 `context_config` 对象；「重置默认」按钮一键恢复所有字段到 `ContextConfig()` 默认值

### 3.6 模型切换管理后台 UI

- **F3.15** Workspace 新增 `model_config` JSONB 字段；WorkspaceDetailView 新增「模型配置」tab，表单化编辑：
  - `provider`：radio（anthropic / openai_compatible）
  - `model`：text input + datalist（从 `ModelRegistry` 提供建议 model 名）
  - `api_base_url`：text input（provider=openai_compatible 时启用，留空走 settings 全局）
  - `api_key`：password input（留空走 settings 全局 key；填了则加密存储为 `api_key_enc`）
- **F3.16** `make_provider()` 改造：优先从 `Workspace.model_config` 构造 provider；WS 未配置时 fallback 到 `settings` 全局（保持现有行为）

---

## 3. 非功能性需求

- **NF3.1** 摘要生成是异步任务，不阻塞 Run 完成；失败仅 log warning，不影响主流程
- **NF3.2** `tiktoken` 作为 optional dependency，缺失时 graceful fallback，不强制安装
- **NF3.3** `ModelRegistry` 查询是纯内存操作（dict），不引入 DB / 网络调用
- **NF3.4** 递归摘要有明确的层数上限（3 层）和单段 token 上限，防止无限循环 / 成本失控
- **NF3.5** 所有上下文管理操作（L1/L2/递归摘要/session 摘要生成）均产 observability span，记录前后 token / 压缩比 / 层数 / 段数
- **NF3.6** ContextConfig 表单保存前做字段校验（trigger1 < trigger2 < 0.95、clear_keep ≥ 1 等）；校验失败前端标红提示，不发请求
- **NF3.7** `model_config.api_key` 加密存储（复用 `encrypt_secret`）；API 返回时不回显明文，只返回 `has_api_key: bool`

---

## 4. 约束与假设

- **摘要模型与主模型可不同**：`ContextConfig.summary_provider` 已支持指定摘要用模型（如 GLM 降本），本子主题沿用
- **session_summaries 表与 Session 1:1**：一个 session 只有一条摘要记录；Run 未完成时无摘要
- **摘要一旦生成不可变**：不因后续 session 的上下文变化回溯修改历史摘要（简化实现，避免连锁更新）
- **tiktoken 只覆盖 OpenAI 系**：Anthropic 系仍走官方 `count_tokens` API；其他 provider（如 GLM 自研）无公开 tokenizer，继续用估算
- **model_config 留空 = 用全局**：WS `model_config` 为 `None` / 空 / 缺字段时，对应项 fallback 到 `settings` 全局配置（保持现有行为）
- **api_key 加密存储**：`model_config.api_key` 通过 `encrypt_secret` 加密后存 `api_key_enc`；API 返回时只返回 `has_api_key: bool`，不回显明文
- **provider 类型固定两类**：MVP 只支持 `anthropic` / `openai_compatible` 两类 provider；其他 provider（如 Gemini 原生）P4 再考虑

---

## 5. 与 MVP / P2 的关系

| 来源 | 关系 | 说明 |
|---|---|---|
| MVP D34「上下文管理 L0-L4」 | **增强** | L2 改为递归摘要；跨 session 加载改为滑动窗口；L1/L3/L4 逻辑不变 |
| MVP D23「1 Session : 1 Run」 | **不变** | session/run 结构不变，新增 `session_summaries` 表为 1:1 附属 |
| MVP `load_chat_history` | **重写** | 从「最近 1 session 原文」改为「最近 N session 摘要 + 最近 1 session 原文」 |
| MVP `chat_history_max_messages` | **保留** | 仍控制原文消息条数上限；摘要预算由新配置 `summary_budget_pct` 控制 |
| P2 direct-chat | **无影响** | 单聊 / 群聊的上下文加载逻辑统一走新路径 |

> 本子主题不修改 MVP/P2 既有文档；MVP D34 的"L2 单次摘要"约束在本子主题 design §D-CE.2 中明确"按 P3 覆盖为递归摘要"。
