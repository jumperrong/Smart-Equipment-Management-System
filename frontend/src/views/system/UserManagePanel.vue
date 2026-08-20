<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span style="font-weight:600">用户管理</span>
        <el-button type="success" size="small" @click="openDialog()">+ 新增用户</el-button>
      </div>
    </template>

    <el-table :data="list" stripe v-loading="loading" border size="small">
      <el-table-column prop="id" label="ID" width="60" align="center" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="full_name" label="姓名" width="140" />
      <el-table-column label="角色" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="roleTagType(row.role)" size="small" effect="dark">{{ roleLabel(row.role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag v-if="isLocked(row)" type="danger" size="small" effect="dark">已锁定</el-tag>
          <el-tag v-else :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="安全提示" width="150" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.must_change_password" type="warning" size="small">需改密</el-tag>
          <el-tag v-if="(row.failed_login_count || 0) > 0" type="info" size="small">失败{{ row.failed_login_count }}次</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="360" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button
            size="small" link
            :type="row.is_active ? 'warning' : 'success'"
            @click="toggleActive(row)"
          >{{ row.is_active ? '停用' : '启用' }}</el-button>
          <el-button
            v-if="isLocked(row)"
            size="small" link type="primary"
            @click="onUnlock(row)"
          >解锁账户</el-button>
          <el-button size="small" link type="primary" @click="openResetDialog(row)">重置密码</el-button>
          <el-button
            size="small" link type="danger"
            :disabled="row.id === currentUserId"
            @click="onDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!form.id" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="姓名" prop="full_name">
          <el-input v-model="form.full_name" placeholder="显示姓名" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width:100%">
            <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!form.id" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位，建议包含大小写+数字+特殊符号中的 3 类" />
        </el-form-item>
        <el-form-item v-if="!form.id" label="强制改密">
          <el-switch v-model="form.must_change_password" />
          <span class="tip">首次登录时强制修改密码</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetDialogVisible" :title="resetDialogTitle" width="420px">
      <el-form :model="resetForm" :rules="resetRules" ref="resetFormRef" label-width="100px">
        <el-form-item label="目标用户">
          <el-tag>{{ resetForm.username }}</el-tag>
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="resetForm.new_password" type="password" show-password placeholder="至少 8 位；包含大小写+数字+特殊符号中至少 3 类" />
        </el-form-item>
        <el-form-item>
          <el-alert type="info" :closable="false" show-icon
            title="重置后，用户下次登录将被强制跳转到修改密码页，必须设置新密码才能进入系统。" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetSaving" @click="onResetSave">确认重置</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, createUser, updateUser, deleteUser, resetPassword, unlockUser } from '@/api/auth'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const currentUserId = computed(() => userStore.user?.id)

function isLocked(row) {
  if (!row?.locked_until) return false
  return new Date(row.locked_until) > new Date()
}

function validatePwd(rule, value, cb) {
  if (!value) return cb()
  if (value.length < 8) return cb(new Error('密码至少 8 位'))
  const cls = [/[a-z]/.test(value), /[A-Z]/.test(value), /\d/.test(value), /[^A-Za-z0-9]/.test(value)]
    .filter(Boolean).length
  if (cls < 3) return cb(new Error('密码需包含【大小写字母/数字/特殊符号】中的 3 类'))
  cb()
}

const list = ref([])
const loading = ref(false)

const roleOptions = [
  { value: 'admin', label: '管理员' },
  { value: 'engineer', label: '工程师' },
  { value: 'process_engineer', label: '工艺员' },
  { value: 'qa', label: 'QA审核员' },
  { value: 'production_manager', label: '生产主管' },
  { value: 'team_leader', label: '班组长' },
  { value: 'operator', label: '生产操作员' },
  { value: 'viewer', label: '查看者' },
]
const roleLabels = { admin: '管理员', engineer: '工程师', process_engineer: '工艺员', qa: 'QA审核员', production_manager: '生产主管', team_leader: '班组长', operator: '生产操作员', viewer: '查看者' }
const roleLabel = (r) => roleLabels[r] || r
const roleTagType = (r) => ({ admin: 'danger', engineer: 'primary', process_engineer: 'warning', qa: 'danger', production_manager: 'primary', team_leader: 'success', operator: 'success', viewer: 'info' }[r] || 'info')

// 新增/编辑表单
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, username: '', full_name: '', role: 'operator', password: '',
  is_active: true, must_change_password: false,
})
const formRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [
    { required: false },
    {
      validator: (rule, value, cb) => {
        if (!form.id && !value) cb(new Error('请输入密码'))
        else if (value) validatePwd(rule, value, cb)
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

// 重置密码表单
const resetDialogVisible = ref(false)
const resetDialogTitle = ref('重置密码')
const resetSaving = ref(false)
const resetFormRef = ref(null)
const resetForm = reactive({ id: null, username: '', new_password: '' })
const resetRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { validator: validatePwd, trigger: 'blur' },
  ],
}

async function loadList() {
  loading.value = true
  try {
    list.value = await listUsers()
  } finally {
    loading.value = false
  }
}

function openDialog(row = null) {
  dialogVisible.value = true
  if (row) {
    dialogTitle.value = `编辑用户: ${row.username}`
    Object.assign(form, {
      id: row.id, username: row.username, full_name: row.full_name || '',
      role: row.role, password: '', is_active: row.is_active,
      must_change_password: !!row.must_change_password,
    })
  } else {
    dialogTitle.value = '新增用户'
    Object.assign(form, {
      id: null, username: '', full_name: '', role: 'operator', password: '',
      is_active: true, must_change_password: true,
    })
  }
}

async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = {
      username: form.username,
      full_name: form.full_name || null,
      role: form.role,
      is_active: form.is_active,
      must_change_password: form.must_change_password,
    }
    if (form.id) {
      await updateUser(form.id, payload)
      ElMessage.success('已更新')
    } else {
      payload.password = form.password
      await createUser(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadList()
    // 若改的是自己，刷新本地 user 信息
    if (form.id && form.id === currentUserId.value) await userStore.fetchMe()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  const action = row.is_active ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}用户【${row.username}】？`, '提示', { type: 'warning' })
    const payload = { is_active: !row.is_active }
    if (!row.is_active) {
      // 启用时顺带解锁
      payload.locked_until = null
    }
    await updateUser(row.id, payload)
    ElMessage.success(`已${action}`)
    loadList()
  } catch (e) {}
}

async function onUnlock(row) {
  try {
    await ElMessageBox.confirm(`确认立即解锁账户【${row.username}】？`, '提示', { type: 'info' })
    await unlockUser(row.id)
    ElMessage.success('已解锁')
    loadList()
  } catch (e) {}
}

function openResetDialog(row) {
  resetDialogVisible.value = true
  resetDialogTitle.value = `重置密码: ${row.username}`
  Object.assign(resetForm, { id: row.id, username: row.username, new_password: '' })
}

async function onResetSave() {
  try {
    await resetFormRef.value.validate()
    resetSaving.value = true
    await resetPassword(resetForm.id, resetForm.new_password)
    ElMessage.success('密码已重置，该用户下次登录将被强制要求改密')
    resetDialogVisible.value = false
    loadList()
  } catch (e) {
  } finally {
    resetSaving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除用户【${row.username}】？该操作不可恢复。`,
      '危险操作',
      { type: 'error', confirmButtonText: '确认删除', confirmButtonClass: 'el-button--danger' },
    )
    await deleteUser(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e) {}
}

onMounted(loadList)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.tip { color: #909399; font-size: 12px; margin-left: 8px; }
</style>
