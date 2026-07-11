<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { feishuAppsApi } from '@/api/feishu-apps'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type { FeishuAppOut } from '@/types/feishu-app'

const apps = ref<FeishuAppOut[]>([])
const loading = ref(false)
const createDialogVisible = ref(false)
const createForm = ref({ app_id: '', app_secret: '', name: '' })
const createLoading = ref(false)
const createdSecret = ref('')
const secretDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingApp = ref<FeishuAppOut | null>(null)
const editForm = ref({ name: '', app_secret: '' })

async function fetchList() {
  loading.value = true
  try {
    const res = await feishuAppsApi.list()
    apps.value = res.items
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!createForm.value.app_id || !createForm.value.app_secret || !createForm.value.name) {
    ElMessage.warning('请填写所有字段')
    return
  }
  createLoading.value = true
  try {
    const res = await feishuAppsApi.create({
      app_id: createForm.value.app_id,
      app_secret: createForm.value.app_secret,
      name: createForm.value.name,
    })
    createdSecret.value = res.app_secret
    secretDialogVisible.value = true
    createDialogVisible.value = false
    createForm.value = { app_id: '', app_secret: '', name: '' }
    await fetchList()
  } finally {
    createLoading.value = false
  }
}

function openEdit(app: FeishuAppOut) {
  editingApp.value = app
  editForm.value = { name: app.name, app_secret: '' }
  editDialogVisible.value = true
}

async function onSaveEdit() {
  if (!editingApp.value) return
  const data: { name?: string; app_secret?: string } = {}
  if (editForm.value.name !== editingApp.value.name) data.name = editForm.value.name
  if (editForm.value.app_secret) data.app_secret = editForm.value.app_secret
  if (Object.keys(data).length === 0) {
    ElMessage.info('未修改')
    return
  }
  await feishuAppsApi.patch(editingApp.value.id, data)
  showSuccess('已更新')
  editDialogVisible.value = false
  await fetchList()
}

async function onDelete(app: FeishuAppOut) {
  const ok = await confirmDelete(`确定删除飞书 App「${app.name}」？需先解绑所有群聊。`)
  if (!ok) return
  await feishuAppsApi.delete(app.id)
  showSuccess('已删除')
  await fetchList()
}

function connStatusType(status: string) {
  return { connected: 'success', disconnected: 'info', error: 'danger' }[status] || 'info'
}

function copySecret() {
  navigator.clipboard.writeText(createdSecret.value)
  ElMessage.success('已复制')
}

onMounted(fetchList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>飞书 App 注册</h2>
      <el-button type="primary" @click="createDialogVisible = true">
        <el-icon><Plus /></el-icon> 注册 App
      </el-button>
    </div>

    <el-table :data="apps" v-loading="loading">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="app_id" label="App ID" width="180" />
      <el-table-column prop="app_secret_masked" label="Secret" width="200" />
      <el-table-column label="连接状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="connStatusType(row.connection_status)">{{ row.connection_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <el-button text @click="openEdit(row)">编辑</el-button>
          <el-button text type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createDialogVisible" title="注册飞书 App" width="480">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="应用名称" />
        </el-form-item>
        <el-form-item label="App ID">
          <el-input v-model="createForm.app_id" placeholder="cli_xxx" />
        </el-form-item>
        <el-form-item label="App Secret">
          <el-input v-model="createForm.app_secret" type="password" show-password placeholder="仅创建时显示一次" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreate">注册</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="secretDialogVisible" title="App Secret（仅此一次）" width="500">
      <el-alert type="warning" title="请立即复制保存，关闭后不再显示" :closable="false" style="margin-bottom: 16px" />
      <el-input :model-value="createdSecret" readonly style="font-family: monospace">
        <template #append>
          <el-button @click="copySecret">复制</el-button>
        </template>
      </el-input>
      <template #footer>
        <el-button type="primary" @click="secretDialogVisible = false">已保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑飞书 App" width="480">
      <el-form label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="新 App Secret">
          <el-input v-model="editForm.app_secret" type="password" show-password placeholder="留空不修改" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
}
</style>
