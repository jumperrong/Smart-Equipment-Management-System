<template>
  <div class="login-bg">
    <el-card class="login-card" shadow="hover">
      <div class="title-area">
        <el-icon :size="36" class="login-logo-icon"><Cpu /></el-icon>
        <h2>半导体设备管理系统</h2>
        <p class="subtitle">Semiconductor Equipment Management System</p>
      </div>
      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="onLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名：admin" size="large" :prefix-icon="UserIcon" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="密码：Admin@2026" size="large" :prefix-icon="LockIcon" @keyup.enter="onLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="onLogin">登 录</el-button>
      </el-form>
      <div class="tip">默认账号：admin / Admin@2026</div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User as UserIcon, Lock as LockIcon } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores'

const form = reactive({ username: 'admin', password: 'Admin@2026' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const formRef = ref(null)
const loading = ref(false)
const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

async function onLogin() {
  try {
    await formRef.value.validate()
    loading.value = true
    const resp = await userStore.doLogin({ username: form.username, password: form.password })
    ElMessage.success(`欢迎，${userStore.fullName}`)
    // 若后端标记必须改密（首次登录/弱密码）→ 跳强制改密页
    if (resp?.must_change_password || userStore.must_change_password) {
      router.replace({ name: 'ChangePassword' })
      return
    }
    const redirect = route.query.redirect || '/'
    router.replace(redirect)
  } catch (e) {
    // message from interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-bg {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-login-grad);
}
.login-card {
  width: 420px;
  padding: 16px 24px 8px;
  border-radius: 12px;
}
.title-area { text-align: center; margin-bottom: 24px; }
.login-logo-icon { color: var(--app-primary); }
.title-area h2 { margin: 10px 0 6px; color: var(--app-text-primary); letter-spacing: 1px; }
.subtitle { margin: 0; color: var(--app-text-secondary); font-size: 13px; }
.tip { text-align: center; margin-top: 16px; color: var(--app-text-muted); font-size: 12px; }
</style>
