import { http } from './client'
import type { MemoryFile, MemoryFileIn } from '@/types/memory'

export const memoryApi = {
  list(wsId: number, feishuChatId: number) {
    return http.get<unknown, { files: MemoryFile[] }>(
      `/admin/workspaces/${wsId}/chats/${feishuChatId}/memory`,
    )
  },
  get(wsId: number, feishuChatId: number, filename: string) {
    return http.get<unknown, { filename: string; content: string }>(
      `/admin/workspaces/${wsId}/chats/${feishuChatId}/memory/${filename}`,
    )
  },
  put(wsId: number, feishuChatId: number, filename: string, data: MemoryFileIn) {
    return http.put<unknown, void>(
      `/admin/workspaces/${wsId}/chats/${feishuChatId}/memory/${filename}`,
      data,
    )
  },
  delete(wsId: number, feishuChatId: number, filename: string) {
    return http.delete<unknown, void>(
      `/admin/workspaces/${wsId}/chats/${feishuChatId}/memory/${filename}`,
    )
  },
}
