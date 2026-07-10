import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import type { UserInfo } from '@/types/user'

export const useUserStore = defineStore('user', () => {
  const user = ref<UserInfo | null>(null)
  const isAuthenticated = ref(false)

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
      isAuthenticated.value = true
    } catch {
      reset()
    }
  }

  function reset() {
    user.value = null
    isAuthenticated.value = false
  }

  return { user, isAuthenticated, login, logout, fetchMe, reset }
})
