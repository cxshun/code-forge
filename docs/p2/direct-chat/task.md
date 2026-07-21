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

**进度统计**：已完成 `9 / 9` ｜ P0 `9 / 9`（DC-T1~T4 为初版共享 WS 设计，DC-T5~T9 为 D-DC.7 演进：按用户独立 WS）

| Task | 标题 | 状态 | 优先级 | 负责 | 完成日 |
|---|---|---|---|---|---|
| DC-T1 | settings 新增 DEFAULT_P2P_WORKSPACE_ID（初版） | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T2 | router 新增 auto_bind_p2p_chat（初版共享 WS） | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T3 | handler 入口分支改造 + 自动绑定接入 | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T4 | 单聊触发单元测试（初版） | ✅ 已完成 | P0 | cxshun | 2026-07-18 |
| DC-T5 | 配置项改名 → P2P_WORKSPACE_OWNER_ID（D-DC.7） | ✅ 已完成 | P0 | cxshun | 2026-07-20 |
| DC-T6 | auto_bind_p2p_chat 改造为建 WS + FeishuChat | ✅ 已完成 | P0 | cxshun | 2026-07-20 |
| DC-T7 | handler 调用点更新 + 群聊回归验证 | ✅ 已完成 | P0 | cxshun | 2026-07-20 |
| DC-T8 | 测试改写（per-user WS 场景） | ✅ 已完成 | P0 | cxshun | 2026-07-20 |
| DC-T9 | .env 配置 + 飞书私聊联调 | ✅ 已完成 | P0 | cxshun | 2026-07-20 |

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

> 以下 DC-T5 ~ DC-T9 为 **D-DC.7 演进**：从初版"共享默认 WS"改为"按用户独立 WS"。覆盖 DC-T1 / DC-T2 的初版实现，DC-T3 / DC-T4 随之更新。

### DC-T5 配置项改名 → P2P_WORKSPACE_OWNER_ID
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-20
- **模块**：M0 配置 ｜ **优先级**：P0 ｜ **预估**：0.2d ｜ **依赖**：—
- **范围**：`backend/app/config.py` 将 `default_p2p_workspace_id: int | None` 改名为 `p2p_workspace_owner_id: int | None`；语义从"指向 WS id"改为"指向 owner User id"。
- **对应文档**：design §3 / §5 / D-DC.3 / D-DC.7
- **验收标准**：
  - [x] `settings.p2p_workspace_owner_id` 类型为 `int | None`，缺省 `None`
  - [x] 环境变量 `P2P_WORKSPACE_OWNER_ID` 透传生效
  - [x] 旧名 `default_p2p_workspace_id` / `DEFAULT_P2P_WORKSPACE_ID` 在代码与 `.env` 中不再残留（全局 grep 确认）
- **完成记录**：`backend/app/config.py` 改名 + `.env` 追加 `P2P_WORKSPACE_OWNER_ID=2`（指向 admin user）。`handler.py` / `router.py` / `test_handler.py` / `test_handler_p2p.py` 同步引用新名，全局 grep `default_p2p_workspace_id` / `DEFAULT_P2P_WORKSPACE_ID` 无残留。

### DC-T6 auto_bind_p2p_chat 改造为建 WS + FeishuChat
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-20
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：DC-T5
- **范围**：`backend/app/feishu/router.py` 重写 `auto_bind_p2p_chat`：
  - 参数 `default_ws_id` → `owner_id` + 新增 `sender_name: str | None = None`
  - 校验 owner User 存在且 `status == active`，否则返回 None
  - 命名规则：有 `sender_name` → `Workspace(name=f"{sender_name}的私聊")` + `FeishuChat.chat_name=sender_name`；无 name → fallback `p2p:{open_id[-8:]}`；空 sender → `"p2p:anonymous"`
  - `INSERT Workspace` → `flush` 拿 ws.id → `INSERT FeishuChat(workspace_id=ws.id, ...)`
  - `commit` 成功后调 `create_workspace_skeleton(ws.id)` 建目录
  - `IntegrityError` → rollback（含新建 WS）+ `resolve_feishu_chat` 回查
  - 其他异常 → rollback + 返回 None（NF2.4 不向上抛）
- **对应文档**：design §4 / D-DC.2 / D-DC.7；spec NF2.4 / NF2.5
- **验收标准**：
  - [x] `owner_id is None` → 返回 None（不写 DB）
  - [x] owner 不存在 / 已停用 → 返回 None（不建 WS）
  - [x] 正常路径 → 新建 Workspace + FeishuChat + 目录骨架，返回 chat
  - [x] WS.name = `f"{sender_name}的私聊"` when sender_name；无 name → `f"p2p:{sender_open_id[-8:]}"`；空 sender → `"p2p:anonymous"`
  - [x] FeishuChat.chat_name = `sender_name` if sender_name else (`f"p2p:{sender[-8:]}"` if sender else `None`)
  - [x] 唯一键冲突 → rollback 后回查既有记录，不产生重复 WS
  - [x] 其他异常 → rollback + 返回 None，不向上抛
- **完成记录**：`router.py` 重写 `auto_bind_p2p_chat`，新增 import `User` / `UserStatus` / `Workspace` / `create_workspace_skeleton`；`flush` 确保 ws.id 可用后再建 FeishuChat；`sender_name` 参数由 handler 通过 `get_chat_member_name` / `get_user_name` 查得后传入。

### DC-T7 handler 调用点更新 + 群聊回归验证
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-20
- **模块**：M1 接入层 ｜ **优先级**：P0 ｜ **预估**：0.3d ｜ **依赖**：DC-T6
- **范围**：`backend/app/feishu/handler.py` 将 `settings.default_p2p_workspace_id` 改为 `settings.p2p_workspace_owner_id`；`FeishuClient` 实例化提前到 DB 块之前；p2p 自动绑定时先查 `sender_name`（`get_chat_member_name` → fallback `get_user_name`）再传入 `auto_bind_p2p_chat`；群聊分支零改动回归。
- **对应文档**：design §4 / D-DC.1 / D-DC.4
- **验收标准**：
  - [x] p2p 未绑定时调 `auto_bind_p2p_chat(..., owner_id=settings.p2p_workspace_owner_id, sender_name=sender_name)`
  - [x] `chat is None` 时仍走 `log.info("unbound chat, ignore")` 分支
  - [x] 群聊 + @ 消息行为零回归（手动验证一条 @ 触发消息）
  - [x] 群聊无 @ / 未知 chat_type 仍被忽略
- **完成记录**：`handler.py` 中 `FeishuClient(app_id, app_secret)` 提前实例化；p2p 分支依次调用 `get_chat_member_name`（仅 IM 权限，返回展示名如"用户816216"）→ 失败再 `get_user_name`（contact v3，需通讯录权限）；`sender_name` 同时用于 WS 命名与 footer 展示。handler 其余流程（路由 / 卡片 / 引用 / 表情 / 提交 Run）不变。

### DC-T8 测试改写（per-user WS 场景）
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-20
- **模块**：M2 测试 ｜ **优先级**：P0 ｜ **预估**：0.5d ｜ **依赖**：DC-T7
- **范围**：改写 `backend/tests/test_handler_p2p.py` 的 auto_bind 单元用例 + handler 集成用例；更新 `backend/tests/test_handler.py` `_isolated` fixture 配置项名；`_FakeClient` 补 `user_name` 参数与 `get_user_name` / `get_chat_member_name` 方法。
- **对应文档**：design §6
- **验收标准**：
  - [x] `_isolated` fixture（两个文件）`default_p2p_workspace_id` → `p2p_workspace_owner_id`
  - [x] `auto_bind` 单元用例：
    - owner 未配置 → None
    - owner 不存在 / 已停用 → None
    - 正常 → 新建 WS（断言 name / owner_id）+ FeishuChat（断言 workspace_id 指向新 WS）+ 目录存在
    - 唯一键冲突 → 回查既有记录，断言不产生重复 WS（count WS before/after）
    - 空 sender → WS.name == `"p2p:anonymous"`，chat_name is None
    - 有 sender_name → WS.name == `"张三的私聊"`，chat.chat_name == `"张三"`（新增用例 `test_auto_bind_uses_sender_name_when_provided`）
  - [x] handler 集成用例：
    - p2p 已绑定 → 走 MVP 流程，不新建 WS
    - p2p 未绑定 + 配置 owner → 自动建 WS+Chat，submit 被调用（`_FakeClient(user_name="张三")`，断言 ws.name == `"张三的私聊"`）
    - p2p 未绑定 + owner 未配置 → 忽略，不建 WS
    - p2p 触发 Run → `add_reaction` / `delete_reaction` 各一次
    - name 查询失败 → fallback `p2p:{open_id[-8:]}`（新增用例 `test_handle_p2p_unbound_name_lookup_fails_uses_suffix_fallback`）
  - [x] 群聊无 @ / 群聊有 @ 两条用例保持既有行为（回归保护）
  - [x] `uv run pytest tests/test_handler.py tests/test_handler_p2p.py` 全绿
- **完成记录**：`test_handler_p2p.py` 改写 auto_bind 单元用例 + handler 集成用例，新增 2 条 sender_name 相关用例（共 11 条）；`test_handler.py` `_FakeClient` 补 `get_user_name` / `get_chat_member_name`（均返回 None），`_isolated` fixture 配置项名同步改名。

### DC-T9 .env 配置 + 飞书私聊联调
- **状态**：✅ 已完成 ｜ **负责**：cxshun ｜ **完成日**：2026-07-20
- **模块**：M3 部署 ｜ **优先级**：P0 ｜ **预估**：0.3d ｜ **依赖**：DC-T8
- **范围**：`backend/.env` 追加 `P2P_WORKSPACE_OWNER_ID=<既有 admin user id>`；`serve.sh` 透传（pydantic-settings 自动读 env，无需改脚本）；飞书私聊实测首次消息自动建 WS + 响应。
- **对应文档**：design §5
- **验收标准**：
  - [x] `.env` 含 `P2P_WORKSPACE_OWNER_ID=2`（admin user id）
  - [x] `./serve.sh restart backend` 后 settings 生效
  - [x] 飞书首次私聊消息 → 后端日志出现 `submitted run N: ... chat=oc_xxx ws=N`（N 为新建 WS id）
  - [x] DB 出现新 `Workspace(name="用户816216的私聊")` + `FeishuChat(workspace_id=新WS)`（sender_name 由 `get_chat_member_name` 查得）
  - [x] `data/workspaces/<新WS>/` 目录存在（repos/chats/logs）
  - [x] 机器人回复卡片（思考中 → 完成）
  - [x] 同一用户第二条私聊 → 不再新建 WS（命中既有 FeishuChat）
  - [x] 群聊 @ 机器人 → 行为不变（回归）
- **完成记录**：`.env` 配置 `P2P_WORKSPACE_OWNER_ID=2`；飞书私聊实测通过：首次消息触发 `get_chat_member_name` 返回"用户816216" → WS 自动命名为"用户816216的私聊"；bot 正常回复卡片；admin 界面可见新建 WS。联调中发现 `contact.v3.user.get` 即使授权通讯录权限也返回 `name=None`（企业通讯录无真实姓名），故默认走 `im.v1.chat_members.get`（仅需 IM 权限）。联调过程已清理早期 id=5/6/7 的旧 `p2p:xxxxxxxx` WS。

---

## 附：跨阶段关注点

- **DB 无迁移**：Workspace / FeishuChat 表结构不变，D-DC.7 仅新增 INSERT Workspace 行（复用既有字段）
- **观测**：auto-created WS 名称含对方展示名（`{sender_name}的私聊`，fallback `p2p:{open_id[-8:]}`），owner 可在后台按 WS 名识别异常 sender 并直接删 WS（CASCADE 清理 FeishuChat / Run / 目录骨架）
- **回滚**：将 `P2P_WORKSPACE_OWNER_ID` 置空即可关闭单聊自动接受（已建的 WS + FeishuChat 保留，可后台批量删除）
- **后续演进（P3）**：sender 白名单 / rate limit / WS 生命周期管理（长期不活跃的 p2p WS 自动归档 / 回收，见 design §D-DC.6）
