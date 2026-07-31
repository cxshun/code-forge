# P3 - 零外部依赖（Zero Deps）：需求规格

> 子主题：[zero-deps](./)。P3 总览见 [../README.md](../README.md)。

---

## 1. 背景与目标

### 1.1 问题

当前部署 Code Forge 需要两个外部服务：

1. **PostgreSQL 16** — 全部业务数据（Workspace / User / Session / Run / Span / MCP / Skill / AlertRule 等）
2. **Redis 7** — 运行时协调（消息去重、WS 写锁、Run 队列、session 存储、登录限流）

对于个人开发者或小团队，安装配置 PostgreSQL + Redis 是上手的第一道门槛。项目定位为"云端多租户 Coding Agent SaaS"，但在早期试用 / 本地开发 / 单实例部署场景下，强制依赖两个外部服务是不必要的摩擦。

### 1.2 目标

将 PostgreSQL 和 Redis 从**强制依赖**降级为**可选依赖**：

- **不配置任何外部服务时**：应用使用内置 SQLite（文件）+ 纯内存协调，开箱即用
- **配置了 PostgreSQL 时**：自动切换到 PostgreSQL，获得完整的生产级能力
- **配置了 Redis 时**：自动启用 Redis 做分布式协调（多实例部署时需要）
- **启动命令不变**：`uv run uvicorn app.main:app` 即可启动，无需额外步骤

### 1.3 非目标

- **不做 PostgreSQL → SQLite 的数据迁移工具**：两种存储是独立模式，不提供跨存储数据搬运
- **不修改前端**：前端 API 不变，存储切换对前端透明
- **不支持多实例 + SQLite**：SQLite 是单写入锁，多实例必须用 PostgreSQL + Redis
- **不改业务逻辑**：存储层切换不改变任何业务行为（Run 编排、上下文管理、飞书集成等）

---

## 2. 功能性需求

### 2.1 存储引擎自动选择

- **F3.20** 应用启动时根据配置自动选择存储引擎：
  - `DATABASE_URL` 非空 → PostgreSQL（`asyncpg` 驱动）
  - `DATABASE_URL` 为空 / 未配置 → SQLite（`aiosqlite` 驱动），数据库文件路径由 `DATA_DIR/sqlite/codeforge.db` 决定
- **F3.21** Redis 同理：
  - `REDIS_URL` 非空 → Redis 客户端
  - `REDIS_URL` 为空 / 未配置 → 内存协调器（`MemoryBackend`），功能等价但不跨进程
- **F3.22** 启动时日志输出当前存储模式：`storage=sqlite|postgresql, redis=memory|redis`

### 2.2 SQLite 兼容

- **F3.23** 所有 SQLAlchemy 模型在 SQLite 下正常工作：
  - `JSONB` 列在 SQLite 下退化为 `JSON`（SQLAlchemy 的 `JSON` 类型两种数据库都支持）
  - `DateTime(timezone=True)` 在 SQLite 下正常存储（SQLite 不强制时区，但 SQLAlchemy 处理 ISO 格式）
  - `Numeric(12, 6)` 在 SQLite 下正常工作
  - `ondelete="CASCADE"` / `ondelete="RESTRICT"` 在 SQLite 下需要 `PRAGMA foreign_keys=ON`（默认关闭）
- **F3.24** Alembic 迁移在 SQLite 下正常执行：
  - 使用 `render_as_batch=True`（SQLite 不支持大部分 ALTER TABLE，需要 batch mode 重建表）
  - 现有迁移脚本不需要修改（batch mode 对 PostgreSQL 透明）

### 2.3 Redis 替代（MemoryBackend）

- **F3.25** `MemoryBackend` 提供与 `redis.asyncio.Redis` 等价的接口子集：
  - `SET` / `GET` / `DELETE`（带 TTL 过期）
  - `SET` with `nx=True`（原子 SETNX）
  - `INCR` / `EXPIRE`
  - `ZADD` / `ZRANK` / `ZREM`（sorted set）
  - `PUBLISH` / `SUBSCRIBE`（pub/sub，进程内）
- **F3.26** TTL 过期采用惰性清理（访问时检查过期）+ 定期扫描（每 60s 清理过期 key）
- **F3.27** pub/sub 在内存模式下退化为进程内 `asyncio.Queue`（单进程，无需跨进程通知）
- **F3.28** Lua 脚本（`WsLock` 的 renew / release）改为 Python 原子操作（`asyncio.Lock` 保护 check-then-act）

### 2.4 Session 存储

- **F3.29** 用户 session（登录 token → user_id）在 Redis 模式下走 Redis（现有行为）；在内存模式下走 `MemoryBackend`（进程内 dict + TTL）
- **F3.30** 登录限流（IP → 计数 + 窗口）同理：Redis 模式走 Redis，内存模式走 `MemoryBackend`

### 2.5 配置变更

- **F3.31** `.env` 模板更新：
  - `DATABASE_URL=` （留空 = SQLite，填 DSN = PostgreSQL）
  - `REDIS_URL=` （留空 = 内存，填 URL = Redis）
  - 新增 `SQLITE_PATH=` （可选，默认 `{DATA_DIR}/sqlite/codeforge.db`）
- **F3.32** `config.py` 调整：
  - `pg_dsn` 改名为 `database_url`，默认值改为空字符串
  - `redis_url` 默认值改为空字符串
  - 新增 `sqlite_path` 属性（默认 `{data_dir}/sqlite/codeforge.db`）
  - `pg_dsn_effective` 改为 `database_url_effective`，逻辑调整为：非空用原值，空则返回 SQLite 路径

---

## 3. 非功能性需求

- **NF3.8** SQLite 模式下应用启动时间 < 3s（无外部服务连接等待）
- **NF3.9** 内存模式下 Run 队列 / WS 锁 / 消息去重功能与 Redis 模式行为一致（单进程内）
- **NF3.10** 存储引擎切换不引入新的 `import` 失败风险：`aiosqlite` 作为必装依赖（轻量纯 Python），`asyncpg` 保留为必装（不影响）
- **NF3.11** Alembic batch mode 对 PostgreSQL 无副作用（batch mode 检测到 PostgreSQL 会直接执行 ALTER TABLE，不重建表）
- **NF3.12** 现有测试在 PostgreSQL 模式下全绿（回归保护）；新增 SQLite 模式下的兼容性测试

---

## 4. 约束与假设

- **单实例假设**：SQLite + 内存模式仅适用于单实例部署；多实例必须配置 PostgreSQL + Redis
- **并发写入**：SQLite 单写入锁，高并发写入时会串行等待；单实例小团队使用可接受
- **数据安全**：SQLite 文件存储在 `DATA_DIR` 下，备份策略为文件拷贝（比 pg_dump 更简单）
- **Redis 不再强制安装**：`redis` Python 包从必装依赖降级为可选依赖（`redis_url` 非空时才 import）
- **向后兼容**：已有 `PG_DSN` 环境变量仍然有效（作为 `DATABASE_URL` 的别名），降低升级摩擦
- **测试策略不变**：现有测试使用 PostgreSQL（`asyncpg`）；新增 SQLite 兼容性测试在 CI 中并行运行

---

## 5. 与 MVP / P2 / P3 的关系

| 来源 | 关系 | 说明 |
|---|---|---|
| MVP 数据层 | **重构** | `db/session.py` 引擎创建逻辑改为双引擎；`db/models/` 的 `JSONB` 改为条件导入 `JSON` |
| MVP Redis 层 | **重构** | `core/redis_client.py` 改为可选；`agent/lock.py` / `agent/queue.py` / `feishu/dedup.py` / `core/session.py` 接受抽象接口 |
| MVP Alembic | **增强** | `env.py` 加 `render_as_batch=True`；现有迁移脚本不改 |
| P2 direct-chat | **无影响** | 存储切换对飞书消息处理流透明 |
| P3 context-eng | **无影响** | 上下文管理逻辑不依赖存储引擎类型 |

> 本子主题不修改 MVP/P2/P3 既有文档的业务逻辑部分；仅在数据层和协调层做抽象与适配。
