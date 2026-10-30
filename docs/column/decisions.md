# 专栏素材库：设计决策索引（D1–D40）

> 来源：`docs/mvp/design.md` 的编号决策体系。这套「每个决策有编号、有 why」的开发方式本身就是专栏的差异化卖点——文中所有「为什么不用 X」段落都从这里取材。
> 「章节」对应 `outline.md` 篇目；⭐ = 故事性强，建议展开讲；素材不重复 POV，一篇只讲透一个决策。

## 决策总表

| # | 决策 | 一句话 why / 故事点 | 章节 |
|---|------|---------------------|------|
| D1 | 部署形态 = 云端 Web 服务 | 不做本地 CLI，agent 要 7x24 在线收消息 | 0 |
| D2 | 使用范围 = 多租户 | 从一开始就按 SaaS 设计，租户隔离贯穿所有表 | 8 |
| D3 | LLM 选型 = 多模型可切换 | Provider 抽象先行，mock provider 让 276 个测试不花一分钱 ⭐ | 1 |
| D4 | 飞书交互 = 文本 + 富卡片 | 卡片是 IM 里唯一的「流式 UI」，也是限频重灾区 | 3 |
| D5 | 代码执行 = 不用沙箱，工作空间软隔离 | ⭐ 反直觉决策：path_guard 子树限定 vs 容器沙箱的取舍 | 2 |
| D6 | 项目代码来源 = 多 Repo + Git clone | SSH 优先/HTTPS 可选/无 OAuth——最小可用闭环 | 2 |
| D7 | 飞书应用 = 企业自建应用，支持多 App | 多 App 是后来所有连接池故事的根源 ⭐ | 3/8 |
| D8 | Workspace : FeishuChat = 1:N，Chat 独占 | 一个群只能绑一个工作空间，杜绝路由歧义 | 3/8 |
| D9 | 后端语言 = Python | asyncio 生态 + LLM SDK 一等公民 | 0 |
| D10 | 工作空间管理 = Web 管理后台 | agent 系统的「控制面」不该在聊天窗口里 | 9 |
| D11 | Skill/MCP = 全局广场 + 上传 + WS 引用挂载 | 广场复用 vs 私有隔离的平衡 | 2 |
| D12 | 前端 = Vue 3 + Element Plus | 控制面够用就好，重心在后端 | 番外 |
| D13 | 聊天场景 = 群聊为主（MVP） | 群聊才有 @路由、去重这些「IM 特有问题」 | 3 |
| D14 | Run 调度 = 同 WS 多 Run 共存（写串行） | ⭐ 读并发、写排队——WsLock 的设计前提 | 4 |
| D15 | Skill 形态 = 一个目录 | 对齐 Anthropic Agent Skills 约定，zip 上传即装 | 2 |
| D16 | Skill 加载 = 按需 invoke（3 阶段渐进式） | 名字+描述常驻，正文按需——上下文预算的经典取舍 | 2/5 |
| D17 | WS 内路径安全 = 工具强制限定 repos/ 子树 | ⭐ path_guard 是 D5 的执行面，memory/ 前缀是后加的特例 | 2 |
| D18 | Memory 作用域 = FeishuChat 级 | 跨 session 持久、跨群隔离——群是用户的「项目」隐喻 | 6 |
| D19 | Memory 写入 = 复用内置 Write/Edit | 不发明 memory 工具，agent 已会写文件 | 6 |
| D20 | WS 写锁 = 工作空间级串行写 | ⭐ 为什么不用独立线程锁：asyncpg 跨 loop 的血泪 | 4 |
| D21 | 群聊权限 = 无权限模型（拉群即用） | MVP 主动砍掉的功能，写砍掉什么比写做了什么更难 | 3 |
| D22 | Memory 写入策略 = Agent 自主 + 强信号触发 | ⭐ 与「陈旧性」的攻防，prompt 里怎么下规则 | 6 |
| D23 | 会话语义 = 1 Session : 1 Run | 把「一次任务」作为一等公民，不是聊天记录 | 4 |
| D24 | AGENT.md = 项目级指令文件（WS 级 + Repo 级） | 给 agent 的 README：分层注入的优先级设计 | 6 |
| D25 | 可观测性存储 = 自建，不接第三方平台 | ⭐ Langfuse 们为什么不够：多租户+成本+自托管 | 7 |
| D26 | 采集粒度 = 分层（元数据入库，大 payload 落文件） | 数据库存 blob 是反模式 | 7 |
| D27 | Trace 模型 = span 树（单表自引用） | 一张表支持任意嵌套，瀑布图的数据基础 | 7 |
| D28 | 采集机制 = contextvars + 内存缓冲批写 | ⭐ 零侵入采集；缓冲满了怎么办（降级策略） | 7 |
| D29 | Trace payload = 独立 traces/ 目录 | 与 session JSONL 分家，各自的生命周期 | 7 |
| D30 | 敏感信息脱敏 = 落盘前管线化 | 不依赖 agent 自觉——安全要做成管线不做约定 | 7 |
| D31 | Trace 隔离 = WS 边界，ORM 强制注入 ws_id | 忘写 where 就泄露全租户？让 ORM 替你写 | 8 |
| D32 | 管理后台鉴权 = 自建账号密码 | 不接飞书 SSO 的取舍 | 9 |
| D33 | 并行子代理 = 单 Run 内并行（L1），worktree/DAG 预留 | 分级演进而非一步到位 | 番外 |
| D34 | 上下文管理 = 自研四道防线（Provider 无关） | ⭐ 全文最重的决策，compaction 按 tool_call_id 配对的细节 | 5 |
| D35 | 代码交付 = 本地副本 + diff 预览卡片，不自动 push | agent 的手该伸多长：写权限与信任边界 ⭐ | 3/10 |
| D36 | 启动恢复 = 孤儿 Run/锁/任务清理 | 崩溃是常态：重启后世界如何自愈 | 4 |
| D37 | MCP 生命周期 = 每 Run 按需连接 + 工具锁 | ⭐ anyio cancel scope 跨任务崩溃的踩坑（98c8957） | 2 |
| D38 | 飞书消息去重 = message_id 幂等 | 飞书会重推事件，不去重一条消息跑两遍 agent | 3 |
| D39 | 引用回复 = 纯文本注入，不恢复 session | ⭐ 「引用」语义的重新设计：上下文≠历史 | 3 |
| D40 | 跨 session 对话历史加载 | 新 session 如何「接上文」而不爆 token | 5/6 |

## 事故与故事索引（专栏的血肉）

| 故事 | 出处 | 用于章节 |
|------|------|----------|
| lark SDK 模块级 loop 竞态：第二个 App 加入互相打崩，断线重连必踩 | commit `b9ce24f`，`ws_pool.py:ThreadLoopClient` docstring | 8 压轴 |
| 飞书卡片引用解析 + 消息链路健壮性 | commit `ebbeb6e` | 3 |
| p2p 自动绑定静默失败 + 无 repo 时 AI 误判已绑定 | commit `4d4f579` | 3 |
| MCP 客户端 anyio cancel scope 跨任务退出崩溃 | commit `98c8957` | 2 |
| L2 compaction 预算感知（max_tokens 约束 + suffix 缩减 + 收敛） | commit `76cba5f`、`a0b9273` | 5 |
| 零外部依赖开箱即用（SQLite + MemoryBackend 双后端） | commit `3d10183` | 9 |
| stdlib logger 打 structlog kwargs → TypeError 掩盖真异常（首启崩溃） | commit `77e6e0e`，教训：统一日志门面 | 9 |
| alembic.ini 中文注释在 Windows GBK 下崩溃 | commit `29ae9e1` | 9 彩蛋 |
| 事故一：跑 pytest 把 dev 库全表 TRUNCATE（app_secret 永久丢失） | 测试库隔离三层防护：APP_ENV 前置 / DSN 强制切换 / assert 护栏 | 10 |
| 事故二：`rm -rf workspaces/1` 删掉主库真实会话 JSONL | 教训：清理前逐路径确认；数字目录可能属于主库 | 10 |

## 写作红线（每篇发表前过一遍）

- 截图/示例不得出现：真实 app_id / app_secret、内网 repo 名、PAT、`backend/.env` 内容、真实群名与 open_id。
- 演示数据一律来自独立 DATA_DIR 的演示库（README 截图管线可复用）。
- 引用公司内网信息为零容忍（本仓库为个人项目，但写作素材常来自聊天记录，需人工过一遍）。
