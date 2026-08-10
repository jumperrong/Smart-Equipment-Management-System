<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" size="default">
          <el-form-item label="设备">
            <el-select
              v-model="currentEquipmentId"
              filterable
              placeholder="请选择设备"
              style="width:300px"
              @change="load"
            >
              <el-option
                v-for="e in equipmentList"
                :key="e.id"
                :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                :value="e.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="success" :disabled="!currentEquipmentId" @click="openDialog()">新建阶段记录</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column label="阶段" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="stageTag(row.stage)" effect="dark" size="small">{{ stageLabel(row.stage) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="阶段日期" width="120">
          <template #default="{ row }">{{ formatDate(row.stage_date) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" effect="light" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关键信息摘要" min-width="300">
          <template #default="{ row }">
            <span class="summary-text">{{ stageSummary(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" link type="primary" @click="openTimeline(row)">查看时间线</el-button>
            <el-button size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑阶段记录' : '新建阶段记录'" width="740px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="form.equipment_id" filterable placeholder="请选择设备" style="width:100%">
                <el-option v-for="e in equipmentList" :key="e.id" :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="阶段" prop="stage">
              <el-select v-model="form.stage" style="width:100%">
                <el-option v-for="s in STAGE_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="阶段日期" prop="stage_date">
              <el-date-picker v-model="form.stage_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width:100%">
                <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="标题" prop="title"><el-input v-model="form.title" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>

        <!-- T0 选型 -->
        <template v-if="form.stage === 'T0'">
          <el-divider content-position="left">T0 选型信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="24">
              <el-form-item label="候选供应商"><el-input v-model="form.candidate_suppliers" type="textarea" :rows="2" placeholder="多个供应商可用逗号分隔" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="选定供应商"><el-input v-model="form.selected_supplier" /></el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="UR需求摘要"><el-input v-model="form.ur_summary" type="textarea" :rows="2" /></el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- T1 采购 -->
        <template v-if="form.stage === 'T1'">
          <el-divider content-position="left">T1 采购信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="采购订单号"><el-input v-model="form.po_no" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="采购金额(¥)"><el-input-number v-model="form.po_amount" :min="0" :precision="2" :step="1000" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="交货日期">
                <el-date-picker v-model="form.delivery_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- T2 安装调试 -->
        <template v-if="form.stage === 'T2'">
          <el-divider content-position="left">T2 安装调试信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="FAT日期"><el-date-picker v-model="form.fat_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="FAT结果">
                <el-select v-model="form.fat_result" clearable placeholder="请选择" style="width:100%">
                  <el-option v-for="r in RESULT_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="FAT备注"><el-input v-model="form.fat_remark" type="textarea" :rows="2" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="SAT日期"><el-date-picker v-model="form.sat_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="SAT结果">
                <el-select v-model="form.sat_result" clearable placeholder="请选择" style="width:100%">
                  <el-option v-for="r in RESULT_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="SAT备注"><el-input v-model="form.sat_remark" type="textarea" :rows="2" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="安装调试日期"><el-date-picker v-model="form.install_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="调试记录"><el-input v-model="form.commissioning_record" type="textarea" :rows="3" /></el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- T3 量产移交 -->
        <template v-if="form.stage === 'T3'">
          <el-divider content-position="left">T3 量产移交信息</el-divider>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="移交日期"><el-date-picker v-model="form.handover_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="移交给谁"><el-input v-model="form.handover_to" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="验收结果">
                <el-select v-model="form.acceptance_result" clearable placeholder="请选择" style="width:100%">
                  <el-option v-for="r in RESULT_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="验收备注"><el-input v-model="form.acceptance_remark" type="textarea" :rows="2" /></el-form-item>
            </el-col>
          </el-row>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 时间线对话框 -->
    <el-dialog v-model="timelineVisible" :title="`生命周期时间线${timelineEquipmentName ? '：' + timelineEquipmentName : ''}`" width="700px">
      <el-empty v-if="!timeline.length && !timelineLoading" description="暂无生命周期记录" />
      <el-timeline v-else v-loading="timelineLoading">
        <el-timeline-item
          v-for="(item, idx) in timeline"
          :key="idx"
          :timestamp="formatDate(item.stage_date)"
          placement="top"
          :type="stageTag(item.stage)"
          :hollow="item.status !== 'COMPLETED'"
        >
          <div class="tl-head">
            <el-tag :type="stageTag(item.stage)" effect="dark" size="small">{{ stageLabel(item.stage) }}</el-tag>
            <span class="tl-title">{{ item.title || '无标题' }}</span>
            <el-tag :type="statusTag(item.status)" effect="light" size="small">{{ statusLabel(item.status) }}</el-tag>
          </div>
          <div class="tl-desc" v-if="item.description">{{ item.description }}</div>
          <div class="tl-summary">{{ stageSummary(item) }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { formatTime } from '@/utils'

const STAGE_OPTIONS = [
  { value: 'T0', label: 'T0 选型', tag: 'info' },
  { value: 'T1', label: 'T1 采购', tag: 'primary' },
  { value: 'T2', label: 'T2 安装调试', tag: 'warning' },
  { value: 'T3', label: 'T3 量产移交', tag: 'success' },
]
const STATUS_OPTIONS = [
  { value: 'PLANNED', label: '已计划', tag: 'info' },
  { value: 'IN_PROGRESS', label: '进行中', tag: 'warning' },
  { value: 'COMPLETED', label: '已完成', tag: 'success' },
]
const RESULT_OPTIONS = [
  { value: 'PASS', label: '通过', tag: 'success' },
  { value: 'FAIL', label: '不通过', tag: 'danger' },
  { value: 'CONDITIONAL', label: '有条件通过', tag: 'warning' },
]
const STAGE_ORDER = { T0: 0, T1: 1, T2: 2, T3: 3 }

function stageLabel(s) { return STAGE_OPTIONS.find(x => x.value === s)?.label || s }
function stageTag(s) { return STAGE_OPTIONS.find(x => x.value === s)?.tag || 'info' }
function statusLabel(s) { return STATUS_OPTIONS.find(x => x.value === s)?.label || s }
function statusTag(s) { return STATUS_OPTIONS.find(x => x.value === s)?.tag || 'info' }
function resultLabel(r) { return RESULT_OPTIONS.find(x => x.value === r)?.label || (r || '-') }
function formatDate(d) { return formatTime(d, 'YYYY-MM-DD') }

// ---- 设备下拉 ----
const equipmentList = ref([])
const currentEquipmentId = ref(null)
async function loadEquipments() {
  try {
    const res = await request.get('/api/v1/equipments')
    equipmentList.value = Array.isArray(res) ? res : (res?.items || [])
    if (equipmentList.value.length && !currentEquipmentId.value) {
      currentEquipmentId.value = equipmentList.value[0].id
      await load()
    }
  } catch (e) {
    console.warn('load equipments failed', e)
  }
}

// ---- 列表 ----
const list = ref([])
const loading = ref(false)
async function load() {
  if (!currentEquipmentId.value) { list.value = []; return }
  loading.value = true
  try {
    const res = await request.get('/equipment-lifecycle', { params: { equipment_id: currentEquipmentId.value } })
    list.value = Array.isArray(res) ? res : (res?.items || [])
  } finally {
    loading.value = false
  }
}

function stageSummary(row) {
  if (!row) return '-'
  if (row.stage === 'T0') {
    return [
      row.selected_supplier && `选定供应商: ${row.selected_supplier}`,
      row.ur_summary && `UR: ${row.ur_summary}`,
    ].filter(Boolean).join(' | ') || '-'
  }
  if (row.stage === 'T1') {
    return [
      row.po_no && `PO: ${row.po_no}`,
      (row.po_amount != null && row.po_amount !== '') && `金额: ¥${row.po_amount}`,
      row.delivery_date && `交货: ${formatDate(row.delivery_date)}`,
    ].filter(Boolean).join(' | ') || '-'
  }
  if (row.stage === 'T2') {
    return [
      row.fat_date && `FAT: ${formatDate(row.fat_date)}(${resultLabel(row.fat_result)})`,
      row.sat_date && `SAT: ${formatDate(row.sat_date)}(${resultLabel(row.sat_result)})`,
      row.install_date && `安装调试: ${formatDate(row.install_date)}`,
    ].filter(Boolean).join(' | ') || '-'
  }
  if (row.stage === 'T3') {
    return [
      row.handover_date && `移交: ${formatDate(row.handover_date)}`,
      row.handover_to && `移交至: ${row.handover_to}`,
      row.acceptance_result && `验收: ${resultLabel(row.acceptance_result)}`,
    ].filter(Boolean).join(' | ') || '-'
  }
  return '-'
}

// ---- 新建/编辑 ----
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)

function emptyForm() {
  return {
    id: null, equipment_id: null, stage: 'T0', stage_date: '', title: '', description: '', status: 'PLANNED',
    candidate_suppliers: '', selected_supplier: '', ur_summary: '',
    po_no: '', po_amount: null, delivery_date: '',
    fat_date: '', fat_result: '', fat_remark: '', sat_date: '', sat_result: '', sat_remark: '',
    install_date: '', commissioning_record: '',
    handover_date: '', handover_to: '', acceptance_result: '', acceptance_remark: '',
  }
}
const form = reactive(emptyForm())
const formRules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  stage: [{ required: true, message: '请选择阶段', trigger: 'change' }],
  stage_date: [{ required: true, message: '请选择阶段日期', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

function openDialog(row = null) {
  Object.assign(form, emptyForm())
  form.equipment_id = currentEquipmentId.value
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
      await request.put(`/equipment-lifecycle/${id}`, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await request.post('/equipment-lifecycle', payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {} finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除阶段记录【${stageLabel(row.stage)} - ${row.title || ''}】？`,
      '危险操作',
      { type: 'error' },
    )
    await request.delete(`/equipment-lifecycle/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e) {}
}

// ---- 时间线 ----
const timelineVisible = ref(false)
const timelineLoading = ref(false)
const timeline = ref([])
const timelineEquipmentName = ref('')
function openTimeline(row) {
  const eqId = row.equipment_id || currentEquipmentId.value
  timelineEquipmentName.value = equipmentList.value.find(e => e.id === eqId)?.name || ''
  timelineLoading.value = true
  timelineVisible.value = true
  // 复用当前设备已加载的列表，按阶段顺序 T0→T3 排序
  timeline.value = list.value.slice().sort((a, b) => {
    const so = (STAGE_ORDER[a.stage] ?? 99) - (STAGE_ORDER[b.stage] ?? 99)
    if (so !== 0) return so
    return (a.stage_date || '').localeCompare(b.stage_date || '')
  })
  timelineLoading.value = false
}

onMounted(loadEquipments)
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.summary-text { color: var(--app-text-regular); font-size: 13px; }

.tl-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.tl-title { font-weight: 600; color: var(--app-text-primary); }
.tl-desc { color: var(--app-text-regular); font-size: 13px; margin-bottom: 4px; }
.tl-summary { color: var(--app-text-secondary); font-size: 12px; }
</style>
