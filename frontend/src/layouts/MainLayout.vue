<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const isCollapse = ref(false)

const isAdmin = computed(() => userStore.user?.role === 'admin')

const menuItems = computed(() => {
  const items = [
    { index: '/workspaces', label: '工作空间', icon: 'Folder' },
    { index: '/skills', label: 'Skill 广场', icon: 'Files' },
    { index: '/mcps', label: 'MCP 广场', icon: 'Connection' },
    { index: '/feishu-apps', label: '飞书 App', icon: 'ChatDotRound' },
    { index: '/memory', label: 'Memory 管理', icon: 'Notebook' },
    { index: '/sessions', label: '会话历史', icon: 'Clock' },
    { index: '/traces', label: 'Trace 观测', icon: 'DataLine' },
    { index: '/insights', label: 'Insights', icon: 'TrendCharts' },
    { index: '/monitoring', label: '监控告警', icon: 'Warning' },
  ]
  if (isAdmin.value) {
    items.push({ index: '/users', label: '用户管理', icon: 'User' })
  }
  return items
})

const activeMenu = computed(() => {
  const path = route.path
  const match = menuItems.value.find((item) => path.startsWith(item.index))
  return match?.index ?? path
})

async function handleLogout() {
  await userStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar cf-sidebar">
      <div class="logo">
        <span class="logo-badge">CF</span>
        <span v-if="!isCollapse" class="logo-text">Code Forge</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
        class="sidebar-menu"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.index"
          :index="item.index"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.label }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
        </div>
        <div class="header-right">
          <span class="user-info">
            <span class="avatar">{{ (userStore.user?.username || '?').slice(0, 1).toUpperCase() }}</span>
            {{ userStore.user?.username }}
            <el-tag size="small" :type="isAdmin ? 'danger' : 'info'">
              {{ isAdmin ? '管理员' : '用户' }}
            </el-tag>
          </span>
          <el-button text @click="handleLogout">登出</el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100vh;
}

.sidebar {
  background: var(--cf-sidebar-gradient);
  transition: width 0.25s ease;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.logo-badge {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  background: var(--cf-gradient-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.45);
}
.logo-text {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: #ffffff;
}

.sidebar-menu {
  padding-top: 8px;
  border-right: none;
  background: transparent;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #ffffff;
  border-bottom: solid 1px var(--el-border-color-light);
  box-shadow: 0 1px 2px rgba(17, 24, 39, 0.03);
  position: relative;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: color 0.18s ease;
}
.collapse-btn:hover {
  color: var(--el-color-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}
.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--cf-gradient-brand);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
}

.main-content {
  background: linear-gradient(180deg, #f7f8fa 0%, #f4f3fb 100%);
  padding: 24px;
}
</style>
