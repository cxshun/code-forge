<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workspacesApi } from '@/api/workspaces'
import type { WorkspaceBrief, ChatBrief } from '@/types/workspace'
import type { RunOut } from '@/types/run'

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
const messages = ref<Array<{ role: string; content: string | null; reasoning?: string | null; created_at?: string | null }>>([])

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
    messages.value = res.messages
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
            <pre v-if="msg.content" class="msg-content">{{ msg.content }}</pre>
            <span v-else-if="!msg.reasoning" style="color: #999; font-style: italic">无内容</span>
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
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
}
</style>
