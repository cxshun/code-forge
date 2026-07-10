# Code Forge

云端多租户 Coding Agent SaaS：以飞书 WebSocket 为统一交互入口，以工作空间（Workspace）
为一等公民组织 `MCP + Skill + 项目代码`。

- 设计文档：[docs/design.md](docs/design.md)
- 需求规格：[docs/spec.md](docs/spec.md)
- 接口设计：[docs/api.md](docs/api.md)
- 任务列表：[docs/task.md](docs/task.md)

## 仓库结构（Monorepo）

```
code-forge/
├── backend/    # FastAPI 后端（Python 3.11+，uv 管理依赖）
├── frontend/   # Vue 3 管理后台（pnpm）
├── deploy/     # docker-compose / .env.example
├── docs/       # spec / design / api / task
└── .github/    # CI（lint / test / alembic check）
```

## 快速开始

### 后端

```bash
cd backend
uv sync                    # 安装依赖（首次会自动拉取 Python 3.11）
uv run uvicorn app.main:app --reload --port 8000
# 健康检查：curl http://localhost:8000/healthz
```

测试与 lint：

```bash
uv run pytest
uv run ruff check .
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev                   # 占位首页 http://localhost:5173
```

### 全栈（Docker Compose）

```bash
cp deploy/.env.example .env
docker compose -f deploy/docker-compose.yml up --build
```

一键拉起 PostgreSQL / Redis / 后端 / 前端，PG / Redis 数据持久化于卷。
