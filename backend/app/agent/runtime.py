"""Run 启动期工厂：按 WS 构建 Provider / 工具注册表 / cwd / 引用块（design §6.1 / §6.5）。

接入层（飞书 handler）路由到 (ws_id, feishu_chat_id) 后，用本模块组装 Run 所需依赖，
再经 ``RunQueue.submit`` 入队。所有工厂按 WS 实际挂载情况构造（内置工具 + 挂载 Skill + 挂载 MCP）。
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context_config import ContextConfig
from app.config import settings
from app.db.models import GitRepo, Workspace
from app.feishu.client import FeishuClient
from app.feishu.quote import extract_plain_text
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import Provider
from app.providers.openai_compatible_provider import OpenAICompatibleProvider
from app.tools.builtin.bash import BashTool
from app.tools.builtin.edit import EditTool
from app.tools.builtin.glob import GlobTool
from app.tools.builtin.grep import GrepTool
from app.tools.builtin.read import ReadTool
from app.tools.builtin.write import WriteTool
from app.tools.mcp import build_mcp_tools
from app.tools.registry import ToolRegistry
from app.tools.skill import build_skill_tools

log = logging.getLogger("agent.runtime")

McpCleanup = Callable[[], Awaitable[None]] | None


def make_provider() -> Provider:
    """构造主 LLM Provider。

    - 配了 ``openai_compatible_*`` 三项 → 国内模型（智谱/通义/DeepSeek/Moonshot 等），
      支持无 Anthropic key 的部署（design D3 多模型备选）。
    - 否则 → Anthropic（key 缺失时 Provider 仍返回，stream 时失败）。
    """
    if (
        settings.openai_compatible_api_key
        and settings.openai_compatible_base_url
        and settings.openai_compatible_model
    ):
        return OpenAICompatibleProvider(model=settings.openai_compatible_model)
    return AnthropicProvider()


def make_summary_provider(cfg: ContextConfig) -> Provider:
    """按 WS ``context_config.summary_provider`` 选 L2 摘要模型（design D34）。

    - ``openai_compatible``（``glm`` 作历史别名）：需 ``openai_compatible_*`` 三项齐配，
      否则回退 anthropic。支持任意 OpenAI 兼容服务（智谱/通义/DeepSeek/Moonshot 等）。
    - ``anthropic``（默认）/未知 kind：用 AnthropicProvider；主 key 也缺则回退 ``make_provider``
    """
    kind = (cfg.summary_provider or "anthropic").lower()
    model = cfg.summary_model or None
    if kind in ("openai_compatible", "glm"):  # glm 作历史别名
        if (
            settings.openai_compatible_api_key
            and settings.openai_compatible_base_url
            and settings.openai_compatible_model
        ):
            return OpenAICompatibleProvider(model=model)
        log.warning(
            "summary_provider=%s 但 openai_compatible_* 未完整配置，回退 anthropic",
            kind,
        )
    elif kind != "anthropic":
        log.warning("未知 summary_provider=%r，回退 anthropic", kind)
    if settings.anthropic_api_key:
        return AnthropicProvider(model=model)
    return make_provider()


async def build_registry(
    db: AsyncSession, ws_id: int, provider: Provider
) -> tuple[ToolRegistry, list[str], McpCleanup]:
    """WS 工具注册表 = 内置 6 工具 + Agent 子代理工具 + 挂载 Skill + 挂载 MCP。

    ``provider`` 用于构造 ``AgentTool``（子代理复用父 provider，design D33）。

    返回 (registry, skill_descriptions, mcp_cleanup)：
    - descriptions 用于 system prompt 的「可用 Skills」段（D16 阶段 1 元信息注入）
    - mcp_cleanup 在 Run 结束后调用，关闭 MCP 客户端连接（无 MCP 时为 None）
    """
    registry = ToolRegistry()
    for tool in (ReadTool(), GlobTool(), GrepTool(), WriteTool(), EditTool(), BashTool()):
        registry.register(tool)
    skill_descriptions: list[str] = []
    for skill_tool in await build_skill_tools(db, ws_id):
        registry.register(skill_tool)
        skill_descriptions.append(f"{skill_tool.name}: {skill_tool.description}")

    mcp_tools, mcp_clients = await build_mcp_tools(db, ws_id)
    for tool in mcp_tools:
        registry.register(tool)

    # Agent 子代理工具（D33）：复用父 provider/registry，深度 1 防递归；并行度 semaphore 限流
    from app.agent.subagent import AgentTool

    semaphore = asyncio.Semaphore(settings.agent_max_concurrency)
    registry.register(AgentTool(provider, registry, semaphore))

    async def _mcp_cleanup() -> None:
        for c in mcp_clients:
            await c.close()

    return registry, skill_descriptions, (_mcp_cleanup if mcp_clients else None)


async def resolve_cwd(db: AsyncSession, ws: Workspace) -> str:
    """Run 的 cwd（相对 repos/ 的 repo 目录名）。

    - ``ws.cwd_repo_id`` 指定且 repo 属于本 WS → str(repo_id)
    - 否则取第一个挂载 repo → str(repo_id)
    - 无 repo → ""（工具 cwd_root 退化为 repos/，加载器不注入 Repo 级 AGENT.md）
    """
    if ws.cwd_repo_id:
        repo = await db.get(GitRepo, ws.cwd_repo_id)
        if repo is not None and repo.workspace_id == ws.id:
            return str(repo.id)
    first = await db.scalar(
        select(GitRepo).where(GitRepo.workspace_id == ws.id).order_by(GitRepo.id)
    )
    return str(first.id) if first is not None else ""


async def fetch_quote_text(client: FeishuClient, parent_id: str | None) -> str | None:
    """D39：拉被引用消息正文，返回 markdown 引用块；取不到返回 None。

    被引用为富卡片时尽力提取纯文本，失败返回 None（由调用方决定是否标注）。
    """
    if not parent_id:
        return None
    try:
        data = await client.get_message(parent_id)
    except Exception:
        log.warning("fetch quote failed: %s", parent_id, exc_info=True)
        return None
    if data is None or not data.items:
        return None
    msg = data.items[0]
    body = getattr(msg, "body", None)
    content = getattr(body, "content", None) if body is not None else None
    if not content:
        return None
    text = extract_plain_text(content, getattr(msg, "msg_type", "") or "")
    if not text:
        return None
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    return f"**引用消息：**\n{quoted}\n"


__all__ = [
    "build_registry",
    "fetch_quote_text",
    "make_provider",
    "make_summary_provider",
    "resolve_cwd",
]

