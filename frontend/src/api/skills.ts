import { http } from './client'
import type { ListResult } from '@/types/common'
import type { SkillOut, SkillPatchIn } from '@/types/skill'

const BASE = '/admin/skills'

export const skillsApi = {
  list(q?: string) {
    return http.get<unknown, ListResult<SkillOut>>(`${BASE}`, { params: q ? { q } : undefined })
  },
  get(skillId: number) {
    return http.get<unknown, SkillOut>(`${BASE}/${skillId}`)
  },
  create(file: File, visibility: 'private' | 'public' = 'private') {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('visibility', visibility)
    return http.post<unknown, SkillOut>(`${BASE}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  patch(skillId: number, data: SkillPatchIn) {
    return http.patch<unknown, SkillOut>(`${BASE}/${skillId}`, data)
  },
  delete(skillId: number) {
    return http.delete<unknown, void>(`${BASE}/${skillId}`)
  },
}
