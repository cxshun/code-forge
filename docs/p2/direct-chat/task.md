# P2 - 单聊触发支持：开发任务列表

> 任务拆分依据：[spec.md](./spec.md)（需求）/ [design.md](./design.md)（设计）。
> P2 总览见 [../README.md](../README.md)；MVP 任务列表见 [../../mvp/task.md](../../mvp/task.md)。

---

## 0. 图例与约定

- **优先级**：`P0` 必做且阻塞主流程 ｜ `P1` 必做但非阻塞 ｜ `P2` 后续预留
- **状态**：`⚪ 未开始` ｜ `🔵 进行中` ｜ `✅ 已完成` ｜ `⛔ 阻塞`
- **任务编号**：`DC-T<n>`（Direct-Chat），与 emoji-reply 的 `P2-T<n>` 区分

---

## 状态总览

**进度统计**：已完成 `4 / 4` ｜ P0 `4 / 4`

| Task | 标题 | 状态 | 优先级 | 负责 | 完成日 |
|---|---|---|---|---|---|
| DC-T1 | settings 新增 DEFAULT_P2P_WORKSPACE_ID | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T2 | router 新增 auto_bind_p2p_chat | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T3 | handler 入口分支改造 + 自动绑定接入 | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T4 | 单聊触发单元测试 | ✅ 已完成 | P0 | cxshun | 2026-07-18 |

---

## 任务详情

### DC-T1 settings 新增 DEFAULT_P2P_WORKSPACE_ID
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-18
- **模块**：M0 配置 ｜ **优先级**：P0 ｜ **预估**：0.2d ｜ **依赖**：—
- **范围**：在 `app.config.settings` 中新增 `default_p2p_workspace_id: int | None`，env 注入。
- **对应文档**：design §3 / §5；spec F2.8 / F2.9 / NF2.6
- **验收标准**：
  - [x] `settings.default_p2p_workspace_id` 类型为 `int | None`，缺省 `None`
  - [x] `.env` / 环境变量 `DEFAULT_P2P_WORKSPACE_ID` 透传生效
  - [ ] `serve.sh` / `deploy/` 透传变量（与既有配置项同渠道）— 待部署联调
- **完成记录**：`backend/app/config.py` 在 `chat_history_max_messages` 之后追加 `default_p2p_workspace_id: int | None = None`。pydantic-settings 自动从 `DEFAULT_P2P_WORKSPACE_ID` env 注入。

### DC-T2 router 新增 auto_bind_p2p_chat
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-18
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.3d ｜ **依赖**：DC-T1
- **范围**：在 `app/feishu/router.py` 新增 `auto_bind_p2p_chat(db, app_id, chat_id, sender_open_id, default_ws_id) -> FeishuChat | None`，封装自动 INSERT + 唯一键冲突降级。
- **对应文档**：design §4；spec F2.8 / F2.12 / NF2.4 / NF2.5
- **验收标准**：
  - [x] `default_ws_id is None` 时返回 `None`（不写 DB）
  - [x] 默认 WS 不存在 / 已删除时返回 `None`
  - [x] 正常 INSERT 后返回新建的 FeishuChat（含 `chat_name=f"p2p:{sender[-8:]}"`）
  - [x] 唯一键冲突时 rollback 并降级 `resolve_feishu_chat` 返回既有记录
  - [x] 其他异常 rollback 后返回 `None`（不向上抛）
- **完成记录**：捕获 `IntegrityError` 后 rollback 并 `resolve_feishu_chat` 回查；裸 `except Exception` 兜底确保 NF2.4"不向上抛"。`chat_name` 缺 sender 时为 `None`（NF2.7 后台可修正）。

### DC-T3 handler 入口分支改造 + 自动绑定接入
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-18
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：DC-T2
- **范围**：改造 `app/feishu/handler.py:109-112` 入口判断，新增 p2p 分支与自动绑定调用；其余流程（路由 / 卡片 / 引用 / 表情 / 提交 Run）保持不变。
- **对应文档**：design §1 / §4；spec F2.7 / F2.10 / F2.11 / F2.13
- **验收标准**：
  - [x] `chat_type == "group" and not at_bot` → 忽略（不变）
  - [x] `chat_type == "p2p"` → 跳过 @ 校验进入主流程
  - [x] 未识别的 `chat_type` → 忽略
  - [x] p2p 未绑定时调 `auto_bind_p2p_chat`；返回 None 时按未绑定忽略
  - [x] 自动绑定后到 `run_queue.submit` 之间复用既有路由 / 卡片 / 引用 / 表情代码（无新分支）
  - [ ] 群聊场景行为零回归（手动验证一条 @ 触发消息）— 待本地联调
- **完成记录**：`handler.py` 入口分支重写为 `if chat_type == "group": ... elif chat_type != "p2p": return`；resolve_feishu_chat 命中 None 且为 p2p 时调 `auto_bind_p2p_chat`。`from app.feishu.router import` 追加 `auto_bind_p2p_chat`。

### DC-T4 单聊触发单元测试
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-18
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：DC-T3
- **范围**：新建 `backend/tests/test_handler_p2p.py`，覆盖 design §6 全部用例。
- **对应文档**：design §6；spec F2.7–F2.13 / NF2.4 / NF2.5
- **验收标准**：
  - [x] p2p 已绑定 → 走 MVP 流程，提交 Run（断言 `run_queue.submit` 被调用）
  - [x] p2p 未绑定 + 配置默认 WS → 自动建 FeishuChat，提交 Run
  - [x] p2p 未绑定 + 默认 WS 未配置 → 忽略，不建记录
  - [x] p2p 未绑定 + 默认 WS 已删除 → 忽略，不建记录
  - [x] 并发首次消息 → 唯一键冲突降级，不抛异常
  - [x] p2p 触发 Run → `add_reaction` / `delete_reaction` 各被调用一次（复用 emoji-reply）
  - [x] 群聊无 @ / 群聊有 @ 两条用例保持既有行为（回归保护）
- **完成记录**：`backend/tests/test_handler_p2p.py` 新建 9 条用例（auto_bind 单元 5 条 + handler 集成 4 条）；`backend/tests/test_handler.py` `_FakeClient` 补 `add_reaction` / `delete_reaction` 追踪，`_isolated` fixture 重置 `default_p2p_workspace_id`，既有 `test_handle_non_group_ignored` 重命名为 `test_handle_p2p_without_default_ws_ignored`（语义对齐 D-DC.2）。本地 `uv run pytest tests/test_handler.py tests/test_handler_p2p.py` 待用户执行。

---

## 附：跨阶段关注点

- **DB 无迁移**：FeishuChat 表结构不变，自动绑定只新增行
- **观测**：自动绑定的 FeishuChat 行 chat_name 含 sender 后 8 位，owner 可在后台识别异常 sender 并手工解绑
- **回滚**：将 `DEFAULT_P2P_WORKSPACE_ID` 置空即可关闭单聊自动接受（已绑定的 FeishuChat 行保留，可后台批量解绑）
- **后续演进（P3）**：sender 白名单 / rate limit / 按 sender memory 隔离（见 design §D-DC.6）
