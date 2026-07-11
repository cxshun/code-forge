<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { workspacesApi } from '@/api/workspaces'
import { skillsApi } from '@/api/skills'
import { mcpsApi } from '@/api/mcps'
import { feishuAppsApi } from '@/api/feishu-apps'
import { useTaskPolling } from '@/composables/useTaskPolling'
import { confirmDelete, showSuccess } from '@/composables/useConfirmAction'
import type {
  WorkspaceDetail,
  RepoOut,
  ChatOut,
  ChatCheckResult,
  SkillBrief,
  McpBrief,
} from '@/types/workspace'
import type { SkillOut } from '@/types/skill'
import type { McpOut } from '@/types/mcp'
import type { FeishuAppOut } from '@/types/feishu-app'

const route = useRoute()
const wsId = Number(route.params.wsId)

const ws = ref<WorkspaceDetail | null>(null)
const activeTab = ref('overview')
const loading = ref(false)

// Overview
const editName = ref('')
const editConfig = ref('')
const savingOverview = ref(false)

// Repos
const repos = ref<RepoOut[]>([])
const repoDialogVisible = ref(false)
const repoForm = ref({ url: '', token: '' })
const repoLoading = ref(false)
const { task: repoTask, isDone: repoTaskDone, start: startRepoPoll } = useTaskPolling()

// Chats
const chats = ref<ChatOut[]>([])
const chatAppId = ref('')
const chatIdInput = ref('')
const chatCheckResult = ref<ChatCheckResult | null>(null)
const chatChecking = ref(false)
const chatBinding = ref(false)
const feishuApps = ref<FeishuAppOut[]>([])

// Skills
const mountedSkills = ref<SkillBrief[]>([])
const allSkills = ref<SkillOut[]>([])
const selectedSkillId = ref<number | null>(null)

// MCPs
const mountedMcps = ref<McpBrief[]>([])
const allMcps = ref<McpOut[]>([])
const selectedMcpId = ref<number | null>(null)

// AGENT.md
const agentMdContent = ref('')
const agentMdSaving = ref(false)
const repoAgentMdRepoId = ref<number | null>(null)
const repoAgentMdContent = ref('')

async function fetchDetail() {
  loading.value = true
  try {
    ws.value = await workspacesApi.get(wsId)
    editName.value = ws.value.name
    editConfig.value = JSON.stringify(ws.value.context_config ?? {}, null, 2)
    repos.value = (await workspacesApi.listRepos(wsId)).items
    chats.value = (await workspacesApi.listChats(wsId)).items
    mountedSkills.value = (await workspacesApi.listMountedSkills(wsId)).items
    mountedMcps.value = (await workspacesApi.listMountedMcps(wsId)).items
  } finally {
    loading.value = false
  }
}

// Overview
async function saveOverview() {
  let config: Record<string, unknown> | null = null
  try {
    config = JSON.parse(editConfig.value)
  } catch {
    ElMessage.error('context_config 不是有效的 JSON')
    return
  }
  savingOverview.value = true
  try {
    await workspacesApi.patch(wsId, { name: editName.value, context_config: config })
    showSuccess('保存成功')
    await fetchDetail()
  } finally {
    savingOverview.value = false
  }
}

// Repos
async function onAddRepo() {
  if (!repoForm.value.url.trim()) {
    ElMessage.warning('请输入 Git URL')
    return
  }
  repoLoading.value = true
  try {
    const res = await workspacesApi.createRepo(wsId, {
      url: repoForm.value.url,
      token: repoForm.value.token || null,
    })
    showSuccess('Clone 任务已提交')
    repoDialogVisible.value = false
    repoForm.value = { url: '', token: '' }
    startRepoPoll(res.task_id)
  } finally {
    repoLoading.value = false
  }
}

async function onSyncRepo(repo: RepoOut) {
  try {
    const res = await workspacesApi.syncRepo(wsId, repo.id)
    showSuccess('同步任务已提交')
    startRepoPoll(res.task_id)
  } catch {
    // handled
  }
}

async function onDeleteRepo(repo: RepoOut) {
  const ok = await confirmDelete(`确定删除 Repo「${repo.url}」？`)
  if (!ok) return
  await workspacesApi.deleteRepo(wsId, repo.id)
  showSuccess('已删除')
  repos.value = (await workspacesApi.listRepos(wsId)).items
}

// Chats
async function onCheckChat() {
  if (!chatAppId.value || !chatIdInput.value) {
    ElMessage.warning('请选择 App 并输入 chat_id')
    return
  }
  chatChecking.value = true
  chatCheckResult.value = null
  try {
    chatCheckResult.value = await workspacesApi.checkChat(wsId, {
      app_id: chatAppId.value,
      chat_id: chatIdInput.value,
    })
  } finally {
    chatChecking.value = false
  }
}

async function onBindChat() {
  chatBinding.value = true
  try {
    await workspacesApi.bindChat(wsId, {
      app_id: chatAppId.value,
      chat_id: chatIdInput.value,
    })
    showSuccess('绑定成功')
    chatCheckResult.value = null
    chatIdInput.value = ''
    chats.value = (await workspacesApi.listChats(wsId)).items
  } finally {
    chatBinding.value = false
  }
}

async function onUnbindChat(chat: ChatOut) {
  const ok = await confirmDelete(`确定解绑「${chat.chat_name || chat.chat_id}」？`)
  if (!ok) return
  await workspacesApi.unbindChat(wsId, chat.id)
  showSuccess('已解绑')
  chats.value = (await workspacesApi.listChats(wsId)).items
}

// Skills
async function onMountSkill() {
  if (!selectedSkillId.value) {
    ElMessage.warning('请选择 Skill')
    return
  }
  await workspacesApi.mountSkill(wsId, selectedSkillId.value)
  showSuccess('已挂载')
  selectedSkillId.value = null
  mountedSkills.value = (await workspacesApi.listMountedSkills(wsId)).items
}

async function onUnmountSkill(skill: SkillBrief) {
  const ok = await confirmDelete(`确定解挂 Skill「${skill.name}」？`)
  if (!ok) return
  await workspacesApi.unmountSkill(wsId, skill.id)
  showSuccess('已解挂')
  mountedSkills.value = (await workspacesApi.listMountedSkills(wsId)).items
}

// MCPs
async function onMountMcp() {
  if (!selectedMcpId.value) {
    ElMessage.warning('请选择 MCP')
    return
  }
  await workspacesApi.mountMcp(wsId, selectedMcpId.value)
  showSuccess('已挂载')
  selectedMcpId.value = null
  mountedMcps.value = (await workspacesApi.listMountedMcps(wsId)).items
}

async function onUnmountMcp(mcp: McpBrief) {
  const ok = await confirmDelete(`确定解挂 MCP「${mcp.name}」？`)
  if (!ok) return
  await workspacesApi.unmountMcp(wsId, mcp.id)
  showSuccess('已解挂')
  mountedMcps.value = (await workspacesApi.listMountedMcps(wsId)).items
}

// AGENT.md
async function loadAgentMd() {
  const res = await workspacesApi.getAgentMd(wsId)
  agentMdContent.value = res.content
}

async function saveAgentMd() {
  agentMdSaving.value = true
  try {
    await workspacesApi.putAgentMd(wsId, agentMdContent.value)
    showSuccess('AGENT.md 已保存')
  } finally {
    agentMdSaving.value = false
  }
}

async function loadRepoAgentMd() {
  if (!repoAgentMdRepoId.value) {
    repoAgentMdContent.value = ''
    return
  }
  const res = await workspacesApi.getRepoAgentMd(wsId, repoAgentMdRepoId.value)
  repoAgentMdContent.value = res.content
}

watch(repoTaskDone, (done) => {
  if (done) {
    fetchDetail()
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'skills' && allSkills.value.length === 0) {
    allSkills.value = (await skillsApi.list()).items
  } else if (tab === 'mcps' && allMcps.value.length === 0) {
    allMcps.value = (await mcpsApi.list()).items
  } else if (tab === 'agent-md' && !agentMdContent.value) {
    await loadAgentMd()
  } else if (tab === 'chats' && feishuApps.value.length === 0) {
    feishuApps.value = (await feishuAppsApi.list()).items
  }
})

function cloneStatusType(status: string) {
  return { ready: 'success', cloning: 'warning', failed: 'danger', pending: 'info' }[status] || 'info'
}

onMounted(fetchDetail)
</script>

<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" :content="ws?.name || '...'" style="margin-bottom: 16px" />

    <el-tabs v-model="activeTab">
      <!-- Overview -->
      <el-tab-pane label="概览" name="overview">
        <el-form label-width="120px" style="max-width: 600px" v-if="ws">
          <el-form-item label="名称">
            <el-input v-model="editName" />
          </el-form-item>
          <el-form-item label="Owner ID">
            <span>{{ ws.owner_id }}</span>
          </el-form-item>
          <el-form-item label="Context Config">
            <el-input v-model="editConfig" type="textarea" :rows="10" style="font-family: monospace" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingOverview" @click="saveOverview">保存</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- Repos -->
      <el-tab-pane label="Git Repo" name="repos">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="repoDialogVisible = true">
            <el-icon><Plus /></el-icon> 挂载 Repo
          </el-button>
        </div>
        <el-table :data="repos">
          <el-table-column prop="url" label="URL" min-width="200" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="cloneStatusType(row.clone_status)">{{ row.clone_status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="local_path" label="路径" width="150" />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button text @click="onSyncRepo(row)">同步</el-button>
              <el-button text type="danger" @click="onDeleteRepo(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="repoDialogVisible" title="挂载 Git Repo" width="480">
          <el-form label-width="60px">
            <el-form-item label="URL">
              <el-input v-model="repoForm.url" placeholder="https://github.com/user/repo.git" />
            </el-form-item>
            <el-form-item label="Token">
              <el-input v-model="repoForm.token" placeholder="可选，私有 repo" show-password />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="repoDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="repoLoading" @click="onAddRepo">挂载</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Chats -->
      <el-tab-pane label="飞书群绑定" name="chats">
        <el-card style="margin-bottom: 16px">
          <template #header>绑定新群</template>
          <el-form label-width="80px" style="max-width: 500px">
            <el-form-item label="飞书 App">
              <el-select v-model="chatAppId" placeholder="选择已注册的 App" filterable>
                <el-option
                  v-for="app in feishuApps"
                  :key="app.id"
                  :label="`${app.name} (${app.app_id})`"
                  :value="app.app_id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="Chat ID">
              <el-input v-model="chatIdInput" placeholder="oc_xxxxx" />
            </el-form-item>
            <el-form-item>
              <el-button :loading="chatChecking" @click="onCheckChat">预校验</el-button>
              <el-button
                v-if="chatCheckResult?.valid && chatCheckResult?.bot_in_chat"
                type="primary"
                :loading="chatBinding"
                @click="onBindChat"
              >绑定</el-button>
            </el-form-item>
          </el-form>
          <el-alert
            v-if="chatCheckResult"
            :type="chatCheckResult.valid && chatCheckResult.bot_in_chat ? 'success' : 'warning'"
            :title="`群名: ${chatCheckResult.chat_name || '未知'}`"
            :description="
              chatCheckResult.existing_binding
                ? `已绑定到 WS ${chatCheckResult.existing_binding.workspace_id}`
                : chatCheckResult.valid
                  ? '校验通过，可绑定'
                  : '机器人不在群或群不存在'
            "
            :closable="false"
            style="margin-top: 12px"
          />
        </el-card>

        <el-table :data="chats">
          <el-table-column prop="app_id" label="App ID" width="150" />
          <el-table-column prop="chat_name" label="群名称" />
          <el-table-column prop="chat_id" label="Chat ID" width="200" />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button text type="danger" @click="onUnbindChat(row)">解绑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Skill Mounts -->
      <el-tab-pane label="Skill 挂载" name="skills">
        <el-card style="margin-bottom: 16px">
          <template #header>挂载 Skill（{{ mountedSkills.length }}/50）</template>
          <el-form label-width="60px" style="max-width: 500px" inline>
            <el-form-item label="Skill">
              <el-select v-model="selectedSkillId" placeholder="选择 Skill" filterable>
                <el-option
                  v-for="s in allSkills"
                  :key="s.id"
                  :label="`${s.name} — ${s.description}`"
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="onMountSkill">挂载</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-table :data="mountedSkills">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button text type="danger" @click="onUnmountSkill(row)">解挂</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- MCP Mounts -->
      <el-tab-pane label="MCP 挂载" name="mcps">
        <el-card style="margin-bottom: 16px">
          <template #header>挂载 MCP</template>
          <el-form label-width="60px" style="max-width: 500px" inline>
            <el-form-item label="MCP">
              <el-select v-model="selectedMcpId" placeholder="选择 MCP" filterable>
                <el-option
                  v-for="m in allMcps"
                  :key="m.id"
                  :label="`${m.name} (${m.type})`"
                  :value="m.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="onMountMcp">挂载</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-table :data="mountedMcps">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button text type="danger" @click="onUnmountMcp(row)">解挂</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- AGENT.md -->
      <el-tab-pane label="AGENT.md" name="agent-md">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-card>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>WS 级 AGENT.md（可编辑）</span>
                  <el-button type="primary" size="small" :loading="agentMdSaving" @click="saveAgentMd">
                    保存
                  </el-button>
                </div>
              </template>
              <el-input
                v-model="agentMdContent"
                type="textarea"
                :rows="20"
                style="font-family: monospace"
                placeholder="编辑 WS 级 AGENT.md..."
              />
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <template #header>Repo 级 AGENT.md（只读）</template>
              <el-select
                v-model="repoAgentMdRepoId"
                placeholder="选择 Repo"
                style="margin-bottom: 12px; width: 100%"
                @change="loadRepoAgentMd"
              >
                <el-option v-for="r in repos" :key="r.id" :label="r.url" :value="r.id" />
              </el-select>
              <el-input
                v-model="repoAgentMdContent"
                type="textarea"
                :rows="20"
                style="font-family: monospace"
                readonly
                placeholder="选择 Repo 后展示..."
              />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
