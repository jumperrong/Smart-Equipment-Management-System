<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="设备ID">
            <el-select v-model="query.equipment_id" filterable clearable placeholder="全部设备" style="width:200px">
              <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="检查类型">
            <el-select v-model="query.inspection_type" clearable placeholder="全部" style="width:150px">
              <el-option v-for="t in INSPECTION_TYPE_OPTIONS" :key="t" :label="inspectionTypeLabel(t)" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="结果">
            <el-select v-model="query.result" clearable placeholder="全部" style="width:120px">
              <el-option v-for="r in RESULT_OPTIONS" :key="r" :label="resultLabel(r)" :value="r" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button type="success" @click="openDialog()">新建检查项</el-button>
            <el-badge :value="alertList.length" :hidden="alertList.length === 0" :max="99" type="danger">
              <el-button type="warning" @click="openAlertDialog">告警列表</el-button>
            </el-badge>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column label="设备名" width="160">
          <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column label="检查类型" width="110">
          <template #default="{ row }">
            <el-tag :type="inspectionTypeTag(row.inspection_type)" size="small">{{ inspectionTypeLabel(row.inspection_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="item_name" label="检查项目名" min-width="160" />
        <el-table-column label="频次" width="90">
          <template #default="{ row }">{{ frequencyLabel(row.frequency) }}</template>
        </el-table-column>
        <el-table-column label="上次检查日" width="120">
          <template #default="{ row }">{{ formatDate(row.last_inspection_date) }}</template>
        </el-table-column>
        <el-table-column label="下次检查日" width="130">
          <template #default="{ row }">
            <span :class="{ 'alert-cell': isNextAlert(row) }">{{ formatDate(row.next_inspection_date) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="resultTag(row.result)" size="small">{{ resultLabel(row.result) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="certificate_no" label="证书编号" width="140" />
        <el-table-column label="证书到期日" width="130">
          <template #default="{ row }">
            <span :class="{ 'alert-cell': isCertAlert(row) }">{{ formatDate(row.certificate_expiry_date) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openExecuteDialog(row)">执行</el-button>
            <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 告警列表 -->
    <el-dialog v-model="alertDialogVisible" title="告警列表（30天内到期或已过期）" width="900px">
      <el-table :data="alertList" stripe border size="small" empty-text="暂无告警">
        <el-table-column label="设备名" width="160">
          <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column prop="item_name" label="检查项目名" min-width="160" />
        <el-table-column label="下次检查日" width="130">
          <template #default="{ row }"><span class="alert-cell">{{ formatDate(row.next_inspection_date) }}</span></template>
        </el-table-column>
        <el-table-column label="证书到期日" width="130">
          <template #default="{ row }"><span :class="{ 'alert-cell': isCertAlert(row) }">{{ formatDate(row.certificate_expiry_date) }}</span></template>
        </el-table-column>
        <el-table-column label="告警类型" width="180">
          <template #default="{ row }">
            <el-tag v-if="isNextAlert(row)" type="danger" size="small">检查到期</el-tag>
            <el-tag v-if="isCertAlert(row)" type="danger" size="small" style="margin-left:4px">证书到期</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="alertDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑检查项 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑检查项' : '新建检查项'" width="720px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="form.equipment_id" filterable placeholder="选择设备" style="width:100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检查类型" prop="inspection_type">
              <el-select v-model="form.inspection_type" style="width:100%">
                <el-option v-for="t in INSPECTION_TYPE_OPTIONS" :key="t" :label="inspectionTypeLabel(t)" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="检查项目名" prop="item_name"><el-input v-model="form.item_name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="频次" prop="frequency">
              <el-select v-model="form.frequency" style="width:100%">
                <el-option v-for="f in FREQUENCY_OPTIONS" :key="f" :label="frequencyLabel(f)" :value="f" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="检查标准"><el-input v-model="form.standard" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="证书编号"><el-input v-model="form.certificate_no" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="证书到期日">
              <el-date-picker v-model="form.certificate_expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 执行检查 -->
    <el-dialog v-model="executeDialogVisible" :title="`执行检查：${currentRow?.item_name || ''}`" width="640px">
      <el-form :model="executeForm" label-width="100px">
        <el-form-item label="检查结果">
          <el-radio-group v-model="executeForm.result">
            <el-radio value="pass">通过 pass</el-radio>
            <el-radio value="fail">不通过 fail</el-radio>
            <el-radio value="n_a">不适用 n/a</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="检查发现"><el-input v-model="executeForm.findings" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="整改措施"><el-input v-model="executeForm.corrective_action" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <div class="exec-tip">提交后将根据频次（{{ currentRow ? frequencyLabel(currentRow.frequency) : '' }}）自动计算下次检查日期</div>
      <template #footer>
        <el-button @click="executeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="executeSaving" @click="onSubmitExecute">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { listEquipments } from '@/api/equipment'
import { dayjs } from '@/utils'

// ---------- 常量 ----------
const INSPECTION_TYPE_OPTIONS = ['safety_device', 'special_equipment', 'environmental', 'fire_protection']
const FREQUENCY_OPTIONS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
const RESULT_OPTIONS = ['pass', 'fail', 'pending']

function inspectionTypeLabel(t) {
  return ({
    safety_device: '安全装置',
    special_equipment: '特种设备',
    environmental: '环保',
    fire_protection: '消防',
  }[t]) || t
}
function inspectionTypeTag(t) {
  return ({
    safety_device: 'primary',
    special_equipment: 'warning',
    environmental: 'success',
    fire_protection: 'danger',
  }[t]) || 'info'
}
function frequencyLabel(f) {
  return ({ daily: '每日', weekly: '每周', monthly: '每月', quarterly: '每季', yearly: '每年' }[f]) || f
}
function resultLabel(r) {
  return ({ pass: '通过', fail: '不通过', pending: '待检', n_a: '不适用' }[r]) || r
}
function resultTag(r) {
  return ({ pass: 'success', fail: 'danger', pending: 'warning', n_a: 'info' }[r]) || 'info'
}
function formatDate(d) {
  return d ? dayjs(d).format('YYYY-MM-DD') : '-'
}

// 根据频次计算下次检查日期
function calcNextDate(frequency, base = new Date()) {
  const b = dayjs(base)
  switch (frequency) {
    case 'daily': return b.add(1, 'day').format('YYYY-MM-DD')
    case 'weekly': return b.add(7, 'day').format('YYYY-MM-DD')
    case 'monthly': return b.add(1, 'month').format('YYYY-MM-DD')
    case 'quarterly': return b.add(3, 'month').format('YYYY-MM-DD')
    case 'yearly': return b.add(1, 'year').format('YYYY-MM-DD')
    default: return null
  }
}

// 告警判断：30天内到期或已过期
function isWithin30DaysOrPast(dateStr) {
  if (!dateStr) return false
  const target = dayjs(dateStr)
  const now = dayjs()
  if (target.isBefore(now, 'day')) return true
  return target.diff(now, 'day') <= 30
}
function isNextAlert(row) {
  return isWithin30DaysOrPast(row.next_inspection_date)
}
function isCertAlert(row) {
  return isWithin30DaysOrPast(row.certificate_expiry_date)
}

// ---------- 设备 ----------
const equipments = ref([])
function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}

// ---------- 列表 ----------
const query = reactive({ equipment_id: null, inspection_type: '', result: '' })
const list = ref([])
const loading = ref(false)
async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.equipment_id) params.equipment_id = query.equipment_id
    if (query.inspection_type) params.inspection_type = query.inspection_type
    if (query.result) params.result = query.result
    list.value = await request.get('/api/v1/safety-inspections', { params })
  } catch (e) {} finally {
    loading.value = false
  }
}

const alertList = computed(() => list.value.filter((r) => isNextAlert(r) || isCertAlert(r)))
const alertDialogVisible = ref(false)
function openAlertDialog() {
  alertDialogVisible.value = true
}

// ---------- 新建/编辑 ----------
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null,
  equipment_id: null,
  inspection_type: 'safety_device',
  item_name: '',
  standard: '',
  frequency: 'monthly',
  certificate_no: '',
  certificate_expiry_date: '',
})
const formRules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  inspection_type: [{ required: true, message: '请选择检查类型', trigger: 'change' }],
  item_name: [{ required: true, message: '请输入检查项目名', trigger: 'blur' }],
  frequency: [{ required: true, message: '请选择频次', trigger: 'change' }],
}
function openDialog(row = null) {
  Object.assign(form, {
    id: null, equipment_id: null, inspection_type: 'safety_device',
    item_name: '', standard: '', frequency: 'monthly',
    certificate_no: '', certificate_expiry_date: '',
  })
  if (row) Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = JSON.parse(JSON.stringify(form))
    if (payload.id) {
      const { id, ...rest } = payload
      await request.put(`/api/v1/safety-inspections/${id}`, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await request.post('/api/v1/safety-inspections', payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除检查项【${row.item_name}】？`, '提示', { type: 'warning' })
    await request.delete(`/api/v1/safety-inspections/${row.id}`)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

// ---------- 执行检查 ----------
const executeDialogVisible = ref(false)
const executeSaving = ref(false)
const currentRow = ref(null)
const executeForm = reactive({ result: 'pass', findings: '', corrective_action: '' })
function openExecuteDialog(row) {
  currentRow.value = row
  executeForm.result = 'pass'
  executeForm.findings = ''
  executeForm.corrective_action = ''
  executeDialogVisible.value = true
}
async function onSubmitExecute() {
  executeSaving.value = true
  try {
    const today = new Date()
    const nextDate = calcNextDate(currentRow.value.frequency, today)
    await request.post(`/api/v1/safety-inspections/${currentRow.value.id}/execute`, {
      result: executeForm.result,
      findings: executeForm.findings || undefined,
      corrective_action: executeForm.corrective_action || undefined,
      inspected_at: dayjs(today).format('YYYY-MM-DDTHH:mm:ss'),
      next_inspection_date: nextDate,
    })
    ElMessage.success(`检查已提交，下次检查日：${nextDate || '-'}`)
    executeDialogVisible.value = false
    load()
  } catch (e) {} finally {
    executeSaving.value = false
  }
}

onMounted(async () => {
  equipments.value = await listEquipments({ limit: 500 })
  await load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.alert-cell { color: var(--app-danger); font-weight: 600; }
.exec-tip { font-size: 12px; color: var(--app-text-secondary); margin-top: 8px; }
</style>
