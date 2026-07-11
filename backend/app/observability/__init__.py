"""可观测性模块（M8，design §7）。

模块构成：
- ``tenancy`` — Span 查询 WS 隔离 event listener（D31）
- ``tracer`` — contextvars 零侵入 span 上下文管理器（D28 / §7.3）
- ``buffer`` — SpanBuffer 批写 + 降级（§7.4）
- ``payload`` — payload 文件写入 + 截断（§7.5 / D26）
- ``redaction`` — 敏感信息脱敏管线（D30 / NF4.6.2）

设计原则：observability 是基础设施层，不依赖 agent / feishu / tools（design §3.5）。
所有操作 best-effort，永不阻断 Agent 主流程（NF4.3.1 / §7.4）。

SpanBuffer 需在应用 lifespan 中 ``start()`` / ``stop()``（启动后台消费协程）。
"""
