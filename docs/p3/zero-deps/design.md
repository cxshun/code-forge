# P3 - 零外部依赖（Zero Deps）：设计

> 子主题：[zero-deps](./)。规格见 [spec.md](./spec.md)。

---

## 0. 现状回顾

### 0.1 存储架构（当前）

```
┌───────────────────────────────────────────────┐
│  Application                                   │
│   ├─ SQLAlchemy ORM (models/)                  │
│   │   └─ JSONB / DateTime / Numeric / FK       │
│   ├─ Alembic (async migrations)                │
│   ├─ async_session_factory (asyncpg engine)    │
│   └─ redis_client (redis.asyncio.Redis)        │
│                                                │
│  ┌─────────────┐    ┌──────────────┐           │
│  │ PostgreSQL   │    │ Redis         │          │
│  │ (external)   │    │ (external)    │          │
│  └─────────────┘    └──────────────┘           │
└───────────────────────────────────────────────┘

部署需要：PostgreSQL 16 + Redis 7 + Python 3.11+
```

### 0.2 Redis 使用点（5 处）

| 模块 | 用途 | Redis 操作 |
|---|---|---|
| `core/session.py` | 用户 session（token → user_id） | `SET` (TTL) / `GET` / `DELETE` |
| `core/session.py` | 登录限流（IP → 计数） | `INCR` / `EXPIRE` |
| `feishu/dedup.py` | 消息去重 | `SET` (NX + TTL) |
| `agent/lock.py` | WS 写锁 | `SET` (NX + TTL) / `EVAL` (Lua) / `PUBLISH` |
| `agent/queue.py` | Run 队列（FIFO） | `INCR` / `ZADD` / `ZRANK` / `ZREM` |

### 0.3 PostgreSQL 特定类型

| 类型 | 使用处 | SQLite 兼容性 |
|---|---|---|
| `JSONB` | `mcp.config` / `task.result` / `workspace.context_config` / `workspace.model_config` / `span.attributes` | SQLAlchemy `JSON` 类型在 SQLite 下用 TEXT 存储 JSON 字符串，功能等价 |
| `DateTime(timezone=True)` | `TimestampMixin` / 多处 | SQLite 存 ISO 字符串，SQLAlchemy 自动处理 |
| `Numeric(12, 6)` | `span.cost_usd` | SQLite 存为 REAL，精度足够 |
| `ondelete="CASCADE"/"RESTRICT"` | 16 处 FK | SQLite 需 `PRAGMA foreign_keys=ON` |
| `server_default="now()"` / `func.now()` | `TimestampMixin` / `session_summaries` | SQLite 的 `CURRENT_TIMESTAMP` 等价 |
| `UniqueConstraint` | `feishu_chats(app_id, chat_id)` | SQLite 支持 |

---

## 1. 整体架构

```
┌───────────────────────────────────────────────┐
│  Application                                   │
│   ├─ SQLAlchemy ORM (models/)                  │
│   │   └─ JSON (统一，PG 下用 JSONB 兼容)        │
│   ├─ Alembic (batch mode)                      │
│   ├─ async_session_factory                     │
│   │   ├─ database_url 非空 → asyncpg engine    │
│   │   └─ database_url 空   → aiosqlite engine  │
│   ├─ CoordinationBackend (抽象接口)             │
│   │   ├─ redis_url 非空 → RedisBackend          │
│   │   └─ redis_url 空   → MemoryBackend         │
│   └─ 启动时日志: storage=xxx, redis=xxx         │
│                                                │
│  ┌──────────────┐    ┌──────────────┐          │
│  │ SQLite (内置)  │    │ Memory (内置) │          │
│  │  或 PostgreSQL │    │  或 Redis     │         │
│  └──────────────┘    └──────────────┘          │
└───────────────────────────────────────────────┘

部署门槛：
  零依赖模式：Python 3.11+ （SQLite + Memory 内置）
  生产模式：  Python 3.11+ PostgreSQL + Redis
```

---

## 2. 关键决策

### D-ZD.1: 存储引擎选择（database_url 空 → SQLite）

- **规则**：`settings.database_url` 非空时用 PostgreSQL（`asyncpg`），空时用 SQLite（`aiosqlite`）
- **引擎参数**：

  ```python
  # PostgreSQL（现有）
  create_async_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)

  # SQLite（新增）
  create_async_engine(
      f"sqlite+aiosqlite:///{sqlite_path}",
      pool_pre_ping=True,
      connect_args={"check_same_thread": False},  # 允许多线程共享
  )
  ```

- **SQLite 连接初始化**：每次连接建立后执行 `PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;`，通过 `event.listens_for(engine.sync_engine, "connect")` 注册
- **WAL 模式**：Write-Ahead Logging 提升并发读性能（读写不互斥），单写入锁仍存在但读不阻塞
- **向后兼容**：`PG_DSN` 环境变量作为 `DATABASE_URL` 的别名，两者都配置时 `DATABASE_URL` 优先
- **不做的事**：
  - 不做运行时引擎切换（启动时确定，不支持热切换）
  - 不做 SQLite 分库 / 分表（单文件足够）
- **理由**：SQLite 是 Python 内置库（`sqlite3`），`aiosqlite` 是轻量纯 Python async 封装；零配置、零端口、文件即数据库

### D-ZD.2: JSONB → JSON 统一类型

- **规则**：所有模型中的 `from sqlalchemy.dialects.postgresql import JSONB` 改为 `from sqlalchemy import JSON`
- **兼容性**：
  - PostgreSQL：`JSON` 类型在 PG 中也是合法的（存储为 JSON 字符串，不支持 GIN 索引但本项目未用）
  - SQLite：`JSON` 类型存为 TEXT，SQLAlchemy 自动处理序列化 / 反序列化
  - 查询行为一致：`col["key"]` 在两种数据库下都可用（SQLAlchemy 的 JSON 路径访问）
- **迁移影响**：现有 `JSONB` 列在 PG 下不需要变（`JSON` 和 `JSONB` 在 PG 中可隐式转换）；Alembic autogenerate 可能检测到类型变化，需要手动调整迁移脚本忽略或用 `render_as_batch=True` 处理
- **不做的事**：
  - 不做条件导入（`JSONB if PG else JSON`）—— 统一用 `JSON` 更简洁，功能无损失
  - 不为 SQLite 添加 JSON 索引（数据量小，全表扫描可接受）
- **理由**：统一类型消除条件分支，代码更简洁；PG 的 `JSON` 类型功能足够（项目未用 JSONB GIN 索引）

### D-ZD.3: Alembic Batch Mode

- **规则**：`alembic/env.py` 中 `context.configure()` 添加 `render_as_batch=True`
- **行为**：
  - SQLite：ALTER TABLE 操作被自动包装为 "重建表" 模式（创建新表 → 复制数据 → 删旧表 → 重命名）
  - PostgreSQL：Batch mode 检测到原生 ALTER TABLE 支持，直接执行，无额外开销
- **现有迁移脚本**：不需要修改。Batch mode 对迁移脚本是透明的——`op.add_column()` / `op.drop_column()` 等调用不变
- **新迁移脚本**：如果需要 SQLite 兼容，避免使用 PG 特有 DDL（如 `CREATE INDEX ... USING gin`）
- **不做的事**：
  - 不为 SQLite 单独写一套迁移脚本（batch mode 复用现有脚本）
  - 不在迁移中做条件分支（`if PG: ... else: ...`）
- **理由**：Batch mode 是 Alembic 官方推荐的 SQLite 兼容方案，对 PG 透明，零维护成本

### D-ZD.4: CoordinationBackend 抽象接口

- **规则**：新增 `app/core/coordination.py` 定义 `CoordinationBackend` 抽象接口，`RedisBackend` 和 `MemoryBackend` 各自实现

  ```python
  class CoordinationBackend(ABC):
      # KV with TTL
      async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool: ...
      async def get(self, key: str) -> str | None: ...
      async def delete(self, key: str) -> int: ...

      # Counter
      async def incr(self, key: str) -> int: ...
      async def expire(self, key: str, seconds: int) -> bool: ...

      # Sorted set
      async def zadd(self, key: str, mapping: dict[str, int]) -> int: ...
      async def zrank(self, key: str, member: str) -> int | None: ...
      async def zrem(self, key: str, *members: str) -> int: ...

      # Pub/sub
      async def publish(self, channel: str, message: str) -> int: ...
      async def subscribe(self, channel: str) -> AsyncIterator[str]: ...
  ```

- **MemoryBackend 实现**：
  - KV：`dict[str, tuple[str, float]]`（value + expire_at），惰性过期 + 定期扫描
  - Sorted set：`dict[str, dict[str, float]]`（key → {member: score}），`zrank` 用 sorted 排序
  - Pub/sub：`dict[str, list[asyncio.Queue]]`，`publish` 向所有订阅者的 queue put 消息
  - 原子性：`asyncio.Lock` 保护所有 check-then-act 操作（替代 Redis Lua 脚本）
- **RedisBackend 实现**：直接委托给 `redis.asyncio.Redis`，签名一一对应
- **选择逻辑**：`settings.redis_url` 非空 → `RedisBackend(redis.from_url(...))`，空 → `MemoryBackend()`
- **不做的事**：
  - 不实现 Redis 的全部命令（只覆盖项目用到的子集）
  - 不做 MemoryBackend 的持久化（进程重启丢失，单实例可接受）
  - 不做 MemoryBackend 的跨进程通信（单进程 `asyncio.Queue` 足够）
- **理由**：抽象接口让上层代码（lock / queue / dedup / session）不感知后端类型；MemoryBackend 用纯 Python 标准库实现，零依赖

### D-ZD.5: WsLock 改造（去掉 Lua 脚本）

- **规则**：`WsLock` 不再直接调 `redis.eval()`，改为通过 `CoordinationBackend` 的组合操作实现原子语义
- **acquire**：`backend.set(key, holder, nx=True, ex=ttl)` —— SETNX 语义，Redis 和 Memory 都支持
- **renew**：先 `get(key)` 检查 holder 匹配，再 `set(key, holder, ex=ttl)` 续期。用 `asyncio.Lock` 保证 Memory 模式下的原子性；Redis 模式下可接受极小的 check-then-set 竞态窗口（TTL 兜底）
- **release**：先 `get(key)` 检查 holder 匹配，再 `delete(key)`。同理用 `asyncio.Lock` 保证 Memory 原子性
- **notify**：`backend.publish(channel, "released")`，Memory 模式下退化为进程内 Queue
- **不做的事**：
  - 不为 Redis 模式保留 Lua 脚本（简化代码，竞态窗口 < 1ms 可接受，TTL 30s 兜底）
  - 不做 lock 续期失败后的自动中断（现有行为不变，TTL 过期后其他 Run 可抢锁）
- **理由**：Lua 脚本是 Redis 特有的，去掉后接口统一；竞态窗口极小且 TTL 兜底，实际影响可忽略

### D-ZD.6: RunQueue 改造

- **规则**：`RunQueue` 不再直接持有 `Redis` 实例，改为持有 `CoordinationBackend`
- **FIFO 序号**：`backend.incr(seqkey)` 替代 `redis.incr()`
- **入队**：`backend.zadd(qkey, {run_id: seq})` 替代 `redis.zadd()`
- **排队位置**：`backend.zrank(qkey, run_id)` 替代 `redis.zrank()`
- **出队**：`backend.zrem(qkey, run_id)` 替代 `redis.zrem()`
- **等待通知**：Memory 模式下 `backend.subscribe()` 返回 `asyncio.Queue`，`publish` 直接 put；Redis 模式下走 pub/sub
- **不做的事**：
  - 不改变队列的 FIFO 公平性逻辑
  - 不改变排队取消 / 运行中断的行为
- **理由**：`CoordinationBackend` 接口与 Redis 命令一一对应，改动量最小

### D-ZD.7: Session / Dedup 改造

- **规则**：`core/session.py` 和 `feishu/dedup.py` 改为接受 `CoordinationBackend` 参数
- **session**：`backend.set(f"session:{token}", user_id, ex=ttl)` / `backend.get(...)` / `backend.delete(...)`
- **限流**：`backend.incr(key)` + `backend.expire(key, window_s)`
- **去重**：`backend.set(f"msg_dedup:{message_id}", "1", nx=True, ex=600)`
- **不做的事**：
  - 不改变 session TTL（7 天）和去重 TTL（10 分钟）
  - 不改变限流阈值（5 次 / 60s）
- **理由**：直接替换底层客户端，上层逻辑不变

### D-ZD.8: 配置变更

- **规则**：`config.py` 调整字段名和默认值

  | 字段 | 旧 | 新 | 默认值 |
  |---|---|---|---|
  | `pg_dsn` | `str`，默认 PG DSN | `database_url: str`（`pg_dsn` 保留为别名 property） | `""` |
  | `redis_url` | `str`，默认 `redis://localhost:6379/0` | `redis_url: str` | `""` |
  | — | — | `sqlite_path: str` | `{data_dir}/sqlite/codeforge.db` |

- **`database_url_effective`**（替代 `pg_dsn_effective`）：
  ```python
  @property
  def database_url_effective(self) -> str:
      if self.database_url:
          return self.database_url  # PostgreSQL
      # SQLite fallback
      path = Path(self.sqlite_path)
      path.parent.mkdir(parents=True, exist_ok=True)
      return f"sqlite+aiosqlite:///{path}"
  ```
- **`is_postgresql`** / **`is_redis`** 属性：方便其他模块判断当前模式
- **`.env.example`** 更新：注释说明留空 = 内置模式
- **向后兼容**：`pg_dsn` 作为 `database_url` 的 property 别名（`return self.database_url`），`PG_DSN` 环境变量仍然有效
- **理由**：空字符串 = "未配置" 是最直觉的信号，不需要额外的 boolean 开关

---

## 3. 模型类型兼容对照

| 模型文件 | 列 | 当前类型 | 改为 | 说明 |
|---|---|---|---|---|
| `mcp.py` | `config` | `JSONB` | `JSON` | PG 下 JSON 也可用 |
| `task.py` | `result` | `JSONB` | `JSON` | 同上 |
| `workspace.py` | `context_config` | `JSONB` | `JSON` | 同上 |
| `workspace.py` | `model_config` | `JSONB` | `JSON` | 同上 |
| `span.py` | `attributes` | `JSONB` | `JSON` | 同上 |

其余类型（`String` / `Integer` / `DateTime` / `Boolean` / `Float` / `Numeric` / `Text`）两种数据库都原生支持，不需要修改。

---

## 4. 数据流

### 4.1 启动时存储引擎选择

```
app.config.Settings 加载
  ├─ database_url 非空? → PostgreSQL engine (asyncpg)
  └─ database_url 空?   → SQLite engine (aiosqlite) + PRAGMA init
  ├─ redis_url 非空?    → RedisBackend
  └─ redis_url 空?      → MemoryBackend
  └─ 日志: storage=postgresql|sqlite, redis=redis|memory
```

### 4.2 运行时请求流（不变）

```
飞书消息 → handler → dedup(backend) → queue.submit(backend)
  → _drive → _execute_run → DB(async_session_factory) → 完成
  → on_done → lock.release(backend) → queue.zrem(backend)
```

存储引擎和协调后端对业务逻辑完全透明。

---

## 5. 涉及文件

| 文件 | 改动 | 说明 |
|---|---|---|
| `backend/app/config.py` | 字段重命名 + 新增 `sqlite_path` / `is_postgresql` / `is_redis` | D-ZD.8 |
| `backend/app/db/session.py` | 引擎创建双分支 + SQLite PRAGMA | D-ZD.1 |
| `backend/app/db/models/mcp.py` | `JSONB` → `JSON` | D-ZD.2 |
| `backend/app/db/models/task.py` | `JSONB` → `JSON` | D-ZD.2 |
| `backend/app/db/models/workspace.py` | `JSONB` → `JSON`（2 列） | D-ZD.2 |
| `backend/app/db/models/span.py` | `JSONB` → `JSON` | D-ZD.2 |
| `backend/alembic/env.py` | 添加 `render_as_batch=True` | D-ZD.3 |
| `backend/app/core/coordination.py` | **新建** | `CoordinationBackend` 抽象 + `MemoryBackend` + `RedisBackend` (D-ZD.4) |
| `backend/app/core/redis_client.py` | 改为返回 `CoordinationBackend` | 根据 `redis_url` 选择后端 |
| `backend/app/core/session.py` | 接受 `CoordinationBackend` | D-ZD.7 |
| `backend/app/core/deps.py` | 注入 `CoordinationBackend` | 适配 session 改动 |
| `backend/app/api/auth.py` | 传入 `CoordinationBackend` | 适配 session 改动 |
| `backend/app/feishu/dedup.py` | 接受 `CoordinationBackend` | D-ZD.7 |
| `backend/app/feishu/handler.py` | 传入 `CoordinationBackend` | 适配 dedup 改动 |
| `backend/app/agent/lock.py` | 去掉 Lua 脚本，用 `CoordinationBackend` | D-ZD.5 |
| `backend/app/agent/queue.py` | 持有 `CoordinationBackend` | D-ZD.6 |
| `backend/app/agent/run.py` | `WsLock` 构造改为 `CoordinationBackend` | 适配 lock 改动 |
| `backend/pyproject.toml` | 新增 `aiosqlite` 依赖 | D-ZD.1 |
| `backend/.env.example` | 更新注释 | D-ZD.8 |
| `backend/tests/test_coordination.py` | **新建** | MemoryBackend 单元测试 |
| `backend/tests/test_sqlite_compat.py` | **新建** | SQLite 模式模型兼容测试 |
| 现有测试文件 | `redis_client` → `coordination_backend` | 适配接口变更 |

---

## 6. 测试策略

### 6.1 单元测试

- **`test_coordination.py`**（新建）：
  - `MemoryBackend` SET / GET / DELETE with TTL —— 基本读写
  - TTL 过期 —— 惰性清理 + 定期扫描
  - SETNX —— 原子性验证（并发 100 个协程同时 SETNX 同一 key，只有 1 个成功）
  - INCR / EXPIRE —— 计数 + 窗口过期
  - ZADD / ZRANK / ZREM —— sorted set 顺序 / 排名 / 删除
  - PUBLISH / SUBSCRIBE —— pub/sub 消息传递
  - 并发安全 —— `asyncio.Lock` 保护下的原子操作验证

- **`test_sqlite_compat.py`**（新建）：
  - 所有模型的 CRUD 在 SQLite 下正常工作
  - JSON 列读写 —— 序列化 / 反序列化正确
  - FK CASCADE —— `PRAGMA foreign_keys=ON` 下级联删除生效
  - FK RESTRICT —— 级联阻止生效
  - `DateTime` 时区 —— 存取一致
  - `Numeric` 精度 —— 12 位 6 小数正常

### 6.2 集成测试

- 现有测试继续使用 PostgreSQL（`asyncpg`），确保回归保护
- 新增 SQLite 模式的端到端测试（`test_e2e_sqlite.py`）：
  - 完整 Run 流程（消息 → 队列 → 执行 → 落盘 → 摘要）
  - WS 锁竞争（同一 WS 连续提交 2 个 Run，第二个排队）
  - 消息去重（重复 message_id 被丢弃）
  - Session 存取（登录 → 请求鉴权 → 登出）

### 6.3 手动联调

- 不配置 `DATABASE_URL` 和 `REDIS_URL`，直接 `uv run uvicorn app.main:app` → 验证零依赖启动
- 飞书群对话 → 验证 Run 正常执行、消息去重、排队
- 关闭服务后重启 → 验证 SQLite 数据持久化（Workspace / Session 历史可查）
- 配置 `DATABASE_URL` → 验证切换到 PostgreSQL，行为一致

---

## 7. 风险与缓解

- **SQLite 写入并发瓶颈**：单写入锁，高并发时串行等待
  - 缓解：WAL 模式下读不阻塞写；单实例小团队并发量低（飞书消息频率 < 10/min）
  - 如需高并发：配置 `DATABASE_URL` 切换到 PostgreSQL

- **MemoryBackend 进程重启丢失**：session / 去重 / 队列状态不持久
  - 缓解：飞书 webhook 会重试（去重窗口 10min 内重启概率低）；session 丢失用户需重新登录（可接受）
  - 如需持久化：配置 `REDIS_URL` 切换到 Redis

- **Alembic batch mode 性能**：SQLite 重建大表耗时
  - 缓解：数据量小（单实例），迁移在启动前执行；batch mode 对 PG 透明

- **JSONB → JSON 类型变更触发 Alembic autogenerate**：PG 下检测到类型变化
  - 缓解：手动调整迁移脚本，用 `alter_column(type_=JSON)` 或忽略类型差异（`compare_type=False` for JSON columns）

- **`redis` 包从必装降为可选**：现有代码 `import redis` 可能在未安装时报错
  - 缓解：`RedisBackend` 内部延迟 import；`redis_client.py` 在 `redis_url` 为空时不 import `redis`

---

## 8. 演进路径（P4+）

- **SQLite 加密**：SQLCipher 支持 SQLite 文件加密，适合个人数据保护
- **SQLite → PostgreSQL 迁移工具**：提供 CLI 命令将 SQLite 数据导出并导入 PostgreSQL
- **MemoryBackend 持久化**：可选将 session / 去重状态写入 SQLite，实现重启恢复
- **多实例自动检测**：启动时检测是否多实例运行，提示切换到 PostgreSQL + Redis
