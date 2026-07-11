import { ref } from 'vue'
import { tasksApi } from '@/api/tasks'
import type { TaskOut } from '@/types/task'

export function useTaskPolling() {
  const task = ref<TaskOut | null>(null)
  const isRunning = ref(false)
  const isDone = ref(false)
  const isFailed = ref(false)
  const error = ref<string | null>(null)

  let timer: ReturnType<typeof setTimeout> | null = null

  async function poll(taskId: number) {
    try {
      const t = await tasksApi.get(taskId)
      task.value = t
      if (t.status === 'done') {
        isDone.value = true
        isRunning.value = false
        cleanup()
        return
      }
      if (t.status === 'failed') {
        isFailed.value = true
        error.value = t.error || '任务失败'
        isRunning.value = false
        cleanup()
        return
      }
      timer = setTimeout(() => poll(taskId), 1500)
    } catch (e) {
      isFailed.value = true
      error.value = (e as Error)?.message || '轮询失败'
      isRunning.value = false
      cleanup()
    }
  }

  function cleanup() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function start(taskId: number) {
    cleanup()
    isRunning.value = true
    isDone.value = false
    isFailed.value = false
    error.value = null
    task.value = null
    poll(taskId)
  }

  function stop() {
    cleanup()
    isRunning.value = false
  }

  return { task, isRunning, isDone, isFailed, error, start, stop }
}
