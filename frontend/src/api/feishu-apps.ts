import { http } from './client'
import type { ListResult } from '@/types/common'
import type { FeishuAppOut, FeishuAppCreateIn, FeishuAppPatchIn } from '@/types/feishu-app'

const BASE = '/admin/feishu-apps'

export const feishuAppsApi = {
  list() {
    return http.get<unknown, ListResult<FeishuAppOut>>(`${BASE}`)
  },
  get(appPk: number) {
    return http.get<unknown, FeishuAppOut>(`${BASE}/${appPk}`)
  },
  create(data: FeishuAppCreateIn) {
    return http.post<unknown, FeishuAppOut & { app_secret: string }>(`${BASE}`, data)
  },
  patch(appPk: number, data: FeishuAppPatchIn) {
    return http.patch<unknown, FeishuAppOut>(`${BASE}/${appPk}`, data)
  },
  delete(appPk: number) {
    return http.delete<unknown, void>(`${BASE}/${appPk}`)
  },
}
