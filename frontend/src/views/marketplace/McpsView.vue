<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { mcpsApi } from '@/api/mcps'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type { McpOut } from '@/types/mcp'

const mcps = ref<McpOut[]>([])
const loading = ref(false)
const createDialogVisible = ref(false)
const createForm = ref({
  name: '',
  type: 'stdio' as 'stdio' | 'http',
  command: '',
  args: '',
  endpoint: '',
  headers: '',
  visibility: 'private' as 'private' | 'public',
  read_only: false,
})
const createLoading = ref(false)
const editDialogVisible = ref(false)
const editingMcp = ref<McpOut | null>(null)
const editForm = ref({ visibility: 'private' as 'private' | 'public', read_only: false, configText: '' })

async function fetchList() {
  loading.value = true
  try {
    const res = await mcpsApi.list()
    mcps.value = res.items
  } finally {
    loading.value = false
  }
}

function buildConfig(form: typeof createForm.value): Record<string, unknown> {
  if (form.type === 'stdio') {
    const config: Record<string, unknown> = { command: form.command }
    if (form.args) config.args = form.args.split(/\s+/).filter(Boolean)
    return config
  }
  const config: Record<string, unknown> = { endpoint: form.endpoint }
  if (form.headers) {
    try {
      config.headers = JSON.parse(form.headers)
    } catch {
      throw new Error('headers 不是有效 JSON')
    }
  }
  return config
}

async function onCreate() {
  if (!createForm.value.name) {
    ElMessage.warning('请输入名称')
    return
  }
  if (createForm.value.type === 'stdio' && !createForm.value.command) {
    ElMessage.warning('请输入 command')
    return
  }
  if (createForm.value.type === 'http' && !createForm.value.endpoint) {
    ElMessage.warning('请输入 endpoint')
    return
  }
  let config: Record<string, unknown>
  try {
    config = buildConfig(createForm.value)
  } catch (e) {
    ElMessage.error((e as Error).message)
    return
  }
  createLoading.value = true
  try {
    await mcpsApi.create({
      name: createForm.value.name,
      type: createForm.value.type,
      config,
      visibility: createForm.value.visibility,
      read_only: createForm.value.read_only,
    })
    showSuccess('注册成功')
    createDialogVisible.value = false
    createForm.value = {
      name: '', type: 'stdio', command: '', args: '', endpoint: '', headers: '',
      visibility: 'private', read_only: false,
    }
    await fetchList()
  } finally {
    createLoading.value = false
  }
}

function openEdit(mcp: McpOut) {
  editingMcp.value = mcp
  editForm.value = {
    visibility: mcp.visibility,
    read_only: mcp.read_only,
    configText: JSON.stringify(mcp.config, null, 2),
  }
  editDialogVisible.value = true
}

async function onSaveEdit() {
  if (!editingMcp.value) return
  let config: Record<string, unknown>
  try {
    config = JSON.parse(editForm.value.configText)
  } catch {
    ElMessage.error('config 不是有效 JSON')
    return
  }
  await mcpsApi.patch(editingMcp.value.id, {
    config,
    visibility: editForm.value.visibility,
    read_only: editForm.value.read_only,
  })
  showSuccess('已更新')
  editDialogVisible.value = false
  await fetchList()
}

async function onDelete(mcp: McpOut) {
  const ok = await confirmDelete(`确定删除 MCP「${mcp.name}」？被引用时无法删除。`)
  if (!ok) return
  await mcpsApi.delete(mcp.id)
  showSuccess('已删除')
  await fetchList()
}

function visType(vis: string) {
  return vis === 'public' ? 'success' : 'info'
}

function mcpEndpoint(mcp: McpOut): string {
  const cfg = mcp.config as Record<string, any>
  if (mcp.type === 'stdio') {
    const args = Array.isArray(cfg.args) ? (cfg.args as string[]).join(' ') : ''
    return args ? `${cfg.command || ''} ${args}` : (cfg.command || '')
  }
  return cfg.endpoint || ''
}

onMounted(fetchList)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>MCP 广场</h2>
      <el-button type="primary" @click="createDialogVisible = true">
        <el-icon><Plus /></el-icon> 注册 MCP
      </el-button>
    </div>

    <el-row :gutter="16" v-loading="loading">
      <el-col
        v-for="mcp in mcps"
        :key="mcp.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
        class="mcp-col"
      >
        <el-card shadow="hover" class="mcp-card">
          <div class="mcp-head">
            <span class="mcp-name" :title="mcp.name">{{ mcp.name }}</span>
            <el-tag size="small">{{ mcp.type }}</el-tag>
          </div>
          <div class="mcp-endpoint" :title="mcpEndpoint(mcp)">{{ mcpEndpoint(mcp) || '—' }}</div>
          <div class="mcp-tags">
            <el-tag :type="visType(mcp.visibility)" size="small">{{ mcp.visibility }}</el-tag>
            <el-tag :type="mcp.read_only ? 'warning' : 'info'" size="small">
              {{ mcp.read_only ? '只读' : '可写' }}
            </el-tag>
          </div>
          <div class="mcp-foot">
            <span class="mcp-owner">{{ mcp.owner_name || `#${mcp.owner_id}` }}</span>
            <div>
              <el-button text size="small" @click="openEdit(mcp)">编辑</el-button>
              <el-button text size="small" type="danger" @click="onDelete(mcp)">删除</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!loading && !mcps.length" description="暂无 MCP，点击右上角注册" />

    <el-dialog v-model="createDialogVisible" title="注册 MCP" width="560">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="MCP 名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="createForm.type">
            <el-radio value="stdio">stdio</el-radio>
            <el-radio value="http">http</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="createForm.type === 'stdio'">
          <el-form-item label="Command">
            <el-input v-model="createForm.command" placeholder="npx / python3 / ..." />
          </el-form-item>
          <el-form-item label="Args">
            <el-input v-model="createForm.args" placeholder="空格分隔参数" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="Endpoint">
            <el-input v-model="createForm.endpoint" placeholder="https://..." />
          </el-form-item>
          <el-form-item label="Headers">
            <el-input v-model="createForm.headers" type="textarea" :rows="2" placeholder='{"Authorization": "Bearer xxx"}' />
          </el-form-item>
        </template>
        <el-form-item label="可见性">
          <el-radio-group v-model="createForm.visibility">
            <el-radio value="private">私有</el-radio>
            <el-radio value="public">公开</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="只读">
          <el-switch v-model="createForm.read_only" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="onCreate">注册</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑 MCP" width="560">
      <el-form label-width="80px" v-if="editingMcp">
        <el-form-item label="名称">
          <el-input :model-value="editingMcp.name" disabled />
        </el-form-item>
        <el-form-item label="Config">
          <el-input v-model="editForm.configText" type="textarea" :rows="8" style="font-family: monospace" />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="editForm.visibility">
            <el-radio value="private">私有</el-radio>
            <el-radio value="public">公开</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="只读">
          <el-switch v-model="editForm.read_only" />
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

.mcp-col {
  margin-bottom: 16px;
}
.mcp-card {
  height: 100%;
}
.mcp-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.mcp-name {
  font-weight: 600;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mcp-endpoint {
  margin: 10px 0;
  font-family: monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mcp-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.mcp-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 8px;
}
.mcp-owner {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
