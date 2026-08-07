<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="类型">
            <el-select v-model="query.type" placeholder="全部" clearable style="width:140px">
              <el-option v-for="t in WORK_ORDER_TYPE_OPTIONS" :key="t" :label="woTypeLabel(t)" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:140px">
              <el-option v-for="s in WORK_ORDER_STATUS_OPTIONS" :key="s" :label="woStatusLabel(s)" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="设备">
            <el-select v-model="query.equipment_id" filterable placeholder="选择设备" clearable style="width:200px">
              <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新建工单</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="order_no" label="工单号" width="150" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }"><el-tag :type="woTypeTag(row.type)" size="small">{{ woTypeLabel(row.type) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="woStatusTag(row.status)" size="small">{{ woStatusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column label="设备" width="120">
          <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column label="故障分类" width="100">
          <template #default="{ row }">{{ row.fault_category ? faultCategoryLabel(row.fault_category) : '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="$router.push({ name: 'WorkOrderDetail', params: { id: row.id } })">详情</el-button>
            <el-button v-if="canWrite" size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑工单 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑工单' : '新建工单'" width="640px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类型" prop="type">
              <el-select v-model="form.type" style="width:100%">
                <el-option v-for="t in WORK_ORDER_TYPE_OPTIONS" :key="t" :label="woTypeLabel(t)" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="form.equipment_id" filterable placeholder="选择设备" style="width:100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="标题" prop="title"><el-input v-model="form.title" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划开始"><el-date-picker v-model="form.planned_start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划结束"><el-date-picker v-model="form.planned_end" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
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
import { ElMessage } from 'element-plus'
import { listWorkOrders, createWorkOrder, updateWorkOrder } from '@/api/work_order'
import { listEquipments } from '@/api/equipment'
import { useUserStore } from '@/stores'
import {
  WORK_ORDER_TYPE_OPTIONS, WORK_ORDER_STATUS_OPTIONS,
  woTypeLabel, woTypeTag, woStatusLabel, woStatusTag, faultCategoryLabel, formatTime,
} from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('work_order.write'))

const query = reactive({ type: null, status: null, equipment_id: null })
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
    if (query.type) params.type = query.type
    if (query.status) params.status = query.status
    if (query.equipment_id) params.equipment_id = query.equipment_id
    list.value = await listWorkOrders(params)
  } finally {
    loading.value = false
  }
}

// 新建/编辑
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, type: 'REPAIR', equipment_id: null, title: '', description: '', planned_start: null, planned_end: null, remark: '' })
const formRules = {
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}
function openDialog(row = null) {
  Object.assign(form, { id: null, type: 'REPAIR', equipment_id: null, title: '', description: '', planned_start: null, planned_end: null, remark: '' })
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
      await updateWorkOrder(id, { title: rest.title, description: rest.description, planned_start: rest.planned_start, planned_end: rest.planned_end, remark: rest.remark })
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createWorkOrder(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadEquipments()
  await load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
</style>
