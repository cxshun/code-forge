# P3 - 上下文工程增强：任务拆分

> 子主题：[context-eng](./)。规格见 [spec.md](./spec.md)，设计见 [design.md](./design.md)。
> 编号接续 [direct-chat DC-T9](../direct-chat/task.md)。本子主题范围 CE-T1 ~ CE-T8。

---

## 任务总览

| 编号 | 名称 | 模块 | 优先级 | 预估 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| CE-T1 | `SessionSummary` model + migration | M0 DB | P0 | 0.3d | — | ✅ 完成 |
| CE-T2 | `ContextConfig` 扩展 2 字段 | M0 配置 | P0 | 0.2d | — | ✅ 完成 |
| CE-T3 | `ModelRegistry` + provider 接入 | M1 provider | P0 | 0.5d | — | ✅ 完成 |
| CE-T4 | tiktoken 集成（OpenAI provider） | M1 provider | P0 | 0.3d | CE-T3 | ✅ 完成 |
| CE-T5 | session 摘要生成（异步任务） | M2 agent | P0 | 0.8d | CE-T1, CE-T2 | ✅ 完成 |
| CE-T6 | `load_chat_history` 滑动窗口重写 | M2 agent | P0 | 0.5d | CE-T1, CE-T5 | ✅ 完成 |
| CE-T7 | L2 递归摘要 | M2 agent | P0 | 0.8d | CE-T2, CE-T3 | ✅ 完成 |
| CE-T8 | 测试 + 联调 | M3 测试 | P0 | 0.8d | CE-T1~T7 | ✅ 完成 |
| CE-T9 | ContextConfig 管理后台 UI | M4 前端 | P0 | 0.8d | CE-T2 | ✅ 完成 |
| CE-T10 | 模型切换 per-WS + UI + `make_provider` 改造 | M4 前端 + M1 provider | P0 | 1.5d | CE-T3 | ✅ 完成 |
| CE-T11 | L2 预算感知 compaction（max_tokens + suffix 缩减 + 最终收敛） | M2 agent + M1 provider | P0 | 0.5d | CE-T7 | ✅ 完成 |

**总计**：7.0d ｜ 关键路径：CE-T1 → CE-T5 → CE-T6（滑动窗口链） + CE-T3 → CE-T7 → CE-T11（递归摘要 → 预算感知链） + CE-T3 → CE-T10（模型切换链）

---

## 任务详情

### CE-T1 SessionSummary model + Alembic migration

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M0 DB ｜ **优先级**：P0 ｜ **预估**：0.3d ｜ **依赖**：—
- **范围**：`backend/app/db/models/session_run.py` 新增 `SessionSummary` model；`backend/alembic/versions/xxx_add_session_summaries.py` 建表。
- **对应文档**：design §D-CE.1
- **验收标准**：
  - [x] `SessionSummary` 字段：`session_id` (PK + FK → sessions.id, ON DELETE CASCADE) / `summary_text` (TEXT) / `token_count` (int) / `summary_model` (varchar 64) / `created_at` (timestamptz default now())
  - [x] `SessionSummary.session_id` 与 `Session.id` 1:1，FK CASCADE（删 session 自动删摘要）
  - [x] Alembic migration 可 `upgrade head` / `downgrade -1` 无错
  - [x] `SessionSummary` 导入到 `app/db/models/__init__.py`
- **备注**：不新增 `updated_at`（摘要不可变，无需 TimestampMixin）。

### CE-T2 ContextConfig 扩展 2 字段

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M0 配置 ｜ **优先级**：P0 ｜ **预估**：0.2d ｜ **依赖**：—
- **范围**：`backend/app/agent/context_config.py` 新增 `summary_budget_pct: float = 0.25` / `compact_recursive: bool = True`；`from_ws` 容错保持。
- **对应文档**：design §3
- **验收标准**：
  - [x] `ContextConfig` 新增 2 字段，默认值符合 design
  - [x] `from_ws` 解析含新字段；旧 WS（无此字段）走默认值
  - [x] 未知 key 仍 ignore（`extra="ignore"`）
- **备注**：无需 DB migration（`context_config` 是 JSONB，schema-free）。`summary_target_pct` 由 CE-T11 追加。

### CE-T3 ModelRegistry + provider 接入

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M1 provider ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：—
- **范围**：`backend/app/providers/registry.py` 新建 `MODEL_REGISTRY` dict + `ModelMeta` dataclass；`Provider.__init__` 接受 `model_name`；`AnthropicProvider` / `OpenAICompatibleProvider` 的 `context_window` 改为从 registry 查；`MODEL_OVERRIDES` 环境变量支持。
- **对应文档**：design §D-CE.4
- **验收标准**：
  - [x] `MODEL_REGISTRY` 至少含 design 列出的 9 个 model
  - [x] `Provider.__init__` 接受 `model_name: str`，构造时 `MODEL_REGISTRY.get(model_name)` 查 meta
  - [x] 未知 model → 走 provider 的 `_FALLBACK_CTX`
  - [x] `MODEL_OVERRIDES` JSON 解析成功时合并到 registry；解析失败 log warning 并忽略
  - [x] `make_provider()` 传入当前 `settings.anthropic_model` / `settings.openai_model`
- **备注**：`max_output` 字段先落地到 `ModelMeta` 但本期不使用（P3 二期再接 max_tokens）。`Provider.chat()`/`stream()` 的 `max_tokens` 参数由 CE-T11 追加。

### CE-T4 tiktoken 集成

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M1 provider ｜ **优先级**：P0 ｜ **预估**：0.3d ｜ **依赖**：CE-T3
- **范围**：`backend/app/providers/openai_compatible_provider.py` `count_tokens` 改造；`tiktoken` 作为 optional dependency；encoding 按 model 选择 + 缓存。
- **对应文档**：design §D-CE.3
- **验收标准**：
  - [x] `count_tokens` 优先用 `tiktoken`；`import` 失败时 fallback 到 `len//4`
  - [x] encoding 选择：`gpt-4o*` / `o1*` → `o200k_base`；其余 → `cl100k_base`
  - [x] encoding 实例缓存（不每次调用都 `get_encoding`）
  - [x] `requirements.txt` 不强制加 `tiktoken`；README / AGENT.md 说明 optional 安装
- **备注**：Anthropic provider 的 `count_tokens` 不动（已有官方 API）。

### CE-T5 session 摘要生成（异步任务）

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M2 agent ｜ **优先级**：P0 ｜ **预估**：0.8d ｜ **依赖**：CE-T1, CE-T2
- **范围**：`backend/app/agent/session_summary.py` 新建 `generate_session_summary(session_id)`；`run.py` Run 完成后通过 `task_runner.submit` 异步触发；复用 `ContextConfig.summary_provider` / `compact_instructions`。
- **对应文档**：design §D-CE.1 / §4.1
- **验收标准**：
  - [x] `generate_session_summary` 读 JSONL 原文 → 调 summary_provider → INSERT `session_summaries`
  - [x] LLM 调用失败 / JSONL 不存在 → log warning + 不写 DB + 不抛
  - [x] Run 完成后通过 `task_runner.submit` 触发，不阻塞用户回复
  - [x] 摘要 token_count 用 summary_provider.count_tokens 计算
  - [x] 重复触发（同 session）→ UPSERT（idempotent）
- **备注**：summary_provider 的构造复用 `make_summary_provider(ctx_cfg)`（已有）。

### CE-T6 load_chat_history 滑动窗口重写

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M2 agent ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：CE-T1, CE-T5
- **范围**：`backend/app/agent/run.py` `load_chat_history` 重写：先查最近 N 个 `session_summaries`（token 预算内）拼前缀，再读最近 1 session JSONL 原文。
- **对应文档**：design §D-CE.1 / §4.2
- **验收标准**：
  - [x] 先查 `session_summaries` 按 session.id DESC，累加 `token_count` ≤ `budget = window * summary_budget_pct`
  - [x] 摘要拼成 1 条 user 消息 `[历史摘要]\n{summary_N}\n...\n{summary_1}`
  - [x] 最近 1 session 原文仍走 JSONL，过滤 tool_result，取最近 `chat_history_max_messages` 条
  - [x] 返回 `[摘要前缀] + [原文]`（当前 user message 由调用方追加）
  - [x] 无摘要 / 无历史 → 返回空 list（与 MVP 行为一致）
- **备注**：`chat_history_max_messages` 仍只管原文条数，不管摘要。

### CE-T7 L2 递归摘要

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M2 agent ｜ **优先级**：P0 ｜ **预估**：0.8d ｜ **依赖**：CE-T2, CE-T3
- **范围**：`backend/app/agent/context.py` `_compact` 改造：前缀 > 摘要窗口 60% 时分段递归；`compact_recursive=False` 时回退 MVP 单次摘要。
- **对应文档**：design §D-CE.2 / §4.3
- **验收标准**：
  - [x] 前缀 ≤ 60% 窗口 → 单次摘要（MVP 行为，回归保护）
  - [x] 前缀 > 60% 窗口 → 按回合分段，每段 ≤ 60% 窗口
  - [x] 分段边界不切断 tool_use/tool_result 配对
  - [x] 段摘要合并后 > 80% 窗口 → 递归（层数 +1）
  - [x] 递归层数 ≥ 3 → 截断 + 提示
  - [x] 单段失败 → 该段降级截断（首 500 + 尾 500 + `[中段省略]`），不整体 skip
  - [x] `compact_recursive=False` → 走 MVP 单次摘要路径
  - [x] observability span 记录：递归层数 / 段数 / 各段 token
- **备注**：分段逻辑按回合（user/assistant 一对）累加，避免切断对话完整性。后续 CE-T11 增强为预算感知 compaction（目标预算 + suffix 缩减 + max_tokens + 最终收敛）。

### CE-T8 测试 + 联调

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M3 测试 ｜ **优先级**：P0 ｜ **预估**：0.8d ｜ **依赖**：CE-T1~T7
- **范围**：`backend/tests/test_context.py` 扩展；`test_session_summary.py` / `test_token_count.py` 新建；`test_e2e.py` 加跨 session 用例；飞书群实测。
- **对应文档**：design §6
- **验收标准**：
  - [x] `test_context.py`：L2 单次 / 递归 / 上限 / 单段失败 4 条用例
  - [x] `test_session_summary.py`：生成 / 失败 / JSONL 缺失 / 滑动窗口 / 预算截断 5 条用例
  - [x] `test_token_count.py`：tiktoken / fallback / encoding 选择 3 条用例
  - [x] `test_e2e.py`：连续 3 Run 跨 session 摘要链用例
  - [x] `uv run pytest tests/test_context.py tests/test_session_summary.py tests/test_token_count.py tests/test_e2e.py` 全绿
  - [x] 飞书群连续 5+ 轮对话 → 第 6 轮验证摘要链加载（日志 / observability）
  - [x] 构造超长 context → L2 递归摘要不报 ContextLimitError
- **备注**：手动联调前确认 `task_runner` 正常调度摘要生成任务。

### CE-T9 ContextConfig 管理后台 UI

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M4 前端 ｜ **优先级**：P0 ｜ **预估**：0.8d ｜ **依赖**：CE-T2
- **范围**：`frontend/src/views/workspaces/WorkspaceDetailView.vue` 新增「上下文管理」tab；表单化编辑 `ContextConfig` 11 个字段；Overview tab 移除 raw JSON textarea（`editConfig`）。
- **对应文档**：design §D-CE.5
- **验收标准**：
  - [x] 新增「上下文管理」tab，含 11 个表单控件（对齐 design §D-CE.5 字段表）
  - [x] switch / slider / number input / select / text input / textarea / tag input 控件类型正确
  - [x] slider 显示 `% of context_window`（trigger1 / trigger2 / summary_budget_pct）
  - [x] 前端校验：`trigger1 < trigger2 < 0.95` / `clear_keep ≥ 1` / `compact_recent ≥ 1` / `summary_budget_pct ∈ [0, 0.5]`
  - [x] 校验失败标红 + 禁用保存按钮
  - [x] 「重置默认」按钮一键填入 `ContextConfig()` 默认值
  - [x] 保存调 `PATCH /workspaces/{id}` 传 `context_config` 对象
  - [x] Overview tab 移除 raw JSON textarea，不再直接编辑 `context_config`
  - [x] 浏览器手动验证：修改 trigger1 → 保存 → 刷新页面值持久化
- **备注**：`compact_instructions` 的「重置默认」需前端硬编码 `_DEFAULT_COMPACT_INSTRUCTIONS`（或后端 API 返回默认值）。

### CE-T10 模型切换 per-WS + UI + `make_provider` 改造

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-21
- **模块**：M4 前端 + M1 provider ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：CE-T3
- **范围**：`backend/app/db/models/workspace.py` 新增 `model_config` JSONB；`backend/app/agent/model_config.py` 新建 `ModelConfig.from_ws()`；`backend/app/agent/runtime.py` `make_provider()` 改造接受 `ws_model_config`；`backend/app/api/workspaces.py` GET/PATCH 处理 `model_config` + `has_api_key`；`backend/app/api/models.py` 新建 `GET /api/models`；`frontend` 新增「模型配置」tab。
- **对应文档**：design §D-CE.6
- **验收标准**：
  - [x] `Workspace.model_config` JSONB 字段 + Alembic migration（与 CE-T1 同一个 migration）
  - [x] `ModelConfig.from_ws` 容错解析（None / 空 / 缺字段 → None；未知 key 忽略）
  - [x] `make_provider(ws_model_config)` 优先用 WS 配置；`None` 时 fallback 到 settings 全局
  - [x] provider 构造接受 `api_key` / `base_url` / `model` 参数；留空时走 settings
  - [x] `GET /workspaces/{id}` 返回 `model_config` 时 `api_key_enc` 不回显，改为 `has_api_key: bool`
  - [x] `PATCH /workspaces/{id}` 传 `model_config.api_key` 非空时加密存储；为空时不覆盖既有 key
  - [x] `GET /api/models` 返回 `MODEL_REGISTRY` 列表（model_name + context_window + max_output）
  - [x] 前端「模型配置」tab：provider radio / model input + datalist / api_base_url / api_key password
  - [x] api_key 已配置时显示「已配置（不回显）」+ 「清除」按钮
  - [x] `run.py` `_execute_run` 构造 provider 时传 `ws.model_config`
  - [x] `make_summary_provider` 不动（仍走 `ContextConfig.summary_provider`）
  - [x] 浏览器手动验证：切到 GLM + 填 key → 新 Run 用 GLM；切回 anthropic → 用全局 key
- **备注**：api_key 加密复用 `app.core.security.encrypt_secret`；`api_key_enc` 解密在 provider 构造时做（`ModelConfig` 只持有加密串，provider 持有明文）。

### CE-T11 L2 预算感知 compaction

- **状态**：✅ 完成 ｜ **负责**：Qoder ｜ **完成日**：2026-07-24
- **模块**：M2 agent + M1 provider ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：CE-T7
- **范围**：`Provider.chat()`/`stream()` 加 `max_tokens` 参数（base / anthropic / openai_compatible / mock）；`ContextConfig` 新增 `summary_target_pct`；`context.py` `_compact` 改为预算感知（suffix 自动缩减 + summary_budget + max_tokens 传递）；`_recursive_compact` 加最终收敛；`_find_compact_split` 提取为纯函数；前端类型同步。
- **对应文档**：design §D-CE.2（更新）/ §3 / §4.3
- **验收标准**：
  - [x] `Provider.chat()` / `stream()` 接受 `max_tokens: int | None = None`；默认 None 回退 4096
  - [x] `ContextConfig` 新增 `summary_target_pct: float = 0.4`
  - [x] `_compact` 计算 `target = window * summary_target_pct`，suffix 超 `target * 60%` 时递减 `compact_recent`
  - [x] `summary_budget = max(800, target - suffix_tokens)` 传给 `_single_summary` / `_recursive_compact`
  - [x] `_single_summary` 传 `max_tokens` 到 `chat()` + prompt 追加长度约束
  - [x] `_recursive_compact` 合并后超 `max_tokens` 时递归或最终收敛（single_summary）
  - [x] `_find_compact_split` 提取为 staticmethod
  - [x] `test_context.py`：`max_tokens` 传递验证 + 大 suffix 自动缩减验证
  - [x] 全部 251 个测试通过
  - [x] 前端 `workspace.ts` 类型同步 `summary_target_pct`
- **备注**：解决 `context still 74696 > 60800 after clearing/compaction` 报错；根因是 L2 摘要无输出预算约束，段摘要拼接后可能远超主模型窗口。

---

## 附：跨阶段关注点

- **向后兼容**：旧 WS（`context_config` 无新字段）自动走默认值；旧 session 无摘要 → `load_chat_history` 跳过摘要前缀，行为同 MVP；`model_config` 为 None 时 fallback 到全局 settings（现有行为不变）
- **观测**：所有 L1/L2/session 摘要操作均产 span；建议 admin 界面后续加「上下文健康度」面板（展示触发频率 / 压缩比 / 递归层数分布）
- **成本**：每个 Run 多一次摘要 LLM 调用；建议 summary_provider 用便宜 model（GLM-4-air / claude-haiku），单次成本 < ¥0.01
- **安全**：`model_config.api_key` 加密存储；GET API 不回显明文；前端 password input 不显示已填值
- **回滚**：`ContextConfig.compact_recursive=False` 可回退 MVP L2 行为；`summary_budget_pct=0` 可关闭跨 session 摘要加载；`model_config=None` 可回退全局 settings provider；`summary_target_pct` 调高可放宽 compaction 预算约束
- **后续演进（P4）**：嵌入检索 / 跨 session tool 摘要 / 并行递归摘要 / 摘要缓存 / max_output 联动（按 model 适配主模型输出上限）/ model 测试连通性按钮 / ContextConfig 预设模板（见 design §8）
