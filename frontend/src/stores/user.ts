import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import type { UserInfo, LoginResponse } from '@/types/user'
import type { WorkspaceBrief } from '@/types/workspace'

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null)
  const isAuthenticated = ref(false)
  const initialized = ref(false)
  const workspaces = ref<WorkspaceBrief[]>([])

  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    user.value = res.user
    isAuthenticated.value = true
    return res.user
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      reset()
    }
  }

  async function fetchMe() {
    try {
      const res = await authApi.me()
      user.value = res.user
      workspaces.value = res.workspaces
      isAuthenticated.value = true
    } catch {
      reset()
    } finally {
      initialized.value = true
    }
  }

  function reset() {
    user.value = null
    isAuthenticated.value = false
    workspaces.value = []
  }

  return { user, isAuthenticated, initialized, workspaces, login, logout, fetchMe, reset }
})
