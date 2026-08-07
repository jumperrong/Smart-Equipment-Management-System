<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="关键字">
            <el-input v-model="query.keyword" placeholder="设备名称/资产编号" clearable style="width:200px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item label="厂区">
            <el-input v-model="query.factory" placeholder="例如 FAB1" clearable style="width:140px" />
          </el-form-item>
          <el-form-item label="区域">
            <el-input v-model="query.area" placeholder="例如 PHOTO" clearable style="width:140px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:140px">
              <el-option v-for="s in statusOptions" :key="s" :label="statusLabel(s)" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增设备</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="设备名称" min-width="120">
          <template #default="{ row }">
            <b>{{ row.name }}</b>
          </template>
        </el-table-column>
        <el-table-column prop="asset_no" label="资产编号" width="120" />
        <el-table-column prop="factory" label="厂区" width="90" />
        <el-table-column prop="area" label="区域" width="90" />
        <el-table-column prop="model" label="机型" width="120" />
        <el-table-column prop="vendor" label="供应商" width="110" />
        <el-table-column label="当前状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.current_status)" effect="dark" size="small">{{ statusLabel(row.current_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="goDetail(row)">档案</el-button>
            <el-button size="small" link type="primary" @click="openStatusDialog(row)">切换状态</el-button>
            <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑设备' : '新增设备'" width="680px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备名称" prop="name"><el-input v-model="form.name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产编号" prop="asset_no"><el-input v-model="form.asset_no" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="厂区"><el-input v-model="form.factory" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="区域"><el-input v-model="form.area" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机型"><el-input v-model="form.model" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商"><el-input v-model="form.vendor" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="序列号"><el-input v-model="form.serial_no" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="理论节拍(秒)">
              <el-input-number v-model="form.theoretical_cycle" :min="0" :precision="2" :step="1" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="初始状态">
              <el-select v-model="form.current_status" style="width:100%">
                <el-option v-for="s in statusOptions" :key="s" :label="statusLabel(s)" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 状态切换 -->
    <el-dialog v-model="statusDialogVisible" :title="`切换状态：${targetEquipment?.name || ''}`" width="520px">
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
        <el-form-item label="备注">
          <el-input v-model="statusForm.remark" type="textarea" :rows="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveStatus">确认切换</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listEquipments,
  createEquipment,
  updateEquipment,
  deleteEquipment,
  changeStatus,
} from '@/api/equipment'
import { useUserStore } from '@/stores'
import { STATUS_OPTIONS, statusLabel, statusType, requiresDetail } from '@/utils'

const userStore = useUserStore()
const router = useRouter()
const canWrite = computed(() => userStore.can('equipment.write'))
const canDelete = computed(() => userStore.can('equipment.delete'))

function goDetail(row) {
  router.push({ name: 'EquipmentDetail', params: { id: row.id } })
}

const statusOptions = STATUS_OPTIONS

const query = reactive({ keyword: '', factory: '', area: '', status: null })
const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const q = { ...query }
    if (!q.keyword) delete q.keyword
    if (!q.factory) delete q.factory
    if (!q.area) delete q.area
    if (!q.status) delete q.status
    list.value = await listEquipments(q)
  } finally {
    loading.value = false
  }
}
function resetQuery() {
  Object.assign(query, { keyword: '', factory: '', area: '', status: null })
  load()
}

// ---- 新增/编辑 ----
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, name: '', asset_no: '', factory: '', area: '', model: '', vendor: '',
  serial_no: '', theoretical_cycle: null, current_status: 'OFFLINE', description: '', spec: {}, is_active: true,
})
const formRules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
}

function openDialog(row = null) {
  Object.assign(form, {
    id: null, name: '', asset_no: '', factory: '', area: '', model: '', vendor: '',
    serial_no: '', theoretical_cycle: null, current_status: 'OFFLINE', description: '', spec: {}, is_active: true,
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
      delete payload.id
      delete payload.current_status // current_status 只能通过状态机 API 切换
      await updateEquipment(form.id, payload)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createEquipment(payload)
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
    await ElMessageBox.confirm(`确认删除设备【${row.name}】？`, '危险操作', { type: 'error' })
    await deleteEquipment(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

// ---- 状态切换 ----
const statusDialogVisible = ref(false)
const targetEquipment = ref(null)
const statusFormRef = ref(null)
const statusForm = reactive({ to_status: '', reason_code: '', reason_detail: '', remark: '' })
const statusRules = computed(() => ({
  to_status: [{ required: true, message: '请选择目标状态', trigger: 'change' }],
  reason_detail:
    statusForm.to_status === 'OTHER'
      ? [{ required: true, message: '切换到"其他"状态时必须填写详细原因', trigger: 'blur' }]
      : [],
}))
function openStatusDialog(row) {
  targetEquipment.value = row
  Object.assign(statusForm, {
    to_status: row.current_status === 'RUN' ? 'IDLE' : 'RUN',
    reason_code: '', reason_detail: '', remark: '',
  })
  statusDialogVisible.value = true
}
async function onSaveStatus() {
  try {
    await statusFormRef.value.validate()
    saving.value = true
    await changeStatus(targetEquipment.value.id, { ...statusForm })
    ElMessage.success(`已切换到 ${statusLabel(statusForm.to_status)}`)
    statusDialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
</style>
