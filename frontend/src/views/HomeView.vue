<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const router = useRouter()

function onLogout() {
  userStore.logout().then(() => router.push('/login'))
}
</script>

<template>
  <div style="padding: 24px">
    <h1>Code Forge 管理后台</h1>
    <p v-if="userStore.user">
      欢迎，{{ userStore.user.username }}（{{ userStore.user.role }}）
    </p>
    <el-button @click="onLogout">登出</el-button>
  </div>
</template>
