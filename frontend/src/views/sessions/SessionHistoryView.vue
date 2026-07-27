<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { workspacesApi } from '@/api/workspaces'
import type { WorkspaceBrief, ChatBrief } from '@/types/workspace'
import type { RunOut } from '@/types/run'

marked.setOptions({ gfm: true, breaks: true })

const workspaces = ref<WorkspaceBrief[]>([])
const selectedWsId = ref<number | null>(null)
const chats = ref<ChatBrief[]>([])
const selectedChatId = ref<number | null>(null)
const runs = ref<RunOut[]>([])
const loading = ref(false)

// 消息对话框
const msgDialogVisible = ref(false)
const msgDialogRunId = ref<number | null>(null)
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

function contentPreview(text: string | null, max = 200): string {
  if (!text) return ''
  const formatted = formatContent(text)
  return formatted.length > max ? formatted.slice(0, max) + '...' : formatted
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
  runs.value = []
}

async function fetchRuns() {
  if (!selectedWsId.value || !selectedChatId.value) return
  loading.value = true
  try {
    const res = await workspacesApi.listRuns(selectedWsId.value, { chat_id: selectedChatId.value })
    runs.value = res.items
  } finally {
    loading.value = false
  }
}

watch(selectedChatId, fetchRuns)

async function viewMessages(run: RunOut) {
  if (!selectedWsId.value) return
  msgDialogRunId.value = run.id
  msgLoading.value = true
  msgDialogVisible.value = true
  messages.value = []
  try {
    const res = await workspacesApi.getRunMessages(selectedWsId.value, run.id)
    messages.value = res.messages as typeof messages.value
  } catch {
    ElMessage.error('加载消息失败')
  } finally {
    msgLoading.value = false
  }
}

function roleLabel(role: string) {
  return { user: '用户', assistant: '助手', tool_result: '工具结果', tool_use: '工具调用' }[role] || role
}

function roleColor(role: string) {
  return { user: 'primary', assistant: 'success', tool_result: 'warning' }[role] || 'info'
}

function runStatusType(status: string) {
  return {
    completed: 'success',
    running: 'primary',
    queued: 'info',
    failed: 'danger',
    interrupted: 'warning',
    cancelled: 'info',
  }[status] || 'info'
}

function truncate(text: string | null, max = 200) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

function fmtTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
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
    <h2 style="margin-bottom: 16px">会话历史</h2>

    <el-card style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="Workspace">
          <el-select v-model="selectedWsId" placeholder="选择 WS" @change="onWsChange">
            <el-option v-for="ws in workspaces" :key="ws.id" :label="ws.name" :value="ws.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Chat">
          <el-select
            v-model="selectedChatId"
            placeholder="选择群聊"
            :disabled="!selectedWsId"
          >
            <el-option
              v-for="chat in chats"
              :key="chat.id"
              :label="chat.chat_name || `Chat ${chat.id}`"
              :value="chat.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="runs" v-loading="loading" v-if="selectedChatId">
      <el-table-column prop="id" label="Run ID" width="80" />
      <el-table-column prop="session_id" label="Session ID" width="100" />
      <el-table-column label="状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="runStatusType(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="trigger_message_id" label="触发消息 ID" min-width="180" show-overflow-tooltip />
      <el-table-column label="开始时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.ended_at) }}</template>
      </el-table-column>
      <el-table-column label="对话" width="120" align="center">
        <template #default="{ row }">
          <el-button size="small" @click.stop="viewMessages(row)" :disabled="row.status === 'queued' || row.status === 'running'">查看</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip />
    </el-table>
    <el-empty v-else-if="!selectedChatId" description="选择 Workspace 和群聊查看会话历史" />

    <el-dialog v-model="msgDialogVisible" :title="`Run #${msgDialogRunId} 会话消息`" width="80%" top="5vh" destroy-on-close>
      <div v-loading="msgLoading" style="max-height: 65vh; overflow-y: auto; padding: 8px 0">
        <div v-for="(msg, i) in messages" :key="i" class="msg-item">
          <div class="msg-header">
            <el-tag :type="roleColor(msg.role)" size="small">{{ roleLabel(msg.role) }}</el-tag>
            <span class="msg-index">#{{ i + 1 }}</span>
            <span v-if="msg.created_at" class="msg-time">{{ fmtTime(msg.created_at) }}</span>
          </div>
          <div class="msg-body">
            <details v-if="msg.reasoning" style="margin-bottom: 8px; font-size: 13px; color: var(--el-text-color-secondary);">
              <summary style="cursor: pointer;">💭 模型思考</summary>
              <pre style="white-space: pre-wrap; word-break: break-word; margin: 6px 0 0; font-size: 13px; line-height: 1.6;">{{ msg.reasoning }}</pre>
            </details>
            <!-- tool_calls 展示 -->
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
            <!-- content 展示：JSON 格式化，Markdown 渲染，长内容可折叠 -->
            <template v-if="msg.content">
              <template v-if="isJsonContent(msg.content)">
                <details v-if="isLongContent(msg.content)" style="font-size: 14px;">
                  <summary style="cursor: pointer; color: var(--el-text-color-secondary); margin-bottom: 4px;">📄 JSON ({{ msg.content.length }} 字符)</summary>
                  <pre class="msg-content">{{ formatContent(msg.content) }}</pre>
                </details>
                <pre v-else class="msg-content">{{ formatContent(msg.content) }}</pre>
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
.msg-item {
  margin-bottom: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  overflow: hidden;
}
.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color-light);
}
.msg-index {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.msg-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
}
.msg-body {
  padding: 12px;
}
.msg-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
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
.markdown-body :deep(h4) { font-size: 1em; }
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
