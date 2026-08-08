<template>
  <div class="login-bg">
    <el-card class="login-card" shadow="hover">
      <div class="title-area">
        <el-icon :size="32" color="#e6a23c"><Lock /></el-icon>
        <h2>请先修改密码</h2>
        <div v-if="userStore.user?.username" class="sub">
          当前账号：<b>{{ userStore.user.username }}</b><br>
          <span v-if="isAdminDefault">
            检测到仍在使用初始默认密码 <code>admin123</code>，必须先修改后才能进入系统。
          </span>
          <span v-else>管理员或系统已将此账号标记为必须修改密码后才可继续使用。</span>
        </div>
      </div>
      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" @keyup.enter="onSubmit">
        <el-form-item label="旧密码" prop="old_password">
          <el-input v-model="form.old_password" type="password" show-password placeholder="请输入当前使用的旧密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="form.new_password" type="password" show-password placeholder="至少 8 位，建议包含大小写字母+数字+特殊符号中的 3 类" />
          <div class="pwd-tip">
            <el-tag v-if="pwdScore >= 4" type="success">强度：很强</el-tag>
            <el-tag v-else-if="pwdScore === 3" type="primary">强度：良好</el-tag>
            <el-tag v-else-if="pwdScore === 2" type="warning">强度：一般</el-tag>
            <el-tag v-else type="danger">强度：较弱</el-tag>
            <span class="pwd-req">需至少 8 位，建议包含【大小写字母/数字/特殊符号】中的 3 类</span>
          </div>
        </el-form-item>
        <el-form-item label="再次输入新密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" style="width:100%" @click="onSubmit">确认修改并进入系统</el-button>
        </el-form-item>
        <el-form-item>
          <el-button link size="small" @click="onLogout">放弃修改，退出登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { changePassword } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const form = reactive({ old_password: '', new_password: '', confirm: '' })
const formRef = ref(null)
const loading = ref(false)

const isAdminDefault = computed(() => !!(userStore.user?.username === 'admin'))

const pwdScore = computed(() => {
  const p = form.new_password || ''
  let s = 0
  if (p.length >= 8) s++
  if (/[a-z]/.test(p)) s++
  if (/[A-Z]/.test(p)) s++
  if (/\d/.test(p)) s++
  if (/[^A-Za-z0-9]/.test(p)) s++
  return s
})

const validConfirm = (rule, value, cb) => {
  if (value !== form.new_password) return cb(new Error('两次输入的新密码不一致'))
  cb()
}
const validComplex = (rule, value, cb) => {
  if (!value) return cb(new Error('请输入新密码'))
  if (value.length < 8) return cb(new Error('密码至少 8 位'))
  if (value === form.old_password) return cb(new Error('新密码不能与旧密码相同'))
  const cls = [/[a-z]/.test(value), /[A-Z]/.test(value), /\d/.test(value), /[^A-Za-z0-9]/.test(value)]
    .filter(Boolean).length
  if (cls < 3) return cb(new Error('新密码需包含【大小写字母/数字/特殊符号】中的至少 3 类'))
  cb()
}
const rules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [{ required: true, validator: validComplex, trigger: 'blur' }],
  confirm: [{ required: true, validator: validConfirm, trigger: 'blur' }],
}

async function onSubmit() {
  try {
    await formRef.value.validate()
  } catch { return }
  loading.value = true
  try {
    const resp = await changePassword(form.old_password, form.new_password)
    userStore.onPasswordChanged(resp)
    ElMessage.success('密码修改成功')
    // 改密后跳首页
    router.push({ name: 'Dashboard' })
  } catch (e) {} finally {
    loading.value = false
  }
}

function onLogout() {
  userStore.logout({ notifyServer: true })
  router.push({ name: 'Login' })
}

onMounted(() => {
  if (!userStore.token) {
    router.push({ name: 'Login' })
  }
})
</script>

<style scoped>
.login-bg {
  height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 50%, #f5f3ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.login-card {
  width: 100%;
  max-width: 460px;
  border-radius: 10px;
}
.title-area {
  text-align: center;
  margin-bottom: 24px;
}
.title-area h2 {
  margin: 8px 0 6px;
  font-size: 20px;
}
.title-area .sub {
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
  margin-top: 6px;
}
.title-area code {
  padding: 1px 6px;
  background: #f4f4f5;
  color: #606266;
  border-radius: 4px;
  font-size: 12px;
  margin: 0 2px;
}
.pwd-tip {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}
.pwd-req { flex: 1; min-width: 200px; }
</style>
