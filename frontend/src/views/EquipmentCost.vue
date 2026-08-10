<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab" type="border-card">
        <!-- ============ 成本记录 ============ -->
        <el-tab-pane label="成本记录" name="records">
          <div class="toolbar">
            <el-form :inline="true" :model="query" size="default">
              <el-form-item label="设备">
                <el-select v-model="query.equipment_id" filterable placeholder="全部设备" clearable style="width: 200px">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="成本类型">
                <el-select v-model="query.cost_type" placeholder="全部" clearable style="width: 150px">
                  <el-option v-for="c in COST_TYPE_OPTIONS" :key="c" :label="costTypeLabel(c)" :value="c" />
                </el-select>
              </el-form-item>
              <el-form-item label="日期范围">
                <el-date-picker
                  v-model="query.range"
                  type="daterange"
                  value-format="YYYY-MM-DD"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  style="width: 300px"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadList">查询</el-button>
                <el-button type="success" @click="openForm()">新建记录</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="list" stripe v-loading="loading" border size="small">
            <el-table-column label="设备" width="150">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column label="成本类型" width="110">
              <template #default="{ row }">
                <el-tag :type="costTypeTag(row.cost_type)" size="small">{{ costTypeLabel(row.cost_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="金额" width="140" align="right">
              <template #default="{ row }"><span class="amount">¥ {{ formatCurrency(row.amount) }}</span></template>
            </el-table-column>
            <el-table-column label="日期" width="120">
              <template #default="{ row }">{{ formatDate(row.cost_date) }}</template>
            </el-table-column>
            <el-table-column prop="description" label="费用说明" min-width="180" show-overflow-tooltip />
            <el-table-column label="关联工单" width="120">
              <template #default="{ row }">{{ row.work_order_id ? '#' + row.work_order_id : '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openForm(row)">编辑</el-button>
                <el-button size="small" link type="danger" @click="onDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ============ LCC 汇总 ============ -->
        <el-tab-pane label="LCC汇总" name="summary">
          <div class="toolbar">
            <el-form :inline="true" size="default">
              <el-form-item label="设备">
                <el-select v-model="summaryEquipmentId" filterable placeholder="请选择设备（必选）" style="width: 260px" @change="loadSummary">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
            </el-form>
          </div>

          <div v-loading="summaryLoading">
            <!-- 按类型汇总 -->
            <el-row :gutter="12" class="stat-row">
              <el-col :span="4" v-for="c in COST_TYPE_OPTIONS" :key="c">
                <el-card shadow="hover" class="stat-card">
                  <div class="stat-value">{{ formatCurrency(summary.by_type[c] || 0) }}</div>
                  <div class="stat-label">{{ costTypeLabel(c) }}</div>
                </el-card>
              </el-col>
            </el-row>
            <el-card shadow="hover" class="total-card">
              <div class="total-label">总成本 (LCC)</div>
              <div class="total-value">¥ {{ formatCurrency(summary.total || 0) }}</div>
            </el-card>

            <!-- 年度趋势 -->
            <div class="section-title">年度趋势</div>
            <el-table :data="summary.yearly" border size="small">
              <el-table-column prop="year" label="年度" width="100" />
              <el-table-column v-for="c in COST_TYPE_OPTIONS" :key="c" :label="costTypeLabel(c)" align="right" min-width="100">
                <template #default="{ row }">{{ formatCurrency(row[c] || 0) }}</template>
              </el-table-column>
              <el-table-column label="合计" align="right" width="150">
                <template #default="{ row }"><span class="amount">¥ {{ formatCurrency(row.total || 0) }}</span></template>
              </el-table-column>
            </el-table>

            <!-- 全设备成本 Top10 -->
            <div class="section-title">全设备成本 Top10</div>
            <el-table :data="topEquipments" v-loading="topLoading" border size="small">
              <el-table-column type="index" label="排名" width="70" align="center" />
              <el-table-column label="设备" min-width="200">
                <template #default="{ row }">{{ row.equipment_name || eqName(row.equipment_id) }}</template>
              </el-table-column>
              <el-table-column label="总成本" align="right" width="170">
                <template #default="{ row }"><span class="amount">¥ {{ formatCurrency(row.total || 0) }}</span></template>
              </el-table-column>
              <el-table-column prop="record_count" label="记录数" width="100" align="center" />
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- ============ 新建/编辑对话框 ============ -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑成本记录' : '新建成本记录'" width="560px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="form.equipment_id" filterable placeholder="选择设备" style="width: 100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成本类型" prop="cost_type">
              <el-select v-model="form.cost_type" style="width: 100%">
                <el-option v-for="c in COST_TYPE_OPTIONS" :key="c" :label="costTypeLabel(c)" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="金额" prop="amount">
              <el-input-number v-model="form.amount" :min="0" :precision="2" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="日期" prop="cost_date">
              <el-date-picker v-model="form.cost_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联工单"><el-input v-model="form.work_order_id" placeholder="可选工单号" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="费用说明"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { listEquipments } from '@/api/equipment'

const base = '/api/v1/equipment-costs'

// ---------- 成本类型 ----------
const COST_TYPE_OPTIONS = ['procurement', 'maintenance', 'spare_part', 'energy', 'depreciation', 'scrap']
function costTypeLabel(c) {
  return ({ procurement: '采购', maintenance: '维护', spare_part: '备件', energy: '能耗', depreciation: '折旧', scrap: '报废' })[c] || c || '-'
}
function costTypeTag(c) {
  return ({ procurement: 'primary', maintenance: 'success', spare_part: 'warning', energy: 'info', depreciation: 'danger', scrap: 'danger' })[c] || 'info'
}

// ---------- 通用 ----------
const equipments = ref([])
function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}
function formatCurrency(n) {
  const num = Number(n)
  if (Number.isNaN(num)) return '0.00'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function formatDate(d) {
  if (!d) return '-'
  return String(d).slice(0, 10)
}

async function loadEquipments() {
  try {
    equipments.value = await listEquipments({ limit: 500 })
  } catch (e) {}
}

// ---------- 成本记录 ----------
const query = reactive({ equipment_id: null, cost_type: '', range: [] })
const list = ref([])
const loading = ref(false)
async function loadList() {
  loading.value = true
  try {
    const params = {}
    if (query.equipment_id) params.equipment_id = query.equipment_id
    if (query.cost_type) params.cost_type = query.cost_type
    if (query.range && query.range.length === 2) {
      params.start = query.range[0]
      params.end = query.range[1]
    }
    list.value = await request.get(`${base}`, { params })
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
}

const FORM_KEYS = ['equipment_id', 'cost_type', 'amount', 'cost_date', 'description', 'work_order_id']
const formVisible = ref(false)
const formRef = ref(null)
const saving = ref(false)
const form = reactive({
  id: null, equipment_id: null, cost_type: 'procurement', amount: 0, cost_date: '', description: '', work_order_id: '',
})
const rules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  cost_type: [{ required: true, message: '请选择成本类型', trigger: 'change' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
  cost_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
}
function resetForm() {
  Object.assign(form, {
    id: null, equipment_id: null, cost_type: 'procurement', amount: 0, cost_date: '', description: '', work_order_id: '',
  })
}
function openForm(row = null) {
  resetForm()
  if (row) {
    FORM_KEYS.forEach((k) => { form[k] = row[k] != null ? row[k] : form[k] })
    form.id = row.id
  }
  formVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = JSON.parse(JSON.stringify(form))
    if (payload.id) {
      const { id, ...rest } = payload
      await request.put(`${base}/${id}`, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await request.post(`${base}`, payload)
      ElMessage.success('已创建')
    }
    formVisible.value = false
    loadList()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该成本记录？', '提示', { type: 'warning' })
    await request.delete(`${base}/${row.id}`)
    ElMessage.success('已删除')
    loadList()
  } catch (e) {}
}

// ---------- LCC 汇总 ----------
const tab = ref('records')
const summaryEquipmentId = ref(null)
const summaryLoading = ref(false)
const summary = reactive({ by_type: {}, total: 0, yearly: [] })
const topEquipments = ref([])
const topLoading = ref(false)

async function loadSummary() {
  if (!summaryEquipmentId.value) {
    Object.assign(summary, { by_type: {}, total: 0, yearly: [] })
    return
  }
  summaryLoading.value = true
  try {
    const d = await request.get(`${base}/summary`, { params: { equipment_id: summaryEquipmentId.value } })
    Object.assign(summary, {
      by_type: (d && d.by_type) || {},
      total: (d && d.total) || 0,
      yearly: (d && d.yearly) || [],
    })
  } catch (e) {
    Object.assign(summary, { by_type: {}, total: 0, yearly: [] })
  } finally {
    summaryLoading.value = false
  }
}

async function loadTop() {
  topLoading.value = true
  try {
    topEquipments.value = await request.get(`${base}/top`, { params: { limit: 10 } })
  } catch (e) {
    topEquipments.value = []
  } finally {
    topLoading.value = false
  }
}

watch(tab, (v) => {
  if (v === 'summary' && !topEquipments.value.length) loadTop()
})

onMounted(async () => {
  await loadEquipments()
  await loadList()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-value { font-size: 20px; font-weight: 600; color: var(--app-text-primary); line-height: 1.4; word-break: break-all; }
.stat-label { font-size: 12px; color: var(--app-text-secondary); margin-top: 4px; }
.total-card { text-align: center; margin-bottom: 16px; background: var(--app-primary-light); border-color: var(--app-primary-light); }
.total-label { font-size: 14px; color: var(--app-text-regular); }
.total-value { font-size: 30px; font-weight: 700; color: var(--app-primary); margin-top: 6px; }
.section-title { font-size: 15px; font-weight: 600; color: var(--app-text-primary); margin: 18px 0 10px; padding-left: 8px; border-left: 3px solid var(--app-primary); }
.amount { color: var(--app-text-primary); font-weight: 600; }
</style>
