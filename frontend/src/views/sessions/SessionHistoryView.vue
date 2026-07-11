<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { workspacesApi } from '@/api/workspaces'
import type { WorkspaceBrief, ChatBrief } from '@/types/workspace'
import type { RunOut } from '@/types/run'

const workspaces = ref<WorkspaceBrief[]>([])
const selectedWsId = ref<number | null>(null)
const chats = ref<ChatBrief[]>([])
const selectedChatId = ref<number | null>(null)
const runs = ref<RunOut[]>([])
const loading = ref(false)

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
      <el-table-column prop="trigger_message_id" label="触发消息 ID" min-width="200" />
      <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip />
    </el-table>
    <el-empty v-else-if="!selectedChatId" description="选择 Workspace 和群聊查看会话历史" />
  </div>
</template>
