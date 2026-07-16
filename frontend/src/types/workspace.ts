export interface WorkspaceBrief {
  id: number
  name: string
}

export interface WorkspaceOut {
  id: number
  name: string
  owner_id: number
  owner_name?: string
  context_config: Record<string, unknown> | null
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
