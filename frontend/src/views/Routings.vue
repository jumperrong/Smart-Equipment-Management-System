<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="产品">
            <el-select v-model="query.product_id" filterable placeholder="全部" clearable style="width:220px">
              <el-option v-for="p in products" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:140px">
              <el-option v-for="s in ROUTING_STATUS_OPTIONS" :key="s" :label="statusLabel(s)" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增路由</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small" @row-click="showRouting">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="产品" min-width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="showProduct(row.product_id)">
              {{ productName(row.product_id) }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="工序数" width="80" align="center">
          <template #default="{ row }">{{ (row.steps || []).length }}</template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="110" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite && row.status === 'DRAFT'" size="small" link type="primary" @click.stop="openDialog(row)">编辑</el-button>
            <el-button v-if="canWrite && row.status === 'DRAFT'" size="small" link type="success" @click.stop="onRelease(row)">生效</el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click.stop="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑路由 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑路由' : '新增路由'" width="860px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="产品" prop="product_id">
              <el-select v-model="form.product_id" filterable placeholder="选择产品" style="width:100%">
                <el-option v-for="p in products" :key="p.id" :label="`${p.code} ${p.name}`" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本号" prop="version">
              <el-input v-model="form.version" placeholder="如 v1.0" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="form.remark" /></el-form-item>
          </el-col>
        </el-row>

        <div class="steps-bar">
          <span class="steps-title">工序步骤</span>
          <el-button v-if="canWrite" size="small" type="primary" plain @click="addStep">+ 添加工序</el-button>
        </div>
        <el-table :data="form.steps" border size="small">
          <el-table-column label="序号" width="90">
            <template #default="{ row }">
              <el-input-number v-model="row.seq" :min="1" controls-position="right" size="small" style="width:100%" />
            </template>
          </el-table-column>
          <el-table-column label="工序名称" min-width="140">
            <template #default="{ row }"><el-input v-model="row.step_name" size="small" placeholder="工序名称" /></template>
          </el-table-column>
          <el-table-column label="绑定工段" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.process_section_id" size="small" filterable clearable placeholder="从工段库选（自动带出模板）" style="width:100%" @change="(v) => onStepSectionChange(row, v)">
                <el-option
                  v-for="s in sections"
                  :key="s.id"
                  :label="`${s.name}${s.form_template_name ? ' · ' + s.form_template_name : ''}`"
                  :value="s.id"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="标准工时(分)" width="130">
            <template #default="{ row }"><el-input-number v-model="row.standard_cycle_min" :min="0" :precision="2" controls-position="right" size="small" style="width:100%" /></template>
          </el-table-column>
          <el-table-column label="理论UPH" width="120">
            <template #default="{ row }"><el-input-number v-model="row.theoretical_uph" :min="0" :precision="2" controls-position="right" size="small" style="width:100%" /></template>
          </el-table-column>
          <el-table-column label="设备组" min-width="120">
            <template #default="{ row }"><el-input v-model="row.equipment_group" size="small" placeholder="设备组" /></template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ $index }">
              <el-button size="small" link type="danger" @click="removeStep($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 路由详情抽屉 -->
    <el-drawer v-model="routingDrawerVisible" :title="routingDrawerTitle" size="640px" direction="rtl">
      <div v-loading="routingLoading" class="detail-body">
        <template v-if="routingDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="路由ID">{{ routingDetail.id }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ routingDetail.version }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(routingDetail.status)" size="small">{{ statusLabel(routingDetail.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="产品">{{ productName(routingDetail.product_id) }}</el-descriptions-item>
            <el-descriptions-item label="生效日期">{{ formatTime(routingDetail.effective_date) }}</el-descriptions-item>
            <el-descriptions-item label="下次复审">{{ formatTime(routingDetail.next_review_date) }}</el-descriptions-item>
            <el-descriptions-item label="创建人">{{ routingDetail.created_by_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(routingDetail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="变更原因" :span="2">{{ routingDetail.change_reason || '—' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ routingDetail.remark || '—' }}</el-descriptions-item>
          </el-descriptions>

          <div class="section">
            <div class="section-title">工序步骤（{{ (routingDetail.steps || []).length }} 步）</div>
            <el-table :data="routingDetail.steps" size="small" border>
              <el-table-column prop="seq" label="序号" width="70" align="center" />
              <el-table-column prop="step_name" label="工序名称" min-width="140" />
              <el-table-column label="绑定工段" min-width="150">
                <template #default="{ row }">
                  <span v-if="row.process_section_id">{{ sectionName(row.process_section_id) }}</span>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="工艺模板" min-width="140">
                <template #default="{ row }">
                  <span v-if="row.param_form_template_id">{{ sectionFormTemplateName(row.process_section_id) || `#${row.param_form_template_id}` }}</span>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="标准工时" width="100" align="center">
                <template #default="{ row }">{{ row.standard_cycle_min ? row.standard_cycle_min + ' 分' : '—' }}</template>
              </el-table-column>
              <el-table-column label="理论UPH" width="90" align="center">
                <template #default="{ row }">{{ row.theoretical_uph || '—' }}</template>
              </el-table-column>
              <el-table-column prop="equipment_group" label="设备组" width="120" />
            </el-table>
          </div>
        </template>
      </div>
    </el-drawer>

    <!-- 产品详情抽屉 -->
    <el-drawer v-model="productDrawerVisible" :title="productDrawerTitle" size="480px" direction="rtl">
      <div v-loading="productLoading" class="product-detail">
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

          <div class="routings-section">
            <div class="section-title">该产品的工艺路由</div>
            <el-table :data="productRoutings" size="small" border>
              <el-table-column prop="version" label="版本" width="100" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="工序数" width="80" align="center">
                <template #default="{ row }">{{ (row.steps || []).length }}</template>
              </el-table-column>
              <el-table-column label="创建时间">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRoutings, getRouting, createRouting, updateRouting, deleteRouting, releaseRouting } from '@/api/routing'
import { getProducts, getProduct } from '@/api/product'
import { getProcessSections } from '@/api/process_section'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('production.routing_write'))
const canDelete = computed(() => userStore.can('production.routing_delete'))

const ROUTING_STATUS_OPTIONS = ['DRAFT', 'EFFECTIVE', 'OBSOLETE']
function statusLabel(s) {
  return ({ DRAFT: '草稿', EFFECTIVE: '已生效', OBSOLETE: '已作废' }[s]) || s
}
function statusTag(s) {
  return ({ DRAFT: 'info', EFFECTIVE: 'success', OBSOLETE: 'warning' }[s]) || 'info'
}

// 路由详情抽屉
const routingDrawerVisible = ref(false)
const routingDrawerTitle = ref('路由详情')
const routingLoading = ref(false)
const routingDetail = ref(null)
async function showRouting(row, column, event) {
  // 如果点击目标在 button 上，则不触发行详情
  if (event && event.target && event.target.closest('button')) return
  if (!row || !row.id) return
  // 行点击：优先用列表行数据快速展示，再异步拉详情补全工序步骤
  routingDrawerVisible.value = true
  routingLoading.value = true
  routingDetail.value = JSON.parse(JSON.stringify(row))
  routingDrawerTitle.value = `路由详情 · ${row.version}（${productName(row.product_id)}）`
  try {
    const full = await getRouting(row.id)
    routingDetail.value = full
  } catch (e) {} finally {
    routingLoading.value = false
  }
}

// 产品详情抽屉
const productDrawerVisible = ref(false)
const productDrawerTitle = ref('产品详情')
const productLoading = ref(false)
const productDetail = ref(null)
const productRoutings = ref([])
async function showProduct(pid) {
  if (!pid) return
  productDrawerVisible.value = true
  productLoading.value = true
  productDetail.value = null
  productRoutings.value = []
  try {
    const p = await getProduct(pid)
    productDetail.value = p
    productDrawerTitle.value = `产品详情 · ${p.code} ${p.name}`
    // 该产品的所有路由
    const all = await getRoutings({ product_id: pid, limit: 100 })
    productRoutings.value = Array.isArray(all) ? all : []
  } catch (e) {} finally {
    productLoading.value = false
  }
}

const query = reactive({ status: null, product_id: null })
const list = ref([])
const loading = ref(false)
const products = ref([])
// 工段库（含其工艺数据模板信息），供路由步骤绑定
const sections = ref([])

function productName(id) {
  const p = products.value.find((x) => x.id === id)
  return p ? `${p.code} ${p.name}` : `#${id}`
}

function sectionName(id) {
  if (!id) return ''
  const s = sections.value.find((x) => x.id === id)
  return s ? s.name : `#${id}`
}
function sectionFormTemplateName(sectionId) {
  if (!sectionId) return ''
  const s = sections.value.find((x) => x.id === sectionId)
  return s?.form_template_name || ''
}

// 选工段联动：把工段的工艺数据模板带到步骤的 param_form_template_id
function onStepSectionChange(row, sectionId) {
  if (!sectionId) {
    row.param_form_template_id = null
    return
  }
  const s = sections.value.find((x) => x.id === sectionId)
  if (s) {
    row.param_form_template_id = s.form_template_id || null
    // 设备组若空，用工段预设
    if (!row.equipment_group && s.equipment_group) {
      row.equipment_group = s.equipment_group
    }
  }
}

async function loadProducts() {
  products.value = await getProducts({ active_only: false })
}
async function loadSections() {
  try {
    const data = await getProcessSections({ is_active: true, limit: 500 })
    sections.value = Array.isArray(data) ? data : []
  } catch (e) {
    sections.value = []
  }
}
async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.product_id) params.product_id = query.product_id
    if (query.status) params.status = query.status
    list.value = await getRoutings(params)
  } finally {
    loading.value = false
  }
}

// 新增/编辑
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({ id: null, product_id: null, version: '', remark: '', steps: [] })
const formRules = {
  product_id: [{ required: true, message: '请选择产品', trigger: 'change' }],
  version: [{ required: true, message: '请输入版本号', trigger: 'blur' }],
}
function emptyStep() {
  return {
    seq: form.steps.length + 1,
    step_name: '',
    standard_cycle_min: null,
    theoretical_uph: null,
    equipment_group: '',
  }
}
function addStep() { form.steps.push(emptyStep()) }
function removeStep(idx) { form.steps.splice(idx, 1) }
function openDialog(row = null) {
  Object.assign(form, { id: null, product_id: null, version: '', remark: '', steps: [] })
  if (row) {
    Object.assign(form, JSON.parse(JSON.stringify(row)))
    if (!Array.isArray(form.steps)) form.steps = []
  } else {
    form.steps = [emptyStep()]
  }
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = JSON.parse(JSON.stringify(form))
    const steps = (payload.steps || [])
      .filter((s) => s.step_name)
      .map((s) => ({
        seq: s.seq,
        step_name: s.step_name,
        standard_cycle_min: s.standard_cycle_min,
        theoretical_uph: s.theoretical_uph,
        equipment_group: s.equipment_group,
      }))
    if (payload.id) {
      await updateRouting(payload.id, {
        product_id: payload.product_id,
        version: payload.version,
        remark: payload.remark,
        steps,
      })
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createRouting({
        product_id: payload.product_id,
        version: payload.version,
        remark: payload.remark,
        steps,
      })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onRelease(row) {
  try {
    await ElMessageBox.confirm(
      `确认让路由「${productName(row.product_id)} ${row.version}」生效吗？生效后不可再编辑。`,
      '生效确认',
      { type: 'warning' },
    )
    await releaseRouting(row.id)
    ElMessage.success('已生效')
    load()
  } catch (e) {}
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该工序路由？此操作不可恢复。', '删除确认', { type: 'warning' })
    await deleteRouting(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

onMounted(async () => {
  await Promise.all([loadProducts(), loadSections()])
  await load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.steps-bar { display: flex; align-items: center; justify-content: space-between; margin: 14px 0 8px; }
.steps-title { font-weight: 600; }
.detail-body { padding: 4px 16px 16px; }
.product-detail { padding: 4px 16px 16px; }
.routings-section { margin-top: 18px; }
.section { margin-top: 18px; }
.section-title { font-weight: 600; margin-bottom: 8px; color: #303133; }
.muted { color: #999; }
:deep(.el-table__row) { cursor: pointer; }
</style>
