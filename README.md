# Code Forge

云端多租户 Coding Agent SaaS：以飞书 WebSocket 为统一交互入口，以工作空间（Workspace）
为一等公民组织 `MCP + Skill + 项目代码`。

- 设计文档：[docs/mvp/design.md](docs/mvp/design.md)
- 需求规格：[docs/mvp/spec.md](docs/mvp/spec.md)
- 接口设计：[docs/mvp/api.md](docs/mvp/api.md)
- 任务列表：[docs/mvp/task.md](docs/mvp/task.md)

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.x (async) / Alembic |
| 前端 | Vue 3 (Composition API) / TypeScript / Vite / Element Plus / Pinia |
| 数据库 | PostgreSQL 16 |
| 缓存/队列 | Redis 7 |
| 飞书 SDK | lark-oapi (WebSocket 模式) |
| LLM | Anthropic Claude（主）/ OpenAI 兼容端点（GLM / DeepSeek / 通义等备选） |
| 包管理 | uv (后端) / pnpm (前端) |

## 仓库结构

```
code-forge/
├── backend/               # FastAPI 后端
│   ├── app/
│   │   ├── main.py        # 入口（lifespan: Feishu WS / SpanBuffer / TTL loop）
│   │   ├── config.py      # Pydantic Settings（.env 驱动）
│   │   ├── agent/         # Agentic Loop / Run 编排 / 上下文管理 / 队列
│   │   ├── providers/     # LLM 抽象（Anthropic / OpenAI 兼容 / Mock）
│   │   ├── tools/         # 内置工具(bash/read/write/grep/glob/edit) + MCP + Skill
│   │   ├── feishu/        # 飞书 WS 池 / 消息分发 / 卡片渲染
│   │   ├── api/           # HTTP 路由（/api + /api/admin）
│   │   ├── db/            # SQLAlchemy 模型 + 异步 Engine
│   │   ├── observability/ # Tracer / SpanBuffer / 成本计算 / 敏感脱敏
│   │   └── ...
│   ├── alembic/           # 数据库迁移
│   ├── scripts/init_admin.py  # 幂等管理员创建
│   ├── tests/             # pytest（41 文件，独立测试库）
│   └── pyproject.toml     # uv 管理
├── frontend/              # Vue 3 管理后台
│   ├── src/
│   │   ├── views/         # 工作空间 / Skill / MCP / 飞书App / Trace / 监控 ...
│   │   ├── api/           # Axios 客户端
│   │   └── stores/        # Pinia
│   └── package.json
├── deploy/                # Docker Compose / Dockerfile / .env.example
├── docs/                  # 设计文档（spec / design / api / task）
└── .github/workflows/     # CI（ruff + pytest + alembic check + frontend build）
```

## 前置条件

- **Python 3.11+**（后端）
- **Node.js 22+** / **pnpm 9+**（前端）
- **uv**（Python 包管理器，`curl -LsSf https://astral.sh/uv/install.sh | sh`）
- **PostgreSQL 16**（本地开发可用 Docker：`docker run -d --name pg -p 5432:5432 -e POSTGRES_USER=codeforge -e POSTGRES_PASSWORD=codeforge -e POSTGRES_DB=codeforge postgres:16-alpine`）
- **Redis 7**（本地开发可用 Docker：`docker run -d --name redis -p 6379:6379 redis:7-alpine`）

## 快速开始

### 方式一：本地开发（推荐开发调试）

#### 1. 启动 PostgreSQL 和 Redis

```bash
# 用 Docker 快速拉起（或使用本机已有实例）
docker run -d --name codeforge-pg -p 5432:5432 \
  -e POSTGRES_USER=codeforge -e POSTGRES_PASSWORD=codeforge -e POSTGRES_DB=codeforge \
  postgres:16-alpine
docker run -d --name codeforge-redis -p 6379:6379 redis:7-alpine
```

#### 2. 配置环境变量

```bash
cd backend
cat > .env <<'EOF'
APP_ENV=dev
PG_DSN=postgresql+asyncpg://codeforge:codeforge@localhost:5432/codeforge
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-insecure-secret-key-change-me
DATA_DIR=./data

# LLM 配置（二选一）
# 方式 A：Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-xxx

# 方式 B：OpenAI 兼容端点（GLM / DeepSeek / 通义等）
OPENAI_COMPATIBLE_API_KEY=sk-xxx
OPENAI_COMPATIBLE_BASE_URL=https://api.deepseek.com
OPENAI_COMPATIBLE_MODEL=deepseek-v4-flash
EOF
```

#### 3. 安装依赖 & 初始化数据库

```bash
uv sync                    # 安装依赖（首次自动拉取 Python 3.11）
uv run alembic upgrade head  # 执行数据库迁移，建表
uv run python scripts/init_admin.py  # 创建初始管理员（dev 默认 admin/admin）
```

#### 4. 启动后端

```bash
uv run uvicorn app.main:app --reload --port 8000
# 健康检查：curl http://localhost:8000/healthz
```

#### 5. 启动前端

```bash
cd ../frontend
pnpm install
pnpm dev                   # http://localhost:5173（/api 自动代理到后端 8000）
```

用 `admin / admin` 登录管理后台。

### 方式二：全栈 Docker Compose（一键拉起）

```bash
cp deploy/.env.example .env
# 编辑 .env，填入 LLM API Key 等必要配置
docker compose -f deploy/docker-compose.yml up --build
```

自动拉起 PostgreSQL / Redis / 后端(8000) / 前端(5173)，数据持久化于 Docker 卷。

> **注意**：Docker Compose 方式不会自动执行 `alembic upgrade head` 和 `init_admin.py`，
> 需手动执行：
> ```bash
> docker compose -f deploy/docker-compose.yml exec backend uv run alembic upgrade head
> docker compose -f deploy/docker-compose.yml exec backend uv run python scripts/init_admin.py
> ```

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `APP_ENV` | 否 | `dev` | 运行环境：`dev` / `prod` / `test` |
| `PG_DSN` | 是 | `postgresql+asyncpg://codeforge:codeforge@localhost:5432/codeforge` | PostgreSQL 连接串 |
| `REDIS_URL` | 是 | `redis://localhost:6379/0` | Redis 连接串 |
| `SECRET_KEY` | **生产必填** | `dev-insecure-secret-key-change-me` | 凭证加密主密钥（`openssl rand -hex 32`） |
| `DATA_DIR` | 否 | `./data` | 文件系统根（工作空间 / Skill 广场） |
| `ANTHROPIC_API_KEY` | 否 | — | Anthropic Claude API Key |
| `ANTHROPIC_MODEL` | 否 | — | 模型名（留空用默认 `claude-sonnet-5`） |
| `OPENAI_COMPATIBLE_API_KEY` | 否 | — | OpenAI 兼容端点 API Key |
| `OPENAI_COMPATIBLE_BASE_URL` | 否 | — | 如 `https://api.deepseek.com` |
| `OPENAI_COMPATIBLE_MODEL` | 否 | — | 如 `deepseek-v4-flash` / `glm-4.7` |
| `FEISHU_BASE_URL` | 否 | `https://open.feishu.cn/open-apis` | 飞书开放平台 API 地址 |
| `INIT_ADMIN_USERNAME` | 否 | `admin` | 初始管理员用户名 |
| `INIT_ADMIN_PASSWORD` | 否 | — | 初始管理员密码（dev 留空则 `admin/admin`） |

**LLM 配置**：`ANTHROPIC_*` 和 `OPENAI_COMPATIBLE_*` 二选一。Anthropic 为主模型，
OpenAI 兼容端点为国内备选（三项都填才启用）。两者可同时配置，Anthropic 优先。

## 数据库

### 迁移（Alembic）

```bash
cd backend
uv run alembic upgrade head     # 执行所有迁移
uv run alembic check            # 检查模型与迁移是否一致（CI 也会跑）
uv run alembic revision --autogenerate -m "描述"  # 生成新迁移
```

### 主要表

| 表 | 说明 |
|---|---|
| `users` | 管理后台账号（argon2 密码哈希） |
| `workspaces` | 工作空间（隔离单元） |
| `feishu_chats` | 飞书群聊 ↔ 工作空间绑定 |
| `git_repos` | Git 仓库（clone 到本地） |
| `sessions` / `runs` | 会话与执行（1:1，状态机） |
| `spans` | 可观测性 Trace 树（自引用） |
| `mcps` / `skills` | MCP / Skill 全局广场 |
| `alert_rules` | 告警规则（错误率 / 延迟 / 成本） |

### 初始管理员

```bash
uv run python scripts/init_admin.py
# dev 环境：自动创建 admin/admin
# prod 环境：通过 INIT_ADMIN_USERNAME / INIT_ADMIN_PASSWORD 环境变量配置
```

生产环境 Docker 部署时，此脚本由 entrypoint 自动执行。

## 测试

```bash
cd backend
uv run pytest               # 全量测试（自动使用 codeforge_test 测试库）
uv run pytest -x -q         # 失败即停，简洁输出
uv run pytest tests/test_loop.py  # 单文件
```

测试框架：pytest + pytest-asyncio（`asyncio_mode = "auto"`）。测试使用独立的
`codeforge_test` 数据库，每个 session 自动建表，`reset_all()` TRUNCATE 隔离。

## Lint

```bash
cd backend
uv run ruff check .
uv run ruff check . --fix   # 自动修复
```

## 生产部署

### Docker Compose（推荐）

```bash
cp deploy/.env.prod.example .env.prod
# 必填项：
#   PG_PASSWORD     — 数据库密码（强随机）
#   SECRET_KEY      — 凭证加密密钥（openssl rand -hex 32）
#   ANTHROPIC_API_KEY 或 OPENAI_COMPATIBLE_* — LLM 配置
# 可选：
#   INIT_ADMIN_USERNAME / INIT_ADMIN_PASSWORD — 初始管理员

docker compose -f deploy/docker-compose.prod.yml --env-file .env.prod up -d --build
```

生产 compose 与开发 compose 的区别：
- 后端 entrypoint 自动执行 `alembic upgrade head` → `init_admin.py` → `uvicorn`
- 前端由 nginx 静态服务（多阶段构建），端口 80，`/api` 反代到后端
- 全部 `restart: unless-stopped`，日志 json-file 轮转
- Redis AOF 持久化 + PG 备份卷

### 健康检查

```bash
curl http://localhost:8000/healthz   # 后端
curl http://localhost/                # 前端（nginx）
```

## 数据目录结构

```
data/
├── workspaces/{ws_id}/              # 工作空间
│   ├── workspace.toml               # WS 配置
│   ├── AGENT.md                     # Agent 指令
│   ├── repos/{repo_id}/             # Git 仓库
│   ├── chats/{chat_id}/
│   │   ├── memory/                  # 跨会话记忆
│   │   ├── sessions/                # 会话 JSONL
│   │   └── traces/                  # Trace payload
│   └── ...
├── skills/{skill_id}/               # 全局 Skill 广场
│   ├── SKILL.md
│   ├── resources/
│   └── scripts/
└── trace_fallback/                  # SpanBuffer 写库失败兜底
```

## CI

推送到 main 或发 PR 时自动触发（`.github/workflows/ci.yml`）：
- **后端**：`ruff check` → `pytest` → `alembic upgrade head` → `alembic check`（模型漂移检测）
- **前端**：`pnpm install` → `pnpm build`
