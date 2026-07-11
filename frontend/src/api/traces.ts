import { http } from './client'
import type { ListResult } from '@/types/common'
import type { SpanOut, TraceListItem } from '@/types/trace'

const BASE = '/admin/workspaces'

export const tracesApi = {
  list(wsId: number, params?: { chat_id?: number; status?: string; limit?: number }) {
    return http.get<unknown, ListResult<TraceListItem>>(`${BASE}/${wsId}/traces`, { params })
  },
  getSpans(wsId: number, runId: number) {
    return http.get<unknown, ListResult<SpanOut>>(`${BASE}/${wsId}/traces/${runId}`)
  },
  getPayload(wsId: number, spanId: string, suffix: string) {
    return http.get<unknown, ArrayBuffer>(`${BASE}/${wsId}/spans/${spanId}/payload`, {
      params: { suffix },
      responseType: 'arraybuffer',
    })
  },
}
