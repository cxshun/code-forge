import { http } from './client'

const BASE = '/admin/workspaces'

export interface AnomalyItem {
  id: number
  status: string
  started_at: string | null
  ended_at: string | null
  error: string | null
}

export interface AlertRuleItem {
  id: number
  name: string
  rule_type: string
  threshold: number
  window_minutes: number
  enabled: boolean
  last_triggered_at: string | null
  last_result: number | null
}

export interface RuleInput {
  name: string
  rule_type: string
  threshold: number
  window_minutes?: number
  enabled?: boolean
}

export interface RulePatch {
  name?: string
  threshold?: number
  window_minutes?: number
  enabled?: boolean
}

export const monitoringApi = {
  anomalies(wsId: number, limit = 50) {
    return http.get<unknown, { items: AnomalyItem[]; total: number }>(
      `${BASE}/${wsId}/monitoring/anomalies`,
      { params: { limit } },
    )
  },
  rules(wsId: number) {
    return http.get<unknown, { items: AlertRuleItem[]; total: number }>(`${BASE}/${wsId}/monitoring/rules`)
  },
  createRule(wsId: number, body: RuleInput) {
    return http.post<unknown, AlertRuleItem>(`${BASE}/${wsId}/monitoring/rules`, body)
  },
  updateRule(wsId: number, ruleId: number, body: RulePatch) {
    return http.patch<unknown, AlertRuleItem>(`${BASE}/${wsId}/monitoring/rules/${ruleId}`, body)
  },
  deleteRule(wsId: number, ruleId: number) {
    return http.delete<unknown, { ok: boolean }>(`${BASE}/${wsId}/monitoring/rules/${ruleId}`)
  },
}

export const RULE_TYPES = [
  { value: 'error_rate', label: '错误率', unit: '%' },
  { value: 'timeout_rate', label: '超时率', unit: '%' },
  { value: 'p95_latency', label: 'P95 延迟', unit: 'ms' },
  { value: 'run_cost', label: '单 Run 费用', unit: 'USD' },
  { value: 'ws_daily_cost', label: 'WS 日费用', unit: 'USD' },
]
