# P3 - 零外部依赖（Zero Deps）：任务拆分

> 设计见 [design.md](./design.md)，规格见 [spec.md](./spec.md)。

---

## T1: 配置层改造（D-ZD.8）

- [x] T1.1 `config.py` 字段重命名：`pg_dsn` → `database_url`（默认空），保留 `pg_dsn` property 别名
- [x] T1.2 `config.py` `redis_url` 默认值改为空字符串
- [x] T1.3 `config.py` 新增 `sqlite_path` / `database_url_effective` / `is_postgresql` / `is_redis` 属性
- [x] T1.4 新建 `.env.example` 模板，列出全部配置项 + 注释
- [x] T1.5 `pyproject.toml` 新增 `aiosqlite` 依赖

## T2: 模型类型统一（D-ZD.2）

- [x] T2.1 `db/models/mcp.py`：`JSONB` → `JSON`
- [x] T2.2 `db/models/task.py`：`JSONB` → `JSON`
- [x] T2.3 `db/models/workspace.py`：`JSONB` → `JSON`（2 列）
- [x] T2.4 `db/models/span.py`：`JSONB` → `JSON`

## T3: 数据库引擎双分支（D-ZD.1）

- [x] T3.1 `db/session.py`：引擎创建按 `is_postgresql` 分支（asyncpg / aiosqlite）
- [x] T3.2 SQLite 连接初始化：`PRAGMA foreign_keys=ON` + `PRAGMA journal_mode=WAL`
- [x] T3.3 启动时日志输出存储模式

## T4: Alembic Batch Mode（D-ZD.3）

- [x] T4.1 `alembic/env.py`：`context.configure()` 添加 `render_as_batch=True`
- [x] T4.2 `alembic/env.py`：URL 改用 `database_url_effective`

## T5: CoordinationBackend 抽象层（D-ZD.4）

- [x] T5.1 新建 `core/coordination.py`：`CoordinationBackend` 抽象接口
- [x] T5.2 `MemoryBackend` 实现（KV + TTL + sorted set + pub/sub）
- [x] T5.3 `RedisBackend` 实现（委托 `redis.asyncio.Redis`）
- [x] T5.4 `core/redis_client.py` 改为返回 `CoordinationBackend`

## T6: WsLock 改造（D-ZD.5）

- [x] T6.1 `agent/lock.py`：去掉 Lua 脚本，改用 `CoordinationBackend` 组合操作
- [x] T6.2 acquire / renew / release / notify 全部适配

## T7: RunQueue 改造（D-ZD.6）

- [x] T7.1 `agent/queue.py`：持有 `CoordinationBackend` 替代 `Redis`
- [x] T7.2 所有 Redis 操作改为 backend 调用

## T8: Session / Dedup 改造（D-ZD.7）

- [x] T8.1 `core/session.py`：接受 `CoordinationBackend`
- [x] T8.2 `feishu/dedup.py`：接受 `CoordinationBackend`
- [x] T8.3 `core/deps.py` / `api/auth.py` / `feishu/handler.py` 适配注入

## T9: 测试

- [x] T9.1 新建 `tests/test_coordination.py`：MemoryBackend 单元测试（18 条）
- [x] T9.2 `CoordinationBackend` 添加 `flushdb` 方法，适配现有测试的清理调用
- [x] T9.3 `conftest.py` 适配 SQLite（跳过 maintenance DB 创建）
- [x] T9.4 `db/testing.py` 适配 SQLite（`DELETE FROM` + `sqlite_sequence` 条件重置）
- [x] T9.5 全量测试通过（269 passed）
