<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { skillsApi } from '@/api/skills'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type { SkillOut } from '@/types/skill'

const skills = ref<SkillOut[]>([])
const loading = ref(false)
const searchQuery = ref('')
const uploadDialogVisible = ref(false)
const uploadFile = ref<File | null>(null)
const uploadVisibility = ref<'private' | 'public'>('private')
const uploadLoading = ref(false)
const editDialogVisible = ref(false)
const editingSkill = ref<SkillOut | null>(null)
const editForm = ref({ description: '', visibility: 'private' as 'private' | 'public' })

async function fetchList() {
  loading.value = true
  try {
    const res = await skillsApi.list(searchQuery.value || undefined)
    skills.value = res.items
  } finally {
    loading.value = false
  }
}

function onFileChange(file: { raw: File }) {
  uploadFile.value = file.raw
}

async function onUpload() {
  if (!uploadFile.value) {
    ElMessage.warning('请选择 zip 文件（含 SKILL.md）')
    return
  }
  uploadLoading.value = true
  try {
    await skillsApi.create(uploadFile.value, uploadVisibility.value)
    showSuccess('上传成功')
    uploadDialogVisible.value = false
    uploadFile.value = null
    uploadVisibility.value = 'private'
    await fetchList()
  } finally {
    uploadLoading.value = false
  }
}

function openEdit(skill: SkillOut) {
  editingSkill.value = skill
  editForm.value = { description: skill.description, visibility: skill.visibility }
  editDialogVisible.value = true
}

async function onSaveEdit() {
  if (!editingSkill.value) return
  await skillsApi.patch(editingSkill.value.id, editForm.value)
  showSuccess('已更新')
  editDialogVisible.value = false
  await fetchList()
}

async function onDelete(skill: SkillOut) {
  const ok = await confirmDelete(`确定删除 Skill「${skill.name}」？被引用时无法删除。`)
  if (!ok) return
  await skillsApi.delete(skill.id)
  showSuccess('已删除')
  await fetchList()
}

function visType(vis: string) {
  return vis === 'public' ? 'success' : 'info'
}

onMounted(fetchList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>Skill 广场</h2>
      <div style="display: flex; gap: 8px">
        <el-input v-model="searchQuery" placeholder="搜索 Skill" clearable @keyup.enter="fetchList" style="width: 200px" />
        <el-button @click="fetchList">搜索</el-button>
        <el-button type="primary" @click="uploadDialogVisible = true">
          <el-icon><Upload /></el-icon> 上传
        </el-button>
      </div>
    </div>

    <el-table :data="skills" v-loading="loading">
      <el-table-column prop="name" label="名称" width="200" />
      <el-table-column prop="description" label="描述" min-width="200" />
      <el-table-column label="可见性" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="visType(row.visibility)">{{ row.visibility }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="owner_id" label="Owner" width="80" />
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <el-button text @click="openEdit(row)">编辑</el-button>
          <el-button text type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="uploadDialogVisible" title="上传 Skill" width="480">
      <el-form label-width="80px">
        <el-form-item label="文件">
          <el-upload :auto-upload="false" :on-change="onFileChange" accept=".zip" :limit="1">
            <el-button>选择 zip 文件</el-button>
            <template #tip>
              <div style="color: #999; font-size: 12px">zip 包含 SKILL.md + resources/ + scripts/</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="uploadVisibility">
            <el-radio value="private">私有</el-radio>
            <el-radio value="public">公开</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadLoading" @click="onUpload">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑 Skill" width="480">
      <el-form label-width="80px" v-if="editingSkill">
        <el-form-item label="名称">
          <el-input :model-value="editingSkill.name" disabled />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="editForm.visibility">
            <el-radio value="private">私有</el-radio>
            <el-radio value="public">公开</el-radio>
          </el-radio-group>
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
