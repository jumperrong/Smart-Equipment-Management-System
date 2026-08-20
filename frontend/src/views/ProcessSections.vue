<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="设备组">
            <el-input v-model="query.equipment_group" placeholder="按设备组精确匹配" clearable style="width:200px" />
          </el-form-item>
          <el-form-item label="启用">
            <el-select v-model="query.is_active" placeholder="全部" clearable style="width:120px">
              <el-option :value="true" label="启用" />
              <el-option :value="false" label="停用" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="query.keyword" placeholder="名称/编码/说明" clearable style="width:200px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增工段</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="工段名称" min-width="140" />
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column label="设备组" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.equipment_group" size="small">{{ row.equipment_group }}</el-tag>
            <span v-else class="muted">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="采集模板" min-width="180">
          <template #default="{ row }">
            <span v-if="row.form_template_name">{{ row.form_template_name }}</span>
            <span v-else class="muted">未关联</span>
          </template>
        </el-table-column>
        <el-table-column label="标准工时" width="90" align="center">
          <template #default="{ row }">{{ row.standard_cycle_min ? row.standard_cycle_min + ' 分' : '—' }}</template>
        </el-table-column>
        <el-table-column label="理论UPH" width="90" align="center">
          <template #default="{ row }">{{ row.theoretical_uph || '—' }}</template>
        </el-table-column>
        <el-table-column label="资质要求" width="100">
          <template #default="{ row }">{{ row.required_skill_level || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="100" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite" size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="canWrite" size="small" link type="warning" @click="onToggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          :page-sizes="[20, 50, 100]"
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          @current-change="load"
          @size-change="load"
        />
      </div>
    </el-card>

    <!-- 新增/编辑工段 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑工段' : '新增工段'" width="680px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工段名称" prop="name">
              <el-input v-model="form.name" placeholder="如 精车工序" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工段编码">
              <el-input v-model="form.code" placeholder="如 SEC-LATHE（可选）" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备组">
              <el-input v-model="form.equipment_group" placeholder="如 lathe_group" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采集模板">
              <el-select v-model="form.form_template_id" filterable clearable placeholder="选择表单模板" style="width:100%">
                <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标准工时">
              <el-input-number v-model="form.standard_cycle_min" :min="0" :precision="1" controls-position="right" style="width:100%" />
              <span class="hint">分钟</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="理论UPH">
              <el-input-number v-model="form.theoretical_uph" :min="0" :precision="1" controls-position="right" style="width:100%" />
              <span class="hint">片/小时</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资质要求">
              <el-select v-model="form.required_skill_level" clearable placeholder="操作资质级别" style="width:100%">
                <el-option v-for="lvl in ['L1','L2','L3','L4','初级','中级','高级','专家']" :key="lvl" :label="lvl" :value="lvl" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="判定标准">
              <el-input v-model="form.acceptance_criteria" placeholder="如 CD 偏差±2nm,套刻误差<35nm" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="工段说明">
              <el-input v-model="form.description" type="textarea" :rows="2" placeholder="工艺段简要说明" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { formatTime } from '@/utils'
import {
  getProcessSections,
  createProcessSection,
  updateProcessSection,
  deleteProcessSection,
} from '@/api/process_section'
import { listFormTemplates } from '@/api/form_template'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('production.section_write'))
const canDelete = computed(() => userStore.can('production.section_delete'))

const loading = ref(false)
const list = ref([])
const total = ref(0)
const templates = ref([])

const query = reactive({
  equipment_group: '',
  is_active: undefined,
  keyword: '',
  page: 1,
  size: 20,
})

async function load() {
  loading.value = true
  try {
    const params = {
      equipment_group: query.equipment_group || undefined,
      is_active: query.is_active,
      keyword: query.keyword || undefined,
      skip: (query.page - 1) * query.size,
      limit: query.size,
    }
    const data = await getProcessSections(params)
    list.value = data
    total.value = data.length < query.size && query.page === 1 ? data.length : (query.page * query.size + (data.length === query.size ? 1 : 0))
  } catch (e) {
    // request 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  try {
    const data = await listFormTemplates({ limit: 500 })
    templates.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {}
}

// 新增/编辑
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null,
  name: '',
  code: '',
  equipment_group: '',
  form_template_id: null,
  standard_cycle_min: null,
  theoretical_uph: null,
  required_skill_level: '',
  acceptance_criteria: '',
  description: '',
  is_active: true,
})
const formRules = {
  name: [{ required: true, message: '请输入工段名称', trigger: 'blur' }],
}

function openDialog(row = null) {
  Object.assign(form, {
    id: null, name: '', code: '', equipment_group: '', form_template_id: null,
    standard_cycle_min: null, theoretical_uph: null, required_skill_level: '',
    acceptance_criteria: '', description: '', is_active: true,
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
      await updateProcessSection(payload.id, payload)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createProcessSection(payload)
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
    await ElMessageBox.confirm(`确认${action}工段「${row.name}」？`, `${action}确认`, { type: 'warning' })
    await updateProcessSection(row.id, { is_active: !row.is_active })
    ElMessage.success(`已${action}`)
    load()
  } catch (e) {}
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除工段「${row.name}」？被工序步骤或派工引用时无法删除。`,
      '删除确认',
      { type: 'error' },
    )
    await deleteProcessSection(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

onMounted(() => {
  load()
  loadTemplates()
})
</script>

<style scoped>
.toolbar { margin-bottom: 12px; }
.muted { color: #999; }
.hint { color: #999; font-size: 12px; margin-left: 6px; }
.pagination-bar { margin-top: 12px; display: flex; justify-content: flex-end; }
</style>
