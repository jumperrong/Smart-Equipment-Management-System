<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:150px">
              <el-option v-for="s in MO_STATUS_OPTIONS" :key="s" :label="statusLabel(s)" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增订单</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small" @row-click="showMo">
        <el-table-column prop="mo_no" label="MO号" width="170" />
        <el-table-column label="产品" min-width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showProduct(row.product_id)">
              {{ row.product_name || `#${row.product_id}` }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column label="工序路由" width="130">
          <template #default="{ row }">
            <span v-if="row.routing_id">v{{ row.routing_version || `#${row.routing_id}` }}</span>
            <span v-else class="muted">未指定</span>
          </template>
        </el-table-column>
        <el-table-column prop="batch_no" label="批次号" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="优先级" width="90" align="center">
          <template #default="{ row }"><el-tag :type="priorityTag(row.priority)" size="small" effect="light">{{ priorityLabel(row.priority) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="plan_qty" label="计划数量" width="90" align="right" />
        <el-table-column prop="completed_qty" label="完工数量" width="90" align="right" />
        <el-table-column prop="scrapped_qty" label="报废数量" width="90" align="right" />
        <el-table-column label="达成率" width="100" align="center">
          <template #default="{ row }"><el-tag :type="achievementTag(row)" size="small">{{ achievementRate(row) }}%</el-tag></template>
        </el-table-column>
        <el-table-column label="计划开始" width="150">
          <template #default="{ row }">{{ formatTime(row.planned_start) }}</template>
        </el-table-column>
        <el-table-column label="计划结束" width="150">
          <template #default="{ row }">{{ formatTime(row.planned_end) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite && row.status === 'DRAFT'" size="small" link type="success" @click.stop="onTransition(row, 'RELEASED', '下发')">下发</el-button>
            <el-button v-if="canWrite && row.status === 'RELEASED'" size="small" link type="primary" @click.stop="onTransition(row, 'IN_PROGRESS', '开工')">开工</el-button>
            <el-button v-if="canWrite && row.status === 'IN_PROGRESS'" size="small" link type="primary" @click.stop="onTransition(row, 'COMPLETED', '完工')">完工</el-button>
            <el-button v-if="canWrite && row.status === 'COMPLETED'" size="small" link type="warning" @click.stop="onTransition(row, 'CLOSED', '结案')">结案</el-button>
            <el-button v-if="canWrite && (row.status === 'DRAFT' || row.status === 'RELEASED')" size="small" link type="info" @click.stop="onTransition(row, 'CANCELLED', '取消')">取消</el-button>
            <el-button v-if="canWrite && (row.status === 'DRAFT' || row.status === 'CANCELLED')" size="small" link type="danger" @click.stop="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增订单 -->
    <el-dialog v-model="dialogVisible" title="新增生产订单" width="620px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="产品" prop="product_id">
              <el-select v-model="form.product_id" filterable placeholder="选择产品" style="width:100%" @change="onProductChange">
                <el-option v-for="p in products" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="工序路由" prop="routing_id">
              <el-select v-model="form.routing_id" filterable clearable placeholder="按所选产品联动（仅生效中）" style="width:100%">
                <el-option
                  v-for="r in productRoutings"
                  :key="r.id"
                  :label="`v${r.version} · ${r.steps ? r.steps.length : 0}工序 · ${r.status === 'EFFECTIVE' ? '生效中' : r.status}`"
                  :value="r.id"
                  :disabled="r.status !== 'EFFECTIVE'"
                />
              </el-select>
              <div class="hint">提示：必须选择"已生效"的路由；草稿/作废不可用。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="批次号"><el-input v-model="form.batch_no" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" style="width:100%">
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p" :label="priorityLabel(p)" :value="p" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划数量" prop="plan_qty">
              <el-input-number v-model="form.plan_qty" :min="1" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划开始"><el-date-picker v-model="form.planned_start" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划结束"><el-date-picker v-model="form.planned_end" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- MO 详情抽屉 -->
    <el-drawer v-model="moDrawerVisible" :title="moDrawerTitle" size="640px" direction="rtl">
      <div v-loading="moLoading" class="detail-body">
        <template v-if="moDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="MO号">{{ moDetail.mo_no }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(moDetail.status)" size="small">{{ statusLabel(moDetail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="产品">{{ moDetail.product_name || `#${moDetail.product_id}` }}</el-descriptions-item>
            <el-descriptions-item label="批次号">{{ moDetail.batch_no || '—' }}</el-descriptions-item>
            <el-descriptions-item label="工序路由" :span="2">
              <span v-if="moDetail.routing_id">#{{ moDetail.routing_id }}{{ moDetail.routing_version ? ` v${moDetail.routing_version}` : '' }}</span>
              <span v-else>未指定</span>
            </el-descriptions-item>
            <el-descriptions-item label="优先级">
              <el-tag :type="priorityTag(moDetail.priority)" size="small">{{ priorityLabel(moDetail.priority) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{ moDetail.source_type || '—' }}</el-descriptions-item>
            <el-descriptions-item label="计划数量">{{ moDetail.plan_qty }}</el-descriptions-item>
            <el-descriptions-item label="投入数量">{{ moDetail.input_qty }}</el-descriptions-item>
            <el-descriptions-item label="完工数量">{{ moDetail.completed_qty }}</el-descriptions-item>
            <el-descriptions-item label="报废数量">{{ moDetail.scrapped_qty }}</el-descriptions-item>
            <el-descriptions-item label="达成率">
              <el-tag :type="achievementTag(moDetail)" size="small">{{ achievementRate(moDetail) }}%</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="派工数">{{ moDetail.dispatches_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="客户PO">{{ moDetail.customer_po || '—' }}</el-descriptions-item>
            <el-descriptions-item label="父MO">{{ moDetail.parent_mo_id ? `#${moDetail.parent_mo_id}` : '—' }}</el-descriptions-item>
            <el-descriptions-item label="计划开始">{{ formatTime(moDetail.planned_start) }}</el-descriptions-item>
            <el-descriptions-item label="计划结束">{{ formatTime(moDetail.planned_end) }}</el-descriptions-item>
            <el-descriptions-item label="实际开始">{{ formatTime(moDetail.actual_start) }}</el-descriptions-item>
            <el-descriptions-item label="实际结束">{{ formatTime(moDetail.actual_end) }}</el-descriptions-item>
            <el-descriptions-item label="创建人">{{ moDetail.created_by_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="下发人">{{ moDetail.released_by_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="结案人">{{ moDetail.closed_by_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(moDetail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(moDetail.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ moDetail.remark || '—' }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>

    <!-- 产品详情抽屉 -->
    <el-drawer v-model="productDrawerVisible" :title="productDrawerTitle" size="480px" direction="rtl">
      <div v-loading="productLoading" class="detail-body">
        <template v-if="productDetail">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="产品编号">{{ productDetail.code }}</el-descriptions-item>
            <el-descriptions-item label="产品名称">{{ productDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="规格型号">{{ productDetail.spec || '—' }}</el-descriptions-item>
            <el-descriptions-item label="单位">{{ productDetail.unit || '—' }}</el-descriptions-item>
            <el-descriptions-item label="理论节拍">
              {{ productDetail.target_cycle ? productDetail.target_cycle + ' 秒/件' : '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="productDetail.is_active ? 'success' : 'info'" size="small">
                {{ productDetail.is_active ? '启用' : '停用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="备注">{{ productDetail.remark || '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(productDetail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(productDetail.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProductionOrders, getProductionOrder, createProductionOrder, updateProductionOrder, deleteProductionOrder } from '@/api/production_order'
import { getProducts, getProduct } from '@/api/product'
import { getRoutings } from '@/api/routing'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('production.mo_manage'))

// MO 详情抽屉
const moDrawerVisible = ref(false)
const moDrawerTitle = ref('订单详情')
const moLoading = ref(false)
const moDetail = ref(null)
async function showMo(row, column, event) {
  // 如果点击目标在 button 上，则不触发行详情
  if (event && event.target && event.target.closest('button')) return
  if (!row || !row.id) return
  moDrawerVisible.value = true
  moLoading.value = true
  moDetail.value = JSON.parse(JSON.stringify(row))
  moDrawerTitle.value = `订单详情 · ${row.mo_no}`
  try {
    const full = await getProductionOrder(row.id)
    moDetail.value = full
  } catch (e) {} finally {
    moLoading.value = false
  }
}

// 产品详情抽屉
const productDrawerVisible = ref(false)
const productDrawerTitle = ref('产品详情')
const productLoading = ref(false)
const productDetail = ref(null)
async function showProduct(pid) {
  if (!pid) return
  productDrawerVisible.value = true
  productLoading.value = true
  productDetail.value = null
  try {
    const p = await getProduct(pid)
    productDetail.value = p
    productDrawerTitle.value = `产品详情 · ${p.code} ${p.name}`
  } catch (e) {} finally {
    productLoading.value = false
  }
}

const MO_STATUS_OPTIONS = ['DRAFT', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED', 'CANCELLED']
const PRIORITY_OPTIONS = ['HIGH', 'NORMAL', 'LOW']
function statusLabel(s) {
  return ({ DRAFT: '草稿', RELEASED: '已下发', IN_PROGRESS: '执行中', COMPLETED: '已完工', CLOSED: '已结案', CANCELLED: '已取消' }[s]) || s
}
function statusTag(s) {
  return ({ DRAFT: 'info', RELEASED: 'primary', IN_PROGRESS: 'warning', COMPLETED: 'success', CLOSED: '', CANCELLED: 'info' }[s]) || 'info'
}
function priorityLabel(p) { return ({ HIGH: '高', NORMAL: '普通', LOW: '低' }[p]) || p || '-' }
function priorityTag(p) { return ({ HIGH: 'danger', NORMAL: '', LOW: 'info' }[p]) || 'info' }

function achievementRate(row) {
  if (!row.plan_qty) return '0.0'
  return ((row.completed_qty || 0) / row.plan_qty * 100).toFixed(1)
}
function achievementTag(row) {
  const r = Number(achievementRate(row))
  if (r >= 100) return 'success'
  if (r >= 50) return 'warning'
  return 'danger'
}

const query = reactive({ status: null })
const list = ref([])
const loading = ref(false)
const products = ref([])
// 当前所选产品联动出的工序路由列表
const productRoutings = ref([])

async function loadProducts() { products.value = await getProducts({ active_only: true }) }
async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.status) params.status = query.status
    list.value = await getProductionOrders(params)
  } finally {
    loading.value = false
  }
}

// 切换产品时联动拉取该产品所有路由（含草稿/作废以提示）
async function onProductChange(pid) {
  form.routing_id = null
  productRoutings.value = []
  if (!pid) return
  try {
    const data = await getRoutings({ product_id: pid, limit: 100 })
    productRoutings.value = Array.isArray(data) ? data : []
  } catch (e) {
    productRoutings.value = []
  }
}

const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  product_id: null,
  routing_id: null,
  batch_no: '',
  priority: 'NORMAL',
  plan_qty: 1,
  planned_start: null,
  planned_end: null,
})
const formRules = {
  product_id: [{ required: true, message: '请选择产品', trigger: 'change' }],
  routing_id: [{ required: true, message: '请选择工序路由', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  plan_qty: [
    { required: true, message: '请输入计划数量', trigger: 'blur' },
    { type: 'number', min: 1, message: '计划数量必须大于 0', trigger: 'blur' },
  ],
}
function openDialog() {
  Object.assign(form, {
    product_id: null,
    routing_id: null,
    batch_no: '',
    priority: 'NORMAL',
    plan_qty: 1,
    planned_start: null,
    planned_end: null,
  })
  productRoutings.value = []
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    await createProductionOrder(JSON.parse(JSON.stringify(form)))
    ElMessage.success('已创建')
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onTransition(row, status, label) {
  try {
    await ElMessageBox.confirm(`确认对订单 ${row.mo_no} 执行「${label}」操作吗？`, `${label}确认`, { type: 'warning' })
    await updateProductionOrder(row.id, { status })
    ElMessage.success(`已${label}`)
    load()
  } catch (e) {}
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除订单 ${row.mo_no}？`, '删除确认', { type: 'warning' })
    await deleteProductionOrder(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

onMounted(async () => {
  await loadProducts()
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
