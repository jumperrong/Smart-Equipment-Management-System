<template>
  <div>
    <!-- 库存概览统计卡 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="8" :md="4" :span="4">
        <div class="stat-card">
          <div class="stat-label">总品种数</div>
          <div class="stat-num">{{ summary.total_skus }}</div>
          <div class="stat-foot">SKU</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="5" :span="5">
        <div class="stat-card">
          <div class="stat-label">总库存数量</div>
          <div class="stat-num">{{ formatNumber(summary.total_qty) }}</div>
          <div class="stat-foot">件</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="6" :span="6">
        <div class="stat-card highlight-value">
          <div class="stat-label">库存总金额</div>
          <div class="stat-num">¥ {{ formatMoney(summary.total_value) }}</div>
          <div class="stat-foot">库存价值</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="5" :span="5">
        <div class="stat-card" :class="{ 'warn': summary.low_stock_count > 0 }">
          <div class="stat-label">低于安全库存</div>
          <div class="stat-num">{{ summary.low_stock_count }}</div>
          <div class="stat-foot">需要补货</div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="8" :md="4" :span="4">
        <div class="stat-card danger" :class="{ 'active': summary.out_of_stock_count > 0 }">
          <div class="stat-label">已断货</div>
          <div class="stat-num">{{ summary.out_of_stock_count }}</div>
          <div class="stat-foot">立即采购</div>
        </div>
      </el-col>
    </el-row>

    <el-card shadow="never" class="main-card">
      <el-tabs v-model="activeTab" class="main-tabs">
        <!-- ============ 备件库存列表 Tab ============ -->
        <el-tab-pane label="备件库存" name="list">
          <div class="toolbar">
            <el-form :inline="true" :model="query" size="default">
              <el-form-item label="关键字">
                <el-input v-model="query.keyword" placeholder="编号/名称" clearable style="width:200px" @keyup.enter="load" />
              </el-form-item>
              <el-form-item label="仅看库存异常">
                <el-select v-model="query.filter" clearable placeholder="全部" style="width:160px" @change="load">
                  <el-option label="低于安全库存" value="low" />
                  <el-option label="已断货" value="oos" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="load">查询</el-button>
                <el-button v-if="canWrite" type="success" @click="openDialog()">新增备件</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="filteredList" stripe v-loading="loading" border size="small">
            <el-table-column prop="sku" label="备件编号" width="130" fixed="left" />
            <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
            <el-table-column prop="spec" label="规格" min-width="140" show-overflow-tooltip />
            <el-table-column prop="brand" label="品牌" width="100" />
            <el-table-column label="库存状态" width="150" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.current_stock === 0" type="danger" effect="dark">断货</el-tag>
                <el-tag v-else-if="row.current_stock <= row.safety_stock" type="warning" effect="light">偏低</el-tag>
                <el-tag v-else type="success" effect="plain">正常</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前库存" width="110" align="right">
              <template #default="{ row }">
                <span :class="{ 'low-stock': row.current_stock <= row.safety_stock }">
                  {{ row.current_stock }} {{ row.unit }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="safety_stock" label="安全库存" width="90" align="right" />
            <el-table-column label="单价(¥)" width="110" align="right">
              <template #default="{ row }">{{ formatMoney(row.unit_price) }}</template>
            </el-table-column>
            <el-table-column label="库存价值" width="120" align="right">
              <template #default="{ row }">
                <span class="muted">¥</span> {{ formatMoney((row.current_stock || 0) * (row.unit_price || 0)) }}
              </template>
            </el-table-column>
            <el-table-column prop="location" label="库位" width="100" />
            <el-table-column label="操作" width="280" fixed="right" align="center">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openMovements(row)">流水</el-button>
                <el-button v-if="canMove" size="small" link type="success" @click="openMoveDialog(row)">出入库</el-button>
                <el-button v-if="canWrite" size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
                <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ============ 全局出入库流水 Tab ============ -->
        <el-tab-pane label="出入库流水" name="all-movements">
          <div class="toolbar">
            <el-form :inline="true" :model="mvQuery" size="default">
              <el-form-item label="关键字">
                <el-input v-model="mvQuery.keyword" placeholder="备件编号/名称" clearable style="width:200px" @keyup.enter="loadAllMovements" />
              </el-form-item>
              <el-form-item label="操作类型">
                <el-select v-model="mvQuery.movement_type" clearable placeholder="全部" style="width:140px" @change="loadAllMovements">
                  <el-option label="入库" value="IN" />
                  <el-option label="出库" value="OUT" />
                  <el-option label="调整" value="ADJUST" />
                </el-select>
              </el-form-item>
              <el-form-item label="来源">
                <el-select v-model="mvQuery.ref_type" clearable placeholder="全部" style="width:140px" @change="loadAllMovements">
                  <el-option label="期初建账" value="INIT" />
                  <el-option label="手动操作" value="MANUAL" />
                  <el-option label="工单领用" value="WORK_ORDER" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadAllMovements">查询</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="allMovements" stripe v-loading="allMvLoading" border size="small">
            <el-table-column label="时间" width="160" fixed="left">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="备件" min-width="150">
              <template #default="{ row }">
                <span v-if="row.spare_part" class="mv-part">
                  <span class="sku">{{ row.spare_part.sku }}</span>
                  <span class="name">{{ row.spare_part.name }}</span>
                </span>
                <span v-else class="muted">#{{ row.spare_part_id }}</span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="movementTag(row.movement_type)" size="small" effect="light">
                  {{ movementLabel(row.movement_type) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="qty" label="数量" width="80" align="right" />
            <el-table-column label="库存变更" width="170" align="center">
              <template #default="{ row }">
                <span class="muted">{{ row.before_stock }}</span>
                <span class="arrow"> → </span>
                <b>{{ row.after_stock }}</b>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="110" align="center">
              <template #default="{ row }">{{ refTypeLabel(row.ref_type) }}</template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="200" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新增/编辑 备件 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑备件' : '新增备件'" width="640px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="备件编号" prop="sku"><el-input v-model="form.sku" :disabled="!!form.id" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="规格"><el-input v-model="form.spec" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="单位"><el-input v-model="form.unit" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="安全库存"><el-input-number v-model="form.safety_stock" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8" v-if="!form.id"><el-form-item label="初始库存"><el-input-number v-model="form.current_stock" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="单价(¥)"><el-input-number v-model="form.unit_price" :min="0" :precision="2" :step="10" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="库位"><el-input v-model="form.location" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 出入库操作对话框 -->
    <el-dialog v-model="moveDialogVisible" :title="`出入库操作：${moveTarget?.name || ''}`" width="460px">
      <el-form :model="moveForm" :rules="moveRules" ref="moveFormRef" label-width="90px">
        <el-form-item label="当前库存">
          <el-tag size="large" :type="moveTarget?.current_stock === 0 ? 'danger' : (moveTarget?.current_stock <= moveTarget?.safety_stock ? 'warning' : '')">
            {{ moveTarget?.current_stock }} {{ moveTarget?.unit }}
            <span v-if="moveTarget?.unit_price" class="muted"> · 单价 ¥{{ formatMoney(moveTarget.unit_price) }}</span>
          </el-tag>
        </el-form-item>
        <el-form-item label="操作类型" prop="movement_type">
          <el-radio-group v-model="moveForm.movement_type">
            <el-radio-button v-for="m in MOVEMENT_TYPE_OPTIONS" :key="m" :value="m">{{ movementLabel(m) }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="moveForm.movement_type === 'ADJUST' ? '调整为' : '数量'" prop="qty">
          <el-input-number v-model="moveForm.qty" :min="1" style="width:100%" />
        </el-form-item>
        <el-form-item label="预计结果">
          <span class="preview-result">
            <span class="muted">{{ moveTarget?.current_stock }}</span>
            <span class="arrow"> → </span>
            <b :class="{ 'low-stock': (previewStock ?? 0) <= (moveTarget?.safety_stock ?? 9999999) }">
              {{ previewStock }} {{ moveTarget?.unit }}
            </b>
            <el-tag v-if="previewStock === 0" type="danger" effect="dark" style="margin-left:10px">将断货</el-tag>
          </span>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="moveForm.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moveDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="moveSaving" @click="onMove">确认</el-button>
      </template>
    </el-dialog>

    <!-- 单备件出入库记录 drawer -->
    <el-drawer v-model="mvDrawerVisible" :title="`出入库记录：${mvTarget?.name || ''} (${mvTarget?.sku || ''})`" size="65%">
      <div class="drawer-summary" v-if="mvTarget">
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item label="当前库存">
            <span :class="{ 'low-stock': mvTarget.current_stock <= mvTarget.safety_stock }">
              {{ mvTarget.current_stock }} {{ mvTarget.unit }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="安全库存">{{ mvTarget.safety_stock }} {{ mvTarget.unit }}</el-descriptions-item>
          <el-descriptions-item label="库位">{{ mvTarget.location || '-' }}</el-descriptions-item>
          <el-descriptions-item label="单价">¥ {{ formatMoney(mvTarget.unit_price) }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <el-table :data="movements" stripe size="small" border style="margin-top:16px">
        <el-table-column label="时间" width="160" fixed="left">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }"><el-tag :type="movementTag(row.movement_type)" size="small">{{ movementLabel(row.movement_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="qty" label="数量" width="80" align="right" />
        <el-table-column label="库存变更" width="160" align="center">
          <template #default="{ row }">
            <span class="muted">{{ row.before_stock }}</span>
            <span class="arrow"> → </span>
            <b>{{ row.after_stock }}</b>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="110" align="center">
          <template #default="{ row }">{{ refTypeLabel(row.ref_type) }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-drawer>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listSpareParts, createSparePart, updateSparePart, deleteSparePart,
  moveStock, listMovements, getStockSummary, listAllMovements,
} from '@/api/spare_part'
import { useUserStore } from '@/stores'
import { MOVEMENT_TYPE_OPTIONS, movementLabel, movementTag, formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('spare_part.write'))
const canDelete = computed(() => userStore.can('spare_part.delete'))
const canMove = computed(() => userStore.can('spare_part.movement'))

// ============ 库存概览 ============
const summary = reactive({
  total_skus: 0, total_qty: 0, total_value: 0,
  low_stock_count: 0, out_of_stock_count: 0,
})
async function loadSummary() {
  try {
    const r = await getStockSummary()
    Object.assign(summary, r)
  } catch (e) {
    console.warn('load stock summary failed', e)
  }
}

// ============ 备件列表 Tab ============
const activeTab = ref('list')
const query = reactive({ keyword: '', filter: '' })
const list = ref([])
const loading = ref(false)
const filteredList = computed(() => {
  if (!query.filter) return list.value
  if (query.filter === 'low') return list.value.filter(r => r.current_stock <= r.safety_stock)
  if (query.filter === 'oos') return list.value.filter(r => r.current_stock === 0)
  return list.value
})

async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.keyword) params.keyword = query.keyword
    list.value = await listSpareParts(params)
  } finally {
    loading.value = false
  }
}

// ============ 新增/编辑 备件 ============
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, sku: '', name: '', spec: '', brand: '', unit: '个',
  safety_stock: 0, current_stock: 0, unit_price: 0, location: '', remark: '',
})
const formRules = {
  sku: [{ required: true, message: '请输入备件编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}
function openDialog(row = null) {
  Object.assign(form, {
    id: null, sku: '', name: '', spec: '', brand: '', unit: '个',
    safety_stock: 0, current_stock: 0, unit_price: 0, location: '', remark: '',
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
      const { id, ...rest } = payload
      delete rest.current_stock
      await updateSparePart(id, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createSparePart(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await Promise.all([load(), loadSummary()])
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除备件【${row.sku} - ${row.name}】？`, '危险操作', { type: 'error' })
    await deleteSparePart(row.id)
    ElMessage.success('已删除')
    await Promise.all([load(), loadSummary()])
  } catch (e) {}
}

// ============ 出入库操作 ============
const moveDialogVisible = ref(false)
const moveSaving = ref(false)
const moveFormRef = ref(null)
const moveTarget = ref(null)
const moveForm = reactive({ movement_type: 'IN', qty: 1, remark: '' })
const moveRules = {
  movement_type: [{ required: true, message: '请选择操作类型', trigger: 'change' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}
const previewStock = computed(() => {
  if (!moveTarget.value) return null
  const cur = moveTarget.value.current_stock || 0
  const q = moveForm.qty || 0
  if (moveForm.movement_type === 'IN') return cur + q
  if (moveForm.movement_type === 'OUT') return cur - q
  if (moveForm.movement_type === 'ADJUST') return q
  return cur
})
function openMoveDialog(row) {
  moveTarget.value = row
  Object.assign(moveForm, { movement_type: 'IN', qty: 1, remark: '' })
  moveDialogVisible.value = true
}
async function onMove() {
  try {
    await moveFormRef.value.validate()
    // 出库断货预警二次确认
    if (moveForm.movement_type === 'OUT' && previewStock.value < 0) {
      ElMessage.warning('库存不足，无法执行该出库操作')
      return
    }
    if (moveForm.movement_type === 'OUT' && previewStock.value === 0) {
      await ElMessageBox.confirm('本次出库后库存将归零（断货），是否继续？', '断货预警', { type: 'warning' })
    } else if (moveForm.movement_type === 'OUT' && previewStock.value <= (moveTarget.value?.safety_stock ?? 0)) {
      await ElMessageBox.confirm('本次出库后库存将低于安全库存，是否继续？', '低库存预警', { type: 'warning' })
    }
    moveSaving.value = true
    await moveStock(moveTarget.value.id, { ...moveForm })
    ElMessage.success('操作成功')
    moveDialogVisible.value = false
    await Promise.all([load(), loadSummary()])
  } catch (e) {} finally {
    moveSaving.value = false
  }
}

// ============ 单备件出入库 Drawer ============
const mvDrawerVisible = ref(false)
const mvTarget = ref(null)
const movements = ref([])
async function openMovements(row) {
  mvTarget.value = row
  mvDrawerVisible.value = true
  movements.value = await listMovements(row.id, { limit: 300 })
}

// ============ 全局出入库 Tab ============
const mvQuery = reactive({ keyword: '', movement_type: '', ref_type: '' })
const allMovements = ref([])
const allMvLoading = ref(false)
async function loadAllMovements() {
  allMvLoading.value = true
  try {
    const params = {}
    if (mvQuery.keyword) params.keyword = mvQuery.keyword
    if (mvQuery.movement_type) params.movement_type = mvQuery.movement_type
    if (mvQuery.ref_type) params.ref_type = mvQuery.ref_type
    params.limit = 500
    allMovements.value = await listAllMovements(params)
  } finally {
    allMvLoading.value = false
  }
}

// 切换到"出入库流水"Tab 时自动加载一次
watch(activeTab, async (nv) => {
  if (nv === 'all-movements' && allMovements.value.length === 0) {
    await loadAllMovements()
  }
})

// ============ utils ============
function refTypeLabel(t) {
  return ({ INIT: '期初', MANUAL: '手动', WORK_ORDER: '工单领用' }[t]) || (t || '-')
}
function formatMoney(v) {
  if (v == null || isNaN(v)) return '0.00'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function formatNumber(v) {
  if (v == null || isNaN(v)) return '0'
  return Number(v).toLocaleString('zh-CN')
}

onMounted(async () => {
  await Promise.all([load(), loadSummary()])
})
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px 18px;
  box-shadow: 0 1px 4px rgba(0,21,41,.06);
  border: 1px solid #eef1f4;
}
.stat-label { color: #8c8c8c; font-size: 13px; }
.stat-num { font-size: 26px; font-weight: 600; color: #1f2d3d; margin: 6px 0 2px; letter-spacing: 0.5px; }
.stat-foot { color: #b8bcc0; font-size: 12px; }
.stat-card.highlight-value .stat-num { color: #409eff; }
.stat-card.warn .stat-num { color: #e6a23c; }
.stat-card.danger .stat-num { color: #a8abb2; }
.stat-card.danger.active { background: #fef0f0; border-color: #fde2e2; }
.stat-card.danger.active .stat-num { color: #f56c6c; font-size: 28px; }

.main-card { border-radius: 10px; }
.main-tabs :deep(.el-tabs__header) { margin-bottom: 12px; }

.toolbar { margin-bottom: 10px; }

.low-stock { color: #f56c6c; font-weight: 600; }
.muted { color: #909399; font-weight: normal; }
.arrow { color: #c0c4cc; margin: 0 4px; }
.preview-result { font-size: 15px; line-height: 28px; }

.mv-part { display: flex; flex-direction: column; line-height: 1.3; }
.mv-part .sku { color: #409eff; font-size: 12px; }
.mv-part .name { color: #303133; font-size: 13px; margin-top: 2px; }

.drawer-summary { margin-bottom: 6px; }
</style>
