# Code Forge Backend

FastAPI 后端（Python 3.11+，uv 管理依赖）。整体架构与决策见仓库根
[README](../README.md) 与 [docs/design.md](../docs/design.md)。

## 目录结构（design §3.5）

```
backend/
├── pyproject.toml              # uv 管理依赖
├── alembic/                    # 迁移（T1.2）
├── app/
│   ├── main.py                 # FastAPI 入口 + 生命周期
│   ├── config.py               # pydantic-settings 配置
│   ├── core/                   # 横切：日志 / 安全 / 依赖注入 / 启动恢复
│   ├── db/                     # 持久化（ORM / session / 多租户隔离）
│   ├── api/                    # HTTP 接口层（管理后台）
│   ├── feishu/                 # 飞书接入层（WS 池 / 路由 / 卡片）
│   ├── agent/                  # Agent 内核（Loop / Run / 上下文 / 锁 / 子代理）
│   ├── providers/              # LLM Provider 抽象
│   ├── tools/                  # 工具层（内置 / MCP / Skill / 路径安全）
│   ├── workspace/              # 工作空间管理（目录 / git）
│   ├── memory/                 # chat memory 读写
│   ├── observability/          # tracer / buffer / payload / cost
│   └── tasks/                  # 异步任务（asyncio + Redis）
└── tests/
```

## 本地开发

```bash
uv sync --all-extras                                   # 安装依赖（含 dev）
uv run uvicorn app.main:app --reload --port 8000       # 启动服务
uv run pytest                                          # 测试
uv run ruff check .                                    # lint
```

环境变量从 `.env` 加载（见 `deploy/.env.example`）。
