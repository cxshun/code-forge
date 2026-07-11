<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { monitoringApi, RULE_TYPES } from '@/api/monitoring'
import type { AlertRuleItem, AnomalyItem, RuleInput } from '@/api/monitoring'
import { workspacesApi } from '@/api/workspaces'
import type { WorkspaceBrief } from '@/types/workspace'

const workspaces = ref<WorkspaceBrief[]>([])
const selectedWsId = ref<number | null>(null)

const anomalies = ref<AnomalyItem[]>([])
const rules = ref<AlertRuleItem[]>([])
const loading = ref(false)

const dialogVisible = ref(false)
const form = ref<RuleInput>({
  name: '',
  rule_type: 'error_rate',
  threshold: 0.1,
  window_minutes: 60,
  enabled: true,
})

async function fetchAll() {
  if (!selectedWsId.value) return
  loading.value = true
  try {
    const [anom, rl] = await Promise.all([
      monitoringApi.anomalies(selectedWsId.value),
      monitoringApi.rules(selectedWsId.value),
    ])
    anomalies.value = anom.items
    rules.value = rl.items
  } finally {
    loading.value = false
  }
}

watch(selectedWsId, fetchAll)
onMounted(async () => {
  const res = await workspacesApi.list()
  workspaces.value = res.items
  if (res.items.length) selectedWsId.value = res.items[0].id
})

function ruleTypeLabel(t: string): string {
  return RULE_TYPES.find((r) => r.value === t)?.label ?? t
}

function ruleTypeUnit(t: string): string {
  return RULE_TYPES.find((r) => r.value === t)?.unit ?? ''
}

function formatThreshold(v: number, t: string): string {
  const unit = ruleTypeUnit(t)
  if (unit === '%') return `${(v * 100).toFixed(1)}%`
  if (unit === 'USD') return `$${v.toFixed(2)}`
  return `${v.toFixed(0)} ${unit}`
}

function formatResult(v: number | null, t: string): string {
  if (v === null) return '—'
  const unit = ruleTypeUnit(t)
  if (unit === '%') return `${(v * 100).toFixed(1)}%`
  if (unit === 'USD') return `$${v.toFixed(4)}`
  return v.toFixed(0)
}

function statusTag(s: string): 'danger' | 'warning' | 'info' {
  if (s === 'error') return 'danger'
  if (s === 'interrupted' || s === 'timeout') return 'warning'
  return 'info'
}

async function toggleEnabled(rule: AlertRuleItem) {
  try {
    await monitoringApi.updateRule(selectedWsId.value!, rule.id, { enabled: !rule.enabled })
    rule.enabled = !rule.enabled
  } catch {
    ElMessage.error('更新失败')
  }
}

async function deleteRule(rule: AlertRuleItem) {
  try {
    await ElMessageBox.confirm(`确认删除规则「${rule.name}」？`, '删除确认', { type: 'warning' })
    await monitoringApi.deleteRule(selectedWsId.value!, rule.id)
    rules.value = rules.value.filter((r) => r.id !== rule.id)
    ElMessage.success('已删除')
  } catch {
    // cancelled or error
  }
}

function openCreate() {
  form.value = { name: '', rule_type: 'error_rate', threshold: 0.1, window_minutes: 60, enabled: true }
  dialogVisible.value = true
}

async function submitRule() {
  try {
    const created = await monitoringApi.createRule(selectedWsId.value!, form.value)
    rules.value.push(created)
    dialogVisible.value = false
    ElMessage.success('已创建')
  } catch {
    ElMessage.error('创建失败')
  }
}
</script>

<template>
  <div v-loading="loading" class="monitoring-view">
    <div class="filter-bar">
      <el-select v-model="selectedWsId" placeholder="选择工作空间" style="width: 240px">
        <el-option v-for="ws in workspaces" :key="ws.id" :label="ws.name" :value="ws.id" />
      </el-select>
      <el-button type="primary" :disabled="!selectedWsId" @click="openCreate">新建规则</el-button>
      <el-button :disabled="!selectedWsId" @click="fetchAll">刷新</el-button>
    </div>

    <!-- Anomalies -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>
        <span>异常 Run 列表</span>
        <el-tag style="margin-left: 8px" type="danger" size="small">{{ anomalies.length }}</el-tag>
      </template>
      <el-table :data="anomalies" size="small" :max-height="300" empty-text="暂无异常">
        <el-table-column prop="id" label="Run ID" width="80" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" min-width="180" />
        <el-table-column prop="ended_at" label="结束时间" min-width="180" />
        <el-table-column prop="error" label="错误信息" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- Alert Rules -->
    <el-card shadow="never">
      <template #header>
        <span>告警规则</span>
        <el-tag style="margin-left: 8px" size="small">{{ rules.length }}</el-tag>
      </template>
      <el-table :data="rules" size="small" empty-text="暂无规则">
        <el-table-column prop="name" label="规则名称" min-width="150" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ ruleTypeLabel(row.rule_type) }}</template>
        </el-table-column>
        <el-table-column label="阈值" width="120">
          <template #default="{ row }">{{ formatThreshold(row.threshold, row.rule_type) }}</template>
        </el-table-column>
        <el-table-column label="窗口" width="100">
          <template #default="{ row }">{{ row.window_minutes > 0 ? row.window_minutes + ' min' : '实时' }}</template>
        </el-table-column>
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">
            <span :style="{ color: row.last_result !== null && row.last_result > row.threshold ? '#f56c6c' : '#909399' }">
              {{ formatResult(row.last_result, row.rule_type) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="last_triggered_at" label="最近触发" min-width="180" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @update:model-value="toggleEnabled(row)" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" text size="small" @click="deleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create Dialog -->
    <el-dialog v-model="dialogVisible" title="新建告警规则" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则名称">
          <el-input v-model="form.name" placeholder="如：高错误率" />
        </el-form-item>
        <el-form-item label="规则类型">
          <el-select v-model="form.rule_type" style="width: 100%">
            <el-option v-for="rt in RULE_TYPES" :key="rt.value" :label="rt.label" :value="rt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值">
          <el-input-number v-model="form.threshold" :step="0.05" :min="0" />
        </el-form-item>
        <el-form-item label="窗口(分钟)">
          <el-input-number v-model="form.window_minutes" :min="0" :step="30" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRule">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.monitoring-view {
  padding: 16px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
