import { http } from './client'
import type { ListResult } from '@/types/common'
import type {
  WorkspaceOut,
  WorkspaceDetail,
  WorkspaceCreateIn,
  WorkspacePatchIn,
  RepoOut,
  RepoCreateIn,
  ChatOut,
  ChatCheckIn,
  ChatCheckResult,
  SkillBrief,
  McpBrief,
} from '@/types/workspace'
import type { RunOut } from '@/types/run'

const BASE = '/admin/workspaces'

export const workspacesApi = {
  list() {
    return http.get<unknown, ListResult<WorkspaceOut>>(`${BASE}`)
  },
  get(wsId: number) {
    return http.get<unknown, WorkspaceDetail>(`${BASE}/${wsId}`)
  },
  create(data: WorkspaceCreateIn) {
    return http.post<unknown, WorkspaceOut>(`${BASE}`, data)
  },
  patch(wsId: number, data: WorkspacePatchIn) {
    return http.patch<unknown, WorkspaceOut>(`${BASE}/${wsId}`, data)
  },
  delete(wsId: number) {
    return http.delete<unknown, { task_id: number }>(`${BASE}/${wsId}`)
  },

  listRepos(wsId: number) {
    return http.get<unknown, ListResult<RepoOut>>(`${BASE}/${wsId}/repos`)
  },
  createRepo(wsId: number, data: RepoCreateIn) {
    return http.post<unknown, { repo_id: number; task_id: number }>(`${BASE}/${wsId}/repos`, data)
  },
  getRepo(wsId: number, repoId: number) {
    return http.get<unknown, RepoOut>(`${BASE}/${wsId}/repos/${repoId}`)
  },
  syncRepo(wsId: number, repoId: number) {
    return http.post<unknown, { task_id: number }>(`${BASE}/${wsId}/repos/${repoId}:sync`)
  },
  deleteRepo(wsId: number, repoId: number) {
    return http.delete<unknown, void>(`${BASE}/${wsId}/repos/${repoId}`)
  },

  listChats(wsId: number) {
    return http.get<unknown, ListResult<ChatOut>>(`${BASE}/${wsId}/chats`)
  },
  checkChat(wsId: number, data: ChatCheckIn) {
    return http.post<unknown, ChatCheckResult>(`${BASE}/${wsId}/chats:check`, data)
  },
  bindChat(wsId: number, data: ChatCheckIn) {
    return http.post<unknown, ChatOut>(`${BASE}/${wsId}/chats`, data)
  },
  unbindChat(wsId: number, feishuChatId: number) {
    return http.delete<unknown, void>(`${BASE}/${wsId}/chats/${feishuChatId}`)
  },

  listMountedSkills(wsId: number) {
    return http.get<unknown, ListResult<SkillBrief>>(`${BASE}/${wsId}/skills`)
  },
  mountSkill(wsId: number, skillId: number) {
    return http.post<unknown, void>(`${BASE}/${wsId}/skills`, { skill_id: skillId })
  },
  unmountSkill(wsId: number, skillId: number) {
    return http.delete<unknown, void>(`${BASE}/${wsId}/skills/${skillId}`)
  },

  listMountedMcps(wsId: number) {
    return http.get<unknown, ListResult<McpBrief>>(`${BASE}/${wsId}/mcps`)
  },
  mountMcp(wsId: number, mcpId: number) {
    return http.post<unknown, void>(`${BASE}/${wsId}/mcps`, { mcp_id: mcpId })
  },
  unmountMcp(wsId: number, mcpId: number) {
    return http.delete<unknown, void>(`${BASE}/${wsId}/mcps/${mcpId}`)
  },

  getAgentMd(wsId: number) {
    return http.get<unknown, { content: string }>(`${BASE}/${wsId}/agent-md`)
  },
  putAgentMd(wsId: number, content: string) {
    return http.put<unknown, void>(`${BASE}/${wsId}/agent-md`, { content })
  },
  getRepoAgentMd(wsId: number, repoId: number) {
    return http.get<unknown, { content: string }>(`${BASE}/${wsId}/repos/${repoId}/agent-md`)
  },

  listRuns(wsId: number, params?: { chat_id?: number; status?: string }) {
    return http.get<unknown, ListResult<RunOut>>(`${BASE}/${wsId}/runs`, { params })
  },
  getRunMessages(wsId: number, runId: number) {
    return http.get<unknown, { messages: Array<{ role: string; content: string | null; reasoning?: string | null; tool_calls?: unknown[] | null }> }>(`${BASE}/${wsId}/runs/${runId}/messages`)
  },
  cancelRun(wsId: number, runId: number) {
    return http.post<unknown, void>(`${BASE}/${wsId}/runs/${runId}:cancel`)
  },
  interruptRun(wsId: number, runId: number) {
    return http.post<unknown, void>(`${BASE}/${wsId}/runs/${runId}:interrupt`)
  },
}
