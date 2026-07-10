import axios from 'axios'
import { ElMessage } from 'element-plus'

// 统一 axios 实例：baseURL 指向后端 /api，携带 cookie session（D32）。
// 响应拦截：统一错误提示 + 401 跳登录。对齐 api.md §1.2 / §1.4。
export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.error?.message || error.message || '请求失败'
    if (status === 401) {
      const path = window.location.pathname
      if (!path.startsWith('/login')) {
        const redirect = path + window.location.search
        window.location.href = `/login?redirect=${encodeURIComponent(redirect)}`
      }
    } else if (status !== undefined) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)
