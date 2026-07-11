import { http } from './client'
import type { ListResult } from '@/types/common'
import type { McpOut, McpCreateIn, McpPatchIn } from '@/types/mcp'

const BASE = '/admin/mcps'

export const mcpsApi = {
  list() {
    return http.get<unknown, ListResult<McpOut>>(`${BASE}`)
  },
  get(mcpId: number) {
    return http.get<unknown, McpOut>(`${BASE}/${mcpId}`)
  },
  create(data: McpCreateIn) {
    return http.post<unknown, McpOut>(`${BASE}`, data)
  },
  patch(mcpId: number, data: McpPatchIn) {
    return http.patch<unknown, McpOut>(`${BASE}/${mcpId}`, data)
  },
  delete(mcpId: number) {
    return http.delete<unknown, void>(`${BASE}/${mcpId}`)
  },
}
