<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { tracesApi } from '@/api/traces'
import { workspacesApi } from '@/api/workspaces'
import type { TraceListItem, SpanOut } from '@/types/trace'
import type { WorkspaceBrief, ChatBrief } from '@/types/workspace'

marked.setOptions({ gfm: true, breaks: true })

const workspaces = ref<WorkspaceBrief[]>([])
const selectedWsId = ref<number | null>(null)
const chats = ref<ChatBrief[]>([])
const selectedChatId = ref<number | null>(null)
const statusFilter = ref<string>('')

const traces = ref<TraceListItem[]>([])
const loading = ref(false)

const selectedTrace = ref<TraceListItem | null>(null)
const spans = ref<SpanOut[]>([])
const spansLoading = ref(false)
const payloadDialog = ref<{ spanId: string; suffix: string } | null>(null)
const payloadContent = ref('')
const payloadLoading = ref(false)

// 会话消息对话框
const msgDialogVisible = ref(false)
const msgLoading = ref(false)
const messages = ref<Array<{ role: string; content: string | null; reasoning?: string | null; tool_calls?: Array<{ id: string; name: string; input: string }> | null; created_at?: string | null }>>([])

function formatContent(text: string | null): string {
  if (!text) return ''
  const trimmed = text.trim()
  if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
    try {
      return JSON.stringify(JSON.parse(trimmed), null, 2)
    } catch {
      // not valid JSON
    }
  }
  return text
}

function parseToolInput(input: string): string {
  if (!input) return ''
  try {
    return JSON.stringify(JSON.parse(input), null, 2)
  } catch {
    return input
  }
}

function isLongContent(text: string | null, threshold = 500): boolean {
  if (!text) return false
  return text.length > threshold
}

function isJsonContent(text: string | null): boolean {
  if (!text) return false
  const t = text.trim()
  return (t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))
}

function renderMarkdown(text: string): string {
  return marked.parse(text) as string
}

async function onWsChange() {
  if (!selectedWsId.value) return
  const detail = await workspacesApi.get(selectedWsId.value)
  chats.value = detail.chats
  selectedChatId.value = null
  traces.value = []
  selectedTrace.value = null
}

async function fetchTraces() {
  if (!selectedWsId.value) return
  loading.value = true
  try {
    const res = await tracesApi.list(selectedWsId.value, {
      chat_id: selectedChatId.value ?? undefined,
      status: statusFilter.value || undefined,
    })
    traces.value = res.items
  } finally {
    loading.value = false
  }
}

watch([selectedChatId, statusFilter], fetchTraces)

async function openTrace(row: TraceListItem) {
  if (!selectedWsId.value) return
  selectedTrace.value = row
  spansLoading.value = true
  spans.value = []
  try {
    const res = await tracesApi.getSpans(selectedWsId.value, row.run_id)
    spans.value = res.items
  } finally {
    spansLoading.value = false
  }
}

async function viewConversation(runId: number) {
  if (!selectedWsId.value) return
  msgDialogVisible.value = true
  msgLoading.value = true
  messages.value = []
  try {
    const res = await workspacesApi.getRunMessages(selectedWsId.value, runId)
    messages.value = res.messages as typeof messages.value
  } catch {
    ElMessage.error('加载会话消息失败')
  } finally {
    msgLoading.value = false
  }
}

const spanTree = computed(() => buildTree(spans.value))

function buildTree(flatSpans: SpanOut[]): SpanOut[] {
  const map = new Map<string, SpanOut & { children: SpanOut[] }>()
  const roots: SpanOut[] = []
  for (const s of flatSpans) {
    map.set(s.span_id, { ...s, children: [] })
  }
  for (const s of flatSpans) {
    const node = map.get(s.span_id)!
    if (s.parent_span_id && map.has(s.parent_span_id)) {
      map.get(s.parent_span_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
}

function flattenTree(nodes: SpanOut[], depth = 0, acc: (SpanOut & { depth: number })[] = []): (SpanOut & { depth: number })[] {
  for (const n of nodes) {
    acc.push({ ...(n as SpanOut & { children: SpanOut[] }), depth })
    if ((n as SpanOut & { children: SpanOut[] }).children.length) {
      flattenTree((n as SpanOut & { children: SpanOut[] }).children, depth + 1, acc)
    }
  }
  return acc
}

const flatSpans = computed(() => flattenTree(spanTree.value))

const maxDuration = computed(() => {
  const max = spans.value.reduce((m, s) => Math.max(m, s.duration_ms ?? 0), 0)
  return max || 1
})

function barStyle(span: SpanOut) {
  const start = spanOffsetMs(span)
  const width = ((span.duration_ms ?? 0) / maxDuration.value) * 100
  const left = (start / maxDuration.value) * 100
  return { marginLeft: `${left}%`, width: `${Math.max(width, 0.5)}%` }
}

function spanOffsetMs(span: SpanOut): number {
  const root = spans.value.find((s) => s.parent_span_id === null)
  if (!root || !root.started_at || !span.started_at) return 0
  const rootTs = new Date(root.started_at).getTime()
  const spanTs = new Date(span.started_at).getTime()
  return Math.max(0, spanTs - rootTs)
}

function spanTypeColor(type: string): string {
  return {
    run: 'primary',
    llm: 'success',
    tool: 'warning',
    skill: 'info',
  }[type] || 'info'
}

function statusType(status: string): string {
  return {
    ok: 'success',
    error: 'danger',
  }[status] || 'info'
}

async function viewPayload(spanId: string, suffix: string) {
  if (!selectedWsId.value) return
  payloadDialog.value = { spanId, suffix }
  payloadLoading.value = true
  payloadContent.value = ''
  try {
    const buf = await tracesApi.getPayload(selectedWsId.value, spanId, suffix)
    const text = new TextDecoder().decode(buf)
    try {
      payloadContent.value = JSON.stringify(JSON.parse(text), null, 2)
    } catch {
      payloadContent.value = text
    }
  } catch {
    payloadContent.value = '加载失败或文件不存在'
  } finally {
    payloadLoading.value = false
  }
}

function fmtDuration(ms: number | null): string {
  if (ms === null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function fmtCost(cost: number | null): string {
  if (cost === null) return '-'
  return `$${cost.toFixed(4)}`
}

function fmtTokens(input: number | null, output: number | null): string {
  return `${input ?? 0} / ${output ?? 0}`
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function roleLabel(role: string) {
  return { user: '用户', assistant: '助手', tool_result: '工具结果' }[role] || role
}

function roleColor(role: string) {
  return { user: 'primary', assistant: 'success', tool_result: 'warning' }[role] || 'info'
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
    <h2 style="margin-bottom: 16px">Trace 观测</h2>

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
        <el-form-item label="状态">
          <el-select v-model="statusFilter" placeholder="全部" clearable style="width: 120px">
            <el-option label="成功" value="ok" />
            <el-option label="错误" value="error" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="traces" v-loading="loading" @row-click="openTrace" highlight-current-row style="margin-bottom: 16px">
      <el-table-column prop="run_id" label="Run ID" width="80" />
      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
      </el-table-column>
      <el-table-column label="Tokens (in/out)" width="130">
        <template #default="{ row }">{{ fmtTokens(row.total_input_tokens, row.total_output_tokens) }}</template>
      </el-table-column>
      <el-table-column label="费用" width="90">
        <template #default="{ row }">{{ fmtCost(row.total_cost_usd) }}</template>
      </el-table-column>
      <el-table-column prop="span_count" label="Span 数" width="80" />
      <el-table-column label="会话" width="80" align="center">
        <template #default="{ row }">
          <el-button size="small" @click.stop="viewConversation(row.run_id)" :disabled="row.status !== 'ok'">查看</el-button>
        </template>
      </el-table-column>
      <el-table-column label="开始时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column prop="error_type" label="错误类型" min-width="130" show-overflow-tooltip />
    </el-table>

    <el-dialog :model-value="!!selectedTrace" @update:model-value="selectedTrace = null" :title="selectedTrace ? `Run #${selectedTrace.run_id} Span 瀑布图` : ''" width="90%" top="5vh" destroy-on-close @close="selectedTrace = null">
      <template #header="{ titleId, titleClass }">
        <div style="display: flex; align-items: center; justify-content: space-between">
          <span :id="titleId" :class="titleClass">{{ selectedTrace ? `Run #${selectedTrace.run_id} Span 瀑布图` : '' }}</span>
          <el-button size="small" v-if="selectedTrace" @click="viewConversation(selectedTrace.run_id)">查看会话消息</el-button>
        </div>
      </template>
      <div v-loading="spansLoading">
        <el-table :data="flatSpans" row-key="span_id" size="small" :max-height="500" v-if="flatSpans.length">
          <el-table-column label="Span" min-width="300">
            <template #default="{ row }">
              <span :style="{ paddingLeft: `${row.depth * 20}px` }">
                <el-tag :type="spanTypeColor(row.span_type)" size="small" style="margin-right: 6px">{{ row.span_type }}</el-tag>
                <span v-if="row.tool_name">{{ row.tool_name }}</span>
                <span v-else-if="row.model">{{ row.model }}</span>
                <span v-else>{{ row.span_id.slice(0, 8) }}</span>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="100">
            <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column label="时间线" min-width="300">
            <template #default="{ row }">
              <div class="timeline-bar" :style="barStyle(row)" />
            </template>
          </el-table-column>
          <el-table-column label="Tokens" width="120">
            <template #default="{ row }">{{ fmtTokens(row.input_tokens, row.output_tokens) }}</template>
          </el-table-column>
          <el-table-column label="Payload" width="240">
            <template #default="{ row }">
              <el-button v-if="row.payload_ref" link size="small" @click.stop="viewPayload(row.span_id, 'request')">req</el-button>
              <el-button v-if="row.payload_ref" link size="small" @click.stop="viewPayload(row.span_id, 'response')">resp</el-button>
              <el-button v-if="row.span_type === 'tool'" link size="small" @click.stop="viewPayload(row.span_id, 'tool')">tool</el-button>
              <el-tag v-if="row.payload_truncated" type="warning" size="small">截断</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="错误" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error_type" style="color: var(--el-color-danger)">
                {{ row.error_type }}: {{ row.error_message }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="无 span 数据" />
      </div>
    </el-dialog>

    <el-dialog :model-value="!!payloadDialog" @update:model-value="payloadDialog = null" :title="payloadDialog ? `Payload: ${payloadDialog.spanId.slice(0, 8)}.${payloadDialog.suffix}` : ''" width="70%" destroy-on-close>
      <div v-loading="payloadLoading">
        <el-input v-model="payloadContent" type="textarea" :rows="20" readonly style="font-family: monospace" />
      </div>
    </el-dialog>

    <el-dialog v-model="msgDialogVisible" title="会话消息（含模型思考内容）" width="80%" top="5vh" destroy-on-close>
      <div v-loading="msgLoading" style="max-height: 65vh; overflow-y: auto; padding: 8px 0">
        <div v-for="(msg, i) in messages" :key="i" class="msg-item" style="margin-bottom: 16px; border: 1px solid var(--el-border-color-light); border-radius: 6px; overflow: hidden;">
          <div class="msg-header" style="display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--el-fill-color-light); border-bottom: 1px solid var(--el-border-color-light);">
            <el-tag :type="roleColor(msg.role)" size="small">{{ roleLabel(msg.role) }}</el-tag>
            <span style="font-size: 12px; color: var(--el-text-color-secondary)">#{{ i + 1 }}</span>
          </div>
          <div class="msg-body" style="padding: 12px;">
            <details v-if="msg.reasoning" style="margin-bottom: 8px; background: var(--el-fill-color-light); padding: 8px 12px; border-radius: 6px; font-size: 13px;">
              <summary style="cursor: pointer; color: var(--el-text-color-secondary);">💭 模型思考</summary>
              <pre style="margin: 8px 0 0; white-space: pre-wrap; word-break: break-word; font-size: 13px; line-height: 1.6; color: var(--el-text-color-regular);">{{ msg.reasoning }}</pre>
            </details>
            <details v-if="msg.tool_calls && msg.tool_calls.length" style="margin-bottom: 8px; font-size: 13px;">
              <summary style="cursor: pointer; color: var(--el-color-primary);">🔧 工具调用 ({{ msg.tool_calls.length }})</summary>
              <div v-for="tc in msg.tool_calls" :key="tc.id" style="margin: 8px 0; padding: 8px; background: var(--el-fill-color-light); border-radius: 4px;">
                <div style="margin-bottom: 4px;">
                  <el-tag size="small" type="info">{{ tc.name }}</el-tag>
                  <span style="font-size: 12px; color: var(--el-text-color-secondary); margin-left: 6px;">{{ tc.id }}</span>
                </div>
                <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.5; color: var(--el-text-color-regular);">{{ parseToolInput(tc.input) }}</pre>
              </div>
            </details>
            <template v-if="msg.content">
              <template v-if="isJsonContent(msg.content)">
                <details v-if="isLongContent(msg.content)" style="font-size: 14px;">
                  <summary style="cursor: pointer; color: var(--el-text-color-secondary); margin-bottom: 4px;">📄 JSON ({{ msg.content.length }} 字符)</summary>
                  <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: 'Menlo', 'Monaco', 'Courier New', monospace; font-size: 13px; line-height: 1.6;">{{ formatContent(msg.content) }}</pre>
                </details>
                <pre v-else style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: 'Menlo', 'Monaco', 'Courier New', monospace; font-size: 13px; line-height: 1.6;">{{ formatContent(msg.content) }}</pre>
              </template>
              <template v-else>
                <details v-if="isLongContent(msg.content)" style="font-size: 14px;">
                  <summary style="cursor: pointer; color: var(--el-text-color-secondary); margin-bottom: 4px;">📄 内容 ({{ msg.content.length }} 字符)</summary>
                  <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                </details>
                <div v-else class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
              </template>
            </template>
            <span v-else-if="!msg.reasoning && !(msg.tool_calls && msg.tool_calls.length)" style="color: #999; font-style: italic">无内容</span>
          </div>
        </div>
        <el-empty v-if="!msgLoading && messages.length === 0" description="无消息记录" :image-size="60" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.timeline-bar {
  height: 18px;
  border-radius: 3px;
  background: var(--el-color-primary-light-3);
  min-width: 2px;
  transition: width 0.2s;
}
.markdown-body {
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin: 16px 0 8px;
  font-weight: 600;
  line-height: 1.4;
}
.markdown-body :deep(h1) { font-size: 1.5em; }
.markdown-body :deep(h2) { font-size: 1.3em; }
.markdown-body :deep(h3) { font-size: 1.15em; }
.markdown-body :deep(p) { margin: 8px 0; }
.markdown-body :deep(ul),
.markdown-body :deep(ol) { margin: 8px 0; padding-left: 24px; }
.markdown-body :deep(li) { margin: 4px 0; }
.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--el-fill-color-light);
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 0.9em;
}
.markdown-body :deep(pre) {
  margin: 8px 0;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-darker);
  overflow-x: auto;
}
.markdown-body :deep(pre code) {
  padding: 0;
  background: none;
  font-size: 13px;
}
.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 8px 16px;
  border-left: 4px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
}
.markdown-body :deep(table) {
  margin: 8px 0;
  border-collapse: collapse;
  width: 100%;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 6px 12px;
  border: 1px solid var(--el-border-color);
  text-align: left;
}
.markdown-body :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.markdown-body :deep(a) {
  color: var(--el-color-primary);
  text-decoration: none;
}
.markdown-body :deep(a:hover) {
  text-decoration: underline;
}
.markdown-body :deep(hr) {
  margin: 16px 0;
  border: none;
  border-top: 1px solid var(--el-border-color);
}
.markdown-body :deep(img) {
  max-width: 100%;
}
</style>
