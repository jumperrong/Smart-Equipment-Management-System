<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="activeTab" class="main-tabs">
        <!-- ============ 润滑点管理 Tab ============ -->
        <el-tab-pane label="润滑点管理" name="points">
          <div class="toolbar">
            <el-form :inline="true" size="default">
              <el-form-item label="设备">
                <el-select v-model="pointsQuery.equipment_id" filterable clearable placeholder="全部设备" style="width:220px">
                  <el-option v-for="e in equipmentList" :key="e.id" :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="success" @click="openPointDialog()">新建润滑点</el-button>
                <el-button type="warning" @click="openAlarm">告警 ({{ alarmCount }})</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="filteredPoints" stripe v-loading="pointsLoading" border size="small" :row-class-name="pointRowClass">
            <el-table-column label="设备" min-width="130">
              <template #default="{ row }">{{ equipmentName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column prop="part_name" label="润滑部位" min-width="120" show-overflow-tooltip />
            <el-table-column prop="code" label="编号" width="110" />
            <el-table-column prop="location" label="定点" min-width="110" show-overflow-tooltip />
            <el-table-column prop="owner" label="定人" width="90" />
            <el-table-column label="定时(频次)" width="110" align="center">
              <template #default="{ row }">{{ freqLabel(row.frequency) }}</template>
            </el-table-column>
            <el-table-column prop="oil_brand" label="定质(油牌号)" min-width="120" show-overflow-tooltip />
            <el-table-column prop="quantity" label="定量" width="90" />
            <el-table-column label="下次润滑日" width="180">
              <template #default="{ row }">
                <span>{{ formatDate(row.next_lubricate_date) }}</span>
                <el-tag v-if="pointWarnLevel(row) === 'overdue'" type="danger" size="small" effect="dark" style="margin-left:6px">已逾期 {{ -daysUntil(row.next_lubricate_date) }}天</el-tag>
                <el-tag v-else-if="pointWarnLevel(row) === 'soon'" type="warning" size="small" effect="dark" style="margin-left:6px">{{ daysUntil(row.next_lubricate_date) }}天后</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用状态" width="100" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.is_active" @change="(val) => toggleActive(row, val)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right" align="center">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openPointDialog(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="onDeletePoint(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ============ 润滑记录 Tab ============ -->
        <el-tab-pane label="润滑记录" name="records">
          <div class="toolbar">
            <el-form :inline="true" size="default">
              <el-form-item>
                <el-button type="success" @click="openRecordDialog()">新建记录</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="records" stripe v-loading="recordsLoading" border size="small">
            <el-table-column label="润滑点" min-width="180">
              <template #default="{ row }">
                <div class="lp-cell">
                  <span class="lp-name">{{ pointLabel(row.lubrication_point_id) }}</span>
                  <span class="lp-eq muted">{{ equipmentName(pointEquipmentId(row.lubrication_point_id)) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="润滑日期" width="120">
              <template #default="{ row }">{{ formatDate(row.lubricate_date) }}</template>
            </el-table-column>
            <el-table-column prop="actual_oil_brand" label="实际油牌号" min-width="120" show-overflow-tooltip />
            <el-table-column prop="actual_quantity" label="实际用量" width="100" />
            <el-table-column prop="executor" label="执行人" width="100" />
            <el-table-column label="结果" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="recordResultTag(row.result)" size="small" effect="light">{{ recordResultLabel(row.result) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="140" fixed="right" align="center">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openRecordDialog(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="onDeleteRecord(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑 润滑点 -->
    <el-dialog v-model="pointDialogVisible" :title="pointForm.id ? '编辑润滑点' : '新建润滑点'" width="640px">
      <el-form :model="pointForm" :rules="pointRules" ref="pointFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="pointForm.equipment_id" filterable placeholder="请选择设备" style="width:100%">
                <el-option v-for="e in equipmentList" :key="e.id" :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="编号" prop="code"><el-input v-model="pointForm.code" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="润滑部位" prop="part_name"><el-input v-model="pointForm.part_name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="定点位置"><el-input v-model="pointForm.location" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人" prop="owner"><el-input v-model="pointForm.owner" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="频次" prop="frequency">
              <el-select v-model="pointForm.frequency" filterable allow-create default-first-option placeholder="选择或输入" style="width:100%">
                <el-option v-for="f in FREQ_OPTIONS" :key="f.value" :label="f.label" :value="f.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="油牌号" prop="oil_brand"><el-input v-model="pointForm.oil_brand" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用量"><el-input v-model="pointForm.quantity" placeholder="如 50ml" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="下次润滑日">
              <el-date-picker v-model="pointForm.next_lubricate_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch v-model="pointForm.is_active" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="pointForm.remark" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="pointDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="pointSaving" @click="onSavePoint">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑 润滑记录 -->
    <el-dialog v-model="recordDialogVisible" :title="recordForm.id ? '编辑润滑记录' : '新建润滑记录'" width="560px">
      <el-form :model="recordForm" :rules="recordRules" ref="recordFormRef" label-width="100px">
        <el-form-item label="润滑点" prop="lubrication_point_id">
          <el-select v-model="recordForm.lubrication_point_id" filterable placeholder="请选择润滑点" style="width:100%" @change="onRecordPointChange">
            <el-option v-for="p in allPoints" :key="p.id" :label="`${pointLabel(p.id)} - ${equipmentName(p.equipment_id)}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="润滑日期" prop="lubricate_date">
          <el-date-picker v-model="recordForm.lubricate_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="实际油牌号"><el-input v-model="recordForm.actual_oil_brand" /></el-form-item>
        <el-form-item label="实际用量"><el-input v-model="recordForm.actual_quantity" placeholder="如 50ml" /></el-form-item>
        <el-form-item label="执行人"><el-input v-model="recordForm.executor" /></el-form-item>
        <el-form-item label="结果" prop="result">
          <el-radio-group v-model="recordForm.result">
            <el-radio-button v-for="r in RECORD_RESULT_OPTIONS" :key="r.value" :value="r.value">{{ r.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="recordForm.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="recordSaving" @click="onSaveRecord">保存</el-button>
      </template>
    </el-dialog>

    <!-- 告警对话框 -->
    <el-dialog v-model="alarmVisible" title="润滑到期告警" width="820px">
      <div class="alarm-tip" v-if="alarmPoints.length">
        以下润滑点 <b>下次润滑日</b> 已逾期或将在 7 天内到期，请及时处理。
      </div>
      <el-table :data="alarmPoints" v-loading="alarmLoading" stripe border size="small" :row-class-name="pointRowClass">
        <el-table-column label="设备" min-width="130">
          <template #default="{ row }">{{ equipmentName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column label="润滑点" min-width="150">
          <template #default="{ row }">{{ pointLabel(row.id) }}</template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="100" />
        <el-table-column label="下次润滑日" width="180">
          <template #default="{ row }">
            <span>{{ formatDate(row.next_lubricate_date) }}</span>
            <el-tag v-if="pointWarnLevel(row) === 'overdue'" type="danger" size="small" effect="dark" style="margin-left:6px">已逾期 {{ -daysUntil(row.next_lubricate_date) }}天</el-tag>
            <el-tag v-else-if="pointWarnLevel(row) === 'soon'" type="warning" size="small" effect="dark" style="margin-left:6px">{{ daysUntil(row.next_lubricate_date) }}天后</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!alarmPoints.length && !alarmLoading" description="暂无到期/逾期告警" />
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { dayjs, formatTime } from '@/utils'

const FREQ_OPTIONS = [
  { value: 'DAILY', label: '每日' },
  { value: 'WEEKLY', label: '每周' },
  { value: 'BIWEEKLY', label: '每两周' },
  { value: 'MONTHLY', label: '每月' },
  { value: 'QUARTERLY', label: '每季度' },
  { value: 'SEMI_ANNUAL', label: '每半年' },
  { value: 'ANNUAL', label: '每年' },
]
const RECORD_RESULT_OPTIONS = [
  { value: 'done', label: '完成', tag: 'success' },
  { value: 'abnormal', label: '异常', tag: 'danger' },
]

function freqLabel(f) { return FREQ_OPTIONS.find(x => x.value === f)?.label || f || '-' }
function recordResultLabel(r) { return RECORD_RESULT_OPTIONS.find(x => x.value === r)?.label || r || '-' }
function recordResultTag(r) { return RECORD_RESULT_OPTIONS.find(x => x.value === r)?.tag || 'info' }
function formatDate(d) { return formatTime(d, 'YYYY-MM-DD') }

// ---- 设备 ----
const equipmentList = ref([])
const equipmentMap = computed(() => {
  const m = {}
  equipmentList.value.forEach(e => { m[e.id] = e })
  return m
})
function equipmentName(id) { return equipmentMap.value[id]?.name || (id ? `#${id}` : '-') }
async function loadEquipments() {
  try {
    const res = await request.get('/api/v1/equipments')
    equipmentList.value = Array.isArray(res) ? res : (res?.items || [])
  } catch (e) {
    console.warn('load equipments failed', e)
  }
}

// ---- 润滑点 ----
const activeTab = ref('points')
const pointsQuery = reactive({ equipment_id: null })
const allPoints = ref([])
const pointsLoading = ref(false)
const filteredPoints = computed(() => {
  if (!pointsQuery.equipment_id) return allPoints.value
  return allPoints.value.filter(p => p.equipment_id === pointsQuery.equipment_id)
})
const pointMap = computed(() => {
  const m = {}
  allPoints.value.forEach(p => { m[p.id] = p })
  return m
})
function pointLabel(id) {
  const p = pointMap.value[id]
  if (!p) return id ? `#${id}` : '-'
  return p.code ? `${p.part_name} (${p.code})` : p.part_name
}
function pointEquipmentId(id) { return pointMap.value[id]?.equipment_id || null }

async function loadPoints() {
  pointsLoading.value = true
  try {
    const res = await request.get('/lubrication/points')
    allPoints.value = Array.isArray(res) ? res : (res?.items || [])
  } finally {
    pointsLoading.value = false
  }
}

// ---- 告警判定 ----
function daysUntil(dateStr) {
  if (!dateStr) return null
  return dayjs(dateStr).startOf('day').diff(dayjs().startOf('day'), 'day')
}
function pointWarnLevel(row) {
  const d = daysUntil(row.next_lubricate_date)
  if (d === null) return null
  if (d < 0) return 'overdue'
  if (d <= 7) return 'soon'
  return null
}
function pointRowClass({ row }) {
  const lvl = pointWarnLevel(row)
  if (lvl === 'overdue') return 'row-overdue'
  if (lvl === 'soon') return 'row-soon'
  return ''
}
const alarmCount = computed(() => allPoints.value.filter(p => pointWarnLevel(p)).length)

// ---- 润滑点 新建/编辑 ----
const pointDialogVisible = ref(false)
const pointSaving = ref(false)
const pointFormRef = ref(null)
function emptyPointForm() {
  return {
    id: null, equipment_id: null, part_name: '', code: '', location: '',
    owner: '', frequency: 'MONTHLY', oil_brand: '', quantity: '',
    next_lubricate_date: '', is_active: true, remark: '',
  }
}
const pointForm = reactive(emptyPointForm())
const pointRules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  part_name: [{ required: true, message: '请输入润滑部位', trigger: 'blur' }],
  frequency: [{ required: true, message: '请选择频次', trigger: 'change' }],
}
function openPointDialog(row = null) {
  Object.assign(pointForm, emptyPointForm())
  if (row) Object.assign(pointForm, JSON.parse(JSON.stringify(row)))
  pointDialogVisible.value = true
}
async function onSavePoint() {
  try {
    await pointFormRef.value.validate()
    pointSaving.value = true
    const payload = JSON.parse(JSON.stringify(pointForm))
    if (payload.id) {
      const { id, ...rest } = payload
      await request.put(`/lubrication/points/${id}`, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await request.post('/lubrication/points', payload)
      ElMessage.success('已创建')
    }
    pointDialogVisible.value = false
    await loadPoints()
  } catch (e) {} finally {
    pointSaving.value = false
  }
}
async function onDeletePoint(row) {
  try {
    await ElMessageBox.confirm(`确认删除润滑点【${pointLabel(row.id)}】？`, '危险操作', { type: 'error' })
    await request.delete(`/lubrication/points/${row.id}`)
    ElMessage.success('已删除')
    await loadPoints()
  } catch (e) {}
}
async function toggleActive(row, val) {
  try {
    const { id, ...rest } = JSON.parse(JSON.stringify(row))
    await request.put(`/lubrication/points/${id}`, rest)
    ElMessage.success(val ? '已启用' : '已停用')
  } catch (e) {
    row.is_active = !val
  }
}

// ---- 告警对话框 ----
const alarmVisible = ref(false)
const alarmLoading = ref(false)
const alarmPoints = ref([])
async function openAlarm() {
  alarmVisible.value = true
  alarmLoading.value = true
  try {
    // 始终基于全量润滑点计算告警，不受设备筛选影响
    if (!allPoints.value.length) await loadPoints()
    alarmPoints.value = allPoints.value
      .filter(p => p.is_active !== false && pointWarnLevel(p))
      .slice().sort((a, b) => daysUntil(a.next_lubricate_date) - daysUntil(b.next_lubricate_date))
  } finally {
    alarmLoading.value = false
  }
}

// ---- 润滑记录 ----
const records = ref([])
const recordsLoading = ref(false)
async function loadRecords() {
  recordsLoading.value = true
  try {
    const res = await request.get('/lubrication/records')
    records.value = Array.isArray(res) ? res : (res?.items || [])
  } finally {
    recordsLoading.value = false
  }
}

const recordDialogVisible = ref(false)
const recordSaving = ref(false)
const recordFormRef = ref(null)
function emptyRecordForm() {
  return {
    id: null, lubrication_point_id: null, lubricate_date: '',
    actual_oil_brand: '', actual_quantity: '', executor: '', result: 'done', remark: '',
  }
}
const recordForm = reactive(emptyRecordForm())
const recordRules = {
  lubrication_point_id: [{ required: true, message: '请选择润滑点', trigger: 'change' }],
  lubricate_date: [{ required: true, message: '请选择润滑日期', trigger: 'change' }],
  result: [{ required: true, message: '请选择结果', trigger: 'change' }],
}
function openRecordDialog(row = null) {
  Object.assign(recordForm, emptyRecordForm())
  if (row) Object.assign(recordForm, JSON.parse(JSON.stringify(row)))
  recordDialogVisible.value = true
}
// 选择润滑点后，自动带出油牌号与用量，便于录入
function onRecordPointChange() {
  const p = pointMap.value[recordForm.lubrication_point_id]
  if (!p) return
  if (!recordForm.actual_oil_brand) recordForm.actual_oil_brand = p.oil_brand || ''
  if (!recordForm.actual_quantity) recordForm.actual_quantity = p.quantity || ''
}
async function onSaveRecord() {
  try {
    await recordFormRef.value.validate()
    recordSaving.value = true
    const payload = JSON.parse(JSON.stringify(recordForm))
    if (payload.id) {
      const { id, ...rest } = payload
      await request.put(`/lubrication/records/${id}`, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await request.post('/lubrication/records', payload)
      ElMessage.success('已创建')
    }
    recordDialogVisible.value = false
    // 新增记录后后端可能重算下次润滑日，刷新润滑点
    await Promise.all([loadRecords(), loadPoints()])
  } catch (e) {} finally {
    recordSaving.value = false
  }
}
async function onDeleteRecord(row) {
  try {
    await ElMessageBox.confirm('确认删除该润滑记录？', '危险操作', { type: 'error' })
    await request.delete(`/lubrication/records/${row.id}`)
    ElMessage.success('已删除')
    await loadRecords()
  } catch (e) {}
}

// 切到"润滑记录"Tab 时懒加载一次
watch(activeTab, async (nv) => {
  if (nv === 'records' && records.value.length === 0) {
    await loadRecords()
  }
})

onMounted(async () => {
  await Promise.all([loadEquipments(), loadPoints()])
})
</script>

<style scoped>
.main-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }
.toolbar { margin-bottom: 10px; }
.muted { color: var(--app-text-muted); font-size: 12px; }

.lp-cell { display: flex; flex-direction: column; line-height: 1.35; }
.lp-name { color: var(--app-text-primary); font-size: 13px; }
.lp-eq { margin-top: 2px; }

.alarm-tip {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--app-warning-bg);
  border: 1px solid var(--app-warning);
  border-radius: 4px;
  color: var(--app-text-regular);
  font-size: 13px;
}

/* 告警行标红：逾期 / 7天内到期 */
:deep(.el-table .row-overdue td.el-table__cell),
:deep(.el-table .row-overdue:hover td.el-table__cell) {
  background-color: var(--app-danger-bg) !important;
}
:deep(.el-table .row-soon td.el-table__cell),
:deep(.el-table .row-soon:hover td.el-table__cell) {
  background-color: var(--app-danger-bg) !important;
}
</style>
