# P2 - Emoji 确认回复：开发任务列表

> 任务拆分依据：[spec.md](./spec.md)（需求）/ [design.md](./design.md)（设计）。
> 一期 MVP 任务列表见 [../../mvp/task.md](../../mvp/task.md)。

---

## 0. 图例与约定

- **优先级**：`P0` 必做且阻塞主流程 ｜ `P1` 必做但非阻塞 ｜ `P2` 后续预留
- **状态**：`⚪ 未开始` ｜ `🔵 进行中` ｜ `✅ 已完成` ｜ `⛔ 阻塞`
- **维护方式**：同 MVP task.md §0

---

## 状态总览

**进度统计**：已完成 `2 / 2` ｜ P0 `2 / 2`

| Task | 标题 | 状态 | 优先级 | 负责 | 完成日 |
|---|---|---|---|---|---|
| P2-T1 | 飞书 Reaction API 客户端封装 | ✅ 已完成 | P0 | cxshun | 2026-07-16 |
| P2-T2 | handle_message 表情 ack 接入 | ✅ 已完成 | P0 | cxshun | 2026-07-16 |

---

## 任务详情

### P2-T1 飞书 Reaction API 客户端封装
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-16
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：—
- **范围**：在 `FeishuClient` 中封装 `add_reaction` / `delete_reaction` 方法，调用飞书 IM Reaction API。
- **对应文档**：design §4；spec F2.1 / F2.6
- **验收标准**：
  - [x] `add_reaction(message_id, emoji_type)` 返回 `reaction_id`
  - [x] `delete_reaction(message_id, reaction_id)` 无返回值
  - [x] 使用 `asyncio.to_thread` 包装 SDK 同步调用（与既有方法一致）
  - [x] 复用 `_check()` 错误处理
- **完成记录**：`backend/app/feishu/client.py` 新增 `add_reaction`（`CreateMessageReactionRequest` + `Emoji.builder()`）和 `delete_reaction`（`DeleteMessageReactionRequest`），均通过 `asyncio.to_thread` 包装 SDK 同步调用，`_check()` 统一错误处理。默认 emoji_type=`OnIt`。

### P2-T2 handle_message 表情 ack 接入
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-16
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：P2-T1
- **范围**：在 `handle_message` 入口添加表情、在 `on_done` 回调移除表情；LLM 未配置时也移除。
- **对应文档**：design §1 / §2；spec F2.1–F2.5
- **验收标准**：
  - [x] 收到消息后立即在用户消息上添加 `OnIt` 表情
  - [x] `reaction_id` 通过闭包传递到 `on_done` 回调
  - [x] Run 完成（成功 / 失败 / 中断）后移除表情
  - [x] LLM 未配置时发错误卡后移除表情
  - [x] 表情操作失败不阻断主流程（best-effort，log warning）
- **完成记录**：`backend/app/feishu/handler.py` `handle_message` 改动：
  1. 入口处 `client.add_reaction(ctx.message_id, "OnIt")` → 保存 `reaction_id`（try/except 降级）
  2. LLM 未配置分支：发错误卡后 `delete_reaction` 清理
  3. 新增 `_on_done_with_reaction` 包装 `_on_done_with_cleanup`（MVP 原有 MCP 清理 + 卡片 finalize），追加 `delete_reaction`
  4. `run_queue.submit` 的 `on_done` 从 `_on_done_with_cleanup` 改为 `_on_done_with_reaction`
  表情操作全部 try/except 包裹，失败仅 log warning 不影响 Run 状态 / Trace。

---

## 附：跨阶段关注点

- **best-effort 降级**：表情操作失败不重试、不阻断、不污染 Run 状态（对齐 MVP "失败降级"原则）
- **权限前置**：机器人需有 `im:message.reaction:write` 权限且在群内，否则表情添加静默失败
- **无 DB / Trace 变更**：`reaction_id` 是纯 UI 层瞬态状态，不落盘、不入 Trace
