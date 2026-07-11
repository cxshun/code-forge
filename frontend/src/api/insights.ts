import { http } from './client'

const BASE = '/admin/workspaces'

export interface CostDayItem {
  date: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  run_count: number
}

export interface CostInsights {
  items: CostDayItem[]
  total: number
  summary: {
    total_cost_usd: number
    total_input_tokens: number
    total_output_tokens: number
    total_runs: number
  }
}

export interface ToolInsight {
  tool_name: string
  call_count: number
  avg_duration_ms: number
  max_duration_ms: number
  error_count: number
  error_rate: number
}

export interface ModelInsight {
  model: string
  call_count: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
  cost_pct: number
}

export const insightsApi = {
  cost(wsId: number, params?: { chat_id?: number; days?: number }) {
    return http.get<unknown, CostInsights>(`${BASE}/${wsId}/insights/cost`, { params })
  },
  tools(wsId: number, params?: { chat_id?: number; limit?: number }) {
    return http.get<unknown, { items: ToolInsight[]; total: number }>(`${BASE}/${wsId}/insights/tools`, { params })
  },
  models(wsId: number, params?: { chat_id?: number }) {
    return http.get<unknown, { items: ModelInsight[]; total: number }>(`${BASE}/${wsId}/insights/models`, { params })
  },
}
