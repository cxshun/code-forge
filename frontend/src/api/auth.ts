import { http } from './client'
import type { LoginResponse } from '@/types/user'
import type { WorkspaceBrief } from '@/types/workspace'

interface MeResponse extends LoginResponse {
  workspaces: WorkspaceBrief[]
}

export const authApi = {
  login(username: string, password: string) {
    return http.post<unknown, LoginResponse>('/auth/login', { username, password })
  },
  logout() {
    return http.post<unknown, void>('/auth/logout')
  },
  me() {
    return http.get<unknown, MeResponse>('/auth/me')
  },
}
