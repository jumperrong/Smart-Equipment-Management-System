<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">角色权限配置</span>
          <el-tag size="small" type="warning">调整后即时生效</el-tag>
        </div>
        <div class="header-right">
          <el-button size="small" @click="loadMatrix">重置未保存</el-button>
          <el-button size="small" type="success" :disabled="!dirty" :loading="saving" @click="onSave">
            保存修改 <span v-if="dirty" style="margin-left:4px">({{ dirtyCount }})</span>
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      v-if="dirty"
      title="有未保存的修改，保存后才会影响其他用户"
      type="warning"
      :closable="false"
      style="margin-bottom:12px"
    />

    <!-- 按分组展示功能矩阵 -->
    <div v-for="g in groupedFeatures" :key="g.name" class="perm-group">
      <div class="group-title">
        <span class="group-name">{{ g.name }}</span>
        <span class="group-count">{{ g.items.length }} 项</span>
      </div>
      <el-table :data="g.items" border size="small">
        <el-table-column label="功能" min-width="220">
          <template #default="{ row }">
            <div class="feat-cell">
              <span class="feat-label">{{ row.label }}</span>
              <code class="feat-key">{{ row.key }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          v-for="r in roles"
          :key="r"
          :label="roleLabel(r)"
          :width="110"
          align="center"
        >
          <template #header>
            <div class="role-head" :class="`role-${r}`">
              <span>{{ roleLabel(r) }}</span>
            </div>
          </template>
          <template #default="{ row }">
            <el-checkbox
              :model-value="matrix[row.key]?.[r] || false"
              :disabled="row.key === 'system.permission_manage' && r === 'admin'"
              @change="(v) => onToggle(row.key, r, v)"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="tip-text">
      <el-icon><InfoFilled /></el-icon>
      <span>“权限配置”和“字典管理”本身固定仅 admin 可访问，避免权限矩阵被改坏后锁死。</span>
    </div>
  </el-card>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { getPermissionMatrix, updatePermissions } from '@/api/system'

const loading = ref(false)
const saving = ref(false)
const features = ref([])
const roles = ref([])
const matrix = ref({})           // 原始矩阵 {feature_key: {role: bool}}
const pendingChanges = ref({})   // 待保存 {feature_key: {role: bool}}

const roleLabels = {
  admin: '管理员',
  engineer: '工程师',
  process_engineer: '工艺员',
  qa: 'QA审核员',
  operator: '操作员',
  viewer: '查看者',
}
const roleLabel = (r) => roleLabels[r] || r

const groupedFeatures = computed(() => {
  const groups = {}
  features.value.forEach((f) => {
    if (!groups[f.group]) groups[f.group] = { name: f.group, items: [] }
    groups[f.group].items.push(f)
  })
  return Object.values(groups)
})

const dirty = computed(() => Object.keys(pendingChanges.value).length > 0)
const dirtyCount = computed(() => {
  let n = 0
  Object.values(pendingChanges.value).forEach((m) => { n += Object.keys(m).length })
  return n
})

async function loadMatrix() {
  loading.value = true
  try {
    const data = await getPermissionMatrix()
    features.value = data.features || []
    roles.value = data.roles || []
    // 深拷贝避免引用问题
    matrix.value = {}
    Object.keys(data.matrix || {}).forEach((fk) => {
      matrix.value[fk] = { ...(data.matrix[fk] || {}) }
    })
    pendingChanges.value = {}
  } finally {
    loading.value = false
  }
}

function onToggle(featureKey, role, val) {
  if (!pendingChanges.value[featureKey]) pendingChanges.value[featureKey] = {}
  pendingChanges.value[featureKey][role] = val
  // 同步到 matrix 以触发 checkbox 视图更新
  if (!matrix.value[featureKey]) matrix.value[featureKey] = {}
  matrix.value[featureKey][role] = val
}

async function onSave() {
  const updates = []
  Object.keys(pendingChanges.value).forEach((fk) => {
    Object.keys(pendingChanges.value[fk]).forEach((r) => {
      updates.push({ role: r, feature_key: fk, allowed: pendingChanges.value[fk][r] })
    })
  })
  if (!updates.length) return
  saving.value = true
  try {
    await updatePermissions(updates)
    ElMessage.success(`已保存 ${updates.length} 项权限修改`)
    pendingChanges.value = {}
  } catch (e) {
    // 失败时重新拉取，避免本地状态与后端不一致
    await loadMatrix()
  } finally {
    saving.value = false
  }
}

onMounted(loadMatrix)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 8px; }

.perm-group { margin-bottom: 20px; }
.group-title {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 6px;
}
.group-name { font-weight: 600; font-size: 14px; color: #303133; }
.group-count { font-size: 12px; color: #909399; }

.feat-cell { display: flex; flex-direction: column; gap: 2px; }
.feat-label { font-weight: 500; color: #303133; }
.feat-key { font-size: 11px; color: #909399; background: #f5f7fa; padding: 1px 6px; border-radius: 3px; }

.role-head { font-weight: 600; }
.role-head.role-admin { color: #f56c6c; }
.role-head.role-engineer { color: #409eff; }
.role-head.role-process_engineer { color: #e6a23c; }
.role-head.role-qa { color: #9c27b0; }
.role-head.role-operator { color: #67c23a; }
.role-head.role-viewer { color: #909399; }

.tip-text {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 12px;
}
</style>
