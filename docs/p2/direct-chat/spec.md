# P2 - 单聊触发支持：需求规格

> 子主题：[direct-chat](./)。P2 总览见 [../README.md](../README.md)。
> 一期 MVP 文档见 [../../mvp/spec.md](../../mvp/spec.md)（注：MVP 暂不支持私聊 F3.1.2）。

---

## 1. 背景与目标

### 1.1 问题

MVP F3.1.2 / D13 明确"仅支持群聊，私聊暂不做"，接入层 `handle_message` 在 `chat_type != "group" or not at_bot` 时直接 return（`backend/app/feishu/handler.py:109-112`）。

但实际使用中，owner 希望在飞书单聊里直接与机器人对话（不必拉群、不必 @），用于：
- 个人快速问答 / 调试 Agent
- 1对1 私密场景（不希望被群成员看到 memory / 输出）
- 移动端随手用（手机拉群体验差）

### 1.2 目标

放开单聊（p2p）触发，任意好友消息自动落到 owner 预先配置的**默认 WS**：

- 单聊场景**无需 @**，每条消息都触发 Run（与群聊"@ 才触发"形成对比）
- 首次收到未绑定的 p2p chat_id 时，自动创建 FeishuChat 记录并指向默认 WS
- 复用 MVP 路由 / 卡片 / 引用 / D38 去重 / D39 引用回复等全部既有机制
- 复用 P2 [emoji-reply](../emoji-reply/spec.md) 的 `OnIt` 表情 ack 体验

### 1.3 非目标

- **不做用户白名单**：MVP 接受"任意加好友即可触发"的资源风险（design §D-DC.3 风险与缓解）
- **不做按 sender 路由**：所有单聊消息都落到同一个默认 WS（不区分 sender 归属）
- **不区分单聊 chat_type 子类**（如机器人互聊、用户单聊）：MVP 只处理用户发起的 p2p
- **不修改 MVP 群聊逻辑**：群聊场景保持"@ 才触发"不变

---

## 2. 功能性需求

> 编号接续 [emoji-reply F2.1–F2.6](../emoji-reply/spec.md)。本子主题范围 F2.7–F2.13。

- **F2.7** 收到 `chat_type == "p2p"` 的消息事件时，跳过 @ 校验，直接进入 Run 提交流程
- **F2.8** 首次收到未绑定的 p2p `(app_id, chat_id)` 时，自动创建 FeishuChat 记录，`workspace_id` 取自配置项 `DEFAULT_P2P_WORKSPACE_ID`
- **F2.9** 未配置 `DEFAULT_P2P_WORKSPACE_ID` 时，单聊消息按"未绑定"处理（log warning + 忽略，不创建记录）
- **F2.10** 单聊场景复用 MVP 全部既有机制：
  - 路由解析（`resolve_feishu_chat`，唯一键 `(app_id, chat_id)`）
  - D38 去重（按 message_id）
  - D39 引用回复（parent_id 拉被引用消息正文）
  - 卡片生命周期（排队 / 思考中 / 完成）
  - WS 写锁串行（D20）
- **F2.11** 单聊场景复用 P2 [emoji-reply](../emoji-reply/spec.md) 的 `OnIt` 表情 ack 与 `on_done` 移除流程，无需差异化处理
- **F2.12** 自动创建的 FeishuChat 记录的 `chat_name` 字段持久化 sender_open_id 后 8 位（便于 owner 在后台识别来源），可后续手工修正
- **F2.13** 群聊场景的触发逻辑（`chat_type == "group" and at_bot`）**不变**——单聊与群聊在 handler 入口按 `chat_type` 分支判断，互不影响

---

## 3. 非功能性需求

- **NF2.4** 自动创建 FeishuChat 写 DB 失败时降级为"未绑定"处理（log warning + 忽略），不阻断主流程、不抛到接入层之外
- **NF2.5** 单聊触发不受默认 WS 的 owner 离职 / 软删除影响——若默认 WS 不存在 / 已删除，按"未绑定"处理
- **NF2.6** 默认 WS 配置项通过环境变量 / settings 注入，不要求在飞书后台或机器人侧做任何额外配置
- **NF2.7** 自动绑定产生的 FeishuChat 记录在后台可见、可解绑、可改绑到其他 WS（与手工绑定的记录无差别）

---

## 4. 约束与假设

- **机器人需先被用户加为好友**：单聊消息事件才会推送（飞书原生约束）
- **`DEFAULT_P2P_WORKSPACE_ID` 必须存在且 owner 有权使用**：否则按未绑定处理
- **同一 `(app_id, user_open_id)` 的 p2p chat_id 在飞书侧稳定**：一个用户对一个机器人只有一个 p2p chat_id，自动绑定的 FeishuChat 记录不会重复创建（依赖 `(app_id, chat_id)` 唯一键）
- **资源风险**：任意好友即可触发 Run → 恶意用户可耗尽 LLM 配额；MVP 不做限流，由 owner 自行控制机器人好友列表

---

## 5. 与 MVP / P2 emoji-reply 的关系

| 来源 | 关系 | 说明 |
|---|---|---|
| MVP F3.1.2 "暂不支持私聊" | **覆盖** | 本子主题放开 p2p 触发，F3.1.2 的"MVP 暂不支持"约束在 P2 阶段失效 |
| MVP F3.1.3 "群聊场景下识别 @ 机器人触发" | **不变** | 群聊仍要 @；单聊分支独立处理 |
| MVP D8 "FeishuChat 唯一键 (app_id, chat_id)" | **复用** | 单聊 chat_id 直接存入，无需改表 |
| MVP D21 "无权限模型（拉群即用）" | **延伸** | 单聊场景对等为"加好友即用"，权限边界移交飞书好友关系 |
| MVP D13 "聊天场景 = 群聊为主" | **修订** | P2 后群聊 + 单聊并行支持，不再是"群聊为主" |
| P2 emoji-reply F2.1–F2.6 | **复用** | 单聊场景同样打 `OnIt` 表情 / Run 完成后移除 |

> 本子主题不修改 MVP 既有文档；MVP 的"暂不支持私聊"约束在 P2 设计文档 [design.md §D-DC.5](./design.md) 中明确"按 P2 覆盖"。
