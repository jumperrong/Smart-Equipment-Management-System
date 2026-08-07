<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span style="font-weight:600">系统字典配置</span>
        <el-tag size="small" type="info">管理员可自定义厂区、区域、设备状态等选项</el-tag>
      </div>
    </template>

    <!-- 分类切换 -->
    <el-radio-group v-model="currentCategory" @change="loadItems" size="default">
      <el-radio-button v-for="c in categories" :key="c.value" :label="c.value">
        {{ c.label }}
      </el-radio-button>
    </el-radio-group>

    <div class="toolbar">
      <el-form :inline="true" size="default">
        <el-form-item label="状态">
          <el-select v-model="filterActive" clearable placeholder="全部" style="width:120px" @change="loadItems">
            <el-option label="启用" :value="true" />
            <el-option label="停用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadItems">查询</el-button>
          <el-button type="success" @click="openDialog()">新增字典项</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-table :data="list" stripe v-loading="loading" border size="small">
      <el-table-column prop="sort_order" label="排序" width="80" align="center" />
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="label" label="显示名称" min-width="160" />
      <el-table-column prop="value" label="值" width="160" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_system" type="warning" size="small">系统内置</el-tag>
          <el-tag v-else type="primary" size="small" effect="plain">自定义</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="120" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button size="small" link :type="row.is_active ? 'warning' : 'success'" @click="toggleActive(row)">
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
          <el-button v-if="!row.is_system" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 新增/编辑对话框 -->
  <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
    <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
      <el-form-item label="分类" prop="category">
        <el-select v-model="form.category" :disabled="!!form.id" style="width:100%">
          <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="编码" prop="code">
        <el-input v-model="form.code" :disabled="!!form.id" placeholder="英文/简写，如 FAB3" />
      </el-form-item>
      <el-form-item label="显示名称" prop="label">
        <el-input v-model="form.label" placeholder="如 FAB3 三厂区" />
      </el-form-item>
      <el-form-item label="值">
        <el-input v-model="form.value" placeholder="留空则等于编码" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" :max="9999" style="width:100%" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_active" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listCategories, listDictItems, createDictItem, updateDictItem, deleteDictItem,
} from '@/api/dictionary'

const categories = ref([])
const currentCategory = ref('factory')
const filterActive = ref(null)
const list = ref([])
const loading = ref(false)

const dialogVisible = ref(false)
const dialogTitle = ref('新增字典项')
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null, category: 'factory', code: '', label: '', value: '',
  sort_order: 0, is_active: true, remark: '',
})
const formRules = {
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  label: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
}

async function loadCategories() {
  categories.value = await listCategories()
}

async function loadItems() {
  loading.value = true
  try {
    const params = { category: currentCategory.value }
    if (filterActive.value !== null && filterActive.value !== '') {
      params.active_only = filterActive.value === true
    }
    list.value = await listDictItems(params)
  } finally {
    loading.value = false
  }
}

function openDialog(row = null) {
  dialogVisible.value = true
  if (row) {
    dialogTitle.value = `编辑字典项: ${row.label}`
    Object.assign(form, { ...row })
  } else {
    dialogTitle.value = '新增字典项'
    Object.assign(form, {
      id: null, category: currentCategory.value, code: '', label: '', value: '',
      sort_order: (list.value.length || 0), is_active: true, remark: '',
    })
  }
}

async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = { ...form }
    if (!payload.value) payload.value = payload.code
    if (form.id) {
      await updateDictItem(form.id, payload)
      ElMessage.success('已更新')
    } else {
      await createDictItem(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadItems()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  const action = row.is_active ? '停用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}字典项【${row.label}】？`, '提示', { type: 'warning' })
    await updateDictItem(row.id, { is_active: !row.is_active })
    ElMessage.success(`已${action}`)
    loadItems()
  } catch (e) {}
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除字典项【${row.label}】？`, '提示', { type: 'warning' })
    await deleteDictItem(row.id)
    ElMessage.success('已删除')
    loadItems()
  } catch (e) {}
}

onMounted(async () => {
  await loadCategories()
  await loadItems()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.toolbar { margin: 12px 0 8px; }
</style>
