<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="启用">
            <el-select v-model="query.is_active" placeholder="全部" clearable style="width:120px">
              <el-option :value="true" label="启用" />
              <el-option :value="false" label="停用" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="query.keyword" placeholder="编号/名称/规格" clearable style="width:220px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="onSearch">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增产品</el-button>
            <el-button v-if="canWrite" type="warning" @click="openImportDialog">批量导入</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="pagedList" stripe v-loading="loading" border size="small" @row-click="showDetail">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="code" label="产品编号" width="140" />
        <el-table-column prop="name" label="产品名称" min-width="160" />
        <el-table-column prop="spec" label="规格型号" min-width="160">
          <template #default="{ row }">
            <span v-if="row.spec">{{ row.spec }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" align="center" />
        <el-table-column label="理论节拍" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.target_cycle">{{ row.target_cycle }} 秒</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.remark">{{ row.remark }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite" size="small" link type="primary" @click.stop="openDialog(row)">编辑</el-button>
            <el-button v-if="canWrite" size="small" link type="warning" @click.stop="onToggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click.stop="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="filteredTotal"
          :page-sizes="[20, 50, 100]"
          v-model:current-page="query.page"
          v-model:page-size="query.size"
        />
      </div>
    </el-card>

    <!-- 新增/编辑产品 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑产品' : '新增产品'" width="640px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="产品编号" prop="code">
              <el-input v-model="form.code" placeholder="如 P-2024-001（唯一）" :disabled="!!form.id" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产品名称" prop="name">
              <el-input v-model="form.name" placeholder="如 12英寸主控晶圆" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格型号">
              <el-input v-model="form.spec" placeholder="如 12inch / 28nm" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="form.unit" placeholder="片 / 颗 / 套" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="理论节拍">
              <el-input-number v-model="form.target_cycle" :min="0" :precision="2" controls-position="right" style="width:100%" />
              <span class="hint">秒/件</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="产品备注说明" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 产品详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detailTitle" size="480px">
      <div v-loading="detailLoading" class="detail-wrap">
        <el-descriptions :column="1" border size="default">
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="产品编号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="产品名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="规格型号">{{ detail.spec || '—' }}</el-descriptions-item>
          <el-descriptions-item label="单位">{{ detail.unit }}</el-descriptions-item>
          <el-descriptions-item label="理论节拍">{{ detail.target_cycle ? detail.target_cycle + ' 秒/件' : '—' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.is_active ? 'success' : 'info'" size="small">
              {{ detail.is_active ? '启用' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatTime(detail.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-drawer>

    <!-- 批量导入抽屉 -->
    <el-drawer v-model="importVisible" title="产品批量导入" size="640px">
      <div class="import-wrap">
        <el-alert type="info" :closable="false" show-icon class="import-tip">
          <template #title>支持两种方式</template>
          <div class="tip-body">
            <div>① <b>粘贴文本</b>：每行一条，列用逗号或制表符分隔，首行可为表头。</div>
            <div class="tip-cols">列顺序：产品编号*, 产品名称*, 规格型号, 单位, 理论节拍(秒), 启用, 备注</div>
            <div>② <b>上传 CSV</b>：标准 CSV（UTF-8），表头可中文或英文字段名。</div>
          </div>
        </el-alert>
        <el-tabs v-model="importTab">
          <el-tab-pane label="粘贴文本" name="paste">
            <el-input
              v-model="importText"
              type="textarea"
              :rows="14"
              placeholder="产品编号,产品名称,规格型号,单位,理论节拍,启用,备注&#10;P-2024-001,12英寸主控晶圆,12inch/28nm,片,30,是,例&#10;P-2024-002,8英寸电源管理芯片,8inch/90nm,片,25,是,例"
            />
          </el-tab-pane>
          <el-tab-pane label="上传 CSV" name="csv">
            <input ref="csvInputRef" type="file" accept=".csv,text/csv" @change="onCsvChange" />
            <div v-if="csvFileName" class="csv-name">已选文件：{{ csvFileName }}</div>
          </el-tab-pane>
        </el-tabs>
        <div class="import-preview-title">
          预览（前 5 行）
          <span class="muted">{{ importRows.length }} 行将被导入，{{ importSkipped.length }} 行将跳过</span>
        </div>
        <el-table :data="importPreview" size="small" border max-height="220">
          <el-table-column prop="code" label="产品编号" min-width="120" />
          <el-table-column prop="name" label="产品名称" min-width="160" />
          <el-table-column prop="spec" label="规格" min-width="120" />
          <el-table-column prop="unit" label="单位" width="70" align="center" />
          <el-table-column prop="target_cycle" label="节拍" width="80" align="center" />
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="结果" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row._ok ? 'success' : 'danger'" size="small">{{ row._ok ? '可导入' : '跳过' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importSaving" :disabled="!importRows.length" @click="onImport">提交导入</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { formatTime } from '@/utils'
import {
  getProducts,
  getProduct,
  createProduct,
  updateProduct,
  deleteProduct,
  batchImportProducts,
} from '@/api/product'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('production.product_write'))
const canDelete = computed(() => userStore.can('production.product_delete'))

const loading = ref(false)
const list = ref([])

const query = reactive({
  is_active: undefined,
  keyword: '',
  page: 1,
  size: 20,
})

const filteredList = computed(() => {
  let arr = list.value
  if (query.is_active !== undefined && query.is_active !== null && query.is_active !== '') {
    arr = arr.filter((r) => !!r.is_active === !!query.is_active)
  }
  const kw = (query.keyword || '').trim().toLowerCase()
  if (kw) {
    arr = arr.filter((r) =>
      [r.code, r.name, r.spec].some((v) => (v || '').toLowerCase().includes(kw)),
    )
  }
  return arr
})
const filteredTotal = computed(() => filteredList.value.length)
const pagedList = computed(() => {
  const start = (query.page - 1) * query.size
  return filteredList.value.slice(start, start + query.size)
})

async function load() {
  loading.value = true
  try {
    const data = await getProducts({ active_only: false })
    list.value = Array.isArray(data) ? data : []
  } catch (e) {
    // request 拦截器已提示
  } finally {
    loading.value = false
  }
}

function onSearch() {
  query.page = 1
  load()
}

// 新增/编辑
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null,
  code: '',
  name: '',
  spec: '',
  unit: '片',
  target_cycle: null,
  remark: '',
  is_active: true,
})
const formRules = {
  code: [{ required: true, message: '请输入产品编号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
}

function openDialog(row = null) {
  Object.assign(form, {
    id: null, code: '', name: '', spec: '', unit: '片',
    target_cycle: null, remark: '', is_active: true,
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
      // 编辑时仅提交可更新字段
      const update = {
        name: payload.name,
        spec: payload.spec,
        unit: payload.unit,
        target_cycle: payload.target_cycle,
        remark: payload.remark,
        is_active: payload.is_active,
      }
      await updateProduct(payload.id, update)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createProduct(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}

async function onToggleActive(row) {
  const action = row.is_active ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}产品「${row.name}」？`, `${action}确认`, { type: 'warning' })
    await updateProduct(row.id, { is_active: !row.is_active })
    ElMessage.success(`已${action}`)
    load()
  } catch (e) {}
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除产品「${row.name}」？若被工艺路由或生产记录引用时无法删除。`,
      '删除确认',
      { type: 'error' },
    )
    await deleteProduct(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

// 详情抽屉
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailTitle = ref('产品详情')
const detail = reactive({})

async function showDetail(row, column, event) {
  if (event && event.target && event.target.closest('button')) return
  if (!row || !row.id) return
  detailVisible.value = true
  detailLoading.value = true
  Object.assign(detail, JSON.parse(JSON.stringify(row)))
  detailTitle.value = `产品详情 · ${row.code}（${row.name}）`
  try {
    const full = await getProduct(row.id)
    Object.assign(detail, full)
  } catch (e) {} finally {
    detailLoading.value = false
  }
}

// ---------- 批量导入 ----------
const importVisible = ref(false)
const importTab = ref('paste')
const importText = ref('')
const csvInputRef = ref(null)
const csvFileName = ref('')
const csvRows = ref([]) // CSV 解析结果
const importSaving = ref(false)

// 已存在 code 集合（导入预览时本地预跳过，服务端会再校验）
const existingCodes = computed(() => new Set(list.value.map((r) => r.code)))

// 解析单行文本（支持 tab 或逗号）
function parseLine(line) {
  if (!line) return null
  // 同时兼容 tab 与逗号，取分隔符出现位置优先
  let parts
  if (line.includes('\t')) parts = line.split('\t')
  else parts = line.split(',')
  return parts.map((s) => (s || '').trim())
}

// 文本 → 行对象
function textToRows(text) {
  if (!text || !text.trim()) return []
  const lines = text.split(/\r?\n/).filter((l) => l && l.trim())
  if (!lines.length) return []
  let startIdx = 0
  // 首行可能为表头
  const firstParsed = parseLine(lines[0])
  if (firstParsed && firstParsed.some((c) => ['产品编号', 'code', '产品名称', 'name'].includes(c.toLowerCase()))) {
    startIdx = 1
  }
  const rows = []
  for (let i = startIdx; i < lines.length; i++) {
    const p = parseLine(lines[i])
    if (!p) continue
    rows.push({
      code: p[0] || '',
      name: p[1] || '',
      spec: p[2] || '',
      unit: p[3] || '片',
      target_cycle: p[4] !== undefined && p[4] !== '' ? Number(p[4]) : null,
      is_active: !['否', '0', 'false', '停用'].includes((p[5] || '是').toLowerCase()),
      remark: p[6] || '',
    })
  }
  return rows
}

// 当前要导入的行（粘贴或 CSV 任选其一）
const importRowsRaw = computed(() => {
  if (importTab.value === 'paste') return textToRows(importText.value)
  return csvRows.value
})

// 标记可导入 / 跳过
const importRows = computed(() => importRowsRaw.value.filter((r) => r.code && r.name && !existingCodes.value.has(r.code)))
const importSkipped = computed(() => importRowsRaw.value.filter((r) => !r.code || !r.name || existingCodes.value.has(r.code)))
const importPreview = computed(() => {
  // 合并可导入与跳过，前 5 行
  return importRowsRaw.value.slice(0, 5).map((r) => ({
    ...r,
    _ok: !!(r.code && r.name && !existingCodes.value.has(r.code)),
  }))
})

function openImportDialog() {
  importTab.value = 'paste'
  importText.value = ''
  csvRows.value = []
  csvFileName.value = ''
  if (csvInputRef.value) csvInputRef.value.value = ''
  importVisible.value = true
}

// 简易 CSV 解析（不处理引号转义，足够覆盖内部用例）
function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter((l) => l !== undefined && l !== null)
  if (!lines.length) return []
  const header = (lines[0] || '').split(',').map((s) => (s || '').trim().toLowerCase())
  const hasHeader = header.some((h) => ['产品编号', 'code', '产品名称', 'name'].includes(h))
  const rows = []
  const start = hasHeader ? 1 : 0
  for (let i = start; i < lines.length; i++) {
    const parts = (lines[i] || '').split(',').map((s) => (s || '').trim())
    if (!parts.filter((x) => x).length) continue
    let obj
    if (hasHeader) {
      obj = {}
      header.forEach((h, idx) => {
        const v = parts[idx] || ''
        if (['产品编号', 'code'].includes(h)) obj.code = v
        else if (['产品名称', 'name'].includes(h)) obj.name = v
        else if (['规格型号', 'spec'].includes(h)) obj.spec = v
        else if (['单位', 'unit'].includes(h)) obj.unit = v
        else if (['理论节拍', 'target_cycle'].includes(h)) obj.target_cycle = v !== '' ? Number(v) : null
        else if (['启用', 'is_active'].includes(h)) obj.is_active = !['否', '0', 'false', '停用'].includes(v.toLowerCase())
        else if (['备注', 'remark'].includes(h)) obj.remark = v
      })
      // 兜底：若表头未识别，按列顺序补
      if (!obj.code) obj.code = parts[0]
      if (!obj.name) obj.name = parts[1]
      if (obj.spec === undefined) obj.spec = parts[2] || ''
      if (obj.unit === undefined) obj.unit = parts[3] || '片'
      if (obj.target_cycle === undefined) obj.target_cycle = parts[4] !== undefined && parts[4] !== '' ? Number(parts[4]) : null
      if (obj.is_active === undefined) obj.is_active = true
      if (obj.remark === undefined) obj.remark = parts[6] || ''
    } else {
      obj = {
        code: parts[0] || '',
        name: parts[1] || '',
        spec: parts[2] || '',
        unit: parts[3] || '片',
        target_cycle: parts[4] !== undefined && parts[4] !== '' ? Number(parts[4]) : null,
        is_active: !['否', '0', 'false', '停用'].includes((parts[5] || '是').toLowerCase()),
        remark: parts[6] || '',
      }
    }
    rows.push(obj)
  }
  return rows
}

function onCsvChange(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  csvFileName.value = file.name
  const reader = new FileReader()
  reader.onload = (ev) => {
    try {
      csvRows.value = parseCsv(String(ev.target.result || ''))
    } catch (err) {
      csvRows.value = []
      ElMessage.error('CSV 解析失败：' + (err && err.message ? err.message : '格式错误'))
    }
  }
  reader.readAsText(file, 'utf-8')
}

async function onImport() {
  if (!importRows.value.length) {
    ElMessage.warning('没有可导入的有效行（请检查必填字段、编号是否已存在）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认导入 ${importRows.value.length} 行产品？重复编号将自动跳过。`,
      '导入确认',
      { type: 'warning' },
    )
    importSaving.value = true
    const payload = importRows.value.map((r) => ({
      code: r.code,
      name: r.name,
      spec: r.spec || null,
      unit: r.unit || '片',
      target_cycle: typeof r.target_cycle === 'number' && !isNaN(r.target_cycle) ? r.target_cycle : null,
      is_active: !!r.is_active,
      remark: r.remark || null,
    }))
    const res = await batchImportProducts(payload)
    ElMessage.success(`导入完成：成功 ${res.ok} 条，跳过 ${res.failed} 条`)
    importVisible.value = false
    load()
  } catch (e) {} finally {
    importSaving.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.toolbar { margin-bottom: 12px; }
.muted { color: #999; }
.hint { color: #999; font-size: 12px; margin-left: 6px; }
.pagination-bar { margin-top: 12px; display: flex; justify-content: flex-end; }
.detail-wrap { padding: 0 8px; }
.import-wrap { padding: 0 8px; }
.import-tip { margin-bottom: 12px; }
.tip-body { font-size: 12px; line-height: 1.8; }
.tip-cols { color: #909399; }
.import-preview-title { font-weight: 600; margin: 12px 0 6px; display: flex; justify-content: space-between; align-items: center; }
.csv-name { margin-top: 8px; color: #67c23a; }
</style>
