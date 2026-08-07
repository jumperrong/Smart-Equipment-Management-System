<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab">
        <!-- 模板管理 -->
        <el-tab-pane label="点检模板" name="templates">
          <div class="toolbar">
            <el-button v-if="canWrite" type="success" size="small" @click="openTplDialog()">新建模板</el-button>
          </div>
          <el-table :data="templates" stripe v-loading="tplLoading" border size="small">
            <el-table-column prop="name" label="模板名称" min-width="160" />
            <el-table-column label="关联设备" width="160">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column label="频率" width="80">
              <template #default="{ row }">{{ frequencyLabel(row.frequency) }}</template>
            </el-table-column>
            <el-table-column label="检查项" width="80">
              <template #default="{ row }">{{ (row.items || []).length }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="doInspect(row)">点检</el-button>
                <el-button v-if="canDelete" size="small" link type="danger" @click="onDelTpl(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 点检记录 -->
        <el-tab-pane label="点检记录" name="records">
          <div class="toolbar">
            <el-form :inline="true" size="default">
              <el-form-item label="设备">
                <el-select v-model="recQuery.equipment_id" filterable clearable placeholder="全部" style="width:180px">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadRecords">查询</el-button>
              </el-form-item>
            </el-form>
          </div>
          <el-table :data="records" stripe v-loading="recLoading" border size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="模板" min-width="140">
              <template #default="{ row }">{{ tplName(row.template_id) }}</template>
            </el-table-column>
            <el-table-column label="设备" width="140">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column prop="shift" label="班次" width="70" />
            <el-table-column label="结果" width="80">
              <template #default="{ row }"><el-tag :type="row.overall_result === 'OK' ? 'success' : 'danger'" size="small">{{ row.overall_result }}</el-tag></template>
            </el-table-column>
            <el-table-column label="点检时间" width="160">
              <template #default="{ row }">{{ formatTime(row.inspect_time) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="90" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="viewRecord(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 模板编辑 -->
    <el-dialog v-model="tplDialogVisible" :title="tplForm.id ? '编辑模板' : '新建点检模板'" width="720px">
      <el-form :model="tplForm" :rules="tplRules" ref="tplFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="模板名称" prop="name"><el-input v-model="tplForm.name" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="关联设备">
              <el-select v-model="tplForm.equipment_id" filterable clearable placeholder="可选" style="width:100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="频率">
              <el-select v-model="tplForm.frequency" style="width:100%">
                <el-option v-for="f in FREQUENCY_OPTIONS" :key="f" :label="frequencyLabel(f)" :value="f" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24"><el-form-item label="说明"><el-input v-model="tplForm.description" /></el-form-item></el-col>
        </el-row>
        <el-divider>检查项</el-divider>
        <div v-for="(it, i) in tplForm.items" :key="i" class="item-row">
          <el-input-number v-model="it.seq" :min="0" controls-position="right" style="width:90px" />
          <el-input v-model="it.name" placeholder="检查项名称" style="flex:1;margin:0 8px" />
          <el-input v-model="it.standard" placeholder="标准/方法" style="flex:1" />
          <el-button size="small" link type="danger" @click="tplForm.items.splice(i,1)" style="margin-left:6px">删</el-button>
        </div>
        <el-button size="small" type="primary" plain @click="tplForm.items.push({ seq: tplForm.items.length + 1, name: '', standard: '', required: true })" style="margin-top:8px">+ 添加检查项</el-button>
      </el-form>
      <template #footer>
        <el-button @click="tplDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="tplSaving" @click="onSaveTpl">保存</el-button>
      </template>
    </el-dialog>

    <!-- 执行点检 -->
    <el-dialog v-model="inspectDialogVisible" :title="`执行点检：${inspectTemplate?.name || ''}`" width="720px">
      <el-form :model="inspectForm" label-width="100px">
        <el-form-item label="班次">
          <el-radio-group v-model="inspectForm.shift">
            <el-radio-button value="">不指定</el-radio-button>
            <el-radio-button value="A">A</el-radio-button>
            <el-radio-button value="B">B</el-radio-button>
            <el-radio-button value="C">C</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-divider>检查项结果</el-divider>
        <div v-for="(r, i) in inspectForm.results" :key="i" class="result-row">
          <div class="r-name">{{ i + 1 }}. {{ r.item_name }}</div>
          <el-radio-group v-model="r.result" size="small">
            <el-radio-button value="OK">OK</el-radio-button>
            <el-radio-button value="NG">NG</el-radio-button>
            <el-radio-button value="NA">N/A</el-radio-button>
          </el-radio-group>
          <el-input v-model="r.value" placeholder="实测值(可选)" style="width:160px;margin-left:8px" size="small" />
        </div>
        <el-form-item label="备注" style="margin-top:12px"><el-input v-model="inspectForm.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inspectDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="inspectSaving" @click="onSubmitInspect">提交点检</el-button>
      </template>
    </el-dialog>

    <!-- 查看记录 -->
    <el-dialog v-model="recordDialogVisible" title="点检记录详情" width="640px">
      <el-descriptions :column="2" border size="small" v-if="currentRecord">
        <el-descriptions-item label="模板">{{ tplName(currentRecord.template_id) }}</el-descriptions-item>
        <el-descriptions-item label="设备">{{ eqName(currentRecord.equipment_id) }}</el-descriptions-item>
        <el-descriptions-item label="班次">{{ currentRecord.shift || '-' }}</el-descriptions-item>
        <el-descriptions-item label="结果"><el-tag :type="currentRecord.overall_result === 'OK' ? 'success' : 'danger'" size="small">{{ currentRecord.overall_result }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(currentRecord.inspect_time) }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ currentRecord.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="currentRecord?.results || []" stripe size="small" border style="margin-top:12px">
        <el-table-column prop="item_name" label="检查项" min-width="140" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }"><el-tag :type="row.result === 'OK' ? 'success' : row.result === 'NA' ? 'info' : 'danger'" size="small">{{ row.result }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="value" label="实测值" width="120" />
        <el-table-column prop="remark" label="备注" min-width="120" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listTemplates, createTemplate, deleteTemplate,
  listRecords, createRecord, getRecord,
} from '@/api/inspection'
import { listEquipments } from '@/api/equipment'
import { useUserStore } from '@/stores'
import { FREQUENCY_OPTIONS, frequencyLabel, formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('inspection.template_write'))
const canDelete = computed(() => userStore.can('inspection.template_delete'))

const tab = ref('templates')
const equipments = ref([])
function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}

// ---- 模板 ----
const templates = ref([])
const tplLoading = ref(false)
async function loadTemplates() {
  tplLoading.value = true
  try { templates.value = await listTemplates({ limit: 200 }) } finally { tplLoading.value = false }
}
function tplName(id) {
  const t = templates.value.find((x) => x.id === id)
  return t ? t.name : `#${id}`
}

const tplDialogVisible = ref(false)
const tplSaving = ref(false)
const tplFormRef = ref(null)
const tplForm = reactive({ id: null, name: '', equipment_id: null, frequency: 'DAILY', description: '', is_active: true, items: [] })
const tplRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
}
function openTplDialog(row = null) {
  Object.assign(tplForm, { id: null, name: '', equipment_id: null, frequency: 'DAILY', description: '', is_active: true, items: [] })
  if (row) Object.assign(tplForm, JSON.parse(JSON.stringify(row)))
  tplDialogVisible.value = true
}
async function onSaveTpl() {
  try {
    await tplFormRef.value.validate()
    tplSaving.value = true
    const payload = JSON.parse(JSON.stringify(tplForm))
    payload.items = payload.items.filter((x) => x.name)
    await createTemplate(payload)
    ElMessage.success('已保存')
    tplDialogVisible.value = false
    loadTemplates()
  } catch (e) {} finally {
    tplSaving.value = false
  }
}
async function onDelTpl(row) {
  try {
    await ElMessageBox.confirm(`确认删除模板【${row.name}】？`, '提示', { type: 'warning' })
    await deleteTemplate(row.id)
    ElMessage.success('已删除')
    loadTemplates()
  } catch (e) {}
}

// ---- 执行点检 ----
const inspectDialogVisible = ref(false)
const inspectSaving = ref(false)
const inspectTemplate = ref(null)
const inspectForm = reactive({ shift: '', remark: '', results: [] })
function doInspect(tpl) {
  inspectTemplate.value = tpl
  inspectForm.shift = ''
  inspectForm.remark = ''
  inspectForm.results = (tpl.items || []).map((it) => ({
    item_id: it.id,
    item_name: it.name,
    result: 'OK',
    value: '',
    remark: '',
  }))
  inspectDialogVisible.value = true
}
async function onSubmitInspect() {
  if (!inspectForm.results.length) { ElMessage.warning('该模板无检查项'); return }
  inspectSaving.value = true
  try {
    const overall = inspectForm.results.some((r) => r.result === 'NG') ? 'NG' : 'OK'
    await createRecord({
      template_id: inspectTemplate.value.id,
      equipment_id: inspectTemplate.value.equipment_id || undefined,
      shift: inspectForm.shift || undefined,
      results: inspectForm.results,
      remark: inspectForm.remark || undefined,
    })
    ElMessage.success(`点检完成，整体结果：${overall}`)
    inspectDialogVisible.value = false
    await loadRecords()
    tab.value = 'records'
  } catch (e) {} finally {
    inspectSaving.value = false
  }
}

// ---- 记录 ----
const records = ref([])
const recLoading = ref(false)
const recQuery = reactive({ equipment_id: null })
async function loadRecords() {
  recLoading.value = true
  try {
    const params = {}
    if (recQuery.equipment_id) params.equipment_id = recQuery.equipment_id
    records.value = await listRecords(params)
  } finally {
    recLoading.value = false
  }
}

const recordDialogVisible = ref(false)
const currentRecord = ref(null)
async function viewRecord(row) {
  currentRecord.value = await getRecord(row.id)
  recordDialogVisible.value = true
}

onMounted(async () => {
  equipments.value = await listEquipments({ limit: 500 })
  await loadTemplates()
  await loadRecords()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.item-row { display: flex; align-items: center; margin-bottom: 8px; }
.result-row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px dashed #ebeef5; }
.r-name { flex: 1; }
</style>
