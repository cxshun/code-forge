export interface SpanOut {
  span_id: string
  trace_id: string
  parent_span_id: string | null
  span_order: number
  span_type: string
  status: string
  workspace_id: number
  feishu_chat_id: number
  session_id: number
  run_id: number
  provider: string | null
  model: string | null
  stop_reason: string | null
  input_tokens: number | null
  output_tokens: number | null
  cache_read_input_tokens: number | null
  cache_creation_input_tokens: number | null
  tool_name: string | null
  tool_input_summary: string | null
  tool_output_summary: string | null
  tool_acquired_lock: boolean | null
  tool_path_rejected: boolean | null
  cost_usd: number | null
  error_type: string | null
  error_message: string | null
  payload_ref: string | null
  payload_size_bytes: number | null
  payload_truncated: boolean
  attributes: Record<string, unknown> | null
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
}

export interface TraceListItem {
  run_id: number
  trace_id: string
  root_span_id: string
  span_type: string
  status: string
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  total_input_tokens: number | null
  total_output_tokens: number | null
  total_cost_usd: number | null
  span_count: number
  error_type: string | null
}
