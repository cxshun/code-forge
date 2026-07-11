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
    <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar">
      <div class="logo">
        <span v-if="!isCollapse">Code Forge</span>
        <span v-else>CF</span>
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
  background-color: var(--el-menu-bg-color);
  border-right: solid 1px var(--el-border-color);
  transition: width 0.3s;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  color: var(--el-color-primary);
  border-bottom: solid 1px var(--el-border-color);
}

.sidebar-menu {
  border-right: none;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: solid 1px var(--el-border-color);
  background: var(--el-bg-color);
}

.header-left {
  display: flex;
  align-items: center;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
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
}

.main-content {
  background-color: var(--el-bg-color-page);
  padding: 20px;
}
</style>
