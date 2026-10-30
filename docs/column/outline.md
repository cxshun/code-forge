# 专栏大纲：《给 Agent 装上发动机：一个生产级 Coding Agent 的诞生》

> 差异化定位：市面内容两极分化——「100 行玩具 demo」与「框架使用手册」之间，缺的是
> **从能跑到能上生产的那 90% 工程问题**。本专栏以 code-forge（飞书自托管多租户
> Coding Agent）为解剖标本，每篇解决一个真实生产问题。
>
> 每篇固定三段式：**一个设计决策（为什么不用现成方案）→ 一段实现（真实代码切片）
> → 一个踩坑故事**。每篇结尾必须有可演示的里程碑。
>
> 素材索引见同目录 `decisions.md`（决策 D1–D40 + 事故库 + 写作红线）。

## 卷首

- **读者画像**：会用 LLM API、被 demo 与生产之间的鸿沟毒打过1-2 次的后端工程师。
- **不写什么**：prompt 模板合集、模型测评、框架 API 罗列。只写不随模型过时的模式。
- **代码策略**：repo 按章打 tag（`column/ch03`），文中切片标真实路径行号。
- **篇名候选**（系列主标题）：《给 Agent 装上发动机》 / 《造一个能上岗的 Agent》 /
  《Agent 生产化：从 demo 到上岗》

## 第 0 篇 · 为什么 2026 年还要自研 Agent

- **核心问题**：LangChain/CrewAI/OpenAI Agents SDK 都在，Claude Code 直接用不行吗？
- **要点**：三个不自研的理由逐条反驳——深度理解只有造一次才有；飞书生态（国内
  B 端协作入口）没有好的 agent 承载；自托管 = 数据与成本的自主权。给出全系列
  路线图和最终形态截图（README 截图可复用）。
- **素材**：D1/D2/D9；`README.md` 截图管线。
- **里程碑**：最终成品 60 秒演示视频/GIF。

## 第 1 篇 · 最小内核：Agent Loop 就是个 while 循环

- **核心问题**：agent 不是自动驾驶，是「LLM 决策 + 工具执行」的状态循环。
- **要点**：tool use 循环骨架；Provider 抽象（D3）；**mock provider 先行**——测试
  不花钱、不抖动、可断言，276 个测试的底气；流式事件模型设计。
- **素材**：`app/agent/loop.py`、`app/providers/{base,mock_provider,anthropic_provider}.py`；
  D3。
- **里程碑**：终端里跑通「读文件→总结→写文件」，全程 mock provider 单测覆盖。

## 第 2 篇 · 工具系统：能力、边界与扩展

- **核心问题**：工具是 agent 的手——但手该被绑住（安全）还是放开的（能力）？
- **要点**：工具 schema 设计；**D5 反直觉决策**：不用容器沙箱，工作空间软隔离；
  path_guard 子树限定（D17）与 memory/ 特例；Skill 三阶段渐进加载（D15/D16）；
  MCP 挂载与生命周期（D37）。
- **素材**：`app/tools/{base,registry,path_guard,skill}.py`、`app/tools/builtin/`、
  `app/tools/mcp/`；踩坑：anyio cancel scope 跨任务崩溃（`98c8957`）。
- **里程碑**：agent 成功用 grep 定位 bug 并 edit 修复。

## 第 3 篇 · 接上 IM 才是真地狱（样稿已写：`03-im-is-hell.md`）

- **核心问题**：**IM 不是 chat UI**——没有 SSE、有限频、会重推、有群聊路由、
  「引用」语义和你想的不一样。
- **要点**：WebSocket 长连接 vs webhook（D7）；事件转发架构（连接线程 → 业务
  loop，`run_coroutine_threadsafe`）；message_id 幂等去重（D38）；@识别与群路由
  （D13/D21）；Thinking 卡片与 update_card 流式节流（D4）；引用回复的重新设计
  （D39）。
- **素材**：`app/feishu/{handler,dedup,router,cards,quote}.py`；踩坑：卡片引用解析
  （`ebbeb6e`）、p2p 静默失败（`4d4f579`）。
- **里程碑**：群里 @机器人 → Thinking 卡片 → 流式回答 → 引用续聊，完整录屏。

## 第 4 篇 · 并发是生产化的分水岭

- **核心问题**：三个同事同时 @机器人，谁先谁后？跑一半想取消怎么办？后端重启了
  正在跑的任务怎么办？
- **要点**：RunQueue 状态机（排队/运行/取消/中断）；FIFO 公平与 pub/sub 唤醒；
  WsLock 为什么不用独立线程锁——asyncpg 跨 loop 血泪（D20/D14）；1 Session:1 Run
  语义（D23）；启动恢复：孤儿 Run/锁/任务自愈（D36）。
- **素材**：`app/agent/{queue,run,lock}.py`；D14/D20/D23/D36。
- **里程碑**：并发压灌 10 条消息，展示排队序列 + 中途取消 + kill -9 后重启自愈。

## 第 5 篇 · 上下文工程：token 是预算不是垃圾场

- **核心问题**：长任务跑着跑着就爆 context / 答非所问——上下文是被设计出来的，
  不是堆出来的。
- **要点**：四道防线总览（D34）；L2 compaction 按 tool_call_id 配对整段替换（保
  tool_use/tool_result 不断裂）；预算感知的收敛策略（`76cba5f`）；L3 compaction
  后强信号注入；Skill 渐进加载与上下文预算的联动（D16）；跨 session 历史加载
  （D40）。
- **素材**：`app/agent/{context,context_config,session_summary}.py`；CE-T1~T10
  （`995fcce`）。
- **里程碑**：一个必然爆上下文的 200 步任务，展示 compaction 前后的 span 树。

## 第 6 篇 · 记忆：让 agent 记得住、忘得掉

- **核心问题**：跨会话记忆是需求还是诅咒？记住错误的东西比失忆更糟。
- **要点**：Memory 作用域设计（D18：FeishuChat 级）；复用 Write/Edit 而不发明
  memory 工具（D19）；AGENT.md 分层（WS/Repo 级，D24）；写入策略：自主判断 +
  强信号触发 + 陈旧性规则（D22）；注入时机与隔离。
- **素材**：`app/memory/loader.py`、`app/api/memory.py`；D18/D19/D22/D24。
- **里程碑**：教机器人一个项目约定 → 新会话直接生效 → 改掉约定 → 旧记忆被更新。

## 第 7 篇 · 看不见的 Agent 等于没有：可观测性

- **核心问题**：agent 答错了，你猜是 prompt 错了、工具错了还是模型抽风？没有
  trace 全靠玄学。
- **要点**：自建 vs Langfuse（D25）；span 树模型（D27）；contextvars 零侵入采集 +
  缓冲批写降级（D28）；大 payload 落文件（D26/D29）；脱敏管线（D30）；成本引擎
  与告警推飞书；瀑布图如何定位一次劣化。
- **素材**：`app/observability/`（tracer/buffer/payload/redaction/cost/monitor/ttl）、
  `app/api/{traces,insights,monitoring}.py`。
- **里程碑**：录屏：一条慢 Run 从告警到瀑布图定位到「工具重试风暴」的全过程。

## 第 8 篇 · 多租户 SaaS 化：从玩具到平台

- **核心问题**：第一个用户是同事，第 10 个用户是隔壁部门——多 App、多租户隔离、
  密钥安全全部加压。
- **要点**：多 App 连接池架构（D7）；**压轴故事：lark SDK 模块级 loop 竞态**——
  单 App hack 为何在多 App 下互崩、子类化 SDK 的完整修复过程（`b9ce24f`）；
  ORM 强制 ws_id 注入（D31）；secret 加密存储；p2p 按用户独立 WS（`6fc3613`）。
- **素材**：`app/feishu/ws_pool.py`、`app/db/session.py`、`app/core/security.py`。
- **里程碑**：两个真实 App 同时收消息互不干扰（本次修复的验证过程可直接成文）。

## 第 9 篇 · 零依赖开箱即用：工程化的最后一公里

- **核心问题**：「clone 下来跑不起来」杀死的开源项目比烂代码多。
- **要点**：SQLite 默认 + PG 可选的双后端（`3d10183`）；MemoryBackend 兜底；
  启动自建表 + 幂等 init_admin；**踩坑：stdlib logger TypeError 首启崩溃**
  （`77e6e0e`，日志门面统一问题）；alembic GBK 崩溃彩蛋（`29ae9e1`）；deploy/
  生产三件套。
- **素材**：`app/config.py`、`app/db/{session,init}.py`、`docs/p3/zero-deps/`。
- **里程碑**：全新机器 `clone → uv run uvicorn` 3 分钟跑通全功能。

## 第 10 篇 · 事故复盘专刊：两次数据丢失教会我的事

- **核心问题**：agent 系统的测试设施本身就是危险武器——`reset_all()` 曾把 dev 库
  全表 TRUNCATE，app_secret 永久丢失；造演示数据时 `rm -rf` 删掉真实会话文件。
- **要点**：两次事故完整时间线；三层测试隔离防护（APP_ENV 前置 / DSN 强制切换 /
  assert 护栏）；破坏性操作的确认纪律；**为什么备份策略对个人项目更重要**；
  D35（不自动 push）与信任边界的呼应。
- **素材**：`tests/conftest.py`、`app/config.py:pg_dsn_effective`、decisions.md
  事故索引。
- **里程碑**：本篇无代码里程碑，以「现在仓库里的三层防护清单」收尾。

## 番外（按读者反馈排期）

- 并行子代理与 worktree 隔离（D33，L2/L3 演进）
- 管理前端设计复盘（D12）
- Provider 适配细节：Anthropic / OpenAI 兼容层 / reasoning 字段处理
- 专栏写作本身：编号决策体系（design.md 的 D-编号）如何反哺工程效率

## 发布节奏与防烂尾

- 存稿 3 篇再开更；周更或双周更；每篇 3000–5000 字。
- 每篇发出前对照 `decisions.md` 的**写作红线**过一遍敏感信息。
- 数据反馈决定番外排序；烂尾保险：第 5/7/8 篇是干货核心，优先保证。
