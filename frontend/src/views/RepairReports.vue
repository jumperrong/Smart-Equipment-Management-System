<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="设备">
            <el-select v-model="query.equipment_id" filterable placeholder="选择设备" clearable style="width:200px">
              <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:120px">
              <el-option label="待处理" value="OPEN" />
              <el-option label="已转单" value="CONVERTED" />
              <el-option label="已关闭" value="CLOSED" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button type="success" @click="openDialog">发起报修</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="紧急度" width="90">
          <template #default="{ row }"><el-tag :type="urgencyTag(row.urgency)" size="small">{{ urgencyLabel(row.urgency) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="设备" width="140">
          <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column prop="phenomenon" label="故障现象" min-width="220" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><el-tag :type="reportStatusTag(row.status)" size="small">{{ reportStatusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="报修时间" width="160">
          <template #default="{ row }">{{ formatTime(row.reported_at) }}</template>
        </el-table-column>
        <el-table-column label="工单" width="80">
          <template #default="{ row }">
            <el-button v-if="row.work_order_id" size="small" link type="primary" @click="$router.push({ name: 'WorkOrderDetail', params: { id: row.work_order_id } })">#{{ row.work_order_id }}</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'OPEN' && canWrite" size="small" link type="primary" @click="onConvert(row)">转工单</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 发起报修 -->
    <el-dialog v-model="dialogVisible" title="发起报修" width="520px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px">
        <el-form-item label="设备" prop="equipment_id">
          <el-select v-model="form.equipment_id" filterable placeholder="选择设备" style="width:100%">
            <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="紧急度" prop="urgency">
          <el-radio-group v-model="form.urgency">
            <el-radio-button v-for="u in URGENCY_OPTIONS" :key="u" :value="u">{{ urgencyLabel(u) }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="故障现象" prop="phenomenon">
          <el-input v-model="form.phenomenon" type="textarea" :rows="3" placeholder="描述故障现象、发生时间、是否影响生产等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">提交报修</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listReports, createReport, convertReport } from '@/api/work_order'
import { listEquipments } from '@/api/equipment'
import { useUserStore } from '@/stores'
import { URGENCY_OPTIONS, urgencyLabel, urgencyTag, reportStatusLabel, reportStatusTag, formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('repair_report.convert'))

const query = reactive({ equipment_id: null, status: null })
const list = ref([])
const loading = ref(false)
const equipments = ref([])

function eqName(id) {
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}

async function loadEquipments() {
  equipments.value = await listEquipments({ limit: 500 })
}
async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.equipment_id) params.equipment_id = query.equipment_id
    if (query.status) params.status = query.status
    list.value = await listReports(params)
  } finally {
    loading.value = false
  }
}

// 发起报修
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({ equipment_id: null, phenomenon: '', urgency: 'NORMAL' })
const formRules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  phenomenon: [{ required: true, message: '请描述故障现象', trigger: 'blur' }],
}
function openDialog() {
  Object.assign(form, { equipment_id: null, phenomenon: '', urgency: 'NORMAL' })
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    await createReport({ ...form })
    ElMessage.success('报修已提交')
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}

// 转工单
async function onConvert(row) {
  try {
    await ElMessageBox.confirm(`确认将报修单 #${row.id} 转为维修工单？`, '提示', { type: 'warning' })
    const wo = await convertReport(row.id)
    ElMessage.success(`已转单：${wo.order_no}`)
    load()
  } catch (e) {}
}

onMounted(async () => {
  await loadEquipments()
  await load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
</style>
