<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { insightsApi } from '@/api/insights'
import { workspacesApi } from '@/api/workspaces'
import type { CostInsights, ToolInsight, ModelInsight } from '@/api/insights'
import type { WorkspaceBrief, ChatBrief } from '@/types/workspace'

const workspaces = ref<WorkspaceBrief[]>([])
const selectedWsId = ref<number | null>(null)
const chats = ref<ChatBrief[]>([])
const selectedChatId = ref<number | null>(null)
const days = ref(30)

const costData = ref<CostInsights | null>(null)
const toolItems = ref<ToolInsight[]>([])
const modelItems = ref<ModelInsight[]>([])
const loading = ref(false)

async function onWsChange() {
  if (!selectedWsId.value) return
  const detail = await workspacesApi.get(selectedWsId.value)
  chats.value = detail.chats
  selectedChatId.value = null
}

async function fetchAll() {
  if (!selectedWsId.value) return
  loading.value = true
  try {
    const [cost, tools, models] = await Promise.all([
      insightsApi.cost(selectedWsId.value, {
        chat_id: selectedChatId.value ?? undefined,
        days: days.value,
      }),
      insightsApi.tools(selectedWsId.value, {
        chat_id: selectedChatId.value ?? undefined,
      }),
      insightsApi.models(selectedWsId.value, {
        chat_id: selectedChatId.value ?? undefined,
      }),
    ])
    costData.value = cost
    toolItems.value = tools.items
    modelItems.value = models.items
  } finally {
    loading.value = false
  }
}

watch([selectedChatId, days], fetchAll)

function fmtCost(v: number): string {
  if (v < 0.01) return `$${v.toFixed(6)}`
  return `$${v.toFixed(4)}`
}

function fmtTokens(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`
  return String(v)
}

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

const costChartWidth = computed(() => {
  const n = costData.value?.items.length ?? 0
  return Math.max(n * 40, 300)
})

function costBarHeight(item: { cost_usd: number }): number {
  const max = Math.max(...(costData.value?.items.map((i) => i.cost_usd) ?? [0]), 0.001)
  return Math.max((item.cost_usd / max) * 120, 2)
}

onMounted(async () => {
  const { useUserStore } = await import('@/stores/user')
  const store = useUserStore()
  if (!store.initialized) await store.fetchMe()
  workspaces.value = store.workspaces
})
</script>

<template>
  <div>
    <h2 style="margin-bottom: 16px">Insights 聚合视图</h2>

    <el-card style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="Workspace">
          <el-select v-model="selectedWsId" placeholder="选择 WS" @change="onWsChange">
            <el-option v-for="ws in workspaces" :key="ws.id" :label="ws.name" :value="ws.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Chat">
          <el-select v-model="selectedChatId" placeholder="全部群聊" :disabled="!selectedWsId" clearable>
            <el-option v-for="chat in chats" :key="chat.id" :label="chat.chat_name || `Chat ${chat.id}`" :value="chat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="天数">
          <el-select v-model="days" style="width: 100px">
            <el-option :value="7" label="7 天" />
            <el-option :value="30" label="30 天" />
            <el-option :value="90" label="90 天" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-loading="loading">
      <!-- 指标卡 -->
      <el-row :gutter="16" style="margin-bottom: 16px">
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="metric-card">
              <div class="metric-label">总 Token (入/出)</div>
              <div class="metric-value">{{ fmtTokens(costData?.summary.total_input_tokens ?? 0) }} / {{ fmtTokens(costData?.summary.total_output_tokens ?? 0) }}</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="metric-card">
              <div class="metric-label">总费用</div>
              <div class="metric-value cost">{{ fmtCost(costData?.summary.total_cost_usd ?? 0) }}</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="metric-card">
              <div class="metric-label">Run 数</div>
              <div class="metric-value">{{ costData?.summary.total_runs ?? 0 }}</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="metric-card">
              <div class="metric-label">日均费用</div>
              <div class="metric-value cost">{{ fmtCost((costData?.summary.total_cost_usd ?? 0) / Math.max(costData?.total ?? 1, 1)) }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <!-- Cost 趋势图 -->
        <el-col :span="12">
          <el-card style="margin-bottom: 16px">
            <template #header>Cost 趋势（按日）</template>
            <div v-if="costData && costData.items.length" class="chart-container">
              <div v-for="item in costData.items" :key="item.date" class="chart-bar-wrapper">
                <div class="chart-bar" :style="{ height: costBarHeight(item) + 'px' }" :title="`${item.date}: ${fmtCost(item.cost_usd)}`" />
                <div class="chart-label">{{ item.date.slice(5) }}</div>
              </div>
            </div>
            <el-empty v-else description="无数据" :image-size="60" />
          </el-card>
        </el-col>

        <!-- 模型占比 -->
        <el-col :span="12">
          <el-card style="margin-bottom: 16px">
            <template #header>模型占比</template>
            <el-table :data="modelItems" size="small" v-if="modelItems.length">
              <el-table-column prop="model" label="模型" min-width="200" show-overflow-tooltip />
              <el-table-column label="调用次数" width="90" align="center">
                <template #default="{ row }">{{ row.call_count }}</template>
              </el-table-column>
              <el-table-column label="Tokens" width="140">
                <template #default="{ row }">{{ fmtTokens(row.input_tokens) }} / {{ fmtTokens(row.output_tokens) }}</template>
              </el-table-column>
              <el-table-column label="费用" width="100">
                <template #default="{ row }">{{ fmtCost(row.cost_usd) }}</template>
              </el-table-column>
              <el-table-column label="占比" width="80" align="center">
                <template #default="{ row }">{{ (row.cost_pct * 100).toFixed(1) }}%</template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="无数据" :image-size="60" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 工具耗时 TopN -->
      <el-card>
        <template #header>工具统计 TopN</template>
        <el-table :data="toolItems" size="small" v-if="toolItems.length">
          <el-table-column prop="tool_name" label="工具" min-width="150" />
          <el-table-column label="调用次数" width="90" align="center">
            <template #default="{ row }">{{ row.call_count }}</template>
          </el-table-column>
          <el-table-column label="平均耗时" width="100">
            <template #default="{ row }">{{ fmtDuration(row.avg_duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="最大耗时" width="100">
            <template #default="{ row }">{{ fmtDuration(row.max_duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="错误次数" width="90" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.error_count > 0 ? 'var(--el-color-danger)' : '' }">{{ row.error_count }}</span>
            </template>
          </el-table-column>
          <el-table-column label="错误率" width="80" align="center">
            <template #default="{ row }">{{ (row.error_rate * 100).toFixed(1) }}%</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="无数据" :image-size="60" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.metric-card {
  text-align: center;
  padding: 8px 0;
}
.metric-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.metric-value {
  font-size: 22px;
  font-weight: bold;
}
.metric-value.cost {
  color: var(--el-color-success);
}
.chart-container {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 160px;
  overflow-x: auto;
  padding-top: 20px;
}
.chart-bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 36px;
}
.chart-bar {
  width: 24px;
  border-radius: 3px 3px 0 0;
  background: var(--el-color-primary-light-3);
  transition: height 0.3s;
}
.chart-bar:hover {
  background: var(--el-color-primary);
}
.chart-label {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
