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
  ContextConfig,
  ModelConfig,
} from '@/types/workspace'
import { DEFAULT_CONTEXT_CONFIG } from '@/types/workspace'
import { modelsApi, type ModelMeta } from '@/api/models'
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
const savingOverview = ref(false)

// Context Config (P3 D-CE.5)
const ctxCfg = ref<ContextConfig>({ ...DEFAULT_CONTEXT_CONFIG })
const savingCtxCfg = ref(false)

// Model Config (P3 D-CE.6)
const modelCfg = ref<ModelConfig>({ provider: 'anthropic', model: null, api_base_url: null })
const modelList = ref<ModelMeta[]>([])
const hasApiKey = ref(false)
const apiKeyInput = ref('')
const savingModelCfg = ref(false)

function loadModelCfg() {
  if (!ws.value?.model_config) {
    modelCfg.value = { provider: 'anthropic', model: null, api_base_url: null }
    hasApiKey.value = false
    return
  }
  const mc = ws.value.model_config
  modelCfg.value = {
    provider: mc.provider || 'anthropic',
    model: mc.model || null,
    api_base_url: mc.api_base_url || null,
  }
  hasApiKey.value = ws.value.has_model_api_key ?? false
  apiKeyInput.value = ''
}

function resetModelCfg() {
  modelCfg.value = { provider: 'anthropic', model: null, api_base_url: null }
  apiKeyInput.value = ''
}

async function saveModelCfg() {
  savingModelCfg.value = true
  try {
    const payload: Record<string, unknown> = {
      provider: modelCfg.value.provider,
      model: modelCfg.value.model || null,
      api_base_url: modelCfg.value.api_base_url || null,
    }
    // 只有用户输入了 api_key 才发送（空串 = 清除）
    if (apiKeyInput.value) {
      payload.api_key = apiKeyInput.value
    }
    await workspacesApi.patch(wsId, { model_config: payload as unknown as ModelConfig })
    showSuccess('模型配置已保存')
    await fetchDetail()
  } finally {
    savingModelCfg.value = false
  }
}

function loadCtxCfg() {
  if (!ws.value?.context_config) {
    ctxCfg.value = { ...DEFAULT_CONTEXT_CONFIG }
    return
  }
  ctxCfg.value = { ...DEFAULT_CONTEXT_CONFIG, ...ws.value.context_config }
}

function resetCtxCfg() {
  ctxCfg.value = { ...DEFAULT_CONTEXT_CONFIG }
}

function validateCtxCfg(): string | null {
  const c = ctxCfg.value
  if (c.trigger1 >= c.trigger2) return 'L1 阈值必须小于 L2 阈值'
  if (c.trigger2 >= 0.95) return 'L2 阈值必须小于 0.95'
  if (c.clear_keep < 1) return 'L1 保留数必须 ≥ 1'
  if (c.compact_recent < 1) return 'L2 保留轮数必须 ≥ 1'
  if (c.summary_budget_pct < 0 || c.summary_budget_pct > 0.5) {
    return '摘要预算百分比必须在 0 ~ 0.5 之间'
  }
  return null
}

async function saveCtxCfg() {
  const err = validateCtxCfg()
  if (err) {
    ElMessage.error(err)
    return
  }
  savingCtxCfg.value = true
  try {
    await workspacesApi.patch(wsId, { context_config: ctxCfg.value })
    showSuccess('上下文配置已保存')
    await fetchDetail()
  } finally {
    savingCtxCfg.value = false
  }
}

// Repos
const repos = ref<RepoOut[]>([])
const repoDialogVisible = ref(false)
const repoForm = ref({ url: '', token: '' })
const repoLoading = ref(false)
const { task: repoTask, isDone: repoTaskDone, start: startRepoPoll } = useTaskPolling()

async function refreshRepos() {
  repos.value = (await workspacesApi.listRepos(wsId)).items
}

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
    loadCtxCfg()
    loadModelCfg()
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
  savingOverview.value = true
  try {
    await workspacesApi.patch(wsId, { name: editName.value })
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
    await refreshRepos()
    startRepoPoll(res.task_id, refreshRepos)
  } finally {
    repoLoading.value = false
  }
}

async function onSyncRepo(repo: RepoOut) {
  try {
    const res = await workspacesApi.syncRepo(wsId, repo.id)
    showSuccess('同步任务已提交')
    startRepoPoll(res.task_id, refreshRepos)
  } catch {
    // handled
  }
}

async function onRetryRepo(repo: RepoOut) {
  try {
    const res = await workspacesApi.retryRepo(wsId, repo.id)
    showSuccess('重试任务已提交')
    await refreshRepos()
    startRepoPoll(res.task_id, refreshRepos)
  } catch {
    // handled
  }
}

async function onDeleteRepo(repo: RepoOut) {
  const ok = await confirmDelete(`确定删除 Repo「${repo.url}」？`)
  if (!ok) return
  await workspacesApi.deleteRepo(wsId, repo.id)
  showSuccess('已删除')
  await refreshRepos()
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
  } else if (tab === 'model-config' && modelList.value.length === 0) {
    modelList.value = await modelsApi.list()
  }
})

function cloneStatusType(status: string) {
  return { ready: 'success', cloning: 'warning', failed: 'danger', pending: 'info' }[status] || 'info'
}

function cloneStatusLabel(status: string) {
  return { ready: '就绪', cloning: '克隆中', failed: '失败', pending: '等待中' }[status] || status
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
          <el-form-item label="所有者">
            <span>{{ ws.owner_name || `#${ws.owner_id}` }}</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingOverview" @click="saveOverview">保存</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- Context Config (P3 D-CE.5) -->
      <el-tab-pane label="上下文配置" name="context-config">
        <el-form label-width="140px" style="max-width: 680px" v-if="ws">
          <el-form-item label="启用上下文管理">
            <el-switch v-model="ctxCfg.enabled" />
          </el-form-item>
          <el-form-item label="L1 Clearing 阈值">
            <el-slider v-model="ctxCfg.trigger1" :min="0" :max="0.95" :step="0.05" show-input />
            <div style="color: var(--el-text-color-secondary); font-size: 12px;">token 超过 context_window 的此比例 → 触发 L1 clearing（替换旧 tool_result）</div>
          </el-form-item>
          <el-form-item label="L2 Compaction 阈值">
            <el-slider v-model="ctxCfg.trigger2" :min="0" :max="0.95" :step="0.05" show-input />
            <div style="color: var(--el-text-color-secondary); font-size: 12px;">token 超过此比例 → 触发 L2 compaction（旧历史压成摘要）</div>
          </el-form-item>
          <el-form-item label="L1 保留 tool_result">
            <el-input-number v-model="ctxCfg.clear_keep" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="L2 保留轮数">
            <el-input-number v-model="ctxCfg.compact_recent" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="L2 递归分段摘要">
            <el-switch v-model="ctxCfg.compact_recursive" />
            <div style="color: var(--el-text-color-secondary); font-size: 12px;">开启后前缀超摘要窗口 60% 时分段递归摘要（上限 3 层），防长 Run L4 报错</div>
          </el-form-item>
          <el-form-item label="摘要 Provider">
            <el-select v-model="ctxCfg.summary_provider" style="width: 200px">
              <el-option label="Anthropic" value="anthropic" />
              <el-option label="OpenAI 兼容" value="openai_compatible" />
            </el-select>
          </el-form-item>
          <el-form-item label="摘要 Model">
            <el-input v-model="ctxCfg.summary_model" placeholder="留空用 provider 默认 model" />
          </el-form-item>
          <el-form-item label="跨 session 摘要预算">
            <el-slider v-model="ctxCfg.summary_budget_pct" :min="0" :max="0.5" :step="0.05" show-input />
            <div style="color: var(--el-text-color-secondary); font-size: 12px;">占 context_window 的百分比，用于加载历史 session 摘要</div>
          </el-form-item>
          <el-form-item label="排除工具">
            <el-select v-model="ctxCfg.exclude_tools" multiple filterable allow-create default-first-option placeholder="L1 不清的工具名" style="width: 100%" />
          </el-form-item>
          <el-form-item label="摘要指令">
            <el-input v-model="ctxCfg.compact_instructions" type="textarea" :rows="6" />
            <el-button text size="small" @click="ctxCfg.compact_instructions = DEFAULT_CONTEXT_CONFIG.compact_instructions" style="margin-top: 4px">重置默认</el-button>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingCtxCfg" @click="saveCtxCfg">保存配置</el-button>
            <el-button @click="resetCtxCfg">重置全部默认</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- Model Config (P3 D-CE.6) -->
      <el-tab-pane label="模型配置" name="model-config">
        <el-form label-width="140px" style="max-width: 680px" v-if="ws">
          <el-form-item label="Provider">
            <el-select v-model="modelCfg.provider" style="width: 200px">
              <el-option label="Anthropic" value="anthropic" />
              <el-option label="OpenAI 兼容" value="openai_compatible" />
            </el-select>
            <div style="color: var(--el-text-color-secondary); font-size: 12px;">留空字段走全局 settings 默认值</div>
          </el-form-item>
          <el-form-item label="Model">
            <el-input v-model="modelCfg.model" placeholder="如 claude-sonnet-5-20250710 / glm-4.6 / deepseek-v4-flash" list="model-list" />
            <datalist id="model-list">
              <option v-for="m in modelList" :key="m.name" :value="m.name">
                {{ m.context_window > 0 ? `${(m.context_window / 1000).toFixed(0)}K ctx` : '' }}
              </option>
            </datalist>
            <div v-if="modelList.length" style="color: var(--el-text-color-secondary); font-size: 12px;">
              已知 {{ modelList.length }} 个 model，可从下拉列表选择或手动输入
            </div>
          </el-form-item>
          <el-form-item v-if="modelCfg.provider === 'openai_compatible'" label="API Base URL">
            <el-input v-model="modelCfg.api_base_url" placeholder="如 https://open.bigmodel.cn/api/paas/v4" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="apiKeyInput" type="password" show-password :placeholder="hasApiKey ? '已设置，输入新值覆盖' : '可选，留空走全局 key'" />
            <div v-if="hasApiKey" style="color: var(--el-color-success); font-size: 12px;">✓ 已配置独立 API Key</div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingModelCfg" @click="saveModelCfg">保存配置</el-button>
            <el-button @click="resetModelCfg">清空表单</el-button>
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
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="cloneStatusType(row.clone_status)" :effect="row.clone_status === 'ready' ? 'light' : 'plain'">
                <el-icon v-if="row.clone_status === 'pending' || row.clone_status === 'cloning'" class="is-loading" style="margin-right: 2px">
                  <Loading />
                </el-icon>
                {{ cloneStatusLabel(row.clone_status) }}
              </el-tag>
              <el-tooltip v-if="row.clone_status === 'failed' && row.last_error" :content="row.last_error" placement="bottom" :show-after="300">
                <el-icon style="margin-left: 4px; color: var(--el-color-danger); cursor: help"><WarningFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column prop="local_path" label="路径" width="150" />
          <el-table-column label="操作" width="200" align="center">
            <template #default="{ row }">
              <el-button text :disabled="row.clone_status !== 'ready'" @click="onSyncRepo(row)">同步</el-button>
              <el-button v-if="row.clone_status === 'failed'" text type="warning" @click="onRetryRepo(row)">重试</el-button>
              <el-button text type="danger" @click="onDeleteRepo(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="repoDialogVisible" title="挂载 Git Repo" width="480">
          <el-form label-width="60px">
            <el-form-item label="URL">
              <el-input v-model="repoForm.url" placeholder="git@github.com:user/repo.git（推荐 SSH）" />
            </el-form-item>
            <el-collapse>
              <el-collapse-item title="高级选项（HTTPS 私有 repo token）" name="token">
                <el-form-item label="Token">
                  <el-input v-model="repoForm.token" placeholder="可选，仅 HTTPS 私有 repo 需要" show-password />
                  <div style="color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6;">
                    推荐使用 SSH URL（<code>git@host:group/repo.git</code>），通过本机 SSH key 鉴权，无需 token。
                  </div>
                </el-form-item>
              </el-collapse-item>
            </el-collapse>
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
