<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab" type="border-card">
        <!-- 资产盘点 -->
        <el-tab-pane label="资产盘点" name="inventory">
          <div class="toolbar">
            <el-form :inline="true" :model="invQuery" size="default">
              <el-form-item label="状态">
                <el-select v-model="invQuery.status" placeholder="全部" clearable style="width:140px">
                  <el-option v-for="s in INVENTORY_STATUS_OPTIONS" :key="s" :label="inventoryStatusLabel(s)" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadInventories">查询</el-button>
                <el-button v-if="canWriteInv" type="success" @click="openInvDialog">新建盘点</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="invList" stripe v-loading="invLoading" border size="small">
            <el-table-column prop="inventory_no" label="盘点单号" width="150" />
            <el-table-column prop="name" label="名称" min-width="180" />
            <el-table-column label="计划日期" width="130">
              <template #default="{ row }">{{ formatTime(row.plan_date, 'YYYY-MM-DD') }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }"><el-tag :type="inventoryStatusTag(row.status)" size="small">{{ inventoryStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="盘点进度" width="110">
              <template #default="{ row }">{{ invDoneCount(row) }}</template>
            </el-table-column>
            <el-table-column label="完成时间" width="160">
              <template #default="{ row }">{{ formatTime(row.completed_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openLines(row)">明细</el-button>
                <el-button v-if="canWriteInv" size="small" link type="success" :disabled="row.status === 'COMPLETED'" @click="onCompleteInv(row)">完成盘点</el-button>
                <el-button v-if="canDelete" size="small" link type="danger" @click="onDeleteInv(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 调拨/报废申请 -->
        <el-tab-pane label="调拨报废申请" name="applications">
          <div class="toolbar">
            <el-form :inline="true" :model="appQuery" size="default">
              <el-form-item label="类型">
                <el-select v-model="appQuery.type" placeholder="全部" clearable style="width:140px">
                  <el-option v-for="t in APPLICATION_TYPE_OPTIONS" :key="t" :label="applicationTypeLabel(t)" :value="t" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="appQuery.status" placeholder="全部" clearable style="width:140px">
                  <el-option v-for="s in APP_STATUS_OPTIONS" :key="s" :label="applicationStatusLabel(s)" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadApplications">查询</el-button>
                <el-button v-if="canWriteApp" type="success" @click="openAppDialog">新建申请</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="appList" stripe v-loading="appLoading" border size="small">
            <el-table-column prop="application_no" label="申请单号" width="150" />
            <el-table-column label="类型" width="80">
              <template #default="{ row }"><el-tag :type="applicationTypeTag(row.type)" size="small">{{ applicationTypeLabel(row.type) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="设备" width="150">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column prop="from_location" label="原位置" width="130" />
            <el-table-column prop="to_location" label="目标位置" width="130" />
            <el-table-column prop="reason" label="原因" min-width="180" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }"><el-tag :type="applicationStatusTag(row.status)" size="small">{{ applicationStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="申请时间" width="160">
              <template #default="{ row }">{{ formatTime(row.applied_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canApprove" size="small" link type="warning" :disabled="row.status !== 'PENDING'" @click="openApproveDialog(row)">审批</el-button>
                <el-button v-if="canCompleteApp" size="small" link type="success" :disabled="row.status !== 'APPROVED'" @click="onCompleteApp(row)">完成</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建盘点 -->
    <el-dialog v-model="invDialogVisible" title="新建盘点" width="600px">
      <el-form :model="invForm" :rules="invFormRules" ref="invFormRef" label-width="100px">
        <el-form-item label="盘点名称" prop="name"><el-input v-model="invForm.name" /></el-form-item>
        <el-form-item label="计划日期" prop="plan_date">
          <el-date-picker v-model="invForm.plan_date" type="date" value-format="YYYY-MM-DDT00:00:00" style="width:100%" />
        </el-form-item>
        <el-form-item label="盘点设备">
          <el-select v-model="invForm.equipment_ids" multiple filterable placeholder="留空则包含全部在用设备" style="width:100%">
            <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="invForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="invDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="invSaving" @click="onInvSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 盘点明细 -->
    <el-dialog v-model="linesDialogVisible" :title="`盘点明细 - ${currentInv?.inventory_no || ''}`" width="95%">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom:10px">
        勾选"是否找到"与"位置一致"后保存，系统自动判定账实结果
      </el-alert>
      <el-table :data="currentInv?.lines || []" stripe border size="small">
        <el-table-column label="设备" width="160">
          <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column prop="system_status" label="台账状态" width="120" />
        <el-table-column label="是否找到" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.actual_found" :disabled="currentInv?.status === 'COMPLETED' || !canUpdateLine" />
          </template>
        </el-table-column>
        <el-table-column label="位置一致" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.location_match" :disabled="currentInv?.status === 'COMPLETED' || !canUpdateLine" />
          </template>
        </el-table-column>
        <el-table-column label="结果" width="110">
          <template #default="{ row }"><el-tag :type="invLineResultTag(row.result)" size="small">{{ invLineResultLabel(row.result) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="盘点时间" width="160">
          <template #default="{ row }">{{ formatTime(row.checked_at) }}</template>
        </el-table-column>
        <el-table-column label="备注" width="160">
          <template #default="{ row }"><el-input v-model="row.remark" :disabled="currentInv?.status === 'COMPLETED' || !canUpdateLine" size="small" /></template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdateLine" size="small" link type="primary" :disabled="currentInv?.status === 'COMPLETED'" @click="saveLine(row)">保存</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="linesDialogVisible=false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新建申请 -->
    <el-dialog v-model="appDialogVisible" title="新建申请" width="640px">
      <el-form :model="appForm" :rules="appFormRules" ref="appFormRef" label-width="100px">
        <el-form-item label="类型" prop="type">
          <el-select v-model="appForm.type" style="width:100%">
            <el-option v-for="t in APPLICATION_TYPE_OPTIONS" :key="t" :label="applicationTypeLabel(t)" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备" prop="equipment_id">
          <el-select v-model="appForm.equipment_id" filterable placeholder="选择设备" style="width:100%">
            <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="appForm.type === 'TRANSFER'" label="目标位置" prop="to_location">
          <el-input v-model="appForm.to_location" placeholder="厂区/区域，例如 Fab1/清洗区" />
        </el-form-item>
        <el-form-item label="原因" prop="reason"><el-input v-model="appForm.reason" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="appForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="appDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="appSaving" @click="onAppSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 审批 -->
    <el-dialog v-model="approveDialogVisible" :title="`审批申请 - ${approveTarget?.application_no || ''}`" width="480px">
      <el-form :model="approveForm" :rules="approveRules" ref="approveFormRef" label-width="80px">
        <el-form-item label="审批结果" prop="decision">
          <el-radio-group v-model="approveForm.decision">
            <el-radio value="APPROVED">批准</el-radio>
            <el-radio value="REJECTED">驳回</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="approveForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="approveSaving" @click="onApprove">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listInventories, getInventory, createInventory, updateInventoryLine,
  completeInventory, deleteInventory,
  listApplications, createApplication, approveApplication, completeApplication,
} from '@/api/asset'
import { listEquipments } from '@/api/equipment'
import { useUserStore } from '@/stores'
import {
  formatTime,
  INVENTORY_STATUS_OPTIONS, inventoryStatusLabel, inventoryStatusTag,
  invLineResultLabel, invLineResultTag,
  APPLICATION_TYPE_OPTIONS, applicationTypeLabel, applicationTypeTag,
  applicationStatusLabel, applicationStatusTag,
} from '@/utils'

const userStore = useUserStore()
const canWriteInv = computed(() => userStore.can('asset.inventory_write'))
const canUpdateLine = computed(() => userStore.can('asset.inventory_line_update'))
const canWriteApp = computed(() => userStore.can('asset.application_create'))
const canCompleteApp = computed(() => userStore.can('asset.application_complete'))
const canApprove = computed(() => userStore.can('asset.application_approve'))
const canDelete = computed(() => userStore.can('asset.inventory_delete'))

const APP_STATUS_OPTIONS = ['PENDING', 'APPROVED', 'REJECTED', 'COMPLETED']

const tab = ref('inventory')
const equipments = ref([])

function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}

async function loadEquipments() {
  equipments.value = await listEquipments({ limit: 500 })
}

// ---- 资产盘点 ----
const invQuery = reactive({ status: null })
const invList = ref([])
const invLoading = ref(false)
async function loadInventories() {
  invLoading.value = true
  try {
    const params = {}
    if (invQuery.status) params.status = invQuery.status
    invList.value = await listInventories(params)
  } finally {
    invLoading.value = false
  }
}

function invDoneCount(row) {
  const lines = row.lines || []
  return `${lines.filter((l) => l.result !== 'PENDING').length}/${lines.length}`
}

const invDialogVisible = ref(false)
const invSaving = ref(false)
const invFormRef = ref(null)
const invForm = reactive({ name: '', plan_date: null, remark: '', equipment_ids: [] })
const invFormRules = {
  name: [{ required: true, message: '请输入盘点名称', trigger: 'blur' }],
}
function openInvDialog() {
  Object.assign(invForm, { name: '', plan_date: null, remark: '', equipment_ids: [] })
  invDialogVisible.value = true
}
async function onInvSave() {
  try {
    await invFormRef.value.validate()
    invSaving.value = true
    const payload = { name: invForm.name, plan_date: invForm.plan_date, remark: invForm.remark }
    if (invForm.equipment_ids && invForm.equipment_ids.length) payload.equipment_ids = invForm.equipment_ids
    await createInventory(payload)
    ElMessage.success('已创建')
    invDialogVisible.value = false
    loadInventories()
  } catch (e) {} finally {
    invSaving.value = false
  }
}

const linesDialogVisible = ref(false)
const currentInv = ref(null)
async function openLines(row) {
  linesDialogVisible.value = true
  currentInv.value = await getInventory(row.id)
}
async function saveLine(line) {
  try {
    await updateInventoryLine(currentInv.value.id, line.id, {
      actual_found: line.actual_found,
      location_match: line.location_match,
      remark: line.remark,
    })
    ElMessage.success('已保存')
    currentInv.value = await getInventory(currentInv.value.id)
  } catch (e) {}
}

async function onCompleteInv(row) {
  try {
    await ElMessageBox.confirm(`确认完成盘点【${row.inventory_no}】？完成后将无法修改明细`, '提示', { type: 'warning' })
    await completeInventory(row.id)
    ElMessage.success('已完成')
    loadInventories()
  } catch (e) {}
}

async function onDeleteInv(row) {
  try {
    await ElMessageBox.confirm(`确认删除盘点【${row.inventory_no}】？`, '危险操作', { type: 'error' })
    await deleteInventory(row.id)
    ElMessage.success('已删除')
    loadInventories()
  } catch (e) {}
}

// ---- 调拨/报废申请 ----
const appQuery = reactive({ type: null, status: null })
const appList = ref([])
const appLoading = ref(false)
async function loadApplications() {
  appLoading.value = true
  try {
    const params = {}
    if (appQuery.type) params.type = appQuery.type
    if (appQuery.status) params.status = appQuery.status
    appList.value = await listApplications(params)
  } finally {
    appLoading.value = false
  }
}

const appDialogVisible = ref(false)
const appSaving = ref(false)
const appFormRef = ref(null)
const appForm = reactive({ type: 'TRANSFER', equipment_id: null, to_location: '', reason: '', remark: '' })
const appFormRules = computed(() => ({
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  to_location: appForm.type === 'TRANSFER' ? [{ required: true, message: '请输入目标位置', trigger: 'blur' }] : [],
  reason: [{ required: true, message: '请输入申请原因', trigger: 'blur' }],
}))
function openAppDialog() {
  Object.assign(appForm, { type: 'TRANSFER', equipment_id: null, to_location: '', reason: '', remark: '' })
  appDialogVisible.value = true
}
async function onAppSave() {
  try {
    await appFormRef.value.validate()
    appSaving.value = true
    const payload = {
      type: appForm.type,
      equipment_id: appForm.equipment_id,
      reason: appForm.reason,
      remark: appForm.remark,
    }
    if (appForm.type === 'TRANSFER') payload.to_location = appForm.to_location
    await createApplication(payload)
    ElMessage.success('已创建')
    appDialogVisible.value = false
    loadApplications()
  } catch (e) {} finally {
    appSaving.value = false
  }
}

const approveDialogVisible = ref(false)
const approveSaving = ref(false)
const approveFormRef = ref(null)
const approveTarget = ref(null)
const approveForm = reactive({ decision: 'APPROVED', remark: '' })
const approveRules = {
  decision: [{ required: true, message: '请选择审批结果', trigger: 'change' }],
}
function openApproveDialog(row) {
  approveTarget.value = row
  Object.assign(approveForm, { decision: 'APPROVED', remark: '' })
  approveDialogVisible.value = true
}
async function onApprove() {
  try {
    await approveFormRef.value.validate()
    approveSaving.value = true
    await approveApplication(approveTarget.value.id, { decision: approveForm.decision, remark: approveForm.remark })
    ElMessage.success('已审批')
    approveDialogVisible.value = false
    loadApplications()
  } catch (e) {} finally {
    approveSaving.value = false
  }
}

async function onCompleteApp(row) {
  try {
    await ElMessageBox.confirm(`确认完成申请【${row.application_no}】？`, '提示', { type: 'warning' })
    await completeApplication(row.id)
    ElMessage.success('已完成')
    loadApplications()
  } catch (e) {}
}

watch(tab, (val) => {
  if (val === 'inventory') loadInventories()
  else if (val === 'applications') loadApplications()
})

onMounted(async () => {
  await loadEquipments()
  await loadInventories()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
</style>
