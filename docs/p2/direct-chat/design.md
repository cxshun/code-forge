# P2 - 单聊触发支持：设计文档

> 子主题：[direct-chat](./)。需求见 [spec.md](./spec.md)。
> P2 总览见 [../README.md](../README.md)；MVP 设计见 [../../mvp/design.md](../../mvp/design.md)。

---

## 1. 整体流程

```
飞书消息事件 (im.message.receive_v1)
  │
  ▼
parse_message_event → MessageContext(chat_type, at_bot, ...)
  │
  ├─ chat_type == "group"
  │     ├─ at_bot=False → 忽略（MVP 不变）
  │     └─ at_bot=True  → 走 MVP 群聊流程（不变）
  │
  └─ chat_type == "p2p"  ← P2 新增分支
        │
        ├─ D38 去重（不变）
        │
        ├─ resolve_feishu_chat(app_id, chat_id)
        │     ├─ 命中 → 走 MVP 流程（路由 / 卡片 / 引用 / 提交 Run）
        │     └─ 未命中 → 自动绑定分支 ↓
        │
        ├─ 自动绑定（D-DC.2）：
        │     ├─ DEFAULT_P2P_WORKSPACE_ID 未配置 → log warning + 忽略
        │     ├─ 默认 WS 不存在 / 已删 → log warning + 忽略（NF2.5）
        │     └─ INSERT FeishuChat(app_id, chat_id, workspace_id=默认, chat_name=sender 后 8 位)
        │           └─ 失败（含唯一键冲突）→ 降级为"未绑定"忽略（NF2.4）
        │
        ├─ 表情 ack（复用 emoji-reply：add_reaction OnIt）
        │
        └─ run_queue.submit(..., on_done=emoji-reply 的 _on_done_with_reaction)
              └─ Run 完成 → 移除表情（不变）
```

---

## 2. 关键决策

### D-DC.1: 按 `chat_type` 分支，单聊无需 @

- **规则**：handler 入口按 `chat_type` 分支
  - `"group"` → 维持 MVP 群聊约束（必须 `at_bot`）
  - `"p2p"` → 跳过 @ 校验，每条消息都触发
- **理由**：单聊里 @ 概念不存在（机器人本身就是会话对象），强行要求 @ 反而违反飞书交互直觉
- **代码位置**：`backend/app/feishu/handler.py:109-112` 的 if 条件改造为分支判断

### D-DC.2: 自动绑定（首次见到即建 FeishuChat）

- **规则**：未绑定的 p2p chat_id 不再直接忽略，而是尝试 INSERT 一条 FeishuChat 记录指向默认 WS
- **唯一性保证**：依赖 FeishuChat 既有 `(app_id, chat_id)` 唯一键（D8）；并发首次消息时 INSERT 失败的那一方降级忽略，不影响一致性
- **chat_name 取值**：`f"p2p:{sender_open_id[-8:]}"`，便于后台识别来源；owner 可后续手工修正为有意义的名字
- **理由**：与"任意单聊自动接受（默认 WS）"的产品定位一致；省去 owner 手工收集 chat_id 的成本

### D-DC.3: 默认 WS 单一全局配置

- **规则**：新增 settings 项 `DEFAULT_P2P_WORKSPACE_ID: int | None`，所有 App 的所有单聊消息共享同一个默认 WS
- **不做的事**：
  - 不按 App 区分默认 WS（避免配置矩阵膨胀）
  - 不按 sender 路由（违背"无权限模型"原则）
- **理由**：MVP 阶段 owner 通常只有一个主力 WS；多 App 共享同一默认 WS 足以覆盖绝大多数场景；后续如需按 App 区分可在 P3 演进
- **配置方式**：环境变量 `DEFAULT_P2P_WORKSPACE_ID`，缺省为 `None`（关闭单聊自动绑定）

### D-DC.4: 复用既有 MVP / P2 全部机制

| 机制 | 来源 | 单聊复用方式 |
|---|---|---|
| 路由 `(app_id, chat_id) → FeishuChat` | MVP D8 / `router.py` | 不变，自动绑定后走同一查询 |
| D38 去重 | MVP | 不变 |
| D39 引用回复 | MVP | 单聊里引用上一条消息同样生效 |
| 卡片生命周期（排队 / 思考中 / 完成） | MVP T4.5 | 不变 |
| WS 写锁串行 | MVP D20 | 单聊与群聊触发同一 WS 时共享队列 |
| OnIt 表情 ack + 移除 | P2 emoji-reply F2.1–F2.6 | 不变，handler 入口对 p2p 分支同样调 `add_reaction` |

**含义**：D-DC.x 不引入新的卡片 / 表情 / 路由分支逻辑，仅在"是否触发 Run"和"未绑定时是否自动建记录"两点上放宽。

### D-DC.5: 显式覆盖 MVP F3.1.2 / D13

- **覆盖点**：
  - MVP F3.1.2 "支持群聊场景（MVP 暂不支持私聊）" → P2 后放开 p2p
  - MVP D13 "聊天场景 = 群聊为主（MVP）" → P2 后群聊 + 单聊并行
- **不修改 MVP 文档**：MVP 文档保持原状作为一期快照；P2 的覆盖关系在本设计文档中显式声明，避免回溯改写历史决策
- **理由**：保留 MVP 文档的"时间点真相"，让 P2 的演进可追溯

### D-DC.6: 资源风险与缓解策略

- **风险**：
  - 任意好友可触发 Run → 恶意用户耗尽 LLM 配额
  - 默认 WS 被多个 sender 共享 → memory 融合污染（D22 已接受群聊同等问题，单聊场景同样接受）
- **缓解（MVP 阶段）**：
  - **不做限流**：依赖 owner 自行控制机器人好友列表（飞书侧拉黑即可切断）
  - **不做 sender 白名单**：与 D21 "无权限模型"原则一致
  - **观测**：自动绑定的 FeishuChat 记录 chat_name 含 sender 后 8 位，owner 可在后台识别异常 sender 并手工解绑
- **P3 演进方向（不在本期）**：
  - sender 白名单（owner 配置允许触发的 open_id 列表）
  - rate limit（按 sender / 按 App 限频）
  - 按(sender) memory 隔离（而非共享默认 WS memory）

---

## 3. 涉及文件

| 文件 | 改动 | 说明 |
|---|---|---|
| `backend/app/config.py` | 新增 `DEFAULT_P2P_WORKSPACE_ID: int \| None` | 全局 settings 项，env 注入 |
| `backend/app/feishu/handler.py` | 入口分支改造 + 自动绑定调用 | `chat_type` 分支判断、p2p 未命中时调 `auto_bind_p2p_chat` |
| `backend/app/feishu/router.py` | 新增 `auto_bind_p2p_chat(db, app_id, chat_id, sender_open_id) -> FeishuChat \| None` | 封装自动 INSERT 逻辑，含唯一键冲突降级 |
| `backend/tests/test_handler_p2p.py` | 新增 | 覆盖 F2.7–F2.13 主路径与降级分支 |

> 不需要 DB 迁移：FeishuChat 表结构不变（D-DC.2 复用既有字段）。

---

## 4. 自动绑定伪代码

`router.py` 新增：

```python
async def auto_bind_p2p_chat(
    db: AsyncSession,
    app_id: str,
    chat_id: str,
    sender_open_id: str,
    default_ws_id: int | None,
) -> FeishuChat | None:
    """p2p chat 未绑定时自动建记录指向默认 WS；失败返回 None。"""
    if default_ws_id is None:
        return None
    ws = await db.get(Workspace, default_ws_id)
    if ws is None:
        return None
    chat = FeishuChat(
        app_id=app_id,
        chat_id=chat_id,
        workspace_id=default_ws_id,
        chat_name=f"p2p:{sender_open_id[-8:]}" if sender_open_id else None,
    )
    db.add(chat)
    try:
        await db.commit()
        await db.refresh(chat)
        return chat
    except IntegrityError:  # 唯一键冲突 = 并发首次消息，对方已建记录
        await db.rollback()
        return await resolve_feishu_chat(db, app_id, chat_id)
```

`handler.py` 入口分支改造（伪代码，仅示意关键差异）：

```python
# 旧：
if ctx.chat_type != "group" or not ctx.at_bot:
    return

# 新：
if ctx.chat_type == "group":
    if not ctx.at_bot:
        return
elif ctx.chat_type == "p2p":
    pass  # 跳过 @ 校验
else:
    return  # 未知 chat_type，忽略

# ... D38 去重后 ...
async with async_session_factory() as db:
    chat = await resolve_feishu_chat(db, ctx.app_id, ctx.chat_id)
    if chat is None and ctx.chat_type == "p2p":
        chat = await auto_bind_p2p_chat(
            db, ctx.app_id, ctx.chat_id, ctx.sender_open_id,
            settings.default_p2p_workspace_id,
        )
    if chat is None:
        log.info("unbound chat, ignore: app=%s chat=%s", ctx.app_id, ctx.chat_id)
        return
    # ... 原 MVP 路由 / 卡片 / 引用 / 提交流程不变 ...
```

---

## 5. 配置示例

`.env` 追加：

```
# 单聊自动绑定目标 WS（不配置则关闭单聊自动接受）
DEFAULT_P2P_WORKSPACE_ID=1
```

部署侧需在 `serve.sh` / `deploy/` 中将该变量透传到容器（与既有 `ANTHROPIC_API_KEY` 等配置项同渠道）。

---

## 6. 测试覆盖要点

| 用例 | 期望 |
|---|---|
| p2p 消息 + 已绑定 FeishuChat | 走 MVP 流程，提交 Run |
| p2p 消息 + 未绑定 + 配置默认 WS | 自动建 FeishuChat，提交 Run |
| p2p 消息 + 未绑定 + 未配置默认 WS | log warning + 忽略，不建记录 |
| p2p 消息 + 未绑定 + 默认 WS 已删除 | 忽略，不建记录（NF2.5） |
| p2p 消息 + 并发首次消息 | 唯一键冲突 → 降级查既有记录，不抛异常（NF2.4） |
| p2p 消息触发 Run | OnIt 表情 ack + 完成后移除（F2.11 复用 emoji-reply） |
| 群聊无 @ 消息 | 忽略（不变） |
| 群聊 + @ 消息 | 走 MVP 群聊流程（不变） |

---

## 7. 与 P2 emoji-reply 的关系

单聊分支在 handler 入口与 emoji-reply 共享同一段 `add_reaction` / `_on_done_with_reaction` 代码，不重复实现：

- emoji-reply 已经把表情 ack 逻辑下沉到 `handle_message` 主流程（而非 group 专用分支）
- direct-chat 仅扩展触发条件 + 自动绑定，对 emoji 逻辑零改动

详见 emoji-reply [design.md §1](../emoji-reply/design.md) 流程图——本文档的"表情 ack"节点直接复用其实现。
