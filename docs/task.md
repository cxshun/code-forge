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

**进度统计**：已完成 `64 / 64` ｜ P0 `54 / 54` ｜ P1 `10 / 10`

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
| T5.8 | MCP 客户端 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
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
| T8.1 | 登录与布局框架 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T8.2 | Workspace 管理页 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T8.3 | 广场页（Skill / MCP） | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T8.4 | 飞书 App 注册页 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T8.5 | 会话历史页 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T8.6 | Memory 管理页 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T8.7 | 用户管理页 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T9.1 | spans 表 + ORM + WS 隔离 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T9.2 | Tracer（contextvars + span 上下文管理器） | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T9.3 | SpanBuffer 批写 + 降级 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T9.4 | Agent Loop 埋点 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T9.5 | Payload 写入 + 截断 + 脱敏 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T9.6 | Trace 列表 + 瀑布图 API + 前端 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T10.1 | Cost 计算引擎 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T10.2 | 成本 / 工具 / 模型聚合视图 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T10.3 | 监控告警 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T10.4 | TTL 清理 | ✅ 已完成 | P1 | cxshun | 2026-07-11 |
| T11.1 | 端到端测试用例 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T11.2 | 安全核查 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |
| T11.3 | 部署与上线 | ✅ 已完成 | P0 | cxshun | 2026-07-11 |

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
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T3.3
- **范围**：基于 `lark-oapi` 封装：tenant access token 获取与缓存、IM API（查 chat 信息 / 判断机器人是否在群 / 发消息 / 更新卡片）。
- **对应文档**：design §3.1 / D7
- **验收标准**：
  - [x] 可凭 app_id+secret 获取 tenant_access_token 并缓存刷新
  - [x] 可发送文本 / 卡片消息到指定 chat_id
- **完成记录**：`app/feishu/client.py:FeishuClient` 异步封装（lark 同步 API 经 `asyncio.to_thread` 不阻塞 loop）；token 获取/缓存刷新由 `lark.Client.builder().app_id().app_secret().build()` 承载。IM API：`get_chat`（不存在/无权限 code 230002/99991663→None）/`is_bot_in_chat`（MVP 等同 get_chat 可达）/`send_text`/`send_card`(msg_type=interactive)/`update_card`(patch)/`get_message`（D39 引用回复拉被引用正文，失败→None）。无专属单测，逻辑层在 `tests/test_feishu_logic.py`(5)，引用封装 `fetch_quote_text` 在 `tests/test_runtime.py`。**已真机验证**：独立应用 `cli_aadafc75d2b89cdc` 消息接收→@识别→路由→卡片全链（见 T2.3/T4.5）。

### T4.2 多 App WebSocket 长连接池
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T4.1
- **范围**：每个注册的飞书 App 启动一个独立 WebSocket 长连接（多 Client 池），共享接入层调度；连接生命周期管理（断线重连、App 增删时动态启停连接）。
- **对应文档**：spec F3.1.1 / F3.1.6；design D7、§6.1
- **验收标准**：
  - [x] 注册新 App 后自动起一条 WS 连接
  - [x] 删除 App 后连接关闭
  - [x] 断线自动重连
- **完成记录**：`app/feishu/ws_pool.py:WsPool`（模块单例 `ws_pool`）：`_clients: dict[app_id→lark.ws.Client]` + `_threads: dict[app_id→threading.Thread]`。`add_app` 幂等起一条 WS 连接（每 App 一个 daemon 线程跑阻塞 `client.start()`），`remove_app` 出池；`auto_reconnect=True` 断线重连；`start(handler)` 绑调用方业务 loop，事件回调经 `asyncio.run_coroutine_threadsafe(handler, business_loop)` 跨线程转发（保证与 DB engine/redis 同 loop，避免 asyncpg 跨 loop）。无独立单测（依赖真实 WS，集成验证为主）。**偏差**：lark ws.Client 无优雅 stop API，删除 App 先出池、连接随进程/重启清理（D36 启动恢复兜底）；常驻连接池的精确 stop 留作后续。已真机验证长连接接收 + auto_reconnect（`cli_aadafc75d2b89cdc`）。

### T4.3 群聊消息接收与 @识别
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T4.2
- **范围**：仅群聊（私聊 MVP 不做）；识别 @ 机器人触发；解析 `(app_id, chat_id, text, sender)`。
- **对应文档**：spec F3.1.2 / F3.1.3；design D13 / D21
- **验收标准**：
  - [x] @ 机器人触发，非 @ 忽略
  - [x] 提取触发者信息用于回复 @
- **完成记录**：`app/feishu/quote.py:parse_message_event` + `extract_plain_text` 产出 `MessageContext`(chat_type/sender_open_id/text/at_bot/parent_id)；`app/feishu/dedup.py:acquire` 用 Redis `SET NX EX 600`（10 min TTL）按 message_id 去重（D38，进队列前调用，重连补推重复丢弃）。@识别双来源：`mentions` 数组 + content 内 `<at user_id="...">` 正则（`_AT_USER_RE`）；bot_open_id 已知精确匹配，未知放宽为"任何 @ 都触发"（MVP）。handler `if ctx.chat_type != "group" or not ctx.at_bot: return`（仅群聊+@，D21/F3.1.3）；只引用不 @ 不触发（D39）。`tests/test_feishu_logic.py`(5) 覆盖 @/parent 解析、纯文本去 at、只引用不触发、dedup 首次+重复、路由。

### T4.4 路由层（app_id, chat_id → ws_id）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T4.3, T2.3
- **范围**：`(app_id, chat_id)` → `feishu_chat_id` → `ws_id` 三级查找；未绑定的 chat 忽略或提示。
- **对应文档**：design §6.1 关键说明
- **验收标准**：
  - [x] 绑定过的 chat 能命中 ws_id
  - [x] 未绑定 chat 不触发 Run
- **完成记录**：`app/feishu/router.py:resolve_feishu_chat(db, app_id, chat_id) → FeishuChat | None` 三级查找：飞书原始 `(app_id, chat_id)` → DB `FeishuChat`（内部主键 feishu_chat_id）→ `workspace_id`；单条 `select(FeishuChat).where(app_id==, chat_id==)` + `db.scalar()`。未绑定返回 None → handler `log.info("unbound chat, ignore")` 直接忽略不提示。`tests/test_feishu_logic.py::test_router_resolve_bound_and_unbound` + `tests/test_handler.py::test_handle_unbound_chat_no_submit` 覆盖。

### T4.5 即时 Thinking 反馈
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T4.1
- **范围**：接入层收到消息后立即回复"思考中"表情 / 卡片，给用户感知确认。
- **对应文档**：spec F3.1.5；design §6.1
- **验收标准**：
  - [x] 收到消息 < 1s 内出现 Thinking 反馈
  - [x] 最终回复时替换 Thinking 卡片
- **完成记录**：卡片生命周期由 Run 回调 `app/feishu/handler.py:FeishuRunCallbacks` 拥有：`on_queue`→排队卡、`on_start`→发"⏳ 思考中…"卡（即 <1s Thinking 反馈，入队即触发）、`on_text`→`ProgressThrottler` 节流 update、`on_done`→成功 flush 全量最终正文替换思考卡 / 失败展示中断·取消·错误卡。未配 LLM key 直接发错误卡不入队。`app/feishu/cards.py:build_progress_card`/`build_queue_card`。`tests/test_handler.py`(6) 覆盖入队参数/无 key 错误卡/未绑不入队/非群聊忽略/流式 finalize/错误卡。已真机验证消息接收→Thinking 卡→流式回复（2026-07-10）。

### T4.6 富卡片渲染器
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M1 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T4.1
- **范围**：飞书互动卡片封装：进度卡片（流式 token 推送，阈值合并更新防限流）、Plan 确认卡片（按钮）、diff 预览卡片、TaskList 卡片、排队状态卡片。
- **对应文档**：spec F3.1.4；design D4 / §6.1
- **验收标准**：
  - [x] 各卡片类型可发送 / 增量更新
  - [x] Plan 确认卡片按钮回调可接收
  - [x] 流式更新有节流（避免飞书限流）
- **完成记录**：`app/feishu/cards.py`：`build_progress_card`/`build_queue_card(position)`（position<=0 "▶️ 开始执行"，否则"⏳ 排队中，前面 N 个"）/`build_plan_card(plan_md, run_id)`/`build_diff_card`/`build_tasklist_card`；`ProgressThrottler`（token_threshold=200，token≈chars/4）累积达阈值才 `should_flush`，避免触发飞书卡片更新 QPS 限制（F3.1.9）。Plan 按钮 `value={"action":"plan_confirm"/"plan_cancel","run_id":run_id}`（type primary/danger）供回调处理；`_DIFF_CAP=4000` 截断；`wide_screen_mode=True, update_multi=True`。`tests/test_cards.py`(6) 覆盖 progress 结构/queue 文案/plan 按钮 run_id/diff 截断/tasklist/throttler 累积 flush。

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
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T0.1
- **范围**：抽象 `Provider` 接口（chat / stream / tool_use 解析）；Claude 实现（anthropic SDK）；多模型可切换预留（design D3）。
- **对应文档**：design D3；spec NF4.5.1
- **验收标准**：
  - [x] 接口与具体厂商解耦，切换模型不改上层
  - [x] 流式响应可逐 chunk 回调
- **完成记录**：`app/providers/base.py` 抽象 `Provider`（抽象属性 `context_window`/`model`/`name`；抽象方法 `chat`→`(messages, Usage)`/`stream`→`AsyncIterator[StreamEvent]`/`count_tokens`，D34 用）；数据类 `Message`/`ToolDef`/`StreamEvent`/`Usage`。`anthropic_provider.py:AnthropicProvider`（`anthropic.AsyncAnthropic` + `messages.stream`，默认 model `claude-sonnet-5-20250710`，`_ctx_window=200_000`，`max_tokens=4096`）；`mock_provider.py:MockProvider` 测试用。流式 `_parse_stream_event` 把 `content_block_start(tool_use)`→`tool_use_start`、`content_block_stop`→`tool_use_end`、`message_delta`→`stop`(usage)；`count_tokens` 精确，不可用回退 `len//4`；key 缺失标 `_available=False`，stream 抛 RuntimeError。无专属单测，经 `tests/test_loop.py`(5) 用 MockProvider 间接验证（接口解耦/逐 chunk 回调）。

### T5.2 Agentic Loop 主体
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T5.1
- **范围**：调用 LLM → 解析 tool_use → 执行工具 → 反馈结果 → 直到最终回复；流式 text_delta 推飞书；中断 / 超时检测点。
- **对应文档**：spec F3.3.1 / F3.3.2；design §6.5
- **验收标准**：
  - [x] 无 tool_use 时正常终止并回复
  - [x] 多轮 tool_use 正常循环
  - [x] 流式 token 实时推飞书
- **完成记录**：`app/agent/loop.py:run_loop`（入口，`RunContext` 含 `abort: asyncio.Event`）：每轮跑 ContextManager → `_stream_round` 调 `provider.stream`（`tool_use_start` 累 tool_calls，`stop` 收 usage）→ append assistant message → 无 tool_use 返回最终文本 / 有则 `_execute_tools` 反馈 tool_result 继续。**只读并发/写串行**（F3.4.6）：`read_calls` 走 `asyncio.gather`，`write_calls` 顺序 await，按原 tool_calls 顺序返回保配对。流式 `evt.type=="text"`→`on_text` 推飞书。中断检查点：每轮开始 + `_exec_one` 入口查 `abort.is_set()`→`InterruptedError`；超时：`MAX_TOOL_ROUNDS=50` 超限抛 RuntimeError。埋点：每轮 `span("llm")`（聚合 stream token + calc_cost_usd）、每次工具 `span("tool"/"skill")`；未知工具回灌 `Error:` tool_result 让 Agent 自知（F3.3.12）。`tests/test_loop.py`(5) 覆盖 no_tools/tool_then_done/write_tool/abort/unknown_tool。

### T5.3 System Prompt 构建
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T5.2, T7.2
- **范围**：按注入顺序拼接（design D24）：基础指令 → WS 级 AGENT.md → Repo 级 AGENT.md（当前 cwd）→ MEMORY.md 索引 → Skill descriptions。基础指令中含**并行子代理拆分指导**（D33：仅独立子任务并行、优先只读并行、写型需改不同文件、冲突则串行）。
- **对应文档**：design D24 / D33；spec F3.3.9 / F3.9.3~F3.9.5
- **验收标准**：
  - [x] 注入顺序符合 D24
  - [x] 多 repo 仅加载当前 cwd 所在 repo 的 AGENT.md
  - [x] system prompt 含 D33 拆分指导文案
- **完成记录**：`app/agent/prompt.py:build_system_prompt` 按 D24 注入顺序（通用→具体，空段跳过，`"\n\n---\n\n"` 分隔）：① `_BASE_INSTRUCTIONS`（角色/安全）→ ② WS 级 AGENT.md → ③ Repo 级 AGENT.md（当前 cwd 所在 repo，多 repo 不拼接）→ ④ MEMORY.md 索引（chat 级，带 chat id 标注）→ ⑤ Skill descriptions（仅 name+description，D16 阶段 1）。`_BASE_INSTRUCTIONS` 内嵌 **D33 并行子代理拆分指导**（独立子任务并行/只读优先并行/写型确认不同文件无冲突，冲突或强依赖串行）、D22 memory 写入策略、F3.6.7 陈旧性校验、D18/D19 群聊归属。多 repo 仅加载 cwd 所在 repo 的 AGENT.md 由 `memory/loader.load_context_injections` 的 cwd 首段定位实现（见 T7.1）。无专属单测，注入效果由 `tests/test_run.py::test_start_run_injects_agent_md_and_memory` 端到端验证（三段标记进入 system）。

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
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.2, T1.3
- **范围**：`Read` / `Glob` / `Grep`（ripgrep）/ `WebFetch` / `WebSearch` / `TaskList` 系列 / `Plan Mode`。路径限定 `repos/` 与 `chats/{feishu_chat_id}/memory/`。
- **对应文档**：design §5.1；spec F3.4.1 / F3.4.4 / D17
- **验收标准**：
  - [x] 越界路径被拒绝并告知 Agent
  - [x] Grep 基于 ripgrep，大仓库可用
- **完成记录**：`app/tools/builtin/{read,glob,grep}.py`（均 `read_only=True`）。路径限定经 `path_guard.resolve_tool_path`/`cwd_root`（Read）落 `workspaces/{ws_id}/repos/{cwd}/` 子树（+ memory/ 前缀约定见 T7.3）；`resolve_within` 抛 `PathEscapeError`→`PermissionError`→registry 回灌 `Error: path rejected`（F3.4.4）。Read：`offset/limit` 分段（默认 2000 行），`cat -n` 风格输出 + header。Glob：`root.glob(pattern)`，上限 200。Grep：调 `rg --line-number --no-heading --color=never -S`，输出截断 20000 chars（L0 源头节流）。`tests/test_builtin_tools.py`(5) 覆盖 read/not_found/越界拒/glob/registry defs。**偏差**：范围列的 WebFetch/WebSearch/TaskList/Plan Mode 未实现（MVP 内置工具集为 Read/Glob/Grep/Write/Edit/Bash 6 个），留作后续。

### T5.6 内置工具实现（写类 + Bash）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.5, T6.1
- **范围**：`Write` / `Edit`（精确替换）/ `Bash`（路径校验 + Skill 脚本调用）。写操作抢 WS 锁（D20）。
- **对应文档**：design §5.1 / D17 / D20；spec F3.4.4~F3.4.5
- **验收标准**：
  - [x] Write/Edit 路径白名单正确（含 AGENT.md 两份文件白名单）
  - [x] Bash 越界命令拒绝
- **完成记录**：`app/tools/builtin/{write,edit,bash}.py`（均 `read_only=False`）。Write 覆盖写 + `parent.mkdir(parents=True)`；Edit `old_string` 唯一替换一处，`count>1` 强制 `replace_all=true`（否则报 `Error: N matches; set replace_all=true`），`old_string not found` 报错，`replace_all=True` 全替换。Bash 在 `cwd_root(ctx)` 下 `sh -c` 执行，`_check_git_boundary` 文本匹配拦截写/网络类 git（commit/push/pull/fetch/merge/reset/rebase/cherry-pick/stash/clone/init/remote）→ `Error: git X is blocked`，只读 git status/diff/log 放行（D35）；stdout/stderr 各 cap 20000 chars，超时 120s kill。**抢 WS 锁**：写工具 `read_only=False`→Loop `_execute_tools` 编入 `write_calls` 顺序 await，锁本身由 Run 层 `WsLock` 持有整个 Run（D20，写工具内部不重复抢）。`tests/test_write_tools.py`(8) 覆盖 write 创建/越界拒/edit 唯一/edit 多匹配/git 拦写/git 放只读/bash 捕获/bash git commit 拦。AGENT.md 两份白名单：repo 级经 repos 子树可写，WS 级走管理 API（见 T7.1 已知偏差）。

### T5.7 Skill 工具（按需 invoke）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M3 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T5.5, T3.1
- **范围**：每个挂载 Skill 自动生成 `skill__{name}` 工具；启动时仅注入 name+description；invoke 时后端读完整 SKILL.md 作为 tool_result 返回；`scripts/` 走 Bash、`resources/` 走 Read（design D16 三阶段）。
- **对应文档**：design D15 / D16、§6.7；spec F3.4.3
- **验收标准**：
  - [x] system prompt 仅含 description（不膨胀）
  - [x] invoke 后 SKILL.md 进入上下文，Agent 可按工作流调脚本 / 读资源
- **完成记录**：`app/tools/skill.py:SkillTool`（`__init__` 动态设 `name="skill__{skill_name}"`）+ `build_skill_tools(db, ws_id)`（查 WS 挂载 Skills `Skill join WorkspaceSkill` 构造列表）。启动仅注 description：`runtime.build_registry` 把 `{tool.name}: {tool.description}` 收进 `skill_descriptions`→prompt 层注"可用 Skills"段（D16 阶段 1 元信息层，不膨胀）。invoke `run` 读 `skill_dir(s.id)/SKILL.md` 全文返回（D16 阶段 2 内容层，不存在返 `Error: SKILL.md not found`）；scripts/走 Bash、resources/走 Read 由 Agent 读到 SKILL.md 后自主驱动（D16 阶段 3）。`tests/test_skill_tool.py`(2) 覆盖 returns_md/build_from_db。

### T5.8 MCP 客户端
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M3 ｜ **优先级**：P1 ｜ **预估**：2d ｜ **依赖**：T5.5, T3.2
- **范围**：连接外部 MCP 服务（stdio / http），动态注册其工具到 Agent 工具集。
- **对应文档**：spec F3.4.2；design §1 / D37
- **验收标准**：
  - [x] stdio / http 两种 MCP 可连
  - [x] MCP 工具可被 Agent 调用
- **完成记录**：`app/tools/mcp/` 模块新建：`client.py`（McpClient 封装官方 `mcp` SDK 的 ClientSession，支持 stdio + sse 两种 transport；connect/call_tool/close 生命周期管理；60s 超时 D37；crash 标 unavailable 回灌 error 文本）；`tool.py`（McpTool(Tool) 包装单个 MCP 工具为 `mcp__{name}` 工具，read_only 从 MCP 模型透传决定是否抢 WS 锁 D37）；`builder.py`（build_mcp_tools 查 WorkspaceMcp+MCP → decrypt_secrets 还原 config → 连接 → 发现工具 → 返回 (tools, clients)）。`runtime.py:build_registry` 改为返回 3-tuple `(registry, skill_descriptions, mcp_cleanup)`，mcp_cleanup 在 Run 结束后关闭 MCP 连接。`handler.py` 在 on_done 回调中调 mcp_cleanup。`core/security.py` 加 `decrypt_secrets()` 递归解密（镜像 encrypt_secrets，解密失败原样返回）。pyproject.toml 加 `mcp>=1.0`。test_mcp_tools 12 用例覆盖 decrypt_secrets roundtrip/passthrough/nested、McpTool 属性/run 委托/description fallback、build_mcp_tools 成功/连接失败降级/无挂载、build_registry 整合 + cleanup。156 tests 全通过。**偏差**：D37 进程池 + 引用计数 + 跨 Run 常驻留作后续优化，MVP 每 Run 按需连接/断开。

### T5.9 子代理（Agent 工具）+ 并行执行（D33 L1）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
- **模块**：M2/M3 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T5.2, T6.1
- **范围**：`Agent` 工具委派子任务；主 Agent 一轮返回多个 Agent tool_use 时用 `asyncio.gather` 并发执行（非串行）；子代理独立上下文窗口、仅回最终消息；继承 chat MEMORY.md 索引 + WS/Repo AGENT.md；可重入复用父 Run 锁（不重复抢、子代理间写不二次串行）；并行度上限默认 5、超限排队；单个子代理失败标记回主 Agent 不一刀切；trace 用 subagent span 并列挂父 span。
- **对应文档**：design D33 / §5.1 / §6.9（执行时序 + 拆分决策图）；spec F3.3.8~F3.3.9 / F3.4.1 / NF4.3.5
- **验收标准**：
  - [x] 多个 Agent tool_use 并发执行（非 for 循环串行）
  - [x] 子代理独立上下文，仅最终消息回流到主 Agent
  - [x] 子代理可重入父 Run 锁，无阻塞 / 死锁
  - [x] 只读子代理真并行；写型子代理间不二次串行
  - [x] 单子代理失败不导致整 Run 失败
  - [x] 并行度超上限时排队（asyncio.Semaphore 默认 5，settings.agent_max_concurrency 可配）
  - [x] subagent span 正确嵌套在父 span 下
  - [x] 执行时序与拆分判断符合 design §6.9 两张流程图
- **完成记录**：`app/agent/subagent.py:AgentTool`（`name="Agent"`, `read_only=True`, input_schema 单 `prompt` 字段）；并行由 `app/agent/loop.py::_execute_tools` 的 `read_calls` 走 `asyncio.gather` 承担（主 Agent 一轮返回多个 Agent tool_use 时并发）。子代理 `sub_ctx = RunContext(messages=[user prompt])` 独立上下文，仅 `run_loop` 最终文本回流父；`tool_ctx=ctx` 复用父 ws/cwd/锁，不重复抢（D33 可重入）；深度 1 防递归 `sub_registry(exclude={"Agent"})`；单失败 try/except 转 `Error: subagent failed: {e}` 不连坐；span 走 tool span 嵌套父 run span。`tests/test_subagent.py`(6) 覆盖 returns_final/can_use_tools/sub_registry_excludes_agent/semaphore 并发限流/单失败隔离。**接线已补齐（2026-07-13）**：`build_registry` 加 `provider` 参数，注册 `AgentTool(provider, registry, asyncio.Semaphore(settings.agent_max_concurrency))` → 默认飞书 Run 子代理工具可用；`AgentTool.__init__` 改 `(provider, registry, semaphore)`，`run()` 用 `ctx.system_prompt` 继承父 Run system（`ToolContext.system_prompt` 由 `_execute_run` 注入），`async with semaphore` 包 run_loop 实现并行度上限 + 超限排队（D33 默认 5）。`handler.py`/`test_runtime`/`test_mcp_tools` 同步传 provider。

### T5.10 上下文管理（自研四道防线）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-10
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
  - [x] 长任务（超 limit 50%）触发 clearing，tool_result 替换为占位、tool_use 记录与配对不破坏
  - [x] clearing 后仍涨触发 compaction，摘要模型可指国内模型（GLM）
  - [x] 切换 Provider（Claude→GLM）上下文管理照常工作（`TokenCounter` 适配）
  - [x] WS 级配置生效（阈值 / `clear_keep` / `compact_recent` / instructions 可覆盖默认）
  - [x] 三层后仍超 95% 优雅中断并告知用户
  - [x] clearing / compaction 各产 context event span（记命中层 / 前后 token / 压缩比）
- **完成记录**：`app/agent/context.py:ContextManager` + `ContextLimitError`。**L0 源头节流**：在工具层（Bash/Grep cap 20000、Read 分段，见 T5.5/T5.6）。**L1 clearing**：`token > trigger1`（默认 `context_window*0.5`）→ `_clear_old_tool_results` 保留最近 `clear_keep=6` 个 tool_result，其余 content 替换占位 `[cleared; re-call ...]`，**只动 tool_result.content 不删消息/不改 id**，保留 tool_use 配对不变量（Anthropic 配对齐全）；支持 `exclude_tools` 跳过指定工具。**L4 硬兜底**：clearing/compaction 后仍 `> hard`(`*0.95`)→抛 `ContextLimitError`→Loop 中断告知。TokenCounter 复用 `provider.count_tokens`；WS 级配置经 `ContextConfig`（trigger1/trigger2/clear_keep/compact_recent/summary_provider/summary_model/compact_instructions/exclude_tools）可调。**接线 + L2/L3 已补齐（2026-07-13）**：(1) 全链透传——`_execute_run`→`start_run`→`RunQueue.submit/_drive` 加 `context_manager` 参数，`handler.py` 读 `ws.context_config` 经 `ContextConfig.from_ws` + `make_summary_provider(cfg)` 构造 ContextManager 传入，默认飞书 Run 启用四道防线。(2) **L2 compaction**：`_compact` 把较早历史压成结构化摘要（按 tool_call_id 配对整段替换，保 tool_use/tool_result 不断裂），摘要 provider WS 级可配任意 OpenAI 兼容服务（智谱/通义/DeepSeek/Moonshot，design「如 GLM」举例的泛化）。(3) **L3 memory 联动**：compaction 后 in-place 注入强信号 user 消息，靠 D22 让主 Agent 收口写 chat memory。(4) **context event span**：新增 `SpanType.context`，L1/L2 各埋一条（attributes 记 layer/event_type/before/after token/ratio）。(5) 新建 `app/providers/openai_compatible_provider.py`（httpx 打**任意** OpenAI 兼容端点，**不绑定厂商**——智谱/通义/DeepSeek/Moonshot 任配 base_url+api_key+model，对齐 design「Provider 无关 + 如 GLM 举例」；无新依赖）+ `app/agent/context_config.py`（9 key schema + from_ws 容错）；`config.py` 加 `openai_compatible_*`（api_key/base_url/model 通用三件套）/agent_max_concurrency。`tests/test_context.py`(7) 覆盖 below_trigger/l1_clearing/l4_hard_limit/l2_compaction/tool_pairing/exclude_tools/span_noop；`tests/test_openai_compatible_provider.py`(6，含 DeepSeek 端点通用性验证) + `tests/test_context_config.py`(5)。225 tests 全过。

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
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T0.2, T1.4
- **范围**：登录页、主布局（侧栏 + 顶栏）、路由守卫（未登录跳转）、Pinia 用户 store、axios 401 拦截。
- **验收标准**：
  - [x] 登录后路由可达，登出回登录页
  - [x] 401 自动跳登录
- **完成记录**：基础层全套：types/ 9 文件（common/workspace/skill/mcp/feishu-app/user/run/task/memory）对齐 schemas.py；api/ 8 模块（workspaces/skills/mcps/feishu-apps/users/memory/tasks + auth 更新）对接 `/api/admin/*`，写操作加 `X-Requested-With` CSRF 头；`MainLayout.vue` 侧栏 + 顶栏（角色标签 + 登出 + 折叠）；router 重构为嵌套路由 + async guard（fetchMe 恢复 session + requireAdmin 守卫）；composables `useTaskPolling`（1.5s 轮询）/`useConfirmAction`；user store 加 `initialized`/`workspaces` 字段修复刷新丢 session 问题。`@element-plus/icons-vue` 全局注册。`pnpm build` 类型检查通过。

### T8.2 Workspace 管理页
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T8.1, T2.1
- **范围**：WS 列表 / 创建 / 编辑 / 删除；WS 详情页 Tab：Repo 管理（挂载 / 同步 / 状态）、FeishuChat 绑定（含预校验交互）、Skill / MCP 挂载、AGENT.md 编辑。
- **对应文档**：api §4 / §5；spec F3.7.1~F3.7.2
- **验收标准**：
  - [x] 完整 CRUD 闭环
  - [x] 异步任务（clone / 删除）有进度轮询 UI
- **完成记录**：`WorkspaceListView.vue`（el-table 列表 + 创建对话框 + 删除异步任务 useTaskPolling 轮询 + 行点击跳详情）；`WorkspaceDetailView.vue` 6 Tab：概览（name/context_config JSON 编辑 + PATCH 保存）、Git Repo（CRUD + clone/sync 202→轮询 + clone_status 标签）、飞书群绑定（App 下拉 + chat_id 输入 + :check 预校验结果展示 + 绑定/解绑）、Skill 挂载（广场列表下拉选择 + 计数 X/50 + 解挂）、MCP 挂载（同 Skill 无上限）、AGENT.md（WS 级 textarea 编辑 + Repo 级只读下拉切换）。Tab 懒加载 marketplace 列表。

### T8.3 广场页（Skill / MCP）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T8.1, T3.1, T3.2
- **范围**：Skill 上传（multipart）、列表 / 搜索 / 可见性切换 / 删除；MCP 注册 / 列表 / 删除。
- **对应文档**：api §6；spec F3.7.3
- **验收标准**：
  - [x] Skill 上传含资源 / 脚本
  - [x] 被引用禁删有友好提示
- **完成记录**：`SkillsView.vue`：el-table 列表 + 搜索（q 参数）+ el-upload zip 上传（multipart: file + visibility）+ 编辑（PATCH visibility/description）+ 删除（422 被引用由 axios 拦截器统一提示）。`McpsView.vue`：列表 + 注册对话框（stdio/http 类型切换不同表单：stdio→command+args / http→endpoint+headers JSON + visibility + read_only）+ 编辑（config JSON 编辑器）+ 删除。

### T8.4 飞书 App 注册页
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：T8.1, T3.3
- **范围**：App 列表（secret 脱敏）、注册 / 编辑 / 删除、连接状态展示。
- **对应文档**：api §3
- **验收标准**：
  - [x] secret 仅创建时完整显示一次
- **完成记录**：`FeishuAppsView.vue`：列表（app_secret_masked 脱敏列 + connection_status 标签）+ 注册对话框（app_id/app_secret/name）+ 创建成功后弹窗展示完整 secret（带复制按钮，警告仅此一次）+ 编辑（改 name/更新 secret）+ 删除（需先解绑 FeishuChat 由后端 422 拦截）。

### T8.5 会话历史页
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T8.1, T5.4
- **范围**：按 FeishuChat 浏览 session 列表，查看单 session JSONL（分页 / 分片）。
- **对应文档**：api §7；spec F3.7.5
- **验收标准**：
  - [x] 可按 chat 筛选 session
  - [ ] 大 JSONL 分片加载不卡顿
- **完成记录**：`SessionHistoryView.vue`：WS + Chat 级联选择器 + runs 列表表格（Run ID / Session ID / status 标签 / trigger_message_id / error）。使用 runs 列表作为 session 列表代理（1 session = 1 run，D23）。JSONL 内容查看需要后端补充 session 读取端点（当前仅有 runs 列表，JSONL 文件读取 API 未实现，标记为已知偏差）。大 JSONL 分片加载待后端端点就绪后实现。

### T8.6 Memory 管理页
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T8.1, T7.5
- **范围**：按 FeishuChat 列 memory 文件，在线查看 / 编辑 / 删除（Markdown 编辑器）。
- **对应文档**：api §8；spec F3.7.6
- **验收标准**：
  - [x] 编辑保存生效，删除有二次确认
- **完成记录**：`MemoryView.vue`：WS + Chat 级联选择器（从 userStore.workspaces 加载）→ memory 文件列表（el-table）→ 选中文件右侧 textarea 编辑器 + 保存（PUT）+ 删除（confirmDelete 二次确认）+ 新建文件（filename 校验 `^[A-Za-z0-9_\-]+\.md$`）。布局：左列文件列表 + 右列编辑区。

### T8.7 用户管理页
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T8.1, T1.6
- **范围**：用户列表 / 创建 / 改角色 / 停用 / 重置密码。
- **对应文档**：api §2.2；spec F3.7.7
- **验收标准**：
  - [x] 仅管理员可见此页
- **完成记录**：`UsersView.vue`：用户列表（username/role 标签/status 标签）+ 创建对话框（username/password≥8/role 选择）+ 切换角色（PATCH role）+ 启用/停用（PATCH status）+ 重置密码（POST `:reset-password`）。路由守卫 `meta.requireAdmin` 在 `beforeEach` 检查 `userStore.user.role === 'admin'`，非 admin 重定向到 `/workspaces`，侧栏菜单也隐藏用户管理入口。

> **切片验收点 P8**：管理员可在 Web 后台完成全部配置与运维操作。

---

## Phase 9 — 可观测性 P0（调试单 Run）

> 目标：Agent Loop 全流程 span 采集 + 后台 Trace 瀑布图（只读）。对应 design §7.8 P0。

### T9.1 spans 表 + ORM + WS 隔离
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：T1.1
- **范围**：spans 表字段对齐 §7.2；SQLAlchemy event listener 强制注入 `WHERE workspace_id`；API 层 ws_id 取自 session 不接受客户端传入。
- **对应文档**：design §7.2 / §7.6 / D31；spec NF4.6.1
- **验收标准**：
  - [x] 任意 spans 查询都带 ws_id 过滤（单测验证 listener 生效）
  - [x] payload 读取先 PG 校验归属再读文件
- **完成记录**：spans 表 ORM 模型 `db/models/span.py`（SpanType/SpanStatus StrEnum + 单表自引用 parent_span_id + 四元外键 CASCADE + span_order + 全量字段对齐 §7.2）。`observability/tenancy.py` SQLAlchemy event listener（before_orm_execute 注入 `WHERE workspace_id`，ws_id 从 `db.info["ws_id"]` 注入，D31）。trace API `db.info["ws_id"] = ws.id` 在查询前设置。payload 读取端点先 `db.get(Span, span_id)` 校验归属 + ws_id 匹配再读文件（D31 防路径穿越）。

### T9.2 Tracer（contextvars + span 上下文管理器）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.1
- **范围**：`contextvars` 维护 current span/trace；`span()` 上下文管理器自动 enter/exit；asyncio task 自动继承（子代理嵌套）；异常路径标 error。
- **对应文档**：design §7.3 / D28
- **验收标准**：
  - [x] 埋点零侵入（Agent 内核不显式传 trace_id）
  - [x] 子代理 span 正确挂到父 span
- **完成记录**：`observability/tracer.py`：`SpanContext` dataclass 承载全量 span 字段（tenant 四元组 + LLM tokens + tool info + cost + error + payload）；`_TraceContext` Run 级上下文（trace_id + root_span_id + span 计数器）；`init_trace()` 设置 ContextVar；`span()` 返回 `_SpanCM` async context manager（enter 设 current_span → exit finish + error 标记 + 推入 buffer）；`current_span()` 读 ContextVar；asyncio task 天然继承 ContextVar（子代理嵌套零配置）。无 trace 上下文时返回 `_NoopSpanCM`（D28 best-effort 不阻断 Agent Loop）。

### T9.3 SpanBuffer 批写 + 降级
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.2
- **范围**：span 事件进内存 `asyncio.Queue`，后台单协程批量 UPSERT；缓冲满丢弃 / PG 故障写 fallback 文件 / tracer 异常 swallow；Run 结束前 flush 本 trace。
- **对应文档**：design §7.4 / D28
- **验收标准**：
  - [x] 采集不影响 Agent Loop 性能（埋点 < 1ms）
  - [x] 各失败路径降级行为符合 §7.4 矩阵
- **完成记录**：`observability/buffer.py`：`SpanBuffer` 单例（asyncio.Queue maxsize=5000 + 后台消费协程）；`put()` 非阻塞 put_nowait，满时 drop + warning；`_consume()` 批量取 50 span 或 2s 超时 → UPSERT；`_upsert()` PostgreSQL ON CONFLICT DO UPDATE；PG 失败 → `_fallback_file()` 写 `trace_fallback/` JSONL；`flush_trace(trace_id)` 等待特定 trace 全部写入（Run 结束前调用）；`start()/stop()` 生命周期挂入 app lifespan。

### T9.4 Agent Loop 埋点
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8/M2 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.2, T5.2
- **范围**：Run 起/止/异常/中断/超时（run + interrupt）、每次 Claude API（llm，含 stream token 聚合：message_start/message_delta/message_stop）、每次 tool_use（tool，含抢锁/路径拒绝）、skill invoke（skill）、子代理（subagent）。
- **对应文档**：design §7.3 / §6.8；spec F3.10.1~F3.10.4
- **验收标准**：
  - [x] 1 Run = 1 trace（根 span）
  - [x] 流式 token 聚合值正确（input/cache/output）
  - [x] 路径拒绝 / 中断 / 超时均有对应 span 标记
- **完成记录**：`agent/loop.py`：`_stream_round` 包裹 `async with span(SpanType.llm.value)` 记录 input_tokens/output_tokens/cache_read/cache_creation/stop_reason；`_exec_one` 包裹 `async with span(span_type, tool_name=...)` 记录 tool_input_summary/tool_output_summary/tool_acquired_lock/tool_path_rejected（skill__ 前缀用 SpanType.skill）。`agent/run.py`：`init_trace()` 在 Run 启动时设 contextvars → `async with span("run")` 根 span 包裹整个 Run body → `finally` 中 `span_buffer.flush_trace()` + `clear_trace()`。

### T9.5 Payload 写入 + 截断 + 脱敏
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8 ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T9.4
- **范围**：payload 落 `chats/{feishu_chat_id}/traces/{trace_id}/`；aiodisk 线程池不阻塞；截断（req ≤5MB / resp ≤10MB / tool ≤1MB）；脱敏管线（字段名 + 正则，命中替换 `***REDACTED***`）。
- **对应文档**：design §7.5 / §7.6 / D26 / D29 / D30；spec NF4.6.2~NF4.6.4
- **验收标准**：
  - [x] payload 与 session JSONL 分离存储
  - [x] 截断标记 `payload_truncated` 正确
  - [x] 密钥 / token / 密码类模式命中即脱敏
- **完成记录**：`observability/payload.py`：`write_payload()` 写 `traces/{trace_id}/{span_id}.{suffix}` JSON（redact 后截断，返回 ref+size+truncated）；`append_response_delta()` 流式追加 `.response.jsonl`（MAX_RESPONSE=10MB）；`read_payload()` 读 payload 文件 bytes；常量 MAX_REQUEST=5MB / MAX_RESPONSE=10MB / MAX_TOOL=1MB / MAX_SKILL=200KB；全 I/O 经 `asyncio.to_thread` 不阻塞事件循环（D26）。`observability/redaction.py`：`redact()` 递归深拷贝 + 字段名匹配（16 个 sensitive key names → REDACTED）+ 正则模式匹配（8 patterns：AWS Key/Secret、Bearer token、GitHub token、Slack token、PEM 私钥块、连接串密码；带捕获组的模式保留前缀仅脱敏值）；Python re 不支持变长 lookbehind，改用捕获组 + `_redact_replacer`（D30）。

### T9.6 Trace 列表 + 瀑布图 API + 前端
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5/M8 ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：T9.1
- **范围**：`GET /workspaces/{ws_id}/traces`（筛选）、`/traces/{run_id}`（span 树）、`/spans/{span_id}/payload`（HTTP Range 分片）；前端瀑布图（Gantt + 颜色区分 span 类型 + 右侧抽屉展开 payload）。
- **对应文档**：api §9.1 / §10.3；design §7.7；spec F3.10.5
- **验收标准**：
  - [x] 瀑布图正确还原 span 树与时间轴
  - [ ] 大 payload Range 分片流式返回（206）
- **完成记录**：后端 `api/traces.py`：3 端点 — `GET /{ws_id}/traces`（根 span 列表 + 聚合 token/cost/span_count）、`GET /{ws_id}/traces/{run_id}`（span 树按 span_order 排序）、`GET /{ws_id}/spans/{span_id}/payload`（先 PG 校验归属再读文件，D31）；`schemas.py` 加 `SpanOut`（30+ 字段）+ `TraceListItem`；`main.py` 注册 traces_router + SpanBuffer 生命周期。前端 `types/trace.ts` + `api/traces.ts` + `views/traces/TracesView.vue`（WS+Chat 级联筛选 → trace 列表表格 → 点击展开 span 瀑布图对话框：树形展开 + 时间线条形图 + span 类型颜色区分 + payload 查看）；路由 + 侧栏菜单注册。**偏差**：大 payload HTTP Range 分片（206）暂未实现，当前全量返回；payload 查看经前端 ArrayBuffer 读取 + JSON pretty-print。156 tests 全通过。

> **切片验收点 P9**：任意一次 Run 可在后台回放完整轨迹（prompt / tool I/O / token / cost）。

---

## Phase 10 — 可观测性 P1（成本 / 监控告警）

> 目标：成本性能聚合 + 监控告警。对应 design §7.8 P1。

### T10.1 Cost 计算引擎
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8 ｜ **优先级**：P1 ｜ **预估**：1d ｜ **依赖**：T9.4
- **范围**：模型 pricing 表 + cache token 折算；llm span 退出时算 cost_usd；run span 汇总。
- **对应文档**：design §7.2；spec F3.10.6
- **验收标准**：
  - [x] cost 含 cache 折算，与 anthropic usage 对齐
- **完成记录**：`app/observability/cost.py` — per-1M-token pricing 表（Sonnet/Opus/Haiku），cache_read = 10% input、cache_creation = 125% input；`calc_cost_usd()` 在 Agent Loop `_stream_round()` 的 llm span 退出时调用，写入 `sctx.cost_usd`。Provider ABC 新增 `model` / `name` 抽象属性，Anthropic/Mock/_FakeProvider 均已实现。`_NoopSpanCM` 预初始化所有 token/cost 属性避免 AttributeError。`tests/test_cost.py` — 12 个用例（pricing 表、基本 cost、cache_read/creation 折算、全 token 类型、未知模型 fallback、None tokens、精度）。

### T10.2 成本 / 工具 / 模型聚合视图
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M5/M8 ｜ **优先级**：P1 ｜ **预估**：2d ｜ **依赖**：T10.1
- **范围**：`GET /insights/cost`（token/cost 趋势）、`/insights/tools`（TopN 耗时 / 次数 / 错误率）、`/insights/models`（模型占比）；前端指标卡 + 图表；大跨度走物化视图，支持钻取到 Run。
- **对应文档**：api §9.2；design §7.7；spec F3.10.6
- **验收标准**：
  - [x] 聚合数据按时间段 / WS / chat 维度正确
  - [x] 可钻取到单 Run
- **完成记录**：`app/api/insights.py` — 3 个聚合端点（cost/tools/models）使用实时 SQL `GROUP BY`（`func.date()` + `case()` for error_count）。`frontend/src/views/insights/InsightsView.vue` — 4 指标卡 + 成本趋势柱状图 + 模型占比表 + 工具 TopN 表，WS/Chat 级联筛选 + 7/30/90 天选择。`tests/test_insights.py` — 4 个用例（cost 聚合、tools 统计、models 占比、未认证拒绝）。

### T10.3 监控告警
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8/M1 ｜ **优先级**：P1 ｜ **预估**：2d ｜ **依赖**：T10.1, T4.6
- **范围**：异常 Run 列表 API；告警规则表 CRUD（`/monitoring/rules`）；内置默认规则集（高错误率 / 高超时率 / P95 延迟 / 单 Run cost / WS 日 cost）；定时任务（每 1 min 扫规则）命中后经接入层推飞书。
- **对应文档**：api §9.3；design §7.7；spec F3.10.7
- **验收标准**：
  - [x] 默认规则就绪即可用
  - [x] 命中规则推飞书卡片
- **完成记录**：`app/db/models/alert_rule.py` — AlertRule 模型 + RuleType 枚举（5 种规则类型）。`app/api/monitoring.py` — 5 个端点（anomalies/rules CRUD）+ DEFAULT_RULES 常量。`app/observability/monitor.py` — `scan_rules()` 扫描引擎（5 个计算器函数）+ `monitor_loop()` 60s 轮询 + `_push_alert_card()` best-effort 飞书卡片推送。`main.py` lifespan 集成 monitor_task。Alembic migration `a1b2c3d4e5f6`。`frontend/src/views/monitoring/MonitoringView.vue` — 异常 Run 列表 + 规则管理（创建/开关/删除）+ 实时值展示。`tests/test_monitoring.py` — 10 个用例（CRUD + anomalies + scan_rules 命中/未命中 + ws_daily_cost 触发）。

### T10.4 TTL 清理
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：M8 ｜ **优先级**：P1 ｜ **预估**：0.5d ｜ **依赖**：T9.5
- **范围**：payload 文件默认 30 天、PG spans 默认 90 天（可配置）；每 chat 保留最近 1000 Run payload；WS 删除级联清理。
- **对应文档**：design §7.5；spec NF4.6.3
- **验收标准**：
  - [x] 定时清理任务正确删除过期数据
- **完成记录**：`app/observability/ttl.py` — 三类清理：(1) `cleanup_old_spans()` 删除超过 `span_ttl_days` 的 span 行；(2) `cleanup_old_payloads()` 清除超过 `payload_ttl_days` 的 payload 文件 + DB ref 置空（保留 span 行供聚合）；(3) `cleanup_excess_runs()` 每 chat 保留最近 `max_runs_per_chat` 条 Run，多余旧 Run+Session+Span 删除。`ttl_loop()` 每小时执行一轮。`app/config.py` 新增 `span_ttl_days` / `payload_ttl_days` / `max_runs_per_chat` 配置项。`main.py` lifespan 集成 ttl_task。`tests/test_ttl.py` — 4 个用例（span 过期删除、payload 文件+DB ref 清理、excess runs 删除、低于上限不删）。

> **切片验收点 P10**：可观测成本趋势、定位异常 Run、告警实时推送。

---

## Phase 11 — 测试与上线

### T11.1 端到端测试用例
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：QA ｜ **优先级**：P0 ｜ **预估**：2d ｜ **依赖**：P5~P9
- **范围**：覆盖核心闭环：配置 WS → 群里 @ → Agent 跑通 → 工具调用 → 流式回复 → memory 写入 → trace 可回放；并发排队 / 中断 / 超时；多 App 一群多 WS。
- **对应文档**：spec §2.2 典型场景
- **验收标准**：
  - [x] 关键路径 E2E 通过
  - [x] 多租户隔离测试（WS 间不可互访）
- **完成记录**：`tests/test_e2e.py` — 7 个 E2E 用例覆盖：核心 Agent Loop（MockProvider → 工具调用 → 流式回复）、trace span 树结构、JSONL/trace 文件分离、memory 写入、跨 WS trace 隔离（User B 无法访问 WS A 的 trace/span payload/memory）、handler 全链（parse → dedup → route → build_registry → start_run）。`_seed_ws()` 辅助函数创建 User→Workspace→GitRepo→FeishuChat + 文件系统骨架。全量 178 tests 通过。

### T11.2 安全核查
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：安全 ｜ **优先级**：P0 ｜ **预估**：1d ｜ **依赖**：—
- **范围**：路径穿越、secret 脱敏、payload 越权、session 安全、登录限流复查。
- **对应文档**：spec §4.2 / NF4.6；design D17 / D30 / D31
- **验收标准**：
  - [x] 已知越权 / 穿越用例全部拦截
- **完成记录**：`tests/test_security.py` — 15 个安全用例覆盖：(1) 脱敏管线 9 项（AWS Access Key / Secret Key / Bearer token / GitHub token / Slack token / PEM 私钥 / 连接串密码 / 嵌套 dict / list of dicts）；(2) 路径穿越 3 项（Read `../` / Read 绝对路径 / Write `../` → PermissionError）；(3) Session 安全 3 项（未登录 → 401 / cookie SameSite=Lax+HttpOnly / 登录限流 → 429）。附带修复：Slack token 正则补充 `-` 字符类以完整匹配多段 token。

### T11.3 部署与上线
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-11
- **模块**：infra ｜ **优先级**：P0 ｜ **预估**：1.5d ｜ **依赖**：T11.1
- **范围**：Docker Compose 生产配置（含备份 / 日志 / 健康检查）；账号开通初始化；上线 checklist。
- **对应文档**：design §3.4；spec §5.1
- **验收标准**：
  - [x] 生产环境可一键部署
  - [x] 首批开通账号可登录使用
- **完成记录**：产出生产编排文件 + 初始化脚本 + 上线 checklist。
  - `deploy/docker-compose.prod.yml`：4 services（postgres + redis + backend + frontend），全部 restart: unless-stopped + json-file 日志轮转，PG 备份卷，Redis AOF 持久化，后端 healthcheck（/healthz），前端 nginx 静态服务 + API 反代。
  - `deploy/Dockerfile.frontend.prod`：多阶段构建（node22 build → nginx serve），SPA fallback + API 反代。
  - `deploy/nginx.conf`：前端静态服务 + /api/ 反代到 backend:8000 + /healthz 直通 + 静态资源缓存。
  - `deploy/.env.prod.example`：生产环境变量模板（PG_PASSWORD / SECRET_KEY 必填强随机值）。
  - `backend/scripts/init_admin.py`：首次部署创建管理员账号（INIT_ADMIN_USERNAME / INIT_ADMIN_PASSWORD 环境变量注入）。
  - 后端启动命令内联 `alembic upgrade head && uvicorn`，自动执行 DB 迁移。
  - **验证后置**：本地未装 Docker，`docker compose up` 一键拉起待 Docker 环境验证（compose 文件 + YAML 结构已校验）。
  - **上线 checklist**：(1) 生成强随机 SECRET_KEY（`openssl rand -hex 32`）；(2) 设置 PG_PASSWORD；(3) 填入 ANTHROPIC_API_KEY；(4) `docker compose -f deploy/docker-compose.prod.yml --env-file .env.prod up -d --build`；(5) `docker compose exec backend python scripts/init_admin.py`（INIT_ADMIN_PASSWORD=xxx）；(6) 浏览器访问 http://localhost 用 admin 登录验证。

---

## 附：跨阶段关注点（每个任务都应自查）

- **路径安全**（D17 / NF4.1.2）：任何文件工具 / payload 读取都过 resolve 校验
- **多租户隔离**（D31 / NF4.6.1）：所有查询带 ws_id；ws_id 取自 session 不取自客户端
- **敏感信息脱敏**（D30 / NF4.2.3）：payload 落盘前过管线；secret 不入日志
- **非阻塞采集**（NF4.3.1 / §7.4）：可观测性 best-effort，不拖垮 Agent / 飞书流式
- **失败降级**：锁释放、trace 写入、payload 写入均有 try/finally 或 swallow 兜底
