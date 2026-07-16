<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workspacesApi } from '@/api/workspaces'
import { useTaskPolling } from '@/composables/useTaskPolling'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type { WorkspaceOut } from '@/types/workspace'

const router = useRouter()
const workspaces = ref<WorkspaceOut[]>([])
const loading = ref(false)
const createDialogVisible = ref(false)
const createForm = ref({ name: '' })
const createLoading = ref(false)

const { task: deleteTask, isDone: deleteDone, start: startDeletePoll } = useTaskPolling()

async function fetchList() {
  loading.value = true
  try {
    const res = await workspacesApi.list()
    workspaces.value = res.items
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入工作空间名称')
    return
  }
  createLoading.value = true
  try {
    await workspacesApi.create({ name: createForm.value.name })
    showSuccess('创建成功')
    createDialogVisible.value = false
    createForm.value.name = ''
    await fetchList()
  } finally {
    createLoading.value = false
  }
}

async function onDelete(ws: WorkspaceOut) {
  const ok = await confirmDelete(`确定删除工作空间「${ws.name}」？所有数据将被级联清理。`)
  if (!ok) return
  try {
    const res = await workspacesApi.delete(ws.id)
    ElMessage.info('删除任务已提交，正在清理...')
    startDeletePoll(res.task_id)
  } catch {
    // 错误已由拦截器提示
  }
}

function goToDetail(ws: WorkspaceOut) {
  router.push(`/workspaces/${ws.id}`)
}

onMounted(fetchList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>工作空间</h2>
      <el-button type="primary" @click="createDialogVisible = true">
        <el-icon><Plus /></el-icon> 创建工作空间
      </el-button>
    </div>

    <el-table :data="workspaces" v-loading="loading" @row-click="goToDetail" style="cursor: pointer">
      <el-table-column prop="name" label="名称" />
      <el-table-column label="所有者" width="120">
        <template #default="{ row }">
          {{ row.owner_name || `#${row.owner_id}` }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="center">
        <template #default="{ row }">
          <el-button text type="danger" @click.stop="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createDialogVisible" title="创建工作空间" width="420">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="输入工作空间名称" @keyup.enter="onCreate" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-alert
      v-if="deleteDone"
      title="工作空间删除完成"
      type="success"
      :closable="true"
      @close="fetchList()"
      style="margin-top: 16px"
    />
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
