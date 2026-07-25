"""LLM Provider 抽象层（design D3 / spec NF4.5.1）。

定义统一 ``Provider`` 接口（chat / stream / count_tokens），多模型可切换
（Claude / GLM / mock）。``TokenCounter`` 与 ``context_window`` 由各 Provider 暴露，
供上下文管理四道防线使用（D34 —— clearing / compaction 触发阈值依赖
``context_window`` 与 ``count_tokens``）。

Provider 实现不关心推送层，只做 LLM 调用与结果解析。
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Message:
    """对话消息，对齐 Anthropic Message 协议的子集。"""
    role: str  # user / assistant / tool_result
    content: str | None = None
    reasoning: str | None = None  # assistant: 模型思考（deepseek reasoning_content，多轮需回传）
    tool_calls: list[dict] | None = None  # assistant: [{"id","name","input"}]
    tool_call_id: str | None = None  # tool_result: 对应的 tool_use id
    created_at: str | None = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ToolDef:
    """工具定义，对齐 Anthropic tool_use 格式与 MCP 的 Tool.inputSchema。"""
    name: str
    description: str
    input_schema: dict  # JSON Schema


@dataclass
class StreamEvent:
    """流式事件，抽象化 Provider 差异（Anthropic stream / GLM SSE）。

    type 取值：
    - ``text``：普通文本片段
    - ``reasoning``：模型思考片段（deepseek-v4-flash 等 thinking 模型的 reasoning_content）
    - ``tool_use_start``：开始一个工具调用（含 name + JSON input）
    - ``tool_use_end``：工具调用结束
    - ``stop``：流结束（含最终 usage）
    """
    type: str
    text: str | None = None
    reasoning: str | None = None
    tool_name: str | None = None
    tool_input: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class Provider(ABC):
    """LLM Provider 接口。

    实现需提供：
    - ``context_window``：模型上下文窗口大小（token）
    - ``model``：模型标识（用于 cost 计算与 insights 聚合）
    - ``name``：Provider 名称（anthropic / glm / mock）
    - ``chat``：非流式接口，返回 messages + usage
    - ``stream``：流式接口，生产 StreamEvent
    - ``count_tokens``：消息 token 计数，供 clearing / compaction 层决策
    """

    @property
    @abstractmethod
    def context_window(self) -> int:
        """模型上下文窗口（token）。Claude 200K / GLM 128K 等。"""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """模型标识（如 claude-sonnet-4-20250514），用于 cost 计算。"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称（anthropic / glm / mock）。"""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> tuple[list[Message], Usage]:
        """非流式 LLM 调用。

        Returns:
            (assistant_messages, usage)
            assistant_messages 可能含 tool_calls（需 Loop 解析）。
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式 LLM 调用，生成 StreamEvent（text / tool_use / stop）。

        调用方（Agent Loop）消费流式事件，将 text delta 推送飞书（FeishuClient
        update_card），tool_use 在完整 tool_use_end 事件后开始执行。
        """
        ...  # type: ignore[empty-body]
        if False:
            yield

    @abstractmethod
    async def count_tokens(
        self, messages: list[Message], system: str | None = None
    ) -> Usage:
        """精确或估算的 token 计数（D34 用，非 `len(str)`）。"""
        ...
