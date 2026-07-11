<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { usersApi } from '@/api/users'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type { UserOut } from '@/types/user'

const users = ref<UserOut[]>([])
const loading = ref(false)
const createDialogVisible = ref(false)
const createForm = ref({ username: '', password: '', role: 'user' as 'admin' | 'user' })
const createLoading = ref(false)
const resetDialogVisible = ref(false)
const resettingUser = ref<UserOut | null>(null)
const newPassword = ref('')

async function fetchList() {
  loading.value = true
  try {
    const res = await usersApi.list()
    users.value = res.items
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  if (!createForm.value.username || !createForm.value.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (createForm.value.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  createLoading.value = true
  try {
    await usersApi.create({
      username: createForm.value.username,
      password: createForm.value.password,
      role: createForm.value.role,
    })
    showSuccess('创建成功')
    createDialogVisible.value = false
    createForm.value = { username: '', password: '', role: 'user' }
    await fetchList()
  } finally {
    createLoading.value = false
  }
}

async function toggleStatus(user: UserOut) {
  const newStatus = user.status === 'active' ? 'disabled' : 'active'
  await usersApi.patch(user.id, { status: newStatus })
  showSuccess(`已${newStatus === 'active' ? '启用' : '停用'}`)
  await fetchList()
}

async function toggleRole(user: UserOut) {
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  await usersApi.patch(user.id, { role: newRole })
  showSuccess(`角色已切换为 ${newRole}`)
  await fetchList()
}

function openReset(user: UserOut) {
  resettingUser.value = user
  newPassword.value = ''
  resetDialogVisible.value = true
}

async function onResetPassword() {
  if (!resettingUser.value) return
  if (newPassword.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  await usersApi.resetPassword(resettingUser.value.id, { new_password: newPassword.value })
  showSuccess('密码已重置')
  resetDialogVisible.value = false
  resettingUser.value = null
}

function roleType(role: string) {
  return role === 'admin' ? 'danger' : 'info'
}

onMounted(fetchList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="createDialogVisible = true">
        <el-icon><Plus /></el-icon> 创建用户
      </el-button>
    </div>

    <el-table :data="users" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column label="角色" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="roleType(row.role)">{{ row.role }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" align="center">
        <template #default="{ row }">
          <el-button text size="small" @click="toggleRole(row)">切换角色</el-button>
          <el-button text size="small" @click="toggleStatus(row)">
            {{ row.status === 'active' ? '停用' : '启用' }}
          </el-button>
          <el-button text size="small" type="warning" @click="openReset(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createDialogVisible" title="创建用户" width="440">
      <el-form label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="createForm.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="400">
      <p style="margin-bottom: 12px">为用户「{{ resettingUser?.username }}」重置密码：</p>
      <el-input v-model="newPassword" type="password" show-password placeholder="新密码（至少 8 位）" />
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onResetPassword">重置</el-button>
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
