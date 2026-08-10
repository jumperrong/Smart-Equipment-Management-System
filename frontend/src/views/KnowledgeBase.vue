<template>
  <div>
    <el-card shadow="never">
      <!-- ============ 搜索栏 ============ -->
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="关键词">
            <el-input
              v-model="query.keyword"
              placeholder="标题/现象/根因/处置"
              clearable
              style="width: 240px"
              @keyup.enter="loadList"
            />
          </el-form-item>
          <el-form-item label="故障分类">
            <el-select v-model="query.fault_category" placeholder="全部" clearable style="width: 150px">
              <el-option v-for="c in FAULT_CATEGORY_OPTIONS" :key="c" :label="faultCategoryLabel(c)" :value="c" />
            </el-select>
          </el-form-item>
          <el-form-item label="设备">
            <el-select v-model="query.equipment_id" filterable placeholder="全部设备" clearable style="width: 200px">
              <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadList">搜索</el-button>
            <el-button type="success" @click="openForm()">新建条目</el-button>
            <el-button type="warning" @click="archiveDialogVisible = true">从工单归档</el-button>
            <el-button type="warning" @click="d8ArchiveDialogVisible = true">从8D报告归档</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- ============ 统计行 ============ -->
      <el-row :gutter="16" class="stat-row">
        <el-col :span="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value">{{ list.length }}</div>
            <div class="stat-label">总条目数</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value">{{ monthNewCount }}</div>
            <div class="stat-label">本月新增</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="stat-card">
            <div class="stat-value">{{ recurrenceTotal }}</div>
            <div class="stat-label">复发次数合计</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- ============ 表格 ============ -->
      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="故障分类" width="110">
          <template #default="{ row }">
            <el-tag :type="faultCategoryTag(row.fault_category)" size="small">{{ faultCategoryLabel(row.fault_category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设备" width="140">
          <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
        </el-table-column>
        <el-table-column label="故障现象" min-width="150">
          <template #default="{ row }"><span class="cell-truncate">{{ truncate(row.symptom) }}</span></template>
        </el-table-column>
        <el-table-column label="根因" min-width="140">
          <template #default="{ row }"><span class="cell-truncate">{{ truncate(row.root_cause) }}</span></template>
        </el-table-column>
        <el-table-column label="处置措施" min-width="140">
          <template #default="{ row }"><span class="cell-truncate">{{ truncate(row.solution) }}</span></template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览数" width="80" align="center" />
        <el-table-column prop="recurrence_count" label="复发次数" width="90" align="center" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="kbStatusTag(row.status)" size="small">{{ kbStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDetail(row)">查看详情</el-button>
            <el-button size="small" link type="primary" @click="openForm(row)">编辑</el-button>
            <el-button size="small" link type="warning" @click="onRecurrence(row)">标记复发</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- ============ 详情对话框 ============ -->
    <el-dialog v-model="detailVisible" title="故障知识库详情" width="800px" top="5vh">
      <div v-loading="detailLoading">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="标题" :span="2">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="故障分类">
            <el-tag :type="faultCategoryTag(detail.fault_category)" size="small">{{ faultCategoryLabel(detail.fault_category) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="设备">
            {{ eqName(detail.equipment_id) }}{{ detail.equipment_model ? ' / ' + detail.equipment_model : '' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="kbStatusTag(detail.status)" size="small">{{ kbStatusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="浏览数">{{ detail.view_count }}</el-descriptions-item>
          <el-descriptions-item label="复发次数">{{ detail.recurrence_count }}</el-descriptions-item>
          <el-descriptions-item label="来源工单">{{ detail.source_work_order_id ? '#' + detail.source_work_order_id : '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源8D报告">{{ detail.source_d8_report_id ? '#' + detail.source_d8_report_id : '-' }}</el-descriptions-item>
          <el-descriptions-item label="标签" :span="2">
            <el-tag v-for="t in tagsArray(detail.tags)" :key="t" size="small" class="kb-tag">{{ t }}</el-tag>
            <span v-if="!tagsArray(detail.tags).length">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="故障现象" :span="2"><div class="kb-content">{{ detail.symptom || '-' }}</div></el-descriptions-item>
          <el-descriptions-item label="根因" :span="2"><div class="kb-content">{{ detail.root_cause || '-' }}</div></el-descriptions-item>
          <el-descriptions-item label="处置措施" :span="2"><div class="kb-content">{{ detail.solution || '-' }}</div></el-descriptions-item>
          <el-descriptions-item label="预防措施" :span="2"><div class="kb-content">{{ detail.prevention || '-' }}</div></el-descriptions-item>
        </el-descriptions>

        <!-- 相似案例 -->
        <div class="similar-section">
          <div class="section-title">相似案例</div>
          <el-table :data="similarCases" v-loading="similarLoading" size="small" border max-height="260">
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
            <el-table-column label="故障分类" width="100">
              <template #default="{ row }">
                <el-tag :type="faultCategoryTag(row.fault_category)" size="small">{{ faultCategoryLabel(row.fault_category) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="设备" width="130">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column prop="recurrence_count" label="复发" width="70" align="center" />
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openDetail(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>

    <!-- ============ 新建/编辑对话框 ============ -->
    <el-dialog v-model="formVisible" :title="form.id ? '编辑条目' : '新建条目'" width="760px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="标题" prop="title"><el-input v-model="form.title" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="故障分类" prop="fault_category">
              <el-select v-model="form.fault_category" style="width: 100%">
                <el-option v-for="c in FAULT_CATEGORY_OPTIONS" :key="c" :label="faultCategoryLabel(c)" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联设备">
              <el-select v-model="form.equipment_id" filterable clearable placeholder="可选" style="width: 100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备型号"><el-input v-model="form.equipment_model" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="故障现象" prop="symptom"><el-input v-model="form.symptom" type="textarea" :rows="3" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="根因" prop="root_cause"><el-input v-model="form.root_cause" type="textarea" :rows="3" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="处置措施" prop="solution"><el-input v-model="form.solution" type="textarea" :rows="3" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="预防措施"><el-input v-model="form.prevention" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="标签"><el-input v-model="form.tags" placeholder="多个标签用逗号分隔" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- ============ 从工单归档对话框 ============ -->
    <el-dialog v-model="archiveDialogVisible" title="从工单归档" width="480px">
      <el-form label-width="100px">
        <el-form-item label="工单ID">
          <el-input v-model="archiveWorkOrderId" placeholder="请输入工单ID" @keyup.enter="onArchive" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="archiveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="archiveLoading" @click="onArchive">归档</el-button>
      </template>
    </el-dialog>

    <!-- ============ 从8D报告归档对话框 ============ -->
    <el-dialog v-model="d8ArchiveDialogVisible" title="从8D报告归档" width="520px">
      <el-form label-width="100px">
        <el-form-item label="8D报告">
          <el-select v-model="d8ArchiveId" filterable placeholder="选择8D报告" style="width: 100%">
            <el-option
              v-for="r in d8Reports"
              :key="r.id"
              :label="`${r.report_no} - ${r.title}`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="故障分类">
          <el-select v-model="d8ArchiveCategory" placeholder="自动" clearable style="width: 100%">
            <el-option v-for="c in FAULT_CATEGORY_OPTIONS" :key="c" :label="faultCategoryLabel(c)" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="d8ArchiveTags" placeholder="留空自动生成 8D,报告编号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="d8ArchiveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="d8ArchiveLoading" @click="onD8Archive">归档</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { listEquipments } from '@/api/equipment'
import { listD8 } from '@/api/quality'

const base = '/api/v1/knowledge'

// ---------- 故障分类 / 状态 ----------
const FAULT_CATEGORY_OPTIONS = ['mechanical', 'electrical', 'process', 'software', 'pneumatic', 'other']
function faultCategoryLabel(c) {
  return ({ mechanical: '机械', electrical: '电气', process: '工艺', software: '软件', pneumatic: '气动', other: '其他' })[c] || c || '-'
}
function faultCategoryTag(c) {
  return ({ mechanical: 'warning', electrical: 'primary', process: 'success', software: 'info', pneumatic: 'danger', other: 'info' })[c] || 'info'
}
function kbStatusLabel(s) {
  return ({ draft: '草稿', active: '有效', archived: '已归档' })[s] || s || '-'
}
function kbStatusTag(s) {
  return ({ draft: 'info', active: 'success', archived: 'warning' })[s] || 'info'
}

// ---------- 通用 ----------
const equipments = ref([])
function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}
function truncate(s, n = 40) {
  if (!s) return '-'
  return s.length > n ? s.slice(0, n) + '…' : s
}
function tagsArray(t) {
  if (!t) return []
  if (Array.isArray(t)) return t
  return String(t).split(/[,，]/).map((x) => x.trim()).filter(Boolean)
}

async function loadEquipments() {
  try {
    equipments.value = await listEquipments({ limit: 500 })
  } catch (e) {}
}

// ---------- 列表查询 ----------
const query = reactive({ keyword: '', fault_category: '', equipment_id: null })
const list = ref([])
const loading = ref(false)
async function loadList() {
  loading.value = true
  try {
    const params = {}
    if (query.keyword) params.keyword = query.keyword
    if (query.fault_category) params.fault_category = query.fault_category
    if (query.equipment_id) params.equipment_id = query.equipment_id
    list.value = await request.get(`${base}`, { params })
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
}

// ---------- 统计 ----------
const monthNewCount = computed(() => {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth()
  return list.value.filter((x) => {
    if (!x.created_at) return false
    const d = new Date(x.created_at)
    return d.getFullYear() === y && d.getMonth() === m
  }).length
})
const recurrenceTotal = computed(() =>
  list.value.reduce((s, x) => s + (Number(x.recurrence_count) || 0), 0)
)

// ---------- 详情 ----------
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = reactive({})
const similarCases = ref([])
const similarLoading = ref(false)

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  similarCases.value = []
  Object.keys(detail).forEach((k) => { delete detail[k] })
  try {
    const d = await request.get(`${base}/${row.id}`)
    Object.assign(detail, d)
    // 浏览数自动 +1（后端 GET 时已自增，同步回列表）
    const target = list.value.find((x) => x.id === row.id)
    if (target && d.view_count != null) target.view_count = d.view_count
    loadSimilar(d)
  } catch (e) {} finally {
    detailLoading.value = false
  }
}

async function loadSimilar(d) {
  similarLoading.value = true
  try {
    const params = {}
    if (d.equipment_id) params.equipment_id = d.equipment_id
    if (d.fault_category) params.fault_category = d.fault_category
    if (d.id) params.exclude_id = d.id
    similarCases.value = await request.get(`${base}/similar`, { params })
  } catch (e) {
    similarCases.value = []
  } finally {
    similarLoading.value = false
  }
}

// ---------- 新建/编辑 ----------
const FORM_KEYS = ['title', 'fault_category', 'equipment_id', 'equipment_model', 'symptom', 'root_cause', 'solution', 'prevention', 'tags']
const formVisible = ref(false)
const formRef = ref(null)
const saving = ref(false)
const form = reactive({
  id: null, title: '', fault_category: 'mechanical', equipment_id: null, equipment_model: '',
  symptom: '', root_cause: '', solution: '', prevention: '', tags: '',
})
const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  fault_category: [{ required: true, message: '请选择故障分类', trigger: 'change' }],
  symptom: [{ required: true, message: '请输入故障现象', trigger: 'blur' }],
  root_cause: [{ required: true, message: '请输入根因', trigger: 'blur' }],
  solution: [{ required: true, message: '请输入处置措施', trigger: 'blur' }],
}
function resetForm() {
  Object.assign(form, {
    id: null, title: '', fault_category: 'mechanical', equipment_id: null, equipment_model: '',
    symptom: '', root_cause: '', solution: '', prevention: '', tags: '',
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

// ---------- 标记复发 ----------
async function onRecurrence(row) {
  try {
    await ElMessageBox.confirm(`确认将【${row.title}】标记为复发？`, '提示', { type: 'warning' })
    await request.post(`${base}/${row.id}/recurrence`)
    ElMessage.success('已标记复发')
    loadList()
  } catch (e) {}
}

// ---------- 从工单归档 ----------
const archiveDialogVisible = ref(false)
const archiveWorkOrderId = ref('')
const archiveLoading = ref(false)
async function onArchive() {
  if (!archiveWorkOrderId.value) {
    ElMessage.warning('请输入工单ID')
    return
  }
  archiveLoading.value = true
  try {
    const d = await request.post(`${base}/from-work-order/${archiveWorkOrderId.value}`)
    if (d && d.id) {
      // 后端已直接创建归档条目
      ElMessage.success('归档成功')
      archiveDialogVisible.value = false
      archiveWorkOrderId.value = ''
      loadList()
    } else {
      // 后端返回预填数据，自动填充到表单供用户确认后保存
      archiveDialogVisible.value = false
      archiveWorkOrderId.value = ''
      resetForm()
      FORM_KEYS.forEach((k) => { if (d && d[k] != null) form[k] = d[k] })
      form.id = null
      formVisible.value = true
      ElMessage.success('已从工单自动填充，请确认后保存')
    }
  } catch (e) {} finally {
    archiveLoading.value = false
  }
}

// ---------- 从8D报告归档 ----------
const d8ArchiveDialogVisible = ref(false)
const d8ArchiveId = ref(null)
const d8ArchiveCategory = ref(null)
const d8ArchiveTags = ref('')
const d8ArchiveLoading = ref(false)
const d8Reports = ref([])

async function loadD8Reports() {
  try {
    d8Reports.value = await listD8({ limit: 200 })
  } catch (e) {}
}

async function onD8Archive() {
  if (!d8ArchiveId.value) {
    ElMessage.warning('请选择8D报告')
    return
  }
  d8ArchiveLoading.value = true
  try {
    const payload = {}
    if (d8ArchiveCategory.value) payload.fault_category = d8ArchiveCategory.value
    if (d8ArchiveTags.value.trim()) payload.tags = d8ArchiveTags.value.trim()
    const d = await request.post(`${base}/from-d8/${d8ArchiveId.value}`, payload)
    ElMessage.success('归档成功')
    d8ArchiveDialogVisible.value = false
    d8ArchiveId.value = null
    d8ArchiveCategory.value = null
    d8ArchiveTags.value = ''
    loadList()
  } catch (e) {} finally {
    d8ArchiveLoading.value = false
  }
}

onMounted(async () => {
  await loadEquipments()
  await loadD8Reports()
  await loadList()
})
</script>

<style scoped>
.toolbar { margin-bottom: 12px; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-value { font-size: 26px; font-weight: 600; color: var(--app-text-primary); line-height: 1.4; }
.stat-label { font-size: 13px; color: var(--app-text-secondary); margin-top: 4px; }
.cell-truncate { color: var(--app-text-regular); }
.kb-tag { margin-right: 6px; margin-bottom: 4px; }
.kb-content { white-space: pre-wrap; word-break: break-all; color: var(--app-text-regular); line-height: 1.6; }
.similar-section { margin-top: 18px; }
.section-title { font-size: 14px; font-weight: 600; color: var(--app-text-primary); margin-bottom: 8px; padding-left: 8px; border-left: 3px solid var(--app-primary); }
</style>
