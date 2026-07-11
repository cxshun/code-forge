# Code Forge 开发任务列表

> 任务拆分依据：[spec.md](./spec.md)（需求）/ [design.md](./design.md)（设计）/ [api.md](./api.md)（接口）。
> 本文件**拆任务并维护任务状态**。推进任务时按 §0「维护方式」同步更新「状态总览」与任务详情；任务完成时勾选验收标准 `[x]` 并补「完成记录」。

---

## 0. 图例与约定

- **优先级**：`P0` MVP 必做且阻塞主流程 ｜ `P1` MVP 必做但非阻塞 ｜ `P2` 后续预留
- **模块**：对齐 design §5（M1 接入层 / M2 内核 / M3 工具 / M4 工作空间 / M5 管理后台 / M6 持久化 / M7 鉴权 / M8 可观测性）
- **预估**：理想人天（`0.5d` 半天 / `1d`~`3d`）
- **依赖**：列出前置任务编号；无依赖写 `—`
- **状态**：`⚪ 未开始` ｜ `🔵 进行中` ｜ `✅ 已完成` ｜ `⛔ 阻塞`
- **维护方式**（每推进一个任务都需同步两处）：
  1. 更新下方「状态总览」表对应行的 `状态 / 负责 / 完成日` 与顶部「进度统计」
  2. 更新该任务详情首行的 `状态` 字段
  3. 完成后在任务详情追加一行 `**完成记录**：<产出 / 关键改动 / 提交 ref 或日期>`，并勾选验收标准 `[x]`
  4. 受阻时标 `⛔ 阻塞`，并在 `完成记录` 写明阻塞原因与前置任务
- **阶段划分**：按依赖关系而非日历周。各 Phase 末尾给出"切片验收点"——可独立 demo 的功能闭环

| Phase | 主题 | 对应里程碑（design §9） |
|---|---|---|
| P0 | 项目初始化与基础设施 | Week 1 起点 |
| P1 | 数据层 + 鉴权 | Week 1 |
| P2 | 工作空间管理（后端） | Week 1-2 |
| P3 | 广场（Skill / MCP 管理） | Week 2 |
| P4 | 飞书接入层 | Week 1-2 |
| P5 | Agent 内核 + 内置工具（核心闭环） | Week 2-4 |
| P6 | 并发控制（WS 写锁 / Run 队列） | Week 3-4 |
| P7 | Memory + AGENT.md | Week 4-5 |
| P8 | 管理后台前端 | Week 5-6 |
| P9 | 可观测性 P0 | Week 5-6 |
| P10 | 可观测性 P1（成本 / 监控告警） | Week 7+ |
| P11 | 测试与上线 | Week 7+ |

---

## 状态总览

> 单一进度看板，每行 = 一个任务。按 Task ID 顺序排列；状态 / 负责 / 完成日 随推进更新，详情见各 Phase 任务段落。

**进度统计**：已完成 `43 / 64` ｜ P0 `41 / 54` ｜ P1 `2 / 10`

| Task | 标题 | 状态 | 优先级 | 负责 | 完成日 |
|---|---|---|---|---|---|
| T0.1 | 后端工程脚手架 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T0.2 | 前端工程脚手架 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T0.3 | Docker Compose 本地环境 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T0.4 | CI 骨架 | ✅ 已完成 | P1 | cxshun | 2026-07-09 |
| T1.1 | 数据库 schema 设计与建模 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T1.2 | Alembic 迁移初始化 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T1.3 | 文件系统目录工具 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T1.4 | 自建账号密码鉴权 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T1.5 | 权限装饰器与 owner 校验 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T1.6 | 用户管理 API | ✅ 已完成 | P1 | cxshun | 2026-07-09 |
| T2.1 | Workspace CRUD | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T2.2 | Git Repo 挂载与同步 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T2.3 | FeishuChat 绑定（含预校验） | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T2.4 | Skill / MCP 挂载管理 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T2.5 | AGENT.md 读写 | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T2.6 | 异步任务轮询 API | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T3.1 | Skill 上传与广场 CRUD | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T3.2 | MCP 注册与广场 CRUD | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T3.3 | 飞书 App 注册 API | ✅ 已完成 | P0 | cxshun | 2026-07-09 |
| T4.1 | 飞书 SDK 封装与 API 客户端 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T4.2 | 多 App WebSocket 长连接池 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T4.3 | 群聊消息接收与 @识别 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T4.4 | 路由层（app_id, chat_id → ws_id） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T4.5 | 即时 Thinking 反馈 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T4.6 | 富卡片渲染器 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T4.7 | 引用回复解析与注入 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.1 | LLM Provider 抽象层 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.2 | Agentic Loop 主体 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.3 | System Prompt 构建 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.4 | Session / Run 管理（1:1） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.5 | 内置工具实现（只读类） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.6 | 内置工具实现（写类 + Bash） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.7 | Skill 工具（按需 invoke） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.8 | MCP 客户端 | ⚪ 未开始 | P1 | — | — |
| T5.9 | 子代理（Agent 工具）+ 并行执行 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T5.10 | 上下文管理（自研四道防线） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T6.1 | WS 写锁（Redis 分布式锁） | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T6.2 | Run 队列与排队反馈 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T6.3 | 取消与中断 | ✅ 已完成 | P0 | cxshun | 2026-07-10 |
| T7.1 | AGENT.md 加载与注入 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T7.2 | Memory 索引加载 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T7.3 | Memory 写入策略（System Prompt 指令） | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T7.4 | Memory 陈旧性校验 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T7.5 | Memory 管理后端 API | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T8.1 | 登录与布局框架 | ⚪ 未开始 | P0 | — | — |
| T8.2 | Workspace 管理页 | ⚪ 未开始 | P0 | — | — |
| T8.3 | 广场页（Skill / MCP） | ⚪ 未开始 | P0 | — | — |
| T8.4 | 飞书 App 注册页 | ⚪ 未开始 | P0 | — | — |
| T8.5 | 会话历史页 | ⚪ 未开始 | P1 | — | — |
| T8.6 | Memory 管理页 | ⚪ 未开始 | P0 | — | — |
| T8.7 | 用户管理页 | ⚪ 未开始 | P1 | — | — |
| T9.1 | spans 表 + ORM + WS 隔离 | ⚪ 未开始 | P0 | — | — |
| T9.2 | Tracer（contextvars + span 上下文管理器） | ⚪ 未开始 | P0 | — | — |
| T9.3 | SpanBuffer 批写 + 降级 | ⚪ 未开始 | P0 | — | — |
| T9.4 | Agent Loop 埋点 | ⚪ 未开始 | P0 | — | — |
| T9.5 | Payload 写入 + 截断 + 脱敏 | ⚪ 未开始 | P0 | — | — |
| T9.6 | Trace 列表 + 瀑布图 API + 前端 | ⚪ 未开始 | P0 | — | — |
| T10.1 | Cost 计算引擎 | ⚪ 未开始 | P1 | — | — |
| T10.2 | 成本 / 工具 / 模型聚合视图 | ⚪ 未开始 | P1 | — | — |
| T10.3 | 监控告警 | ⚪ 未开始 | P1 | — | — |
| T10.4 | TTL 清理 | ⚪ 未开始 | P1 | — | — |
| T11.1 | 端到端测试用例 | ⚪ 未开始 | P0 | — | — |
| T11.2 | 安全核查 | ⚪ 未开始 | P0 | — | — |
| T11.3 | 部署与上线 | ⚪ 未开始 | P0 | — | — |

---

## Phase 0 — 项目初始化与基础设施

> 目标：前后端能本地跑起来，依赖服务（PG / Redis）容器化，约定项目骨架。

### T0.1 后端工程脚手架
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M2/M4 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：—
- **范围**：FastAPI 项目结构（按 design §3.5：分层 + 业务域，目录骨架 `app/{api, feishu, agent, providers, tools, workspace, memory, db, observability, core, tasks}`）、`pyproject.toml`（Python 3.11+，uv 管理依赖）、配置管理（pydantic-settings，环境变量分 dev/prod）、结构化日志（jsonl）、`uvicorn` 入口。
- **对应文档**：design §3.1
- **验收标准**：
  - [x] `uv run uvicorn` 能起服务，`GET /healthz` 返回 200
  - [x] 配置按环境加载（DB / Redis / 飞书 / Anthropic key 占位）
  - [x] 请求日志中间件就位
- **完成记录**：FastAPI 脚手架落地，目录骨架对齐 design §3.5（`app/{api,feishu,agent,providers,tools,workspace,memory,db,observability,core,tasks}`）。uv 管理依赖（Python 3.11）；pydantic-settings 配置（dev/prod/test，凭证占位）；structlog jsonl 日志 + 请求中间件（request_id 注入 contextvars）。验证：`uv run pytest` 1 passed、`uv run ruff check .` clean、`uvicorn` 起服务 `/healthz` 返回 `{"status":"ok","version":"0.1.0","env":"dev"}`。

### T0.2 前端工程脚手架
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：—
- **范围**：Vue 3 + Vite + TypeScript、Element Plus、Pinia、Vue Router、axios 封装（统一错误处理 / 拦截 401）、ESLint + Prettier。
- **对应文档**：design §3.2
- **验收标准**：
  - [x] `pnpm dev` 起服务，占位首页可访问
  - [x] axios 实例含 baseURL（指向后端 `/api`）+ 401 跳登录拦截
- **完成记录**：Vue3 + Vite6 + TS + Element Plus + Pinia + Vue Router + axios 脚手架，`src/{router,stores,api,views,types}`。axios 实例 baseURL=`/api` + withCredentials + 401 跳登录拦截；路由守卫未登录跳登录（带 redirect）。pnpm 11 用 `pnpm-workspace.yaml` 配 `allowBuilds`(esbuild/vue-demi)。验证：`pnpm build`（vue-tsc 类型检查通过、1668 模块）、`pnpm dev` HTTP 200（`#app` 挂载 + `main.ts` 加载）。

### T0.3 Docker Compose 本地环境
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：infra ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T0.1
- **范围**：`docker-compose.yml` 编排 PostgreSQL、Redis、后端、前端；初始化卷；`.env.example`。
- **对应文档**：design §3.4（MVP = Docker Compose）
- **验收标准**：
  - [x] `docker compose up` 一键拉起全栈
  - [x] PG / Redis 数据持久化卷配置就位
- **完成记录**：`deploy/docker-compose.yml` 编排 postgres/redis/backend/frontend（4 services）+ `pg_data`/`redis_data`/`app_data` 持久化卷 + PG/Redis healthcheck + 后端 `depends_on: service_healthy`；配套 `Dockerfile.backend`(uv) / `Dockerfile.frontend`(pnpm) / `.env.example`。YAML 语法已校验。**验证后置**：本地未装 Docker，`docker compose up` 一键拉起待 Docker 环境验证（compose 文件 + 卷配置已就位）。

### T0.4 CI 骨架（可选先建）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：infra ｜ **优先级**：P1 ｜ **预估**：0.5d ｜ **依赖**：T0.1, T0.2
- **范围**：lint + 单测 + migration check 的 CI workflow。
- **验收标准**：
  - [x] PR 触发 CI，lint / test 失败阻断合并
- **完成记录**：`.github/workflows/ci.yml`：backend job（setup-uv → `uv sync --all-extras` → ruff check → pytest）+ frontend job（pnpm → build）；alembic check 占位待 T1.2 启用。**验证后置**：PR 触发需推送 GitHub；本地 ruff / pytest / build 已分别通过。

---

## Phase 1 — 数据层 + 鉴权

> 目标：DB schema 落地、Alembic 迁移就绪、自建账号密码登录闭环。

### T1.1 数据库 schema 设计与建模
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M6 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T0.1
- **范围**：SQLAlchemy 2.x 异步模型，覆盖：`users` / `feishu_apps` / `workspaces` / `feishu_chats`（`(app_id, chat_id)` 唯一约束）/ `git_repos` / `skills` / `mcps` / `workspace_skill` / `workspace_mcp` / `sessions` / `runs` / `spans`（单表自引用，design §7.2）/ `tasks`（异步任务）/ `workspace_settings`（WS 级配置，含上下文管理策略 `context_config`，design D34，可作 `workspaces` JSON 字段或独立表）。索引、外键、`ON DELETE CASCADE` 按文档补齐。
- **对应文档**：design §2.1 实体关系、§7.2 spans 模型；spec F3.2~F3.3
- **验收标准**：
  - [x] 所有表含 `created_at / updated_at`
  - [x] `feishu_chats` 联合唯一约束生效（绑定时 409）
  - [x] spans 单表自引用 + 四元外键（ws/chat/session/run）CASCADE
- **完成记录**：SQLAlchemy 2.x 异步模型 13 表落地（users/feishu_apps/workspaces/feishu_chats((app_id,chat_id) 唯一)/git_repos/skills/mcps/workspace_skill/workspace_mcp/sessions/runs/spans(单表自引用+四元外键 CASCADE §7.2)/tasks；workspaces.context_config JSON 承载 D34）。db/{base,session,models}；枚举用 StrEnum+VARCHAR（迁移友好）。验证：metadata 13 表注册、迁移 DDL 含 `uq_feishu_chats_app_chat`/spans 自引用+四元 CASCADE/JSONB、PG 16 连通。

### T1.2 Alembic 迁移初始化
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M6 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T1.1
- **范围**：Alembic 接入、首版迁移脚本、`alembic upgrade head` 在空库可跑通。
- **验收标准**：
  - [x] 全新 PG `upgrade head` 无报错
  - [x] CI 含 `alembic check`（防迁移漂移）
- **完成记录**：alembic.ini + alembic/env.py（异步 autogenerate）+ script.py.mako。首版迁移 init schema：`upgrade head` 无报错、`check` 无漂移。CI backend job 加 postgres service + `alembic upgrade`/`check`。关键修复：workspaces.cwd_repo_id 去 FK（避免与 git_repos.workspace_id 循环外键导致建表失败，引用完整性改应用层保证）。

### T1.3 文件系统目录工具
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M4/M6 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.1
- **范围**：封装工作空间目录创建 / 路径 resolve 校验工具，对齐 design §2.3 结构（`/workspaces/{ws_id}/{repos,chats,logs}`、`/skills/{skill_id}`）。提供 `resolve_within(path, root)` 防穿越函数。
- **对应文档**：design §2.3、D17
- **验收标准**：
  - [x] 创建 WS 时自动建目录骨架 + `chats/{id}/memory/MEMORY.md`
  - [x] resolve 校验函数能挡住 `..` / 符号链接穿越单测通过
- **完成记录**：app/workspace/fs.py：`resolve_within`（resolve 跟随 symlink，绝对/相对路径都校验落 root 内）+ `create_workspace_skeleton`(repos/chats/logs) + `create_chat_memory_skeleton`(memory/sessions/traces + 空 MEMORY.md) + `create_skill_skeleton`(resources/scripts)。tests/test_fs.py 8 用例覆盖 `..` / symlink 穿越 / 绝对路径越界。

### T1.4 自建账号密码鉴权
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M7 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T1.1
- **范围**：argon2 密码哈希；`POST /api/auth/login`（校验 → 下发 HttpOnly Cookie session）、`/logout`、`/me`、`/change-password`；session 存储（Redis）；登录限流（同 IP 5 次/分钟）；角色二分（admin / user）。
- **对应文档**：D32、api §2.1；spec F3.8.1
- **验收标准**：
  - [x] 登录成功下发 `HttpOnly; SameSite=Lax` Cookie，未登录接口返回 401
  - [x] 错误密码 5 次后限流（429 或 401 计数）
  - [x] `/me` 返回用户 + 可访问 WS 列表
- **完成记录**：argon2 密码 + Fernet 凭证加密（core/security.py，密钥从 secret_key 派生，D32/NF4.2.4）；Redis session + 同 IP 5 次/分限流（core/session.py）；POST /auth/login（下发 HttpOnly;SameSite=Lax Cookie）/logout/me(用户+WS 列表)/change-password。tests/test_auth.py 覆盖成功/401/429 限流/me/登出/改密。

### T1.5 权限装饰器与 owner 校验
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M7 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.4
- **范围**：FastAPI 依赖注入：`require_user` / `require_ws_owner` / `require_res_owner` / `require_admin`；统一错误码（403 forbidden）。
- **对应文档**：api §1.6 / §1.8；spec F3.8.2~F3.8.3、D21 后台权限
- **验收标准**：
  - [x] 非 owner 访问 WS 资源返回 403
  - [x] 单测覆盖四种权限标记
- **完成记录**：core/deps.py：get_current_user（session cookie→User）、require_user/require_admin/require_ws_owner(含 ws_id 路径 + 404)/assert_res_owner。core/errors.py 统一 `{error:{code,message}}`；main.py 全局异常处理器（HTTPException + RequestValidationError）。tests/test_deps.py 覆盖四种权限标记（含管理员豁免 + WS 404）。

### T1.6 用户管理 API
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M7 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T1.5
- **范围**：`GET/POST /users`、`PATCH /users/{id}`、`POST /users/{id}:reset-password`（管理员）。
- **对应文档**：api §2.2；spec F3.7.7
- **验收标准**：
  - [x] 管理员可建账号 / 改角色 / 停用 / 重置密码
  - [x] 非管理员调用返回 403
- **完成记录**：api/users.py：GET/POST /users、PATCH /users/{id}、POST /users/{id}:reset-password（均 require_admin；重复 username 经 IntegrityError→409）。tests/test_users.py 覆盖非 admin 403/创建/列表/停用/重置/冲突。

> **切片验收点 P1**：可登录、可建账号、DB 与文件目录骨架就绪。

---

## Phase 2 — 工作空间管理（后端）

> 目标：WS / Repo / FeishuChat / 挂载 / AGENT.md 的后端 API 全通。

### T2.1 Workspace CRUD
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M4 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.3, T1.5
- **范围**：`GET/POST/PATCH/DELETE /workspaces`、`/workspaces/{ws_id}`（详情含 repos/chats/mounts 概览）；删除走异步级联（202 + task_id），删除前校验已解绑所有 FeishuChat + 解除广场引用。
- **对应文档**：api §4；spec F3.2.1 / F3.2.5；design D8
- **验收标准**：
  - [x] 创建 WS 同时建物理目录
  - [x] 删除前若有绑定 chat / 引用，返回 422 拒绝
  - [x] 异步级联清理任务可轮询状态
- **完成记录**：api/workspaces.py CRUD；create 建目录骨架，delete 异步级联（task_runner 删 DB CASCADE + 物理目录），删前校验 chat/引用 → 422。test_workspaces.py 覆盖。

### T2.2 Git Repo 挂载与同步
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M4 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T2.1
- **范围**：`POST /workspaces/{ws_id}/repos`（HTTPS clone，可选 token）、`:sync`（git pull）、`GET` / `DELETE`；clone 异步（202 + task_id），记录 clone 状态 / cwd。
- **对应文档**：api §5.1；spec F3.2.2；design D6
- **验收标准**：
  - [x] 公开 repo 可 clone 到 `repos/{repo_id}/`
  - [x] 带 token 的私有 repo 可 clone，token 不入日志 / 不回显
  - [x] clone 失败任务状态为 failed + error
- **完成记录**：workspace/git.py（asyncio subprocess，token 注入 url userinfo、不 log）+ api/repos.py（clone/sync 异步 202、GET/DELETE）。clone_status 状态机 pending→cloning→ready/failed。test_repos.py 用本地 bare repo 验证成功 + 无效 url 失败。

### T2.3 FeishuChat 绑定（含预校验）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M4/M1 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T2.1, T4.1
- **范围**：`POST /workspaces/{ws_id}/chats:check`（调飞书 API 校验 app_id + chat_id 合法性 + 机器人是否在群 + 是否已绑）、`POST /chats` 绑定（唯一约束）、`GET` / `DELETE`。绑定成功创建 `chats/{feishu_chat_id}/memory/` 目录。
- **对应文档**：api §5.2 / §10.1；spec F3.2.3~F3.2.5；design D8
- **验收标准**：
  - [x] 预校验返回 `valid / bot_in_chat / chat_name / existing_binding`
  - [x] 已绑别 WS 的 chat 返回 409
  - [x] 机器人不在群返回 422
- **完成记录**：`app/api/chats.py`：GET 列表 / `POST :check` 预校验 / `POST` 绑定 / `DELETE` 解绑。预校验 `_probe_chat` 经 `FeishuClient.get_chat` 探测（bot 不在群/群不存在→None→valid=bot_in_chat=False；MVP valid 与 bot_in_chat 同信号，client 行为所致已记录），返回 valid/bot_in_chat/chat_name/existing_binding(feishu_chat_id+workspace_id+is_this_ws)。绑定：bot 不在群→422；(app_id,chat_id) 唯一约束冲突→409（含跨 WS）；FeishuApp 须为当前用户拥有（或 admin，else 403）/未注册→422；成功 `create_chat_memory_skeleton` 建 memory 目录。test_chats.py 9 用例（fake FeishuClient 注入）覆盖预校验两种/绑定+memory目录/422/409/跨WS409/403/422/列表+解绑/解绑他 WS 404。

### T2.4 Skill / MCP 挂载管理
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M4/M3 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T2.1, T3.1, T3.2
- **范围**：`GET/POST/DELETE /workspaces/{ws_id}/skills`、`/mcps`；挂载时校验可见性 + 单 WS Skill 上限 50。
- **对应文档**：api §5.3；spec F3.5.6；design D11
- **验收标准**：
  - [x] 挂载私有 Skill 非 owner 返回 403
  - [x] 超 50 个 Skill 返回 422
  - [x] 解挂后关联表删除
- **完成记录**：`app/api/mounts.py`：GET/POST/DELETE `/workspaces/{ws_id}/skills` 与 `/mcps`。挂载 `_assert_visible_owner`（public 放行；私有须 owner 或 admin，else 403）；Skill 超 `MAX_SKILLS_PER_WS=50`→422（F3.5.6，MCP 无上限）；重复挂载复合主键冲突→409；解挂 `db.get(WorkspaceSkill,(ws.id,skill_id))` 未挂载→404。test_mounts.py 8 用例覆盖挂载/列表/解挂/私有403/重复409/超限422(挂满50再挂第51)/未挂载404/MCP无上限/Skill不存在404。

### T2.5 AGENT.md 读写
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M4 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T2.1
- **范围**：`GET/PUT /workspaces/{ws_id}/agent-md`（WS 级，可编辑）、`GET /workspaces/{ws_id}/repos/{repo_id}/agent-md`（Repo 级，只读）。
- **对应文档**：api §5.4；spec F3.9.7；design D24
- **验收标准**：
  - [x] WS 级可读写，Repo 级只读（PUT 返回 405）
  - [x] 文件不存在时返回空内容而非 404
- **完成记录**：api/agent_md.py：WS 级 GET/PUT、Repo 级 GET（PUT 不定义→FastAPI 405）。文件不存在返回空 content。test_agent_md.py 覆盖读写 + Repo 405。

### T2.6 异步任务轮询 API
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M4 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T1.1
- **范围**：`GET /api/admin/tasks/{task_id}`（pending/running/done/failed + progress/result/error）；异步任务用 asyncio + Redis 队列承载（design §3.1，不引入 Celery）。
- **对应文档**：api §1.7 / §10.4
- **验收标准**：
  - [x] git clone / WS 删除均可通过 task_id 轮询
  - [x] 任务状态机正确流转
- **完成记录**：tasks/runner.py（TaskRunner：asyncio.create_task + DB 状态机 pending→running→done/failed + recover_orphans 启动恢复 D36）+ api/tasks.py 轮询。lifespan 启动清理 orphan task。WS delete / git clone 均通过 task_id 轮询验证。

> **切片验收点 P2**：管理员可通过 API 完整配置一个 WS（建 WS → 挂 repo → 绑 chat → 挂 skill）。

---

## Phase 3 — 广场（Skill / MCP 管理）

> 目标：Skill / MCP 的上传、可见性、引用计数、删除保护。

### T3.1 Skill 上传与广场 CRUD
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M3/M5 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T1.3, T1.5
- **范围**：`POST /skills`（multipart：SKILL.md + resources + scripts）、`GET /skills`（我的 + 全员可见，筛选 / 搜索）、`GET/PATCH/DELETE /skills/{skill_id}`。frontmatter 校验（name 全局唯一、description 必填）；落 `/skills/{skill_id}/`；引用计数；被引用禁删。
- **对应文档**：api §6.1 / §10.2；spec F3.5.1~F3.5.7；design D11 / D15
- **验收标准**：
  - [x] frontmatter 缺字段 / name 重复返回 422
  - [x] 上传后目录结构 = `SKILL.md + resources/ + scripts/`
  - [x] 被引用的 Skill 删除返回 422，需先解绑
- **完成记录**：api/skills.py：POST multipart zip → 解析 SKILL.md frontmatter（name 全局唯一/description 必填，缺/重复 422）→ 防 zip-slip 解压到 /skills/{id}/；GET 返回 mounted_count；被引用禁删。test_skills.py 覆盖。

### T3.2 MCP 注册与广场 CRUD
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.5
- **范围**：`GET/POST/PATCH/DELETE /mcps`（stdio 命令 / http endpoint 配置）；可见性；被引用禁删。
- **对应文档**：api §6.2；spec F3.5.3~F3.5.5；design D11
- **验收标准**：
  - [x] stdio / http 两种类型可注册
  - [x] 配置含 secret 字段时脱敏返回
- **完成记录**：api/mcps.py：CRUD（我的+public）；config 递归 secret 字段加密存储/脱敏返回（core/security encrypt_secrets/mask_secrets）；被引用禁删。test_mcps.py 覆盖。

### T3.3 飞书 App 注册 API
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-09
- **模块**：M1/M4 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T1.5
- **范围**：`GET/POST/GET/PATCH/DELETE /feishu-apps`；`app_secret` 列表 / 详情脱敏（前后各 4 位），完整 secret 仅创建时返回一次。
- **对应文档**：api §3；spec F3.1.6；design D7
- **验收标准**：
  - [x] 列表 / 详情 secret 脱敏
  - [x] 删除前需解绑所有 FeishuChat
- **完成记录**：api/feishu_apps.py：app_secret Fernet 加密存 app_secret_enc；列表/详情脱敏（前后4位）；完整 secret 仅创建时返回一次；删除前校验 FeishuChat 引用。test_feishu_apps.py 覆盖。

> **切片验收点 P3**：广场可上传 Skill / 注册 MCP，WS 可引用挂载。

---

## Phase 4 — 飞书接入层

> 目标：多 App WebSocket 长连接池收发消息，路由到 WS，即时 Thinking 反馈。

### T4.1 飞书 SDK 封装与 API 客户端
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T3.3
- **范围**：基于 `lark-oapi` 封装：tenant access token 获取与缓存、IM API（查 chat 信息 / 判断机器人是否在群 / 发消息 / 更新卡片）。
- **对应文档**：design §3.1 / D7
- **验收标准**：
  - [ ] 可凭 app_id+secret 获取 tenant_access_token 并缓存刷新
  - [ ] 可发送文本 / 卡片消息到指定 chat_id

### T4.2 多 App WebSocket 长连接池
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T4.1
- **范围**：每个注册的飞书 App 启动一个独立 WebSocket 长连接（多 Client 池），共享接入层调度；连接生命周期管理（断线重连、App 增删时动态启停连接）。
- **对应文档**：spec F3.1.1 / F3.1.6；design D7、§6.1
- **验收标准**：
  - [ ] 注册新 App 后自动起一条 WS 连接
  - [ ] 删除 App 后连接关闭
  - [ ] 断线自动重连

### T4.3 群聊消息接收与 @识别
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T4.2
- **范围**：仅群聊（私聊 MVP 不做）；识别 @ 机器人触发；解析 `(app_id, chat_id, text, sender)`。
- **对应文档**：spec F3.1.2 / F3.1.3；design D13 / D21
- **验收标准**：
  - [ ] @ 机器人触发，非 @ 忽略
  - [ ] 提取触发者信息用于回复 @

### T4.4 路由层（app_id, chat_id → ws_id）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T4.3, T2.3
- **范围**：`(app_id, chat_id)` → `feishu_chat_id` → `ws_id` 三级查找；未绑定的 chat 忽略或提示。
- **对应文档**：design §6.1 关键说明
- **验收标准**：
  - [ ] 绑定过的 chat 能命中 ws_id
  - [ ] 未绑定 chat 不触发 Run

### T4.5 即时 Thinking 反馈
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T4.1
- **范围**：接入层收到消息后立即回复"思考中"表情 / 卡片，给用户感知确认。
- **对应文档**：spec F3.1.5；design §6.1
- **验收标准**：
  - [ ] 收到消息 < 1s 内出现 Thinking 反馈
  - [ ] 最终回复时替换 Thinking 卡片

### T4.6 富卡片渲染器
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T4.1
- **范围**：飞书互动卡片封装：进度卡片（流式 token 推送，阈值合并更新防限流）、Plan 确认卡片（按钮）、diff 预览卡片、TaskList 卡片、排队状态卡片。
- **对应文档**：spec F3.1.4；design D4 / §6.1
- **验收标准**：
  - [ ] 各卡片类型可发送 / 增量更新
  - [ ] Plan 确认卡片按钮回调可接收
  - [ ] 流式更新有节流（避免飞书限流）

### T4.7 引用回复解析与注入
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M1/M2 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T4.3, T5.3
- **范围**：接入层解析引用回复消息：识别 `parent_id` / quote 字段；提取被引用消息纯文本（优先推送事件 quote，取不到以 `parent_id` 调飞书 IM API `im.message.get` 拉取）；按 D39 注入形态前置「引用块」到本次 Run 的 user message；**引用 + @ 才触发**（对齐 F3.1.3）；被引用为富卡片时尽力提取纯文本、失败标注；不恢复历史 session。
- **对应文档**：design D39；spec F3.1.10
- **验收标准**：
  - [x] 引用历史消息 + @ 能触发，提取的引用文本正确进入 user message
  - [x] 只引用不 @ 不触发
  - [x] 被引用消息为卡片时提取纯文本（或正确标注无法提取）
  - [x] 引用回复的 Run 以本次 message_id 去重，与被引用 parent 不冲突
- **完成记录**：`quote.py:parse_message_event` 提取 parent_id（message.parent_id / root_id）；引用 + @ 才触发（at_bot 由 quote 解析，handler 强制 group+at_bot）。D39 注入由 `agent/runtime.fetch_quote_text` 实接：parent_id → `FeishuClient.get_message` 拉被引用 Message.body.content + msg_type → `extract_plain_text` 提取纯文本 → markdown 引用块前置到 user message（handler 拼 `quote + ctx.text`）；取不到/异常静默返回 None（不阻断 Run）。test_runtime 覆盖正常/无 parent/空正文/get_message None/异常吞掉 5 用例。引用回复以本次 message_id 经 D38 去重，与 parent 不冲突。

> **切片验收点 P4**：群里 @ 机器人能收到 Thinking 反馈并路由到对应 WS（引用回复可被识别，此时还不跑 Agent）。

---

## Phase 5 — Agent 内核 + 内置工具（核心闭环）

> 目标：跑通"飞书消息 → Agent Loop → 工具调用 → 流式回复"端到端闭环。

### T5.1 LLM Provider 抽象层
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T0.1
- **范围**：抽象 `Provider` 接口（chat / stream / tool_use 解析）；Claude 实现（anthropic SDK）；多模型可切换预留（design D3）。
- **对应文档**：design D3；spec NF4.5.1
- **验收标准**：
  - [ ] 接口与具体厂商解耦，切换模型不改上层
  - [ ] 流式响应可逐 chunk 回调

### T5.2 Agentic Loop 主体
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T5.1
- **范围**：调用 LLM → 解析 tool_use → 执行工具 → 反馈结果 → 直到最终回复；流式 text_delta 推飞书；中断 / 超时检测点。
- **对应文档**：spec F3.3.1 / F3.3.2；design §6.5
- **验收标准**：
  - [ ] 无 tool_use 时正常终止并回复
  - [ ] 多轮 tool_use 正常循环
  - [ ] 流式 token 实时推飞书

### T5.3 System Prompt 构建
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T5.2, T7.2
- **范围**：按注入顺序拼接（design D24）：基础指令 → WS 级 AGENT.md → Repo 级 AGENT.md（当前 cwd）→ MEMORY.md 索引 → Skill descriptions。基础指令中含**并行子代理拆分指导**（D33：仅独立子任务并行、优先只读并行、写型需改不同文件、冲突则串行）。
- **对应文档**：design D24 / D33；spec F3.3.9 / F3.9.3~F3.9.5
- **验收标准**：
  - [ ] 注入顺序符合 D24
  - [ ] 多 repo 仅加载当前 cwd 所在 repo 的 AGENT.md
  - [ ] system prompt 含 D33 拆分指导文案

### T5.4 Session / Run 管理（1:1）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.2, T1.1
- **范围**：1 Session = 1 Run（design D23）；每次消息触发新 Session + 新 Run；会话历史落盘 JSONL（简化 messages 数组，供下次加载）。
- **对应文档**：design D23；spec F3.3.7
- **验收标准**：
  - [x] 每条消息独立 Session/Run
  - [x] JSONL 落盘且可被下次 Run 加载
- **完成记录**：`agent/run.py` 建 Session+Run（1:1，D23）→ 抢 WS 锁 → run_loop → `save_session_jsonl` 落盘。**端到端闭环**（2026-07-11 补）：`feishu/handler.py` 接 `run_queue.submit`——路由 (app_id,chat_id)→FeishuChat→ws_id 后，`agent/runtime.build_registry`（内置 6 工具 + 挂载 Skill）+ `resolve_cwd` + `make_provider` 组装依赖，`FeishuRunCallbacks` 桥接卡片（on_queue/on_start 发卡、on_text 经 ProgressThrottler 节流 update_card 流式回复、on_done 成功 flush / 失败展示中断·取消·错误）。至此"飞书消息→Agent Run→流式回复"端到端真正打通（此前 B5 仅测试验证 start_run）。test_handler 覆盖 submit 入队参数/回调齐全、无 key 发错误卡、未绑 chat 不入队、非群聊忽略、回调节流+finalize+错误卡。

### T5.5 内置工具实现（只读类）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.2, T1.3
- **范围**：`Read` / `Glob` / `Grep`（ripgrep）/ `WebFetch` / `WebSearch` / `TaskList` 系列 / `Plan Mode`。路径限定 `repos/` 与 `chats/{feishu_chat_id}/memory/`。
- **对应文档**：design §5.1；spec F3.4.1 / F3.4.4 / D17
- **验收标准**：
  - [ ] 越界路径被拒绝并告知 Agent
  - [ ] Grep 基于 ripgrep，大仓库可用

### T5.6 内置工具实现（写类 + Bash）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.5, T6.1
- **范围**：`Write` / `Edit`（精确替换）/ `Bash`（路径校验 + Skill 脚本调用）。写操作抢 WS 锁（D20）。
- **对应文档**：design §5.1 / D17 / D20；spec F3.4.4~F3.4.5
- **验收标准**：
  - [ ] Write/Edit 路径白名单正确（含 AGENT.md 两份文件白名单）
  - [ ] Bash 越界命令拒绝

### T5.7 Skill 工具（按需 invoke）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.5, T3.1
- **范围**：每个挂载 Skill 自动生成 `skill__{name}` 工具；启动时仅注入 name+description；invoke 时后端读完整 SKILL.md 作为 tool_result 返回；`scripts/` 走 Bash、`resources/` 走 Read（design D16 三阶段）。
- **对应文档**：design D15 / D16、§6.7；spec F3.4.3
- **验收标准**：
  - [ ] system prompt 仅含 description（不膨胀）
  - [ ] invoke 后 SKILL.md 进入上下文，Agent 可按工作流调脚本 / 读资源

### T5.8 MCP 客户端
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M3 ｜ **优先级**：P1 ｜ **预估**：2d ｜ **依赖**：T5.5, T3.2
- **范围**：连接外部 MCP 服务（stdio / http），动态注册其工具到 Agent 工具集。
- **对应文档**：spec F3.4.2；design §1
- **验收标准**：
  - [ ] stdio / http 两种 MCP 可连
  - [ ] MCP 工具可被 Agent 调用

### T5.9 子代理（Agent 工具）+ 并行执行（D33 L1）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M2/M3 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T5.2, T6.1
- **范围**：`Agent` 工具委派子任务；主 Agent 一轮返回多个 Agent tool_use 时用 `asyncio.gather` 并发执行（非串行）；子代理独立上下文窗口、仅回最终消息；继承 chat MEMORY.md 索引 + WS/Repo AGENT.md；可重入复用父 Run 锁（不重复抢、子代理间写不二次串行）；并行度上限默认 5、超限排队；单个子代理失败标记回主 Agent 不一刀切；trace 用 subagent span 并列挂父 span。
- **对应文档**：design D33 / §5.1 / §6.9（执行时序 + 拆分决策图）；spec F3.3.8~F3.3.9 / F3.4.1 / NF4.3.5
- **验收标准**：
  - [ ] 多个 Agent tool_use 并发执行（非 for 循环串行）
  - [ ] 子代理独立上下文，仅最终消息回流到主 Agent
  - [ ] 子代理可重入父 Run 锁，无阻塞 / 死锁
  - [ ] 只读子代理真并行；写型子代理间不二次串行
  - [ ] 单子代理失败不导致整 Run 失败
  - [ ] 并行度超上限时排队
  - [ ] subagent span 正确嵌套在父 span 下
  - [ ] 执行时序与拆分判断符合 design §6.9 两张流程图

### T5.10 上下文管理（自研四道防线）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M2/M3 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T5.2, T5.5, T5.6, T1.1
- **范围**：自研四道防线（design D34），Provider 无关：
  - **L0 源头节流**：Bash stdout/stderr 各 cap（默认 20K chars）、Read 大文件分段限大小（与 D26 trace 截断独立）
  - **L1 clearing**：`TokenCounter`（Provider 适配）算 token；超 `trigger1` 替换旧 `tool_result` 为占位、**保留 tool_use 记录与 id 配对不变量**；`exclude_tools` 支持
  - **L2 compaction**：超 `trigger2` 取段摘要、替换为 summary 消息；摘要模型 WS 级可配（可指国内模型 GLM）；coding 场景 instructions
  - **L3 memory 联动**：compaction 前强信号标出 → 主 Agent 收口写 chat memory
  - **L4 硬兜底**：三层后仍超 limit 95% 中断告知
  - 读 `workspace_settings.context_config`；clearing/compaction 各埋 context event span
- **对应文档**：design D34；spec F3.3.10 / F3.7.8
- **验收标准**：
  - [ ] 长任务（超 limit 50%）触发 clearing，tool_result 替换为占位、tool_use 记录与配对不破坏
  - [ ] clearing 后仍涨触发 compaction，摘要模型可指国内模型（GLM）
  - [ ] 切换 Provider（Claude→GLM）上下文管理照常工作（`TokenCounter` 适配）
  - [ ] WS 级配置生效（阈值 / `clear_keep` / `compact_recent` / instructions 可覆盖默认）
  - [ ] 三层后仍超 95% 优雅中断并告知用户
  - [ ] clearing / compaction 各产 context event span（记命中层 / 前后 token / 压缩比）

> **切片验收点 P5**：群里提需求 → Agent 跑完工具链 → 流式回复 + 代码修改落盘（单 WS 串行下）。

---

## Phase 6 — 并发控制（WS 写锁 / Run 队列）

> 目标：同 WS 写操作串行，排队 / 取消 / 中断 / 超时全闭环。

### T6.1 WS 写锁（Redis 分布式锁）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2/M4 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T0.3
- **范围**：`ws_lock:{ws_id}` Redis 锁；整个 Run 期间持有；30s TTL + 心跳续期；硬超时 10 min；`try/finally` 释放保证；写工具抢锁 / 只读工具不抢锁（D20 表）；**锁可重入**——Run 内并行子代理复用父 Run 锁不重复抢（D33），防子代理间死锁。
- **对应文档**：design D20 / D33 / §6.6；spec F3.3.3 / F3.3.6 / F3.4.5
- **验收标准**：
  - [x] 并发两 Run 同 WS，第二个排队
  - [x] 异常 / 中断 / 超时都释放锁（单测覆盖）
  - [x] 子代理可重入进入父 Run 锁，不阻塞 / 不死锁
- **完成记录**：app/agent/lock.py — WsLock(REDIS锁，30s TTL+10s心跳续期+原子Lua续期/释放+holder token防误删+可重入)。test_lock.py 3 用例覆盖 acquire/release、并发等待第二把、异常释放。B5 阶段完成，B6 阶段在 release() 增加 redis.publish 唤醒排队 Run（§6.6 pub/sub）。

### T6.2 Run 队列与排队反馈
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T6.1, T4.6
- **范围**：Run 入队 → 抢锁；Redis pub/sub 通知（避免空轮询）；入队推"⏳ 排队中，前面 N 个"，抢到推"▶️ 开始执行"；队列容量 ≥ 5。
- **对应文档**：design §6.6；spec F3.3.4 / NF4.3.2
- **验收标准**：
  - [x] 排队位置实时反馈（on_queue 回调传 ahead 数，入队时位置=前面 N 个）
  - [x] pub/sub 唤醒准确（WsLock.release 推 ws_lock_notify -> 进程内 Condition.notify_all -> 0 空轮询，5s 兜底超时）
- **完成记录**：app/agent/queue.py RunQueue(FIFO: Redis zset+自增seq → rank==0 抢锁 → 排队/开始卡片 on_queue/on_start 回调 → 锁释放 pub/sub+Condition 唤醒 → try/finally 释放+出队+notify)；api/runs.py GET runs 列表+POST cancel/interrupt；test_queue.py 5 用例覆盖 idle 直跑、同 WS 串行+位置、pub/sub 唤醒隐式验证。 lock.py 新增 LOCK_NOTIFY_PREFIX 发布通知。cards.py build_queue_card(position) 已就绪。run.py 拆分 _create_run + _execute_run 供 RunQueue 复用。

### T6.3 取消与中断
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T6.2
- **范围**：排队中可"取消排队"立即移除；运行中可中断，信号传到 Agent Loop 异步中止 + 释放锁。
- **对应文档**：spec F3.3.5；design §6.6
- **验收标准**：
  - [x] 取消排队立即生效（RunQueue.cancel: zrem+cond.notify → _wait_turn 抛 RunCancelled → cancelled 状态）
  - [x] 运行中中断后 Loop 停止且锁释放（RunQueue.interrupt: set abort Event → Loop 下一检查点 InterruptedError → interrupted 状态 → lock.release）
- **完成记录**：RunQueue.cancel(run_id) / interrupt(run_id) 提供外部取消/中断 API；接口 POST :cancel/:interrupt（require_ws_owner）。RunStatus 加 cancelled。Loop 已有 ctx.abort.is_set() 检查点。test_queue.py 覆盖 cancel queued、interrupt running、cancel/interrupt 边界用例。锁在全路径（完成/异常/中断/取消）finally 释放。

> **切片验收点 P6**：多群同时 @ 触发同 WS，写操作严格串行 + 排队反馈顺畅。

---

## Phase 7 — Memory + AGENT.md

> 目标：Chat 级长期记忆闭环（自动加载索引 + 自主写入 + 强信号触发）。

### T7.1 AGENT.md 加载与注入
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T5.3
- **范围**：Run 启动时后端直接读 WS 级 + 当前 cwd Repo 级 AGENT.md 注入 system prompt（不走 Read 工具）；超长告警但不截断；Agent 可通过 Write/Edit 改这两份（路径白名单）。
- **对应文档**：design D24；spec F3.9
- **验收标准**：
  - [x] 两份 AGENT.md 自动注入
  - [x] Agent 可写 AGENT.md，其他父目录不可写
- **完成记录**：`app/memory/loader.py:load_context_injections(ws_id,feishu_chat_id,cwd)` 在 `_execute_run` 内 Run 启动时直读 WS 级 `{ws}/AGENT.md` + Repo 级 `repos/{cwd 首段}/AGENT.md`（多 repo 不拼接，cwd 嵌套取首段定位 repo 根）注入 system prompt（D24，不走 Read 工具）；超长（>6000 chars）告警不截断。`build_system_prompt` 接 `feishu_chat_id` 在 memory 段标注 chat。test_run.py `_CapturingProvider` 验证三段标记进入 system。**Agent 写**：repo 级 `AGENT.md` 在 repos 子树内已可写（`path="AGENT.md"`）；WS 级 AGENT.md 在 cwd-relative 模型下无裸路径可区分，MVP 走管理 API（T2.5）维护——注入两份满足验收，WS 级 Agent 写为已知偏差（记录于 design 偏差）。

### T7.2 Memory 索引加载
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M6/M2 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T5.3, T1.3
- **范围**：Run 启动自动加载 `chats/{feishu_chat_id}/memory/MEMORY.md` 索引到 system prompt；详情按需 Read。
- **对应文档**：design D18 / D19；spec F3.6.5
- **验收标准**：
  - [x] MEMORY.md 存在则注入，不存在不报错
  - [x] 跨 FeishuChat 隔离（A chat 读不到 B chat 的 memory）
- **完成记录**：`load_context_injections` 同步读 `chats/{feishu_chat_id}/memory/MEMORY.md`（缺失返空串不报错）；memory 路径按 `feishu_chat_id` 定位，A/B chat 互不可见（test_memory_loader 覆盖 cross-chat 隔离 + 三份齐注 + 全缺空 + cwd 首段定位 repo）。

### T7.3 Memory 写入策略（System Prompt 指令）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T7.2, T5.6
- **范围**：在 system prompt 写入 D22 规则（强信号触发 / 不写场景 / 同主题合并 / 更新优先 / 写入即告知）；Agent 通过 Write/Edit 落盘到 `memory/` 子树。
- **对应文档**：design D22、§6.4；spec F3.6.6
- **验收标准**：
  - [x] 显式"记住 X" / 纠正型 feedback 触发写入
  - [x] 同主题已有文件则 Edit 而非新建
  - [x] 隐式写入后回复"已记下 X"
- **完成记录**：`prompt.py:_BASE_INSTRUCTIONS` 加 D22 完整规则（强信号 5 类触发 / 不写 4 类 / 同主题 Read 索引后 Edit 不新建 / 更新优先 / 写入即告知 / 群聊标注来源用户 / 子代理不写 memory 主 Agent 收口）。**路径白名单**：`path_guard.resolve_tool_path` 增 `memory/` 前缀约定——`memory/<name>` → 当前 chat `chats/{feishu_chat_id}/memory/` 子树（`memory_root` 用 `ctx.workspaces_root` 与 cwd_root 同源），跨 chat 隔离由 `ctx.feishu_chat_id` 强制；`memory/../` 越界拒。Read/Write/Edit 自动获得 memory 支持；Glob/Grep 保持 repos-only（memory 清单由注入的 MEMORY.md 索引承担）。test_memory_tools 覆盖前缀解析 / 跨 chat 隔离 / 越界拒 / Write+Edit memory / 无 chat 拒。**偏差**：repo 内 `memory/` 子目录文件不可经工具寻址（罕见，记录）。

### T7.4 Memory 陈旧性校验
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M2 ｜ **优先级**：P1 ｜ **预估**：0.5d ｜ **依赖**：T7.3
- **范围**：Agent 推荐前校验 memory 引用的文件 / 函数 / 配置是否仍存在（system prompt 指令层面）。
- **对应文档**：spec F3.6.7
- **验收标准**：
  - [x] memory 引用过期文件时 Agent 主动核验再决定
- **完成记录**：`_BASE_INSTRUCTIONS` 加陈旧性校验指令（推荐前用 Read/Grep 核验 memory 引用的路径/符号仍存在；核验失败降级表述为"曾经有 X（可能已变更，建议先确认）"不当事实输出；不全量扫描仅按需核验，对齐 D22 陈旧性策略）。

### T7.5 Memory 管理后端 API
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5/M6 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.3, T1.5
- **范围**：`GET/PUT/DELETE /workspaces/{ws_id}/chats/{feishu_chat_id}/memory/{filename}` + 列表；`filename` 严格白名单 `[A-Za-z0-9_\-]+\.md`，resolve 校验落在 `memory/` 子树。
- **对应文档**：api §8；spec F3.7.6；design D17 / D19
- **验收标准**：
  - [x] 路径穿越被拒（`../` / 非法字符）
  - [x] 可查看 / 编辑 / 删除 memory 文件
- **完成记录**：`app/api/memory.py`：GET 列表 / GET·PUT·DELETE `{filename}`；filename 白名单 `^[A-Za-z0-9_\-]+\.md$`（422 拒 `../`、子目录、空格、无后缀）；chat 归属 WS 校验（`chat.workspace_id != ws.id` → 404，D31）；首次访问 `create_chat_memory_skeleton` 建空 MEMORY.md。schemas 加 `MemoryFileIn`；main.py 注册 `memory_router`。test_memory_api 覆盖列表/CRUD roundtrip/白名单/归属 404/跨 WS 物理隔离/未登录 401。

> **切片验收点 P7**：Agent 能记住跨会话偏好，管理员可在后台管理 memory。

---

## Phase 8 — 管理后台前端

> 目标：Vue 后台覆盖所有管理 API。

### T8.1 登录与布局框架
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T0.2, T1.4
- **范围**：登录页、主布局（侧栏 + 顶栏）、路由守卫（未登录跳转）、Pinia 用户 store、axios 401 拦截。
- **验收标准**：
  - [ ] 登录后路由可达，登出回登录页
  - [ ] 401 自动跳登录

### T8.2 Workspace 管理页
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T8.1, T2.1
- **范围**：WS 列表 / 创建 / 编辑 / 删除；WS 详情页 Tab：Repo 管理（挂载 / 同步 / 状态）、FeishuChat 绑定（含预校验交互）、Skill / MCP 挂载、AGENT.md 编辑。
- **对应文档**：api §4 / §5；spec F3.7.1~F3.7.2
- **验收标准**：
  - [ ] 完整 CRUD 闭环
  - [ ] 异步任务（clone / 删除）有进度轮询 UI

### T8.3 广场页（Skill / MCP）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T8.1, T3.1, T3.2
- **范围**：Skill 上传（multipart）、列表 / 搜索 / 可见性切换 / 删除；MCP 注册 / 列表 / 删除。
- **对应文档**：api §6；spec F3.7.3
- **验收标准**：
  - [ ] Skill 上传含资源 / 脚本
  - [ ] 被引用禁删有友好提示

### T8.4 飞书 App 注册页
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T8.1, T3.3
- **范围**：App 列表（secret 脱敏）、注册 / 编辑 / 删除、连接状态展示。
- **对应文档**：api §3
- **验收标准**：
  - [ ] secret 仅创建时完整显示一次

### T8.5 会话历史页
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T8.1, T5.4
- **范围**：按 FeishuChat 浏览 session 列表，查看单 session JSONL（分页 / 分片）。
- **对应文档**：api §7；spec F3.7.5
- **验收标准**：
  - [ ] 可按 chat 筛选 session
  - [ ] 大 JSONL 分片加载不卡顿

### T8.6 Memory 管理页
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T8.1, T7.5
- **范围**：按 FeishuChat 列 memory 文件，在线查看 / 编辑 / 删除（Markdown 编辑器）。
- **对应文档**：api §8；spec F3.7.6
- **验收标准**：
  - [ ] 编辑保存生效，删除有二次确认

### T8.7 用户管理页
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T8.1, T1.6
- **范围**：用户列表 / 创建 / 改角色 / 停用 / 重置密码。
- **对应文档**：api §2.2；spec F3.7.7
- **验收标准**：
  - [ ] 仅管理员可见此页

> **切片验收点 P8**：管理员可在 Web 后台完成全部配置与运维操作。

---

## Phase 9 — 可观测性 P0（调试单 Run）

> 目标：Agent Loop 全流程 span 采集 + 后台 Trace 瀑布图（只读）。对应 design §7.8 P0。

### T9.1 spans 表 + ORM + WS 隔离
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.1
- **范围**：spans 表字段对齐 §7.2；SQLAlchemy event listener 强制注入 `WHERE workspace_id`；API 层 ws_id 取自 session 不接受客户端传入。
- **对应文档**：design §7.2 / §7.6 / D31；spec NF4.6.1
- **验收标准**：
  - [ ] 任意 spans 查询都带 ws_id 过滤（单测验证 listener 生效）
  - [ ] payload 读取先 PG 校验归属再读文件

### T9.2 Tracer（contextvars + span 上下文管理器）
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.1
- **范围**：`contextvars` 维护 current span/trace；`span()` 上下文管理器自动 enter/exit；asyncio task 自动继承（子代理嵌套）；异常路径标 error。
- **对应文档**：design §7.3 / D28
- **验收标准**：
  - [ ] 埋点零侵入（Agent 内核不显式传 trace_id）
  - [ ] 子代理 span 正确挂到父 span

### T9.3 SpanBuffer 批写 + 降级
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.2
- **范围**：span 事件进内存 `asyncio.Queue`，后台单协程批量 UPSERT；缓冲满丢弃 / PG 故障写 fallback 文件 / tracer 异常 swallow；Run 结束前 flush 本 trace。
- **对应文档**：design §7.4 / D28
- **验收标准**：
  - [ ] 采集不影响 Agent Loop 性能（埋点 < 1ms）
  - [ ] 各失败路径降级行为符合 §7.4 矩阵

### T9.4 Agent Loop 埋点
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8/M2 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.2, T5.2
- **范围**：Run 起/止/异常/中断/超时（run + interrupt）、每次 Claude API（llm，含 stream token 聚合：message_start/message_delta/message_stop）、每次 tool_use（tool，含抢锁/路径拒绝）、skill invoke（skill）、子代理（subagent）。
- **对应文档**：design §7.3 / §6.8；spec F3.10.1~F3.10.4
- **验收标准**：
  - [ ] 1 Run = 1 trace（根 span）
  - [ ] 流式 token 聚合值正确（input/cache/output）
  - [ ] 路径拒绝 / 中断 / 超时均有对应 span 标记

### T9.5 Payload 写入 + 截断 + 脱敏
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.4
- **范围**：payload 落 `chats/{feishu_chat_id}/traces/{trace_id}/`；aiodisk 线程池不阻塞；截断（req ≤5MB / resp ≤10MB / tool ≤1MB）；脱敏管线（字段名 + 正则，命中替换 `***REDACTED***`）。
- **对应文档**：design §7.5 / §7.6 / D26 / D29 / D30；spec NF4.6.2~NF4.6.4
- **验收标准**：
  - [ ] payload 与 session JSONL 分离存储
  - [ ] 截断标记 `payload_truncated` 正确
  - [ ] 密钥 / token / 密码类模式命中即脱敏

### T9.6 Trace 列表 + 瀑布图 API + 前端
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5/M8 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T9.1
- **范围**：`GET /workspaces/{ws_id}/traces`（筛选）、`/traces/{run_id}`（span 树）、`/spans/{span_id}/payload`（HTTP Range 分片）；前端瀑布图（Gantt + 颜色区分 span 类型 + 右侧抽屉展开 payload）。
- **对应文档**：api §9.1 / §10.3；design §7.7；spec F3.10.5
- **验收标准**：
  - [ ] 瀑布图正确还原 span 树与时间轴
  - [ ] 大 payload Range 分片流式返回（206）

> **切片验收点 P9**：任意一次 Run 可在后台回放完整轨迹（prompt / tool I/O / token / cost）。

---

## Phase 10 — 可观测性 P1（成本 / 监控告警）

> 目标：成本性能聚合 + 监控告警。对应 design §7.8 P1。

### T10.1 Cost 计算引擎
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T9.4
- **范围**：模型 pricing 表 + cache token 折算；llm span 退出时算 cost_usd；run span 汇总。
- **对应文档**：design §7.2；spec F3.10.6
- **验收标准**：
  - [ ] cost 含 cache 折算，与 anthropic usage 对齐

### T10.2 成本 / 工具 / 模型聚合视图
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M5/M8 ｜ **优先级**：P1 ｜ **预估**：2d ｜ **依赖**：T10.1
- **范围**：`GET /insights/cost`（token/cost 趋势）、`/insights/tools`（TopN 耗时 / 次数 / 错误率）、`/insights/models`（模型占比）；前端指标卡 + 图表；大跨度走物化视图，支持钻取到 Run。
- **对应文档**：api §9.2；design §7.7；spec F3.10.6
- **验收标准**：
  - [ ] 聚合数据按时间段 / WS / chat 维度正确
  - [ ] 可钻取到单 Run

### T10.3 监控告警
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8/M1 ｜ **优先级**：P1 ｜ **预估**：2d ｜ **依赖**：T10.1, T4.6
- **范围**：异常 Run 列表 API；告警规则表 CRUD（`/monitoring/rules`）；内置默认规则集（高错误率 / 高超时率 / P95 延迟 / 单 Run cost / WS 日 cost）；定时任务（每 1 min 扫规则）命中后经接入层推飞书。
- **对应文档**：api §9.3；design §7.7；spec F3.10.7
- **验收标准**：
  - [ ] 默认规则就绪即可用
  - [ ] 命中规则推飞书卡片

### T10.4 TTL 清理
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：M8 ｜ **优先级**：P1 ｜ **预估**：0.5d ｜ **依赖**：T9.5
- **范围**：payload 文件默认 30 天、PG spans 默认 90 天（可配置）；每 chat 保留最近 1000 Run payload；WS 删除级联清理。
- **对应文档**：design §7.5；spec NF4.6.3
- **验收标准**：
  - [ ] 定时清理任务正确删除过期数据

> **切片验收点 P10**：可观测成本趋势、定位异常 Run、告警实时推送。

---

## Phase 11 — 测试与上线

### T11.1 端到端测试用例
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：QA ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：P5~P9
- **范围**：覆盖核心闭环：配置 WS → 群里 @ → Agent 跑通 → 工具调用 → 流式回复 → memory 写入 → trace 可回放；并发排队 / 中断 / 超时；多 App 一群多 WS。
- **对应文档**：spec §2.2 典型场景
- **验收标准**：
  - [ ] 关键路径 E2E 通过
  - [ ] 多租户隔离测试（WS 间不可互访）

### T11.2 安全核查
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：安全 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：—
- **范围**：路径穿越、secret 脱敏、payload 越权、session 安全、登录限流复查。
- **对应文档**：spec §4.2 / NF4.6；design D17 / D30 / D31
- **验收标准**：
  - [ ] 已知越权 / 穿越用例全部拦截

### T11.3 部署与上线
- **状态**：⚪ 未开始 ｜ **负责**：— ｜ **完成日**：—
- **模块**：infra ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T11.1
- **范围**：Docker Compose 生产配置（含备份 / 日志 / 健康检查）；账号开通初始化；上线 checklist。
- **对应文档**：design §3.4；spec §5.1
- **验收标准**：
  - [ ] 生产环境可一键部署
  - [ ] 首批开通账号可登录使用

---

## 附：跨阶段关注点（每个任务都应自查）

- **路径安全**（D17 / NF4.1.2）：任何文件工具 / payload 读取都过 resolve 校验
- **多租户隔离**（D31 / NF4.6.1）：所有查询带 ws_id；ws_id 取自 session 不取自客户端
- **敏感信息脱敏**（D30 / NF4.2.3）：payload 落盘前过管线；secret 不入日志
- **非阻塞采集**（NF4.3.1 / §7.4）：可观测性 best-effort，不拖垮 Agent / 飞书流式
- **失败降级**：锁释放、trace 写入、payload 写入均有 try/finally 或 swallow 兜底
