<template>
  <div>
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="总工单数" :value="stats.total" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="超期工单数" :value="stats.breached" :value-style="{ color: 'var(--app-danger)' }" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="达成率" :value="stats.achievementRate" :precision="1">
            <template #suffix>%</template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="平均响应时长(分)" :value="stats.avgResponseMinutes" :precision="1" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top:16px">
      <div class="toolbar">
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="order_no" label="工单号" width="140" />
        <el-table-column label="设备" width="140">
          <template #default="{ row }">{{ eqName(row) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="紧急度" width="90">
          <template #default="{ row }">
            <el-tag :type="urgencyTag(row.urgency)" size="small">{{ urgencyLabel(row.urgency) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="SLA目标响应" width="120">
          <template #default="{ row }">{{ formatDuration(row.sla_response_minutes) }}</template>
        </el-table-column>
        <el-table-column label="实际响应" width="120">
          <template #default="{ row }">
            <span :class="{ 'breach-text': isResponseBreached(row) }">{{ formatDuration(row.actual_response_minutes) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="SLA目标解决" width="120">
          <template #default="{ row }">{{ formatDuration(row.sla_resolution_minutes) }}</template>
        </el-table-column>
        <el-table-column label="实际解决" width="120">
          <template #default="{ row }">
            <span :class="{ 'breach-text': isResolutionBreached(row) }">{{ formatDuration(row.actual_resolution_minutes) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="超期标记" width="100">
          <template #default="{ row }">
            <el-tag :type="breachTag(row)" size="small">{{ breachLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openSlaDialog(row)">设置SLA</el-button>
            <el-button size="small" link type="warning" @click="openEscalateDialog(row)">升级</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- SLA 设置 -->
    <el-dialog v-model="slaDialogVisible" :title="`设置SLA：${currentRow?.order_no || ''}`" width="520px">
      <el-form :model="slaForm" :rules="slaRules" ref="slaFormRef" label-width="140px">
        <el-form-item label="目标响应时长(分)" prop="sla_response_minutes">
          <el-input-number v-model="slaForm.sla_response_minutes" :min="0" :step="5" controls-position="right" style="width:100%" />
        </el-form-item>
        <el-form-item label="目标解决时长(分)" prop="sla_resolution_minutes">
          <el-input-number v-model="slaForm.sla_resolution_minutes" :min="0" :step="15" controls-position="right" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="slaDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="slaSaving" @click="onSaveSla">保存</el-button>
      </template>
    </el-dialog>

    <!-- 升级 -->
    <el-dialog v-model="escalateDialogVisible" :title="`升级工单：${currentRow?.order_no || ''}`" width="520px">
      <el-form :model="escalateForm" :rules="escalateRules" ref="escalateFormRef" label-width="100px">
        <el-form-item label="升级给" prop="escalate_to_user_id">
          <el-select v-model="escalateForm.escalate_to_user_id" filterable placeholder="选择用户" style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="`${u.full_name || u.username} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="escalateForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="escalateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="escalateSaving" @click="onSubmitEscalate">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import { listUsers } from '@/api/auth'
import { formatTime, formatDuration, urgencyLabel, urgencyTag } from '@/utils'

const users = ref([])
function eqName(row) {
  if (!row) return '-'
  if (row.equipment_name) return row.equipment_name
  if (row.equipment && row.equipment.name) return row.equipment.name
  const id = row.equipment_id
  return id ? `#${id}` : '-'
}

// 超期判断
function isResponseBreached(row) {
  if (row.is_breached === false) return false
  if (row.response_breached != null) return !!row.response_breached
  return row.actual_response_minutes != null
    && row.sla_response_minutes != null
    && row.actual_response_minutes > row.sla_response_minutes
}
function isResolutionBreached(row) {
  if (row.is_breached === false) return false
  if (row.resolution_breached != null) return !!row.resolution_breached
  return row.actual_resolution_minutes != null
    && row.sla_resolution_minutes != null
    && row.actual_resolution_minutes > row.sla_resolution_minutes
}
function breachLabel(row) {
  if (row.breach_type) return row.breach_type
  if (row.is_breached === false) return '正常'
  const parts = []
  if (isResponseBreached(row)) parts.push('响应超时')
  if (isResolutionBreached(row)) parts.push('解决超时')
  return parts.length ? parts.join('、') : '超期'
}
function breachTag(row) {
  return (row.is_breached === false) ? 'success' : 'danger'
}

// ---------- 列表 + 统计 ----------
const list = ref([])
const loading = ref(false)
const stats = ref({ total: 0, breached: 0, achievementRate: 0, avgResponseMinutes: 0 })

async function load() {
  loading.value = true
  try {
    const [listResult, statsResult] = await Promise.allSettled([
      request.get('/api/v1/work-order-sla/breaches'),
      request.get('/api/v1/work-order-sla/stats'),
    ])
    list.value = listResult.status === 'fulfilled' ? (listResult.value || []) : []
    const s = statsResult.status === 'fulfilled' ? statsResult.value : null
    const rate = Number(s?.achievement_rate) || 0
    stats.value = {
      total: s?.total ?? 0,
      breached: s?.breached ?? 0,
      achievementRate: rate > 0 && rate <= 1 ? rate * 100 : rate,
      avgResponseMinutes: Number(s?.avg_response_minutes) || 0,
    }
  } finally {
    loading.value = false
  }
}

// ---------- SLA 设置 ----------
const slaDialogVisible = ref(false)
const slaSaving = ref(false)
const slaFormRef = ref(null)
const currentRow = ref(null)
const slaForm = reactive({ sla_response_minutes: 30, sla_resolution_minutes: 480 })
const slaRules = {
  sla_response_minutes: [{ required: true, message: '请输入目标响应时长', trigger: 'blur' }],
  sla_resolution_minutes: [{ required: true, message: '请输入目标解决时长', trigger: 'blur' }],
}
function openSlaDialog(row) {
  currentRow.value = row
  slaForm.sla_response_minutes = row.sla_response_minutes ?? 30
  slaForm.sla_resolution_minutes = row.sla_resolution_minutes ?? 480
  slaDialogVisible.value = true
}
async function onSaveSla() {
  try {
    await slaFormRef.value.validate()
    slaSaving.value = true
    const id = currentRow.value.work_order_id || currentRow.value.id
    await request.put(`/api/v1/work-order-sla/${id}/sla`, {
      sla_response_minutes: slaForm.sla_response_minutes,
      sla_resolution_minutes: slaForm.sla_resolution_minutes,
    })
    ElMessage.success('SLA 已更新')
    slaDialogVisible.value = false
    load()
  } catch (e) {} finally {
    slaSaving.value = false
  }
}

// ---------- 升级 ----------
const escalateDialogVisible = ref(false)
const escalateSaving = ref(false)
const escalateFormRef = ref(null)
const escalateForm = reactive({ escalate_to_user_id: null, remark: '' })
const escalateRules = {
  escalate_to_user_id: [{ required: true, message: '请选择升级目标用户', trigger: 'change' }],
}
function openEscalateDialog(row) {
  currentRow.value = row
  escalateForm.escalate_to_user_id = null
  escalateForm.remark = ''
  escalateDialogVisible.value = true
}
async function onSubmitEscalate() {
  try {
    await escalateFormRef.value.validate()
    escalateSaving.value = true
    const id = currentRow.value.work_order_id || currentRow.value.id
    await request.post(`/api/v1/work-order-sla/${id}/escalate`, {
      escalate_to_user_id: escalateForm.escalate_to_user_id,
      remark: escalateForm.remark || undefined,
    })
    ElMessage.success('已升级')
    escalateDialogVisible.value = false
    load()
  } catch (e) {} finally {
    escalateSaving.value = false
  }
}

onMounted(async () => {
  users.value = await listUsers()
  await load()
})
</script>

<style scoped>
.stat-card { margin-bottom: 16px; }
.toolbar { margin-bottom: 10px; }
.breach-text { color: var(--app-danger); font-weight: 600; }
</style>
