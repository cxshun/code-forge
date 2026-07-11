import { http } from './client'
import type { ListResult } from '@/types/common'
import type { UserOut, UserCreateIn, UserPatchIn, ResetPasswordIn } from '@/types/user'

const BASE = '/admin/users'

export const usersApi = {
  list() {
    return http.get<unknown, ListResult<UserOut>>(`${BASE}`)
  },
  create(data: UserCreateIn) {
    return http.post<unknown, UserOut>(`${BASE}`, data)
  },
  patch(userId: number, data: UserPatchIn) {
    return http.patch<unknown, UserOut>(`${BASE}/${userId}`, data)
  },
  resetPassword(userId: number, data: ResetPasswordIn) {
    return http.post<unknown, void>(`${BASE}/${userId}:reset-password`, data)
  },
}
