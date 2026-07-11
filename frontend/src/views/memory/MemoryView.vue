<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { workspacesApi } from '@/api/workspaces'
import { memoryApi } from '@/api/memory'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type { WorkspaceBrief } from '@/types/workspace'
import type { ChatBrief } from '@/types/workspace'
import type { MemoryFile } from '@/types/memory'

const workspaces = ref<WorkspaceBrief[]>([])
const selectedWsId = ref<number | null>(null)
const chats = ref<ChatBrief[]>([])
const selectedChatId = ref<number | null>(null)
const files = ref<MemoryFile[]>([])
const currentFile = ref<string | null>(null)
const fileContent = ref('')
const loading = ref(false)
const saving = ref(false)
const newFileDialog = ref(false)
const newFileName = ref('')

async function onWsChange() {
  if (!selectedWsId.value) return
  const detail = await workspacesApi.get(selectedWsId.value)
  chats.value = detail.chats
  selectedChatId.value = null
  files.value = []
  currentFile.value = null
}

async function onChatChange() {
  if (!selectedWsId.value || !selectedChatId.value) return
  loading.value = true
  try {
    const res = await memoryApi.list(selectedWsId.value, selectedChatId.value)
    files.value = res.files
    currentFile.value = null
    fileContent.value = ''
  } finally {
    loading.value = false
  }
}

async function openFile(filename: string) {
  if (!selectedWsId.value || !selectedChatId.value) return
  loading.value = true
  try {
    const res = await memoryApi.get(selectedWsId.value, selectedChatId.value, filename)
    currentFile.value = filename
    fileContent.value = res.content
  } finally {
    loading.value = false
  }
}

async function saveFile() {
  if (!selectedWsId.value || !selectedChatId.value || !currentFile.value) return
  saving.value = true
  try {
    await memoryApi.put(selectedWsId.value, selectedChatId.value, currentFile.value, {
      content: fileContent.value,
    })
    showSuccess('已保存')
  } finally {
    saving.value = false
  }
}

async function deleteFile(filename: string) {
  if (!selectedWsId.value || !selectedChatId.value) return
  const ok = await confirmDelete(`确定删除「${filename}」？`)
  if (!ok) return
  await memoryApi.delete(selectedWsId.value, selectedChatId.value, filename)
  showSuccess('已删除')
  if (currentFile.value === filename) {
    currentFile.value = null
    fileContent.value = ''
  }
  await onChatChange()
}

async function createFile() {
  const name = newFileName.value.trim()
  if (!name) {
    ElMessage.warning('请输入文件名')
    return
  }
  if (!/^[A-Za-z0-9_\-]+\.md$/.test(name)) {
    ElMessage.error('文件名仅允许字母、数字、下划线、横线，且以 .md 结尾')
    return
  }
  if (!selectedWsId.value || !selectedChatId.value) return
  await memoryApi.put(selectedWsId.value, selectedChatId.value, name, { content: '' })
  showSuccess('已创建')
  newFileDialog.value = false
  newFileName.value = ''
  await onChatChange()
  await openFile(name)
}

onMounted(async () => {
  const { useUserStore } = await import('@/stores/user')
  const store = useUserStore()
  await store.fetchMe()
  workspaces.value = store.workspaces
})
</script>

<template>
  <div>
    <h2 style="margin-bottom: 16px">Memory 管理</h2>

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
            @change="onChatChange"
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

    <el-row :gutter="16" v-if="selectedChatId">
      <el-col :span="8">
        <el-card v-loading="loading">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>Memory 文件</span>
              <el-button size="small" type="primary" @click="newFileDialog = true">新建</el-button>
            </div>
          </template>
          <el-table :data="files" :show-header="false" @row-click="(row: MemoryFile) => openFile(row.filename)">
            <el-table-column prop="filename" label="文件名" />
            <el-table-column label="" width="60" align="center">
              <template #default="{ row }">
                <el-button text type="danger" size="small" @click.stop="deleteFile(row.filename)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card v-if="currentFile">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>{{ currentFile }}</span>
              <el-button type="primary" size="small" :loading="saving" @click="saveFile">保存</el-button>
            </div>
          </template>
          <el-input
            v-model="fileContent"
            type="textarea"
            :rows="20"
            style="font-family: monospace"
            placeholder="编辑 Markdown 内容..."
          />
        </el-card>
        <el-empty v-else description="选择一个文件查看或编辑" />
      </el-col>
    </el-row>

    <el-dialog v-model="newFileDialog" title="新建 Memory 文件" width="420">
      <el-form label-width="80px">
        <el-form-item label="文件名">
          <el-input v-model="newFileName" placeholder="project_notes.md" @keyup.enter="createFile">
            <template #append>.md</template>
          </el-input>
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" title="仅允许字母、数字、下划线、横线" style="margin-bottom: 12px" />
      <template #footer>
        <el-button @click="newFileDialog = false">取消</el-button>
        <el-button type="primary" @click="createFile">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
