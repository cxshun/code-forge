export interface RunOut {
  id: number
  session_id: number
  feishu_chat_id: number
  status: string
  trigger_message_id: string | null
  started_at: string | null
  ended_at: string | null
  error: string | null
}
