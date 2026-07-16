# P2 - Emoji 确认回复：设计文档

> 二期迭代。一期 MVP 设计文档见 [../mvp/design.md](../mvp/design.md)。

---

## 1. 整体流程

```
用户消息
  │
  ▼
handle_message
  │
  ├─ 1. add_reaction(message_id, "OnIt")  ← 即时 ack（< 200ms）
  │       └─ 失败 → log warning，继续（best-effort）
  │       └─ 成功 → 保存 reaction_id
  │
  ├─ 2. LLM 配置检查
  │       └─ 未配置 → 发错误卡 → delete_reaction → return
  │
  ├─ 3. run_queue.submit(..., on_done=_on_done_with_reaction)
  │
  │   ... Agent Run 执行中 ...
  │
  └─ 4. on_done 回调触发
          ├─ _on_done_with_cleanup (MVP 原有：MCP 清理 + 卡片 finalize)
          └─ delete_reaction(message_id, reaction_id)  ← 移除表情
                  └─ 失败 → log warning，不影响 Run 状态
```

---

## 2. 关键决策

### D2.1: 表情 vs 卡片 vs 两者并存

| 方案 | 延迟 | 信息量 | 适合场景 |
|---|---|---|---|
| 仅表情 | < 200ms | 低（仅"收到"信号） | 轻量 ack |
| 仅卡片 | 300-800ms | 高（可承载进度文本） | 持续进度 |
| **两者并存** | 表情先到，卡片后至 | 渐进式 | **选择** |

**决策**：两者并存。表情先到给用户即时确认，卡片随后承载持续进度更新。用户看到表情就知道"收到了"，看到卡片就知道"在跑了"。

### D2.2: 表情类型选择 `OnIt`

飞书内置表情 `OnIt`（"收到/在忙"语义）最贴切"已收到正在处理"的含义。其他候选：
- `OK` — 过于简短，缺乏"处理中"语义
- `THUMBSUP` — 偏赞同，语义不准
- `PROCESSING` — 不存在该类型

### D2.3: 表情移除时机

**决策**：在 `on_done` 回调中移除，与 Run 生命周期绑定。

- Run 成功 → 移除表情（用户已看到结果卡片）
- Run 失败 / 中断 → 移除表情（用户已看到错误卡片）
- 排队中取消 → `on_done` 仍会触发（传 `CancelledError`），表情被移除

**不在 `on_start` 移除**：排队期间表情仍在 = "已收到，排队中"，符合用户预期。

### D2.4: best-effort 不重试

表情操作失败（API 限流 / 网络抖动）不重试、不阻断：
- `add_reaction` 失败 → `reaction_id = None`，后续 `on_done` 跳过移除
- `delete_reaction` 失败 → 表情残留（用户手动移除或飞书自动过期），不影响任何系统状态

### D2.5: reaction_id 传递方式

`reaction_id` 作为 `handle_message` 函数内的局部变量，通过闭包捕获传入 `_on_done_with_reaction`：

```python
reaction_id = await client.add_reaction(ctx.message_id, "OnIt")

async def _on_done_with_reaction(exc):
    await _on_done_with_cleanup(exc)  # MVP 原有清理
    if reaction_id:
        await client.delete_reaction(ctx.message_id, reaction_id)
```

不将 `reaction_id` 存入 DB / Run 状态 / Trace——它是纯 UI 层的瞬态状态，生命周期与 `handle_message` 函数调用一致。

---

## 3. 涉及文件

| 文件 | 改动 | 说明 |
|---|---|---|
| `backend/app/feishu/client.py` | 新增 `add_reaction` / `delete_reaction` 方法 | 封装飞书 Reaction API |
| `backend/app/feishu/handler.py` | `handle_message` 追加表情逻辑 | 入口 add + `on_done` 回调 delete |
| `backend/tests/test_cards.py` | 无需改动（表情逻辑在 handler 层，非 cards 层） | — |

> 飞书 SDK `lark_oapi` 已内置 `CreateMessageReactionRequest` / `DeleteMessageReactionRequest`，无需额外依赖。

---

## 4. 飞书 API 细节

### 4.1 添加表情

```
POST /open-apis/im/v1/messages/{message_id}/reactions
Body: { "reaction_type": { "emoji_type": "OnIt" } }
Response: { "data": { "reaction_id": "xxxxx" } }
```

### 4.2 移除表情

```
DELETE /open-apis/im/v1/messages/{message_id}/reactions/{reaction_id}
```

### 4.3 权限要求

- `im:message.reaction:write`（机器人添加 / 删除消息表情）
- 机器人须为群成员

---

## 5. 与 MVP 设计的关系

P2 不引入新的设计决策编号冲突。MVP 的 D38（消息去重）、D39（引用回复）等决策不受影响——表情操作发生在去重校验之后、Run 提交之前，与去重 / 引用逻辑无交集。

MVP F3.1.5（即时反馈）的描述"收到消息后立即回复'思考中'表情 / 卡片"在本期被细化为：
- **表情** = P2 实现的 `OnIt` Reaction（D2.1）
- **卡片** = MVP T4.5 实现的进度卡片（不变）
