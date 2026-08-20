<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="生产订单">
            <el-select v-model="query.mo_id" filterable placeholder="全部" clearable style="width:240px">
              <el-option v-for="m in productionOrders" :key="m.id" :label="`${m.mo_no} ${m.product_name || ''}`" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:140px">
              <el-option v-for="s in DISPATCH_STATUS_OPTIONS" :key="s" :label="statusLabel(s)" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增派工</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small" @row-click="showDispatch">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="MO号" width="170">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showMo(row.mo_id)">{{ moNo(row.mo_id) }}</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="step_seq" label="工序序号" width="90" align="center" />
        <el-table-column prop="step_name" label="工序名称" min-width="140" />
        <el-table-column label="设备" width="140">
          <template #default="{ row }">{{ row.equipment_name || (row.equipment_id ? `#${row.equipment_id}` : '-') }}</template>
        </el-table-column>
        <el-table-column label="作业员" width="110">
          <template #default="{ row }">{{ row.operator_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="dispatch_qty" label="派工数量" width="90" align="right" />
        <el-table-column prop="completed_qty" label="完工" width="80" align="right" />
        <el-table-column prop="scrapped_qty" label="报废" width="80" align="right" />
        <el-table-column prop="wip_qty" label="在制" width="80" align="right" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite && row.status === 'ASSIGNED'" size="small" link type="primary" @click.stop="onTransition(row, 'RUNNING', '开工')">开工</el-button>
            <el-button v-if="canWrite && row.status === 'RUNNING'" size="small" link type="warning" @click.stop="onTransition(row, 'HELD', '暂停')">暂停</el-button>
            <el-button v-if="canWrite && row.status === 'HELD'" size="small" link type="primary" @click.stop="onTransition(row, 'RUNNING', '恢复')">恢复</el-button>
            <el-button v-if="canWrite && row.status === 'RUNNING'" size="small" link type="success" @click.stop="onTransition(row, 'COMPLETED', '完工')">完工</el-button>
            <el-button v-if="canWrite && (row.status === 'QUEUED' || row.status === 'ASSIGNED' || row.status === 'HELD')" size="small" link type="info" @click.stop="onTransition(row, 'CANCELLED', '取消')">取消</el-button>
            <el-button v-if="canWrite && (row.status === 'QUEUED' || row.status === 'ASSIGNED')" size="small" link type="danger" @click.stop="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 派工详情抽屉 -->
    <el-drawer v-model="dispatchDrawerVisible" :title="dispatchDrawerTitle" size="640px" direction="rtl">
      <div v-loading="dispatchLoading" class="detail-body">
        <template v-if="dispatchDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="派工ID">{{ dispatchDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(dispatchDetail.status)" size="small">{{ statusLabel(dispatchDetail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="MO号">{{ moNo(dispatchDetail.mo_id) }}</el-descriptions-item>
            <el-descriptions-item label="工序">{{ dispatchDetail.step_seq }} · {{ dispatchDetail.step_name }}</el-descriptions-item>
            <el-descriptions-item label="工段">{{ dispatchDetail.process_section_name || (dispatchDetail.process_section_id ? `#${dispatchDetail.process_section_id}` : '—') }}</el-descriptions-item>
            <el-descriptions-item label="工艺数据模板">{{ dispatchDetail.form_template_name || (dispatchDetail.form_template_id ? `#${dispatchDetail.form_template_id}` : '—') }}</el-descriptions-item>
            <el-descriptions-item label="工艺数据表单" :span="2">
              <span v-if="dispatchDetail.form_record_id">#{{ dispatchDetail.form_record_id }}</span>
              <span v-else class="muted">未自动初始化（无工段模板）</span>
            </el-descriptions-item>
            <el-descriptions-item label="设备">{{ dispatchDetail.equipment_name || (dispatchDetail.equipment_id ? `#${dispatchDetail.equipment_id}` : '—') }}</el-descriptions-item>
            <el-descriptions-item label="作业员">{{ dispatchDetail.operator_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="派工数量">{{ dispatchDetail.dispatch_qty }}</el-descriptions-item>
            <el-descriptions-item label="完工数量">{{ dispatchDetail.completed_qty }}</el-descriptions-item>
            <el-descriptions-item label="报废数量">{{ dispatchDetail.scrapped_qty }}</el-descriptions-item>
            <el-descriptions-item label="在制数量">{{ dispatchDetail.wip_qty }}</el-descriptions-item>
            <el-descriptions-item label="暂停原因" :span="2">
              <span v-if="dispatchDetail.held_reason">{{ dispatchDetail.held_reason }}{{ dispatchDetail.held_work_order_id ? `（关联工单 #${dispatchDetail.held_work_order_id}）` : '' }}</span>
              <span v-else>—</span>
            </el-descriptions-item>
            <el-descriptions-item label="计划开始">{{ formatTime(dispatchDetail.planned_start) }}</el-descriptions-item>
            <el-descriptions-item label="计划结束">{{ formatTime(dispatchDetail.planned_end) }}</el-descriptions-item>
            <el-descriptions-item label="实际开始">{{ formatTime(dispatchDetail.actual_start) }}</el-descriptions-item>
            <el-descriptions-item label="实际结束">{{ formatTime(dispatchDetail.actual_end) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(dispatchDetail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(dispatchDetail.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ dispatchDetail.remark || '—' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>

    <!-- MO 详情抽屉 -->
    <el-drawer v-model="moDrawerVisible" :title="moDrawerTitle" size="640px" direction="rtl">
      <div v-loading="moLoading" class="detail-body">
        <template v-if="moDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="MO号">{{ moDetail.mo_no }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="moStatusTag(moDetail.status)" size="small">{{ moStatusLabel(moDetail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="产品">{{ moDetail.product_name || `#${moDetail.product_id}` }}</el-descriptions-item>
            <el-descriptions-item label="批次号">{{ moDetail.batch_no || '—' }}</el-descriptions-item>
            <el-descriptions-item label="计划数量">{{ moDetail.plan_qty }}</el-descriptions-item>
            <el-descriptions-item label="完工数量">{{ moDetail.completed_qty }}</el-descriptions-item>
            <el-descriptions-item label="计划开始">{{ formatTime(moDetail.planned_start) }}</el-descriptions-item>
            <el-descriptions-item label="计划结束">{{ formatTime(moDetail.planned_end) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间" :span="2">{{ formatTime(moDetail.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>

    <!-- 新增派工 -->
    <el-dialog v-model="dialogVisible" title="新增派工" width="760px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="生产订单" prop="mo_id">
              <el-select v-model="form.mo_id" filterable placeholder="选择MO" style="width:100%" @change="onMoChange">
                <el-option v-for="m in productionOrders" :key="m.id" :label="`${m.mo_no} ${m.product_name || ''}`" :value="m.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工序序号" prop="step_seq">
              <el-input-number v-model="form.step_seq" :min="1" controls-position="right" style="width:100%" @change="onStepSeqChange" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工序名称" prop="step_name"><el-input v-model="form.step_name" placeholder="工序名称" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工段">
              <el-select v-model="form.process_section_id" filterable clearable placeholder="按MO路由联动" style="width:100%" @change="onSectionChange">
                <el-option
                  v-for="s in processSections"
                  :key="s.id"
                  :label="`${s.name}${s.form_template_name ? ' · ' + s.form_template_name : ''}`"
                  :value="s.id"
                />
              </el-select>
              <div class="hint">提示：选择工段后，派工创建时会按工段关联模板自动初始化工艺数据表单</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备">
              <el-select v-model="form.equipment_id" filterable placeholder="选择设备" clearable style="width:100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="作业员">
              <el-select v-model="form.assigned_operator_id" filterable placeholder="选择作业员" clearable style="width:100%">
                <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="派工数量" prop="dispatch_qty">
              <el-input-number v-model="form.dispatch_qty" :min="1" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDispatches, getDispatch, createDispatch, updateDispatch, deleteDispatch } from '@/api/dispatch'
import { getProductionOrders, getProductionOrder } from '@/api/production_order'
import { listEquipments } from '@/api/equipment'
import { getProcessSections } from '@/api/process_section'
import { getRouting } from '@/api/routing'
import request from '@/api/request'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('production.dispatch_assign'))

// 派工详情抽屉
const dispatchDrawerVisible = ref(false)
const dispatchDrawerTitle = ref('派工详情')
const dispatchLoading = ref(false)
const dispatchDetail = ref(null)
async function showDispatch(row, column, event) {
  // 如果点击目标在 button 上，则不触发行详情
  if (event && event.target && event.target.closest('button')) return
  if (!row || !row.id) return
  dispatchDrawerVisible.value = true
  dispatchLoading.value = true
  dispatchDetail.value = JSON.parse(JSON.stringify(row))
  dispatchDrawerTitle.value = `派工详情 · #${row.id}（${moNo(row.mo_id)} / 工序${row.step_seq}）`
  try {
    const full = await getDispatch(row.id)
    dispatchDetail.value = full
  } catch (e) {} finally {
    dispatchLoading.value = false
  }
}

// MO 详情抽屉
const moDrawerVisible = ref(false)
const moDrawerTitle = ref('订单详情')
const moLoading = ref(false)
const moDetail = ref(null)
function moStatusLabel(s) {
  return ({ DRAFT: '草稿', RELEASED: '已下发', IN_PROGRESS: '执行中', COMPLETED: '已完工', CLOSED: '已结案', CANCELLED: '已取消' }[s]) || s || '—'
}
function moStatusTag(s) {
  return ({ DRAFT: 'info', RELEASED: 'primary', IN_PROGRESS: 'warning', COMPLETED: 'success', CLOSED: '', CANCELLED: 'info' }[s]) || 'info'
}
async function showMo(moId) {
  if (!moId) return
  moDrawerVisible.value = true
  moLoading.value = true
  moDetail.value = null
  // 先用列表里的 MO 信息快速展示
  const m = productionOrders.value.find((x) => x.id === moId)
  if (m) {
    moDetail.value = JSON.parse(JSON.stringify(m))
    moDrawerTitle.value = `订单详情 · ${m.mo_no}`
  }
  try {
    const full = await getProductionOrder(moId)
    moDetail.value = full
    moDrawerTitle.value = `订单详情 · ${full.mo_no}`
  } catch (e) {} finally {
    moLoading.value = false
  }
}

const DISPATCH_STATUS_OPTIONS = ['QUEUED', 'ASSIGNED', 'RUNNING', 'HELD', 'COMPLETED', 'SCRAPPED', 'CANCELLED']
function statusLabel(s) {
  return ({ QUEUED: '已排队', ASSIGNED: '已分配', RUNNING: '执行中', HELD: '已暂停', COMPLETED: '已完工', SCRAPPED: '已报废', CANCELLED: '已取消' }[s]) || s
}
function statusTag(s) {
  return ({ QUEUED: 'info', ASSIGNED: 'primary', RUNNING: 'warning', HELD: 'danger', COMPLETED: 'success', SCRAPPED: 'info', CANCELLED: 'info' }[s]) || 'info'
}

const query = reactive({ mo_id: null, status: null })
const list = ref([])
const loading = ref(false)
const productionOrders = ref([])
const equipments = ref([])
const users = ref([])
// 工段库（全部启用），用于派工选工段
const allSections = ref([])
// 当前所选 MO 路由联动出的工段候选（仅路由步骤引用的工段）
const processSections = ref([])
// MO 当前所选路由详情（含 steps）
const currentRouting = ref(null)

function moNo(id) {
  const m = productionOrders.value.find((x) => x.id === id)
  return m ? m.mo_no : `#${id}`
}

// listUsers 仅 admin/engineer 可调，对其它角色静默失败（不弹错误提示），下拉留空
async function loadUsersSilent() {
  try {
    return await request({ url: '/api/v1/auth/users', method: 'get', silent: true })
  } catch (e) {
    return []
  }
}
async function loadRefs() {
  const [mos, eqs, us, secs] = await Promise.all([
    getProductionOrders({ limit: 200 }).catch(() => []),
    listEquipments({ limit: 500 }).catch(() => []),
    loadUsersSilent(),
    getProcessSections({ is_active: true, limit: 500 }).catch(() => []),
  ])
  productionOrders.value = mos || []
  equipments.value = eqs || []
  users.value = us || []
  allSections.value = Array.isArray(secs) ? secs : []
}
async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.mo_id) params.mo_id = query.mo_id
    if (query.status) params.status = query.status
    list.value = await getDispatches(params)
  } finally {
    loading.value = false
  }
}

// 选 MO 时联动：拉取其 routing 详情，并据此填可选工段
async function onMoChange(moId) {
  form.process_section_id = null
  form.step_seq = 1
  form.step_name = ''
  processSections.value = []
  currentRouting.value = null
  if (!moId) return
  const mo = productionOrders.value.find((m) => m.id === moId)
  const routingId = mo?.routing_id
  if (!routingId) {
    // MO 未挂路由：开放所有工段供选
    processSections.value = allSections.value
    return
  }
  try {
    const r = await getRouting(routingId)
    currentRouting.value = r
    // 候选工段 = 路由步骤中引用的工段（去重）
    const sectionIds = (r.steps || [])
      .map((s) => s.process_section_id)
      .filter((v) => v)
    const uniqIds = [...new Set(sectionIds)]
    processSections.value = allSections.value.filter((s) => uniqIds.includes(s.id))
    // 若路由只有一道工序，自动预填
    if (uniqIds.length === 1) {
      const sid = uniqIds[0]
      const st = allSections.value.find((s) => s.id === sid)
      form.process_section_id = sid
      onSectionChange(sid)
    }
  } catch (e) {
    processSections.value = allSections.value
  }
}

// step_seq 联动：从路由步骤预填 step_name + process_section_id
function onStepSeqChange() {
  if (!currentRouting.value) return
  const step = (currentRouting.value.steps || []).find((s) => s.seq === form.step_seq)
  if (step) {
    if (step.step_name) form.step_name = step.step_name
    if (step.process_section_id) {
      // 若工段在 processSections 中则直接选
      const inList = processSections.value.find((s) => s.id === step.process_section_id)
      if (inList) {
        form.process_section_id = step.process_section_id
      }
    }
  }
}

// 选工段：若 step_name 为空，用工段名预填
function onSectionChange(sid) {
  if (!sid) return
  if (!form.step_name) {
    const s = allSections.value.find((x) => x.id === sid)
    if (s) form.step_name = s.name
  }
}

const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  mo_id: null,
  step_seq: 1,
  step_name: '',
  process_section_id: null,
  equipment_id: null,
  assigned_operator_id: null,
  dispatch_qty: 1,
})
const formRules = {
  mo_id: [{ required: true, message: '请选择生产订单', trigger: 'change' }],
  step_seq: [{ required: true, message: '请输入工序序号', trigger: 'blur' }],
  step_name: [{ required: true, message: '请输入工序名称', trigger: 'blur' }],
  dispatch_qty: [
    { required: true, message: '请输入派工数量', trigger: 'blur' },
    { type: 'number', min: 1, message: '派工数量必须大于 0', trigger: 'blur' },
  ],
}
function openDialog() {
  Object.assign(form, {
    mo_id: null,
    step_seq: 1,
    step_name: '',
    process_section_id: null,
    equipment_id: null,
    assigned_operator_id: null,
    dispatch_qty: 1,
  })
  processSections.value = []
  currentRouting.value = null
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    await createDispatch(JSON.parse(JSON.stringify(form)))
    ElMessage.success('已创建')
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onTransition(row, status, label) {
  try {
    await ElMessageBox.confirm(`确认对派工 #${row.id} 执行「${label}」操作吗？`, `${label}确认`, { type: 'warning' })
    await updateDispatch(row.id, { status })
    ElMessage.success(`已${label}`)
    load()
  } catch (e) {}
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除派工 #${row.id}？仅未开工的派工可删除，已开工请走取消流程。`,
      '删除确认',
      { type: 'warning' },
    )
    await deleteDispatch(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

onMounted(async () => {
  await loadRefs()
  await load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.detail-body { padding: 4px 16px 16px; }
.muted { color: #999; }
.hint { color: #999; font-size: 12px; margin-top: 4px; }
:deep(.el-table__row) { cursor: pointer; }
</style>
