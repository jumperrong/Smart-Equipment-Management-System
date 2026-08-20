<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="派工">
            <el-select v-model="query.dispatch_id" filterable placeholder="全部" clearable style="width:300px">
              <el-option v-for="d in dispatches" :key="d.id" :label="`#${d.id} 工序${d.step_seq} ${d.step_name}`" :value="d.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="报工时间">
            <el-date-picker
              v-model="query.date_range"
              type="daterange"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始"
              end-placeholder="结束"
              style="width:300px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增报工</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small" @row-click="showLaborReport">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="派工号" min-width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showDispatch(row.dispatch_id)">{{ row.dispatch_no || `#${row.dispatch_id}` }}</el-button>
          </template>
        </el-table-column>
        <el-table-column label="报工人" width="120">
          <template #default="{ row }">{{ row.reporter_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="报工时间" width="160">
          <template #default="{ row }">{{ formatTime(row.report_time) }}</template>
        </el-table-column>
        <el-table-column prop="input_qty" label="投入" width="80" align="right" />
        <el-table-column prop="good_qty" label="合格" width="80" align="right" />
        <el-table-column prop="defect_qty" label="不良" width="80" align="right" />
        <el-table-column label="人时" width="90" align="right">
          <template #default="{ row }">{{ row.man_hours != null ? row.man_hours : '-' }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canCorrect" size="small" link type="primary" @click.stop="openDialog(row)">编辑</el-button>
            <el-button v-if="canCorrect" size="small" link type="danger" @click.stop="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 报工详情抽屉 -->
    <el-drawer v-model="laborDrawerVisible" :title="laborDrawerTitle" size="640px" direction="rtl">
      <div v-loading="laborLoading" class="detail-body">
        <template v-if="laborDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="报工ID">{{ laborDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="派工号">{{ laborDetail.dispatch_no || `#${laborDetail.dispatch_id}` }}</el-descriptions-item>
            <el-descriptions-item label="报工人">{{ laborDetail.reporter_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="报工时间">{{ formatTime(laborDetail.report_time) }}</el-descriptions-item>
            <el-descriptions-item label="作业开始">{{ formatTime(laborDetail.session_start) }}</el-descriptions-item>
            <el-descriptions-item label="作业结束">{{ formatTime(laborDetail.session_end) }}</el-descriptions-item>
            <el-descriptions-item label="投入数量">{{ laborDetail.input_qty }}</el-descriptions-item>
            <el-descriptions-item label="合格数量">{{ laborDetail.good_qty }}</el-descriptions-item>
            <el-descriptions-item label="不良数量">{{ laborDetail.defect_qty }}</el-descriptions-item>
            <el-descriptions-item label="人时(小时)">{{ laborDetail.man_hours != null ? laborDetail.man_hours : '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(laborDetail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(laborDetail.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ laborDetail.remark || '—' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>

    <!-- 派工详情抽屉 -->
    <el-drawer v-model="dispatchDrawerVisible" :title="dispatchDrawerTitle" size="640px" direction="rtl">
      <div v-loading="dispatchLoading" class="detail-body">
        <template v-if="dispatchDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="派工ID">{{ dispatchDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="dispatchStatusTag(dispatchDetail.status)" size="small">{{ dispatchStatusLabel(dispatchDetail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="工序">{{ dispatchDetail.step_seq }} · {{ dispatchDetail.step_name }}</el-descriptions-item>
            <el-descriptions-item label="MO号">{{ dispatchDetail.mo_no || (dispatchDetail.mo_id ? `#${dispatchDetail.mo_id}` : '—') }}</el-descriptions-item>
            <el-descriptions-item label="设备">{{ dispatchDetail.equipment_name || (dispatchDetail.equipment_id ? `#${dispatchDetail.equipment_id}` : '—') }}</el-descriptions-item>
            <el-descriptions-item label="作业员">{{ dispatchDetail.operator_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="派工数量">{{ dispatchDetail.dispatch_qty }}</el-descriptions-item>
            <el-descriptions-item label="完工数量">{{ dispatchDetail.completed_qty }}</el-descriptions-item>
            <el-descriptions-item label="报废数量">{{ dispatchDetail.scrapped_qty }}</el-descriptions-item>
            <el-descriptions-item label="在制数量">{{ dispatchDetail.wip_qty }}</el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">{{ formatTime(dispatchDetail.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>

    <!-- 新增/编辑报工 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑报工' : '新增报工'" width="640px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="派工" prop="dispatch_id">
              <el-select v-model="form.dispatch_id" filterable placeholder="选择派工" style="width:100%">
                <el-option v-for="d in dispatches" :key="d.id" :label="`#${d.id} 工序${d.step_seq} ${d.step_name}`" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="作业开始"><el-date-picker v-model="form.session_start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="作业结束"><el-date-picker v-model="form.session_end" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="投入数量" prop="input_qty"><el-input-number v-model="form.input_qty" :min="0" controls-position="right" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="合格数量" prop="good_qty"><el-input-number v-model="form.good_qty" :min="0" controls-position="right" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="不良数量"><el-input-number v-model="form.defect_qty" :min="0" controls-position="right" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="人时(小时)"><el-input-number v-model="form.man_hours" :min="0" :precision="2" controls-position="right" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getLaborReports, getLaborReport, createLaborReport, updateLaborReport, deleteLaborReport } from '@/api/labor_report'
import { getDispatches, getDispatch } from '@/api/dispatch'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('production.labor_report'))
const canCorrect = computed(() => userStore.can('production.labor_correct'))

// 报工详情抽屉
const laborDrawerVisible = ref(false)
const laborDrawerTitle = ref('报工详情')
const laborLoading = ref(false)
const laborDetail = ref(null)
async function showLaborReport(row, column, event) {
  // 如果点击目标在 button 上，则不触发行详情
  if (event && event.target && event.target.closest('button')) return
  if (!row || !row.id) return
  laborDrawerVisible.value = true
  laborLoading.value = true
  laborDetail.value = JSON.parse(JSON.stringify(row))
  laborDrawerTitle.value = `报工详情 · #${row.id}`
  try {
    const full = await getLaborReport(row.id)
    laborDetail.value = full
  } catch (e) {} finally {
    laborLoading.value = false
  }
}

// 派工详情抽屉
const dispatchDrawerVisible = ref(false)
const dispatchDrawerTitle = ref('派工详情')
const dispatchLoading = ref(false)
const dispatchDetail = ref(null)
function dispatchStatusLabel(s) {
  return ({ QUEUED: '已排队', ASSIGNED: '已分配', RUNNING: '执行中', HELD: '已暂停', COMPLETED: '已完工', SCRAPPED: '已报废', CANCELLED: '已取消' }[s]) || s || '—'
}
function dispatchStatusTag(s) {
  return ({ QUEUED: 'info', ASSIGNED: 'primary', RUNNING: 'warning', HELD: 'danger', COMPLETED: 'success', SCRAPPED: 'info', CANCELLED: 'info' }[s]) || 'info'
}
async function showDispatch(dispatchId) {
  if (!dispatchId) return
  dispatchDrawerVisible.value = true
  dispatchLoading.value = true
  dispatchDetail.value = null
  // 先用列表里的派工信息快速展示
  const d = dispatches.value.find((x) => x.id === dispatchId)
  if (d) {
    dispatchDetail.value = JSON.parse(JSON.stringify(d))
    dispatchDrawerTitle.value = `派工详情 · #${d.id}（工序${d.step_seq} ${d.step_name}）`
  }
  try {
    const full = await getDispatch(dispatchId)
    dispatchDetail.value = full
    dispatchDrawerTitle.value = `派工详情 · #${full.id}（工序${full.step_seq} ${full.step_name}）`
  } catch (e) {} finally {
    dispatchLoading.value = false
  }
}

const query = reactive({ dispatch_id: null, date_range: null })
const list = ref([])
const loading = ref(false)
const dispatches = ref([])

function resetQuery() {
  query.dispatch_id = null
  query.date_range = null
  load()
}

async function loadDispatches() {
  dispatches.value = await getDispatches({ limit: 200 })
}
async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.dispatch_id) params.dispatch_id = query.dispatch_id
    const all = await getLaborReports(params)
    // 本地按报工时间区间过滤（后端暂未支持时间参数时兜底）
    const [startStr, endStr] = query.date_range || [null, null]
    list.value = (all || []).filter((r) => {
      if (!startStr && !endStr) return true
      const t = (r.report_time || r.created_at || '').slice(0, 10)
      if (!t) return false
      if (startStr && t < startStr) return false
      if (endStr && t > endStr) return false
      return true
    })
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null,
  dispatch_id: null,
  session_start: null,
  session_end: null,
  input_qty: 0,
  good_qty: 0,
  defect_qty: 0,
  man_hours: null,
  remark: '',
})
const formRules = {
  dispatch_id: [{ required: true, message: '请选择派工', trigger: 'change' }],
  input_qty: [{ required: true, message: '请输入投入数量', trigger: 'blur' }],
  good_qty: [{ required: true, message: '请输入合格数量', trigger: 'blur' }],
}
function openDialog(row = null) {
  Object.assign(form, {
    id: null,
    dispatch_id: null,
    session_start: null,
    session_end: null,
    input_qty: 0,
    good_qty: 0,
    defect_qty: 0,
    man_hours: null,
    remark: '',
  })
  if (row) {
    Object.assign(form, JSON.parse(JSON.stringify(row)))
  }
  dialogVisible.value = true
}
function buildSummary(payload) {
  const d = dispatches.value.find((x) => x.id === payload.dispatch_id)
  const dLabel = d ? `#${d.id} 工序${d.step_seq} ${d.step_name}` : `#${payload.dispatch_id}`
  return [
    `派工：${dLabel}`,
    `作业时间：${formatTime(payload.session_start)} ~ ${formatTime(payload.session_end)}`,
    `投入 / 合格 / 不良：${payload.input_qty} / ${payload.good_qty} / ${payload.defect_qty}`,
    `人时：${payload.man_hours != null ? payload.man_hours : '-'} 小时`,
  ].join('<br/>')
}
async function onSave() {
  try {
    await formRef.value.validate()
    const payload = JSON.parse(JSON.stringify(form))
    if (payload.id) {
      saving.value = true
      const { id, ...rest } = payload
      await updateLaborReport(id, rest)
      ElMessage.success('已编辑')
      dialogVisible.value = false
      load()
    } else {
      // 新增报工：提交前展示提交摘要供确认
      await ElMessageBox.confirm(buildSummary(payload), '提交摘要确认', {
        type: 'info',
        confirmButtonText: '确认提交',
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: true,
      })
      saving.value = true
      delete payload.id
      await createLaborReport(payload)
      ElMessage.success('已提交')
      dialogVisible.value = false
      load()
    }
  } catch (e) {
    // 校验失败或用户取消确认框
  } finally {
    saving.value = false
  }
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该报工记录？', '删除确认', { type: 'warning' })
    await deleteLaborReport(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

onMounted(async () => {
  await loadDispatches()
  await load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.detail-body { padding: 4px 16px 16px; }
:deep(.el-table__row) { cursor: pointer; }
</style>
