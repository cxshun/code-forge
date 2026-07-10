"""System Prompt 构建（design D24 / D33）。

注入顺序（从通用到具体）：
1. 基础指令（角色 / 安全 / D33 并行子代理拆分指导）
2. WS 级 AGENT.md
3. Repo 级 AGENT.md（当前 cwd 所在 repo）
4. MEMORY.md 索引（chat 级长期记忆）
5. Skill descriptions（可调用能力，仅 name + description）
"""

_BASE_INSTRUCTIONS = """你是 Code Forge 的 Coding Agent，在飞书群里辅助用户完成编码任务。

## 工作方式
- 通过 Read / Glob / Grep 探索代码，Write / Edit 修改文件，Bash 执行命令。
- 所有文件操作限定在当前工作空间的 repos 子树；越界路径会被拒绝。
- 复杂任务先规划（列步骤），再执行；遇到不确定主动澄清。

## 并行子任务（D33）
- 一条消息可拆成多个相互独立的子任务时，可在单轮返回多个工具调用并行执行。
- 只读 / 调研类子任务优先并行（零冲突风险）。
- 写型子任务并行前，确认改动的是不同文件、无写冲突；存在冲突或强依赖时串行。

## 安全
- 不执行改 git 状态的操作（commit / push 等被拦截）。
- 不把密钥 / 凭证写入 memory。
"""


def build_system_prompt(
    ws_agent_md: str = "",
    repo_agent_md: str = "",
    memory_index: str = "",
    skill_descriptions: list[str] | None = None,
) -> str:
    """按 D24 注入顺序拼接 system prompt。空段跳过。"""
    parts = [_BASE_INSTRUCTIONS]
    if ws_agent_md:
        parts.append("# 工作空间指令（WS 级 AGENT.md）\n" + ws_agent_md)
    if repo_agent_md:
        parts.append("# 仓库指令（Repo 级 AGENT.md）\n" + repo_agent_md)
    if memory_index:
        parts.append("# 记忆索引（MEMORY.md）\n" + memory_index)
    if skill_descriptions:
        skills = "\n".join(f"- {d}" for d in skill_descriptions)
        parts.append("# 可用 Skills\n" + skills)
    return "\n\n---\n\n".join(parts)
