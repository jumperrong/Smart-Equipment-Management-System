<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" class="mb-12">
      <template #content>
        <span class="ph-title">{{ eq.name || '设备档案' }}</span>
        <el-tag v-if="eq.current_status" :type="statusType(eq.current_status)" effect="dark" size="small" style="margin-left:8px">
          {{ statusLabel(eq.current_status) }}
        </el-tag>
        <span class="ph-sub">资产编号: {{ eq.asset_no || '-' }} · 机型: {{ eq.model || '-' }}</span>
      </template>
      <template #extra>
        <el-button
          v-if="canChangeStatus"
          :type="eq.current_status === 'DOWN' ? 'danger' : 'warning'"
          size="small"
          @click="openStatusDialog"
        >切换状态</el-button>
      </template>
    </el-page-header>

    <el-tabs v-model="tab" type="border-card">
      <!-- 档案信息 -->
      <el-tab-pane label="档案信息" name="profile">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="设备名称">{{ eq.name }}</el-descriptions-item>
          <el-descriptions-item label="资产编号">{{ eq.asset_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="厂区">{{ eq.factory || '-' }}</el-descriptions-item>
          <el-descriptions-item label="区域">{{ eq.area || '-' }}</el-descriptions-item>
          <el-descriptions-item label="机型">{{ eq.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="供应商">{{ eq.vendor || '-' }}</el-descriptions-item>
          <el-descriptions-item label="序列号">{{ eq.serial_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="理论节拍(秒)">{{ eq.theoretical_cycle || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(eq.current_status)" effect="dark" size="small">{{ statusLabel(eq.current_status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="描述" :span="3">{{ eq.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(eq.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(eq.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <!-- 附件 -->
      <el-tab-pane label="附件档案" name="attachments">
        <div class="tab-toolbar">
          <el-upload
            v-if="canWrite"
            :show-file-list="false"
            :before-upload="onUpload"
            action=""
            :auto-upload="false"
          >
            <el-button type="primary" :loading="uploading">上传附件</el-button>
          </el-upload>
          <el-select v-model="uploadMeta.category" placeholder="分类" size="small" style="width:140px;margin-left:10px">
            <el-option label="SOP/操作规程" value="SOP" />
            <el-option label="技术说明书" value="MANUAL" />
            <el-option label="图纸" value="DRAWING" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </div>
        <el-table :data="attachments" stripe size="small" border>
          <el-table-column prop="filename" label="文件名" min-width="200" />
          <el-table-column prop="category" label="分类" width="120">
            <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
          </el-table-column>
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="160" />
          <el-table-column label="上传时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="downloadAtt(row)">下载</el-button>
              <el-button v-if="canWrite" size="small" link type="danger" @click="delAtt(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 易损件清单 -->
      <el-tab-pane label="易损件清单" name="spareParts">
        <div class="tab-toolbar">
          <el-button v-if="canWrite" type="primary" size="small" @click="openAddSpareDialog">关联易损件</el-button>
        </div>
        <el-table :data="eqSpareParts" stripe size="small" border>
          <el-table-column label="备件编号" min-width="120">
            <template #default="{ row }">{{ row.spare_part?.sku }}</template>
          </el-table-column>
          <el-table-column label="名称" min-width="140">
            <template #default="{ row }">{{ row.spare_part?.name }}</template>
          </el-table-column>
          <el-table-column label="规格" min-width="120">
            <template #default="{ row }">{{ row.spare_part?.spec || '-' }}</template>
          </el-table-column>
          <el-table-column label="当前库存" width="100">
            <template #default="{ row }">
              <span :class="{ 'low-stock': (row.spare_part?.current_stock ?? 0) <= (row.spare_part?.safety_stock ?? 0) }">
                {{ row.spare_part?.current_stock }} {{ row.spare_part?.unit }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="qty_per" label="单台用量" width="90" />
          <el-table-column prop="remark" label="备注" min-width="120" />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button v-if="canWrite" size="small" link type="danger" @click="removeSpare(row)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 状态历史 -->
      <el-tab-pane label="状态历史" name="statusLogs">
        <el-table :data="statusLogs" stripe size="small" border>
          <el-table-column label="目标状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusType(row.to_status)" size="small">{{ statusLabel(row.to_status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="前一状态" width="120">
            <template #default="{ row }">{{ row.from_status ? statusLabel(row.from_status) : '-' }}</template>
          </el-table-column>
          <el-table-column prop="reason_code" label="原因码" width="110" />
          <el-table-column prop="reason_detail" label="详细原因" min-width="160" />
          <el-table-column label="开始时间" width="160">
            <template #default="{ row }">{{ formatTime(row.start_time) }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="160">
            <template #default="{ row }">{{ row.end_time ? formatTime(row.end_time) : '进行中' }}</template>
          </el-table-column>
          <el-table-column label="持续时长" width="120">
            <template #default="{ row }">{{ formatDuration(row.duration_minutes) }}</template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="120" />
        </el-table>
      </el-tab-pane>

      <!-- 工单 -->
      <el-tab-pane :label="`工单 (${workOrders.length})`" name="workOrders">
        <el-table :data="workOrders" stripe size="small" border>
          <el-table-column prop="order_no" label="工单号" width="150" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }"><el-tag :type="woTypeTag(row.type)" size="small">{{ woTypeLabel(row.type) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="紧急度" width="100" align="center">
            <template #default="{ row }"><el-tag :type="urgencyTag(row.urgency)" effect="light" size="small">{{ urgencyLabel(row.urgency) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><el-tag :type="woStatusTag(row.status)" size="small">{{ woStatusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="180" />
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="$router.push({ name: 'WorkOrderDetail', params: { id: row.id } })">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 关联易损件对话框 -->
    <el-dialog v-model="spareDialogVisible" title="关联易损件" width="520px">
      <el-form :model="spareForm" label-width="100px" size="default">
        <el-form-item label="选择备件" required>
          <el-select v-model="spareForm.spare_part_id" filterable placeholder="搜索备件编号/名称" style="width:100%" @visible-change="onSpareSelectOpen">
            <el-option v-for="p in partOptions" :key="p.id" :label="`${p.sku} - ${p.name}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="单台用量">
          <el-input-number v-model="spareForm.qty_per" :min="1" :max="999" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="spareForm.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="spareDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="spareSaving" @click="onAddSpare">确定</el-button>
      </template>
    </el-dialog>

    <!-- 状态切换 -->
    <el-dialog v-model="statusDialogVisible" :title="`切换状态：${eq.name || ''}`" width="560px">
      <el-form :model="statusForm" :rules="statusRules" ref="statusFormRef" label-width="90px">
        <el-form-item label="目标状态" prop="to_status">
          <el-select v-model="statusForm.to_status" style="width:100%">
            <el-option v-for="s in statusOptions" :key="s" :label="statusLabel(s)" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="原因码">
          <el-select v-model="statusForm.reason_code" filterable allow-create default-first-option placeholder="选择或输入" style="width:100%">
            <el-option label="生产PRODUCTION" value="PRODUCTION" />
            <el-option label="故障FAULT" value="FAULT" />
            <el-option label="换型SETUP" value="SETUP" />
            <el-option label="待料STARVATION" value="STARVATION" />
            <el-option label="预防性维护PM" value="PM" />
            <el-option label="工程调试ENG" value="ENG" />
            <el-option label="工艺验证VALIDATION" value="VALIDATION" />
            <el-option label="其他OTHER" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item
          label="详细原因"
          prop="reason_detail"
          :required="statusForm.to_status === 'OTHER'"
        >
          <el-input
            v-model="statusForm.reason_detail"
            type="textarea"
            :rows="2"
            :placeholder="statusForm.to_status === 'OTHER' ? '必填：请说明具体状态/原因' : ''"
          />
        </el-form-item>

        <!-- 切 DOWN 时必填：故障现象 + 紧急度，自动派 REPAIR 工单 -->
        <template v-if="statusForm.to_status === 'DOWN'">
          <el-form-item label="紧急度" prop="urgency" required>
            <el-radio-group v-model="statusForm.urgency">
              <el-radio-button label="LOW">低</el-radio-button>
              <el-radio-button label="NORMAL">普通</el-radio-button>
              <el-radio-button label="HIGH">高</el-radio-button>
              <el-radio-button label="CRITICAL">紧急</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="故障现象" prop="fault_phenomenon" required>
            <el-input
              v-model="statusForm.fault_phenomenon"
              type="textarea"
              :rows="3"
              placeholder="必填：请详细描述故障现象（如异响、报警代码、无法启动等），提交后将自动派发故障维修工单"
              maxlength="500"
              show-word-limit
            />
          </el-form-item>
          <div style="margin:-6px 0 10px 90px;color:#909399;font-size:12px;">
            ⚠ 切换为 DOWN 后，系统将自动创建 1 条【故障维修】工单并关联本次状态记录。
          </div>
        </template>

        <el-form-item label="备注">
          <el-input v-model="statusForm.remark" type="textarea" :rows="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="statusSaving" @click="onSaveStatus">确认切换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getEquipment, listStatusLogs, changeStatus,
} from '@/api/equipment'
import {
  listAttachments, uploadAttachment, deleteAttachment, downloadAttachmentUrl,
} from '@/api/attachment'
import {
  listEquipmentSpareParts, addEquipmentSparePart, removeEquipmentSparePart,
  listSpareParts,
} from '@/api/spare_part'
import { listWorkOrders } from '@/api/work_order'
import { useUserStore } from '@/stores'
import {
  statusLabel, statusType, woTypeLabel, woTypeTag, woStatusLabel, woStatusTag,
  urgencyLabel, urgencyTag,
  formatTime, formatDuration,
} from '@/utils'
import { STATUS_OPTIONS } from '@/utils'

const route = useRoute()
const userStore = useUserStore()
const canWrite = computed(() => userStore.can('equipment.write'))
const canChangeStatus = computed(() => userStore.can('equipment.change_status'))
const eqId = Number(route.params.id)
const statusOptions = STATUS_OPTIONS

const loading = ref(false)
const tab = ref('profile')
const eq = ref({})
const attachments = ref([])
const eqSpareParts = ref([])
const statusLogs = ref([])
const workOrders = ref([])

async function loadProfile() {
  eq.value = await getEquipment(eqId)
}
async function loadAttachments() {
  attachments.value = await listAttachments(eqId)
}
async function loadEqSpareParts() {
  eqSpareParts.value = await listEquipmentSpareParts(eqId)
}
async function loadStatusLogs() {
  statusLogs.value = await listStatusLogs(eqId)
}
async function loadWorkOrders() {
  workOrders.value = await listWorkOrders({ equipment_id: eqId })
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([
      loadProfile(), loadAttachments(), loadEqSpareParts(), loadStatusLogs(), loadWorkOrders(),
    ])
  } finally {
    loading.value = false
  }
}

// ---- 状态切换 ----
const statusDialogVisible = ref(false)
const statusSaving = ref(false)
const statusFormRef = ref(null)
const statusForm = reactive({
  to_status: '', reason_code: '', reason_detail: '', remark: '',
  urgency: 'NORMAL', fault_phenomenon: '',
})
const statusRules = computed(() => ({
  to_status: [{ required: true, message: '请选择目标状态', trigger: 'change' }],
  reason_detail:
    statusForm.to_status === 'OTHER'
      ? [{ required: true, message: '切换到"其他"状态时必须填写详细原因', trigger: 'blur' }]
      : [],
  urgency:
    statusForm.to_status === 'DOWN'
      ? [{ required: true, message: '请选择紧急度', trigger: 'change' }]
      : [],
  fault_phenomenon:
    statusForm.to_status === 'DOWN'
      ? [
          { required: true, message: '请描述故障现象', trigger: 'blur' },
          { min: 2, message: '至少 2 个字符', trigger: 'blur' },
        ]
      : [],
}))
function openStatusDialog() {
  Object.assign(statusForm, {
    to_status: eq.value.current_status === 'RUN' ? 'IDLE' : 'RUN',
    reason_code: '', reason_detail: '', remark: '',
    urgency: 'NORMAL', fault_phenomenon: '',
  })
  statusDialogVisible.value = true
}
async function onSaveStatus() {
  try {
    await statusFormRef.value.validate()
    statusSaving.value = true
    await changeStatus(eqId, { ...statusForm })
    ElMessage.success(`已切换到 ${statusLabel(statusForm.to_status)}`)
    statusDialogVisible.value = false
    await loadAll()
  } catch (e) {} finally {
    statusSaving.value = false
  }
}

// ---- 附件 ----
const uploading = ref(false)
const uploadMeta = reactive({ category: '', description: '' })

async function onUpload(file) {
  if (!file) return false
  uploading.value = true
  try {
    await uploadAttachment(eqId, file, { category: uploadMeta.category || undefined })
    ElMessage.success('上传成功')
    await loadAttachments()
  } catch (e) {
    // handled by interceptor
  } finally {
    uploading.value = false
  }
  return false
}

function downloadAtt(row) {
  const url = downloadAttachmentUrl(eqId, row.id)
  const token = localStorage.getItem('token')
  // 通过 fetch 携带 token 下载
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then((r) => r.blob())
    .then((b) => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b)
      a.download = row.filename
      a.click()
      URL.revokeObjectURL(a.href)
    })
    .catch(() => ElMessage.error('下载失败'))
}

async function delAtt(row) {
  try {
    await ElMessageBox.confirm(`确认删除附件【${row.filename}】？`, '提示', { type: 'warning' })
    await deleteAttachment(eqId, row.id)
    ElMessage.success('已删除')
    await loadAttachments()
  } catch (e) {}
}

function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}
function categoryLabel(c) {
  return ({ SOP: 'SOP/规程', MANUAL: '说明书', DRAWING: '图纸', OTHER: '其他' }[c]) || (c || '-')
}

// ---- 易损件 ----
const spareDialogVisible = ref(false)
const spareSaving = ref(false)
const partOptions = ref([])
const spareForm = reactive({ spare_part_id: null, qty_per: 1, remark: '' })

async function onSpareSelectOpen(visible) {
  if (visible && !partOptions.value.length) {
    partOptions.value = await listSpareParts({ limit: 200 })
  }
}
function openAddSpareDialog() {
  Object.assign(spareForm, { spare_part_id: null, qty_per: 1, remark: '' })
  spareDialogVisible.value = true
}
async function onAddSpare() {
  if (!spareForm.spare_part_id) {
    ElMessage.warning('请选择备件')
    return
  }
  spareSaving.value = true
  try {
    await addEquipmentSparePart(eqId, { ...spareForm })
    ElMessage.success('已关联')
    spareDialogVisible.value = false
    await loadEqSpareParts()
  } catch (e) {} finally {
    spareSaving.value = false
  }
}
async function removeSpare(row) {
  try {
    await ElMessageBox.confirm(`确认移除易损件【${row.spare_part?.name}】？`, '提示', { type: 'warning' })
    await removeEquipmentSparePart(eqId, row.spare_part_id)
    ElMessage.success('已移除')
    await loadEqSpareParts()
  } catch (e) {}
}

onMounted(loadAll)
</script>

<style scoped>
.mb-12 { margin-bottom: 12px; }
.ph-title { font-weight: 600; font-size: 16px; margin-right: 8px; }
.ph-sub { color: #909399; font-size: 13px; margin-left: 12px; }
.tab-toolbar { margin-bottom: 10px; display: flex; align-items: center; }
.low-stock { color: #f56c6c; font-weight: 600; }
.status-tag-btn { cursor: pointer; transition: opacity .2s, transform .15s; }
.status-tag-btn:hover { opacity: .85; transform: scale(1.05); }
</style>
