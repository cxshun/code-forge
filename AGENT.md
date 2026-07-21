# AGENT.md

本文件为 AI Coding Agent 提供项目级约束与指导。Agent 在本项目内的所有行为须遵循以下规则。

## 语言要求

- **所有回复、解释、总结、问题必须使用中文。**
- 代码中的注释、docstring、commit message、PR 描述均使用中文。
- 变量名、函数名、类名等标识符保持英文（遵循各语言命名规范）。
- 日志消息、错误提示等面向用户可读的文本使用中文。
- 仅在以下情况允许英文：第三方库的 API 调用、框架要求的固定字段名、技术术语无通用中文翻译时。

## 重大决策须等待确认

以下决策属于重大变更，**必须暂停并向用户确认后方可执行**：

1. **新增或移除依赖包**：在 `pyproject.toml`、`package.json` 中增删依赖项。
2. **数据库结构变更**：新增/删除/修改表结构、索引，或新建 Alembic 迁移脚本。
3. **架构级调整**：新增或删除顶层目录、模块；改变模块间通信方式（如引入消息队列）；调整分层架构。
4. **API 接口变更**：新增、修改或删除 HTTP 路由；改变请求/响应结构。
5. **安全相关变更**：认证/授权逻辑、密钥管理、CORS 策略、权限校验等修改。
6. **环境配置变更**：`.env` 模板、Docker 配置、CI/CD 流程、部署脚本修改。
7. **删除已有代码或文件**：任何删除操作（重命名也视同删除+新增）。
8. **破坏性 Git 操作**：force push、reset --hard、删除分支、rebase 已推送的提交。

遇到不确定是否属于重大决策的情况，**默认按重大决策处理，先询问用户。**

## 编码规范

### 通用

- 不要在本次任务范围之外做"顺手清理"。修 Bug 就修 Bug，不要顺带重构周边代码。
- 不要为"将来可能需要"的场景预留接口或抽象层。只实现当前需求。
- 不要添加未被请求的错误处理、降级逻辑或兼容性代码。
- 优先编辑现有文件，不要创建新文件（除非需求明确需要）。
- 不要创建文档文件（`*.md`），除非用户明确要求。

### 后端（Python / FastAPI）

- 使用 `async` 异步模式，数据库操作必须用 async session。
- 类型注解必须完整（参数 + 返回值）。
- 公共逻辑放 `app/core/`，业务逻辑放对应模块内。
- 配置统一走 `app/config.py`（Pydantic Settings），不要硬编码。
- 数据库变更必须通过 Alembic 迁移，不要手动改表。

### 前端（Vue 3 / TypeScript）

- 使用 Composition API（`<script setup lang="ts">`）。
- 状态管理用 Pinia，API 调用放 `src/api/`。
- 组件遵循 Element Plus 设计规范。
- 不要使用 `any`，必要时用 `unknown` + 类型守卫。

## 安全保障

- **禁止将密钥、Token、密码等敏感信息硬编码到代码中。** 所有密钥通过环境变量注入。
- **禁止提交 `.env` 文件。** 确认 `.gitignore` 已覆盖 `.env`、`*.pem`、`*.key` 等敏感文件。
- SQL 查询必须使用参数化绑定，禁止字符串拼接 SQL。
- 用户输入必须做校验和转义，防止注入攻击（SQL 注入、命令注入、XSS）。
- 认证接口、权限校验逻辑修改后，须重新验证所有调用路径的安全性。
- 不要在日志中输出敏感信息（Token、密码、用户隐私数据）。项目已有脱敏机制（`app/observability/`），新增日志须遵守同一标准。

## 测试与质量

- 后端测试位于 `backend/tests/`，使用 pytest；前端测试随组件就近放置。
- 新增功能须附带对应测试。修复 Bug 须附回归测试。
- 提交前确保：`ruff check` 通过、`pytest` 全绿、`pnpm build` 无报错。
- 不要跳过测试（`--no-verify`、`@pytest.mark.skip` 等），除非用户明确要求。

## Git 规范

- Commit message 使用中文，格式：`<类型>: <简要描述>`，类型包括 `feat`、`fix`、`refactor`、`docs`、`test`、`chore`。
- 不要自动提交，除非用户明确要求。
- 不要自动 push，除非用户明确要求。
- 不要修改 `git config`。
- 不要触碰 `main` 分支的 force push。

## 项目上下文

- **项目名称**：Code Forge — 云端多租户 Coding Agent SaaS
- **后端**：Python 3.11+ / FastAPI / SQLAlchemy 2.x (async) / Alembic
- **前端**：Vue 3 (Composition API) / TypeScript / Vite / Element Plus / Pinia
- **数据库**：PostgreSQL 16 + Redis 7
- **包管理**：uv（后端）/ pnpm（前端）
- **LLM 集成**：Anthropic Claude（主）/ OpenAI 兼容端点（GLM / DeepSeek / 通义等备选）
- **飞书 SDK**：lark-oapi（WebSocket 模式）

## 核心架构约束

### Workspace 隔离模型

- **Workspace 是多租户隔离的核心单元**：所有 Run / Repo / Skill / MCP 挂载都归属某个 WS。
- 每个 `FeishuChat (app_id, chat_id)` 绑定到唯一 Workspace（`FeishuChat.workspace_id`）。
- 群聊 WS 由 admin 手动创建；p2p 单聊 WS 首次收到消息时由 `auto_bind_p2p_chat` 自动创建（owner = `P2P_WORKSPACE_OWNER_ID`）。
- **p2p 与群聊一视同仁**：仅触发方式不同（群聊需 @，p2p 直接触发），WS 命名与展示无差异；p2p WS 优先用 sender 展示名命名，不标记 "p2p:" 前缀。

### 飞书消息处理流

- 入口：`app/feishu/handler.py::handle_message(event_dict, app_id, app_secret, bot_open_id)`。
- 流程：`parse_message_event` → `chat_type` 分支（group 需 @ / p2p 直接 / 其他忽略）→ D38 去重 → 路由 `(app_id, chat_id) → FeishuChat → WS` → 组装 Run 依赖 → `run_queue.submit`。
- **Run 串行化**：同一 WS 的 Run 共享队列串行执行（WS 写锁，D20）。
- **卡片生命周期**：`on_queue` → `on_start` → `on_text`（仅累积不更新卡片）→ `on_done`（一次性渲染完整正文，含 GFM 表格等）。

### Run 与上下文管理

- Context 四道防线由 `ContextConfig.from_ws(ws.context_config)` 构造，`ContextManager` 编排；`context_config.enabled=false` 时不启用。
- MCP 连接在 Run 结束后关闭（成功 / 失败 / 中断 / 取消均执行 cleanup）。
- 流式文本仅累积，不在 `on_text` 时更新卡片（避免表格 / 格式解析异常）。

## 飞书集成要点

- **lark_oapi 是同步 API**：所有调用必须用 `asyncio.to_thread` 包装，禁止直接调用同步方法。
- **FeishuClient 生命周期**：每次 `handle_message` 新建一个 client（持有 app_id / app_secret），不复用。
- **bot_open_id**：从飞书事件元数据解析，用于识别 @ 机器人；`parse_message_event` 需要传入。
- **contact v3 API**：`get_user_name(open_id)` 拉 sender 展示名，需飞书应用授予 `contact:contact.base:readonly`（或同级 contact 读权限）；无权限时返回 None（graceful fallback，不抛异常）。
- **消息去重**：`acquire(redis, message_id)` 在进 Run 队列前完成，重复消息直接丢弃。
- **异常不向上抛**：handler 内的飞书 API 调用失败（卡片发送 / 表情添加）仅 log warning，不影响 Run 提交。

## 前端状态刷新

- **异步任务（Task）**：删除 / Clone 等异步操作返回 `task_id`，前端用 `useTaskPolling` 轮询；**必须在 `watch(isDone, ...)` 中触发数据刷新**，不能只靠用户关闭 alert 时刷新。
- **同步 mutation**：直接 `await api.xxx()` 后调用对应的 `fetchXxx()` 刷新列表，不能依赖用户手动刷新。
- **API 模块**：`src/api/` 按资源分文件（workspaces.ts / skills.ts / mcps.ts / tasks.ts 等），不要在一个文件里堆所有接口。
- **UI 改动必须浏览器验证**：前端变更须启动 dev server 在浏览器中实测主路径 + 边界情况；仅靠 TypeScript 编译通过不等于功能正确。

## 设计文档工作流

- **重大改动先文档后代码**：架构调整、新模块、新需求须先在 `docs/` 下改设计文档，用户确认后再动代码。
- **目录结构**：`docs/p1/`（MVP 阶段）、`docs/p2/`（P2 阶段），每个特性一个子目录，含 `spec.md`（需求）、`design.md`（设计 + 决策记录）、`task.md`（任务拆分）。
- **决策记录**：设计文档中用 `D-XX.N` 编号记录关键决策（如 D-DC.7 p2p 按用户独立 WS），含规则 / 理由 / 不做的事。
- **同步更新**：代码实现完成后，设计文档中的伪代码 / 文件表 / 测试用例表须同步更新，保持文档与代码一致。

## 测试约定

- **_FakeClient 模式**：mock `FeishuClient` 时实现需要的 async 方法（`send_card` / `update_card` / `add_reaction` / `delete_reaction` / `get_message` / `get_user_name`），通过 `monkeypatch.setattr(handler_module, "FeishuClient", lambda *a, **k: fake_client)` 注入。
- **isolated fixture**：每个测试用 `@pytest.fixture(autouse=True)` 的 `_isolated` 重置 DB + Redis + 临时数据目录，避免状态泄漏。
- **run_queue.submit mock**：用 `fake_submit` 捕获入队参数，并按需触发 `on_done` 回调测试卡片生命周期。
- **新增功能须附带测试**；修复 Bug 须附回归测试。

## 快速参考

| 操作 | 命令 |
|------|------|
| 安装后端依赖 | `cd backend && uv sync` |
| 安装前端依赖 | `cd frontend && pnpm install` |
| 启动后端 | `cd backend && uv run uvicorn app.main:app --reload` |
| 启动前端 | `cd frontend && pnpm dev` |
| 运行后端测试 | `cd backend && uv run pytest` |
| 代码检查 | `cd backend && uv run ruff check .` |
| 前端构建 | `cd frontend && pnpm build` |
| 数据库迁移 | `cd backend && uv run alembic upgrade head` |
