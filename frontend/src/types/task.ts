export interface TaskOut {
  task_id: number
  type: string
  status: 'pending' | 'running' | 'done' | 'failed'
  progress: number
  result: Record<string, unknown> | null
  error: string | null
}
