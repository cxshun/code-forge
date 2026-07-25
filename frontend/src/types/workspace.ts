export interface WorkspaceBrief {
  id: number
  name: string
}

export interface ContextConfig {
  enabled: boolean
  trigger1: number          // L1 clearing 阈值 (context_window 百分比)
  trigger2: number          // L2 compaction 阈值
  clear_keep: number        // L1 保留最近 N 个 tool_result
  compact_recent: number    // L2 保留最近 M 轮原文
  summary_provider: string  // "anthropic" | "openai_compatible"
  summary_model: string | null
  compact_instructions: string
  exclude_tools: string[]
  summary_budget_pct: number  // P3 D-CE.1 跨 session 摘要预算
  compact_recursive: boolean   // P3 D-CE.2 L2 递归分段摘要开关
  summary_target_pct: number   // L2 compaction 后目标 token 占 context_window 百分比
}

export const DEFAULT_CONTEXT_CONFIG: ContextConfig = {
  enabled: true,
  trigger1: 0.5,
  trigger2: 0.75,
  clear_keep: 6,
  compact_recent: 6,
  summary_provider: 'anthropic',
  summary_model: null,
  compact_instructions: (
    '你是对话历史压缩器。请把以下对话压缩为结构化摘要，务必保留：代码片段与文件路径、' +
    '变量/函数/类名、关键技术决策与理由、当前任务状态与进度、未完成的 todo、' +
    '用户明确表达的偏好。丢弃：寒暄/冗余对话、已处理完毕的大段工具输出。' +
    '输出一份简洁的 markdown 摘要。'
  ),
  exclude_tools: [],
  summary_budget_pct: 0.25,
  compact_recursive: true,
  summary_target_pct: 0.4,
}

export interface ModelConfig {
  provider: string          // "anthropic" | "openai_compatible"
  model: string | null
  api_base_url: string | null
  api_key?: string          // write-only: sent to backend, never returned (has_model_api_key instead)
}

export interface WorkspaceOut {
  id: number
  name: string
  owner_id: number
  owner_name?: string
  context_config: Partial<ContextConfig> | null
  model_config: Partial<ModelConfig> | null  // P3 D-CE.6: 不含 api_key_enc
  has_model_api_key: boolean                   // P3 D-CE.6: 前端展示用
  cwd_repo_id: number | null
}

export interface RepoBrief {
  id: number
  url: string
  clone_status: string
}

export interface ChatBrief {
  id: number
  app_id: string
  chat_name: string | null
}

export interface SkillBrief {
  id: number
  name: string
  description: string
}

export interface McpBrief {
  id: number
  name: string
  type: string
}

export interface WorkspaceDetail extends WorkspaceOut {
  repos: RepoBrief[]
  chats: ChatBrief[]
  skills: SkillBrief[]
  mcps: McpBrief[]
}

export interface WorkspaceCreateIn {
  name: string
  context_config?: Record<string, unknown> | null
}

export interface WorkspacePatchIn {
  name?: string
  context_config?: Record<string, unknown> | null
  model_config?: ModelConfig | null
}

export interface RepoCreateIn {
  url: string
  token?: string | null
}

export interface RepoOut {
  id: number
  url: string
  clone_status: string
  local_path: string | null
  last_error: string | null
}

export interface ChatCheckIn {
  app_id: string
  chat_id: string
}

export interface ChatCheckResult {
  valid: boolean
  bot_in_chat: boolean
  chat_name: string | null
  existing_binding: {
    feishu_chat_id: number
    workspace_id: number
    is_this_ws: boolean
  } | null
}

export interface ChatOut {
  id: number
  app_id: string
  chat_id: string
  chat_name: string | null
  workspace_id: number
}
