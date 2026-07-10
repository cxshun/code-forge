import { http } from './client'
import type { UserInfo } from '@/types/user'

interface LoginResponse {
  user: UserInfo
}

export const authApi = {
  login(username: string, password: string) {
    return http.post<unknown, LoginResponse>('/auth/login', { username, password })
  },
  logout() {
    return http.post<unknown, void>('/auth/logout')
  },
  me() {
    return http.get<unknown, LoginResponse>('/auth/me')
  },
}
