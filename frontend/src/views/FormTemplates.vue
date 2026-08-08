<template>
  <div>
    <el-card shadow="never">
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">表单模板管理</span>
          <el-tag size="small" type="success">替代 PDF 附件模式 · 模板定义 → 动态填写</el-tag>
        </div>
        <div class="header-right">
          <el-button v-if="canManage" type="primary" size="small" @click="openEditor()">
            <el-icon><Plus /></el-icon> 新建模板
          </el-button>
        </div>
      </div>

      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        <template #title>
          <b>什么是表单模板？</b>
          先在这里由管理员定义「工艺参数记录/交接班/检验记录」等表单结构（字段名/类型/必填/选项/单位/范围），
          还能上传一份<b>空白参考模板文件（PDF/Excel/图片）</b>作为填写时对照用。点击模板行的<b>「新建记录」</b>按钮即可直接基于该模板生成表单并填写，提交后自动归档到工艺文件。
        </template>
      </el-alert>

      <!-- 工具条 -->
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="分类">
            <el-select v-model="query.category" placeholder="全部" clearable style="width:140px">
              <el-option label="作业记录类" value="record" />
              <el-option label="通用表单类" value="guide" />
            </el-select>
          </el-form-item>
          <el-form-item label="适用机台">
            <el-select
              v-model="query.equipment_id"
              placeholder="全部（含通用）"
              clearable
              filterable
              style="width:220px"
              @visible-change="onEquipOpen"
            >
              <el-option
                v-for="e in equipmentOptions"
                :key="e.id"
                :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                :value="e.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.is_active" placeholder="全部" clearable style="width:120px">
              <el-option label="启用中" :value="true" />
              <el-option label="已停用" :value="false" />
            </el-select>
          </el-form-item>
          <el-form-item label="编码">
            <el-input v-model="query.code" placeholder="按编码精确匹配" clearable style="width:160px" />
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="query.keyword" placeholder="模板名称" clearable style="width:180px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column label="编码" width="180">
          <template #default="{ row }">
            <span v-if="row.code">{{ row.code }}</span>
            <span style="color:#c0c4cc">(未填)</span>
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="200">
          <template #default="{ row }"><b>{{ row.name }}</b></template>
        </el-table-column>
        <el-table-column label="分类" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.category === 'record' ? 'primary' : 'info'">
              {{ row.category === 'record' ? '作业记录类' : '通用表单' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="适用机台" min-width="150">
          <template #default="{ row }">
            <span v-if="eqName(row.equipment_id)">{{ eqName(row.equipment_id) }}</span>
            <el-tag v-else size="small" type="success">通用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="字段数" width="80" align="center">
          <template #default="{ row }">{{ (row.field_schema || []).length }}</template>
        </el-table-column>
        <el-table-column label="参考模板" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.has_ref_file" size="small" type="success" effect="plain">已上传</el-tag>
            <span v-else style="color:#c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" size="small" type="success">启用</el-tag>
            <el-tag v-else size="small" type="info">停用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建人" width="80" align="center">
          <template #default="{ row }">{{ row.created_by ? '#' + row.created_by : '-' }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="440" fixed="right">
          <template #default="{ row }">
            <el-button v-if="isAdmin && row.is_active" size="small" link type="primary" @click="openFillDialog(row)">
              <el-icon><EditPen /></el-icon> 新建记录
            </el-button>
            <el-button size="small" link type="primary" @click="openEditor(row)">编辑</el-button>
            <el-button size="small" link type="warning" @click="onToggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" link type="success" @click="onUploadRef(row)">上传参考</el-button>
            <el-button
              v-if="row.has_ref_file"
              size="small"
              link
              type="info"
              @click="onDownloadRef(row)"
            >下载参考</el-button>
            <el-button size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 模板编辑 对话框 -->
    <el-dialog v-model="editorVisible" :title="editorTitle" width="960px" top="4vh" destroy-on-close>
      <el-form :model="editForm" :rules="editRules" ref="editFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="模板名称" prop="name">
              <el-input v-model="editForm.name" placeholder="例：ET-200 薄膜沉积工艺参数记录表" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板编码" prop="code">
              <el-input v-model="editForm.code" placeholder="可选，建议英文大写；跨环境匹配用" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="分类" prop="category">
              <el-select v-model="editForm.category" style="width:100%">
                <el-option label="作业记录类(record)" value="record" />
                <el-option label="通用表单类(guide)" value="guide" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="适用机台">
              <el-select
                v-model="editForm.equipment_id"
                placeholder="留空=通用模板，可用于任何机台"
                clearable
                filterable
                style="width:100%"
                @visible-change="onEquipOpen"
              >
                <el-option
                  v-for="e in equipmentOptions"
                  :key="e.id"
                  :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                  :value="e.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="模板说明">
              <el-input v-model="editForm.description" type="textarea" :rows="2" placeholder="填写说明、范围、注意事项等" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用状态">
              <el-switch v-model="editForm.is_active" :active-text="editForm.is_active ? '启用' : '停用'" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">
          <span style="font-weight:600">字段定义（按 seq 升序显示）</span>
        </el-divider>

        <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
          <el-button size="small" type="primary" plain @click="addField('text')"><el-icon><Plus /></el-icon> 文本</el-button>
          <el-button size="small" plain @click="addField('textarea')"><el-icon><Document /></el-icon> 多行文本</el-button>
          <el-button size="small" plain @click="addField('number')"><el-icon><DataLine /></el-icon> 数字</el-button>
          <el-button size="small" plain @click="addField('select')"><el-icon><ArrowDown /></el-icon> 下拉</el-button>
          <el-button size="small" plain @click="addField('radio')"><el-icon><List /></el-icon> 单选</el-button>
          <el-button size="small" plain @click="addField('date')"><el-icon><Calendar /></el-icon> 日期</el-button>
          <el-button size="small" plain @click="addField('datetime')"><el-icon><Clock /></el-icon> 日期时间</el-button>
          <el-button size="small" plain @click="addField('time')">时间</el-button>
          <el-button size="small" plain @click="addField('boolean')"><el-icon><CircleCheck /></el-icon> 是/否</el-button>
          <span style="flex:1" />
          <el-button size="small" link type="danger" :disabled="!selectKeys.length" @click="deleteSelected()">
            删除选中 ({{ selectKeys.length }})
          </el-button>
        </div>

        <el-table :data="editForm.field_schema" border size="small" row-key="key" @selection-change="onSelectChange" height="360">
          <el-table-column type="selection" width="40" reserve-selection />
          <el-table-column label="排序" width="110" align="center">
            <template #default="{ $index }">
              <el-button-group>
                <el-button size="small" @click="moveRow($index, -1)" :disabled="$index === 0">
                  <el-icon><Top /></el-icon>
                </el-button>
                <el-button size="small" @click="moveRow($index, +1)" :disabled="$index === editForm.field_schema.length - 1">
                  <el-icon><Bottom /></el-icon>
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
          <el-table-column label="seq" width="70" align="center">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column label="字段Key" width="150">
            <template #default="{ row }">
              <el-input v-model="row.key" placeholder="英文小写+下划线" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="显示名" width="140">
            <template #default="{ row }">
              <el-input v-model="row.label" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-select v-model="row.type" size="small" style="width:100%">
                <el-option v-for="t in fieldTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="必填" width="60" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.required" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="80">
            <template #default="{ row }">
              <el-input v-model="row.unit" placeholder="℃" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="数字范围" width="170">
            <template #default="{ row }">
              <el-input-number v-model="row.min" size="small" placeholder="min" style="width:76px;max-width:76px" controls-position="right" />
              <span style="margin:0 4px;color:#909399">~</span>
              <el-input-number v-model="row.max" size="small" placeholder="max" style="width:76px;max-width:76px" controls-position="right" />
            </template>
          </el-table-column>
          <el-table-column label="占位/默认值" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.placeholder" :placeholder="row.type==='boolean' ? '' : '占位提示'" size="small" style="width:50%;display:inline-block" />
              <el-input
                v-if="row.type !== 'boolean' && row.type !== 'select' && row.type !== 'radio'"
                v-model="row.default_value"
                placeholder="默认值"
                size="small"
                style="width:48%;display:inline-block;margin-left:4px"
              />
            </template>
          </el-table-column>
          <el-table-column label="选项(label=value)" min-width="220">
            <template #default="{ row }">
              <template v-if="row.type === 'select' || row.type === 'radio'">
                <el-input
                  v-model="row._optionsStr"
                  placeholder="格式：A班=A;B班=B;C班=C"
                  size="small"
                  @blur="parseOptions(row)"
                />
                <div style="font-size:11px;color:#909399">{{ describeOptions(row.options) }}</div>
              </template>
              <span v-else style="color:#c0c4cc">(无)</span>
            </template>
          </el-table-column>
        </el-table>

        <div style="height:10px" />
        <el-alert type="warning" :closable="false" show-icon>
          <template #title>
            小提示：<b>字段 Key</b> 在模板内必须唯一（建议英文如 batch_no / chamber_temp）；
            下拉/单选请填 <b>选项</b>，格式为 <code>标签1=值1;标签2=值2</code>（离开输入框会自动解析）。
          </template>
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建记录（结构化填写）对话框 -->
    <el-dialog v-model="fillDialogVisible" title="基于模板新建记录" width="960px" top="4vh" destroy-on-close>
      <div v-if="fillForm._template">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div>
            <el-tag type="success" size="small">模板：{{ fillForm._template.name }}</el-tag>
            <el-tag v-if="fillForm._template.code" size="small" style="margin-left:4px">{{ fillForm._template.code }}</el-tag>
          </div>
          <el-button v-if="fillForm._template.has_ref_file" size="small" type="info" plain @click="onDownloadRef(fillForm._template)">
            <el-icon><Download /></el-icon> 下载参考模板对照
          </el-button>
        </div>

        <el-form :model="fillForm.meta" label-width="100px" style="background:#f8f9fb;padding:14px;border-radius:6px;margin-bottom:12px">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="关联机台">
                <el-select v-model="fillForm.meta.equipment_id" filterable required style="width:100%" @visible-change="onEquipOpen">
                  <el-option
                    v-for="e in equipmentOptions"
                    :key="e.id"
                    :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                    :value="e.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="批次号"><el-input v-model="fillForm.meta.batch_no" placeholder="例：B20260807-01" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="班次">
                <el-select v-model="fillForm.meta.shift" placeholder="选择班次" clearable style="width:100%">
                  <el-option label="A 班" value="A" /><el-option label="B 班" value="B" /><el-option label="C 班" value="C" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="生产日期">
                <el-date-picker v-model="fillForm.meta.production_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="16">
              <el-form-item label="记录标题">
                <el-input v-model="fillForm.title" placeholder="留空将自动生成：【模板名】-机台-日期/批次" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="备注">
                <el-input v-model="fillForm.remark" type="textarea" :rows="2" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <el-divider content-position="left"><span style="font-weight:600">填写字段</span></el-divider>
        <el-form :model="fillForm.values" label-width="140px" size="default">
          <template v-for="f in fillForm._template.field_schema" :key="f.key">
            <el-form-item
              :label="(f.required ? '* ' : '') + f.label + (f.unit ? ` (${f.unit})` : '')"
              :prop="f.key"
            >
              <el-input
                v-if="f.type === 'text'"
                v-model="fillForm.values[f.key]"
                :placeholder="f.placeholder || `请输入${f.label}`"
                style="width:60%"
              />
              <el-input
                v-else-if="f.type === 'textarea'"
                v-model="fillForm.values[f.key]"
                type="textarea"
                :rows="3"
                :placeholder="f.placeholder || `请输入${f.label}`"
                style="width:60%"
              />
              <el-input-number
                v-else-if="f.type === 'number'"
                v-model="fillForm.values[f.key]"
                :min="f.min !== null ? f.min : undefined"
                :max="f.max !== null ? f.max : undefined"
                controls-position="right"
                style="width:240px"
              />
              <el-select
                v-else-if="f.type === 'select'"
                v-model="fillForm.values[f.key]"
                :placeholder="f.placeholder || `请选择${f.label}`"
                clearable
                style="width:300px"
              >
                <el-option v-for="o in f.options" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
              <el-radio-group v-else-if="f.type === 'radio'" v-model="fillForm.values[f.key]">
                <el-radio v-for="o in f.options" :key="o.value" :label="o.value">{{ o.label }}</el-radio>
              </el-radio-group>
              <el-date-picker
                v-else-if="f.type === 'date'"
                v-model="fillForm.values[f.key]"
                type="date"
                value-format="YYYY-MM-DD"
                :placeholder="f.placeholder || `请选择${f.label}`"
                style="width:240px"
              />
              <el-date-picker
                v-else-if="f.type === 'datetime'"
                v-model="fillForm.values[f.key]"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                :placeholder="f.placeholder || `请选择${f.label}`"
                style="width:260px"
              />
              <el-time-picker
                v-else-if="f.type === 'time'"
                v-model="fillForm.values[f.key]"
                value-format="HH:mm:ss"
                :placeholder="f.placeholder || `请选择${f.label}`"
                style="width:220px"
              />
              <el-switch v-else-if="f.type === 'boolean'" v-model="fillForm.values[f.key]" active-text="是" inactive-text="否" />
              <span v-else style="color:#909399">未知字段类型：{{ f.type }}</span>
            </el-form-item>
          </template>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="fillDialogVisible = false">取消</el-button>
        <el-button :loading="fillSubmitting" @click="submitFill(false)">保存草稿</el-button>
        <el-button :loading="fillSubmitting" type="primary" @click="submitFill(true)">提交（不可修改）</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import {
  Plus, Document, DataLine, ArrowDown, List, Calendar, Clock, CircleCheck, Top, Bottom, EditPen, Download,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listFormTemplates,
  createFormTemplate,
  updateFormTemplate,
  deleteFormTemplate,
  uploadTemplateRefFile,
  downloadTemplateRefFile,
  createFormRecord,
} from '@/api/form_template'
import { listEquipments } from '@/api/equipment'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canManage = computed(() => userStore.can('form_template.manage'))
const isAdmin = computed(() => userStore.role === 'admin')

// ---------- 列表 ----------
const list = ref([])
const loading = ref(false)
const query = reactive({
  category: '', equipment_id: null, is_active: '', code: '', keyword: '',
})
const equipmentOptions = ref([])
const eqMap = computed(() => {
  const m = {}
  equipmentOptions.value.forEach((e) => { m[e.id] = e.name })
  return m
})
const eqName = (id) => (id ? eqMap.value[id] || null : null)

async function onEquipOpen(v) {
  if (v && !equipmentOptions.value.length) {
    equipmentOptions.value = await listEquipments({ limit: 500 })
  }
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (query.category) params.category = query.category
    if (query.equipment_id) params.equipment_id = query.equipment_id
    if (query.is_active !== '') params.is_active = query.is_active
    if (query.code) params.code = query.code
    if (query.keyword) params.keyword = query.keyword
    const rows = await listFormTemplates(params)
    list.value = rows.map((r) => {
      r.field_schema = r.field_schema || []
      return r
    })
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  Object.assign(query, { category: '', equipment_id: null, is_active: '', code: '', keyword: '' })
  load()
}

// ---------- 编辑 ----------
const editorVisible = ref(false)
const editFormRef = ref(null)
const saving = ref(false)
const editingId = ref(null)
const editorTitle = computed(() => (editingId.value ? '编辑模板' : '新建模板'))
const fieldTypes = [
  { label: '文本', value: 'text' },
  { label: '多行文本', value: 'textarea' },
  { label: '数字', value: 'number' },
  { label: '下拉', value: 'select' },
  { label: '单选', value: 'radio' },
  { label: '日期', value: 'date' },
  { label: '日期时间', value: 'datetime' },
  { label: '时间', value: 'time' },
  { label: '是/否', value: 'boolean' },
]
function makeField(type = 'text') {
  return {
    key: `field_${Date.now().toString(36)}${Math.floor(Math.random() * 100)}`,
    type,
    label: '新字段',
    required: false,
    placeholder: '',
    default_value: null,
    options: null,
    _optionsStr: '',
    unit: '',
    min: null,
    max: null,
    seq: 0,
  }
}
const selectKeys = ref([])
function onSelectChange(rows) { selectKeys.value = rows.map((r) => r.key) }

function defaultEditForm() {
  return reactive({
    name: '',
    code: '',
    category: 'record',
    equipment_id: null,
    description: '',
    is_active: true,
    field_schema: [],
  })
}
const editForm = defaultEditForm()
const editRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
}

function openEditor(row) {
  editingId.value = row ? row.id : null
  Object.assign(editForm, defaultEditForm())
  editForm.field_schema = []
  selectKeys.value = []
  if (row) {
    Object.assign(editForm, {
      name: row.name,
      code: row.code || '',
      category: row.category,
      equipment_id: row.equipment_id,
      description: row.description || '',
      is_active: row.is_active,
      field_schema: [],
    })
    ;(row.field_schema || []).forEach((f) => {
      const nf = {
        key: f.key, type: f.type, label: f.label, required: !!f.required,
        placeholder: f.placeholder || '', default_value: f.default_value ?? null,
        options: f.options || null, unit: f.unit || '',
        min: f.min ?? null, max: f.max ?? null, seq: f.seq ?? 0,
        _optionsStr: '',
      }
      if (nf.options && Array.isArray(nf.options)) {
        nf._optionsStr = nf.options.map((o) => `${o.label}=${o.value}`).join(';')
      }
      editForm.field_schema.push(nf)
    })
  }
  editorVisible.value = true
}

function addField(type) {
  const f = makeField(type)
  // 若为 select/radio 预填一条示例
  if (type === 'select' || type === 'radio') {
    f.options = [{ label: '选项A', value: 'A' }, { label: '选项B', value: 'B' }]
    f._optionsStr = '选项A=A;选项B=B'
  }
  editForm.field_schema.push(f)
}

function moveRow(idx, delta) {
  const target = idx + delta
  if (target < 0 || target >= editForm.field_schema.length) return
  const arr = editForm.field_schema
  const tmp = arr[idx]
  arr.splice(idx, 1)
  arr.splice(target, 0, tmp)
}

function deleteSelected() {
  if (!selectKeys.value.length) return
  const keys = new Set(selectKeys.value)
  editForm.field_schema = editForm.field_schema.filter((f) => !keys.has(f.key))
  selectKeys.value = []
}

function parseOptions(row) {
  const s = (row._optionsStr || '').trim()
  if (!s) { row.options = null; return }
  const out = []
  s.split(/[;；\n]/).forEach((seg) => {
    const [a, b] = seg.split('=', 2)
    const label = (a || '').trim()
    const value = (b || '').trim()
    if (label && value) out.push({ label, value })
  })
  row.options = out.length ? out : null
  // 回写：规范格式
  if (row.options) {
    row._optionsStr = row.options.map((o) => `${o.label}=${o.value}`).join(';')
  }
}

function describeOptions(opts) {
  if (!opts || !opts.length) return ''
  return opts.slice(0, 5).map((o) => `${o.label}(${o.value})`).join('、') + (opts.length > 5 ? '…' : '')
}

async function onSave() {
  await editFormRef.value?.validate()
  // 字段校验
  const keys = new Set()
  for (let i = 0; i < editForm.field_schema.length; i++) {
    const f = editForm.field_schema[i]
    f.key = (f.key || '').trim()
    if (!f.key) throw new ElMessage.error(`第 ${i + 1} 行：字段 Key 不能为空`)
    if (keys.has(f.key)) throw new ElMessage.error(`字段 Key 重复：${f.key}`)
    keys.add(f.key)
    f.label = (f.label || '').trim() || f.key
    if ((f.type === 'select' || f.type === 'radio')) {
      parseOptions(f)
      if (!f.options || !f.options.length) {
        throw new ElMessage.error(`字段 [${f.label}] 为${f.type === 'select' ? '下拉' : '单选'}，但未设置任何选项`)
      }
    }
    // 写回 seq（按当前位置）
    f.seq = i + 1
  }
  // 剥离 _optionsStr
  const toSubmit = JSON.parse(JSON.stringify({
    name: editForm.name,
    code: editForm.code || null,
    category: editForm.category,
    equipment_id: editForm.equipment_id || null,
    description: editForm.description || null,
    is_active: !!editForm.is_active,
    field_schema: editForm.field_schema.map(({ _optionsStr, ...rest }) => rest),
  }))
  saving.value = true
  try {
    if (editingId.value) {
      await updateFormTemplate(editingId.value, toSubmit)
      ElMessage.success('已更新模板')
    } else {
      await createFormTemplate(toSubmit)
      ElMessage.success('已创建模板')
    }
    editorVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onToggleActive(row) {
  try {
    await ElMessageBox.confirm(
      `确定要把模板「${row.name}」切换为 ${row.is_active ? '停用' : '启用'} 吗？${!row.is_active ? '启用后操作员可使用它生成记录' : '停用后操作员无法新建记录，但历史记录仍可查看'}`,
      '提示', { type: 'warning' },
    )
  } catch { return }
  await updateFormTemplate(row.id, { is_active: !row.is_active })
  ElMessage.success('已更新状态')
  load()
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`删除模板『${row.name}』？若模板下已有填写记录将无法删除(此时应先停用)。`, '危险操作', { type: 'error' })
  } catch { return }
  await deleteFormTemplate(row.id)
  ElMessage.success('已删除')
  load()
}

// ---------- 参考模板文件 ----------
function onUploadRef(row) {
  const real = document.createElement('input')
  real.type = 'file'
  real.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.txt,.csv,.zip,.rar'
  real.onchange = async () => {
    const f = real.files && real.files[0]
    if (!f) return
    try {
      await uploadTemplateRefFile(row.id, f)
      ElMessage.success('已上传参考模板')
      load()
    } catch { /* 已 toast */ }
  }
  real.click()
}

async function onDownloadRef(row) {
  try {
    await downloadTemplateRefFile(row.id, row.ref_original_name)
  } catch (e) { ElMessage.error(e?.message || '下载失败') }
}

// ---------- 基于模板新建记录 ----------
const fillDialogVisible = ref(false)
const fillSubmitting = ref(false)
const fillForm = reactive({
  _template: null,
  title: '',
  remark: '',
  meta: { equipment_id: null, batch_no: '', shift: '', production_date: '' },
  values: {},
})

function openFillDialog(row) {
  fillForm._template = row
  fillForm.title = ''
  fillForm.remark = ''
  fillForm.meta = {
    equipment_id: row.equipment_id || null,
    batch_no: '',
    shift: '',
    production_date: '',
  }
  // 初始化字段默认值
  fillForm.values = {}
  ;(row.field_schema || []).forEach((f) => {
    if (f.default_value !== null && f.default_value !== undefined) {
      fillForm.values[f.key] = f.default_value
    } else if (f.type === 'boolean') {
      fillForm.values[f.key] = false
    } else {
      fillForm.values[f.key] = null
    }
  })
  // 预加载设备列表
  if (!equipmentOptions.value.length) {
    onEquipOpen(true)
  }
  fillDialogVisible.value = true
}

async function submitFill(doSubmit) {
  if (!fillForm._template) return
  if (!fillForm.meta.equipment_id) {
    ElMessage.error('请先填写关联机台')
    return
  }
  const valuesArr = Object.keys(fillForm.values)
    .filter((k) => fillForm.values[k] !== undefined && fillForm.values[k] !== null && fillForm.values[k] !== '')
    .map((k) => ({ field_key: k, field_value: fillForm.values[k] }))
  const payload = {
    template_id: fillForm._template.id,
    equipment_id: fillForm.meta.equipment_id,
    title: fillForm.title || null,
    batch_no: fillForm.meta.batch_no || null,
    shift: fillForm.meta.shift || null,
    production_date: fillForm.meta.production_date || null,
    remark: fillForm.remark || null,
    values: valuesArr,
    auto_submit: !!doSubmit,
    link_process_doc: true,
  }
  fillSubmitting.value = true
  try {
    const rec = await createFormRecord(payload)
    if (doSubmit) ElMessage.success(`已提交：#${rec.id} ${rec.title}`)
    else ElMessage.success(`已保存草稿：#${rec.id} ${rec.title}`)
    fillDialogVisible.value = false
  } finally {
    fillSubmitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header { display:flex;align-items:center;justify-content:space-between;margin-bottom:8px }
.toolbar { margin-bottom:10px }
:deep(.el-table th .cell) { white-space: nowrap; }
</style>
