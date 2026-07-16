<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })
const loading = ref(false)

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch {
    // 错误已由 axios 拦截器统一提示
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-glow login-glow--1" />
    <div class="login-glow login-glow--2" />

    <el-card class="login-card" :body-style="{ padding: '40px 36px 32px' }">
      <div class="login-header">
        <span class="login-badge">CF</span>
        <h2>Code Forge</h2>
        <p class="login-subtitle">登录到你的工作台</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        size="large"
        label-position="top"
        @submit.prevent="onSubmit"
      >
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-form-item class="login-submit">
          <el-button type="primary" :loading="loading" class="login-btn" @click="onSubmit">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-wrap {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1e1b3a 0%, #2a2766 55%, #3a2f8f 100%);
  overflow: hidden;
}

/* 背景光斑装饰 */
.login-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  pointer-events: none;
}
.login-glow--1 {
  width: 420px;
  height: 420px;
  background: #6366f1;
  opacity: 0.32;
  top: -120px;
  left: -90px;
}
.login-glow--2 {
  width: 380px;
  height: 380px;
  background: #8b8cf7;
  opacity: 0.24;
  bottom: -130px;
  right: -70px;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  border: none;
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.32), 0 4px 16px rgba(30, 27, 58, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}
.login-badge {
  display: inline-flex;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: var(--cf-gradient-brand);
  color: #fff;
  font-weight: 700;
  font-size: 20px;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.45);
}
.login-header h2 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.login-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.login-submit {
  margin-bottom: 0;
}
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 1px;
}
</style>
