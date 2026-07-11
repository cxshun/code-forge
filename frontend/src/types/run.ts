export interface RunOut {
  id: number
  session_id: number
  feishu_chat_id: number
  status: string
  trigger_message_id: string | null
  error: string | null
}
