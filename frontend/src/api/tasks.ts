import { http } from './client'
import type { TaskOut } from '@/types/task'

export const tasksApi = {
  get(taskId: number) {
    return http.get<unknown, TaskOut>(`/admin/tasks/${taskId}`)
  },
}
