<template>
  <div>
    <el-card shadow="never">
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">文档编号规则</span>
          <el-tag size="small" type="success">体系文控 · 编码格式定义</el-tag>
        </div>
        <div class="header-right">
          <el-button type="primary" size="small" @click="openEditor()">
            <el-icon><Plus /></el-icon> 新建规则
          </el-button>
        </div>
      </div>

      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        <template #title>
          <b>编号格式</b>：<code>{前缀}[-{年份}][-{月份}][-{机台码}]-{流水号}</code>
          <br />
          示例：<code>SOP-2026-001</code> / <code>SIP-ET-001</code> / <code>FORM-B202608-0001</code>
          <br />
          每条规则对应一个文控分类（SOP/SIP/SPEC/FORM/RECORD/EXTERN）；生成编号时自动递增流水号。
        </template>
      </el-alert>

      <el-table :data="list" stripe border size="small" v-loading="loading">
        <el-table-column prop="doc_class" label="文控分类" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ row.doc_class }}</el-tag>
            <span style="margin-left:6px">{{ classLabel(row.doc_class) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="prefix" label="前缀" width="100" />
        <el-table-column label="包含年份" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.use_year ? 'success' : 'info'" size="small">{{ row.use_year ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="包含月份" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.use_month ? 'success' : 'info'" size="small">{{ row.use_month ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="包含机台码" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.use_equipment_code ? 'success' : 'info'" size="small">{{ row.use_equipment_code ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="seq_width" label="流水号位数" width="100" align="center" />
        <el-table-column prop="next_seq" label="下一流水号" width="100" align="center" />
        <el-table-column label="预览" min-width="160">
          <template #default="{ row }">
            <code style="color:var(--el-color-primary)">{{ previewMap[row.doc_class] || '...' }}</code>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openEditor(row)">编辑</el-button>
            <el-button size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑/新建对话框 -->
    <el-dialog v-model="editorVisible" :title="editForm.id ? '编辑编号规则' : '新建编号规则'" width="520px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="文控分类">
          <el-select v-model="editForm.doc_class" placeholder="选择分类" :disabled="!!editForm.id" style="width:100%">
            <el-option v-for="c in availableClasses" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="前缀">
          <el-input v-model="editForm.prefix" placeholder="如 SOP / SIP / SPEC" />
        </el-form-item>
        <el-form-item label="包含年份">
          <el-switch v-model="editForm.use_year" />
        </el-form-item>
        <el-form-item label="包含月份">
          <el-switch v-model="editForm.use_month" />
        </el-form-item>
        <el-form-item label="包含机台码">
          <el-switch v-model="editForm.use_equipment_code" />
          <div style="font-size:11px;color:var(--el-text-color-secondary)">开启后生成编号时需传机台ID</div>
        </el-form-item>
        <el-form-item label="流水号位数">
          <el-input-number v-model="editForm.seq_width" :min="1" :max="8" />
          <span style="margin-left:8px">{{ '0'.repeat(editForm.seq_width || 3) }}~{{ '9'.repeat(editForm.seq_width || 3) }}</span>
        </el-form-item>
        <el-form-item v-if="editForm.id" label="下一流水号">
          <el-input-number v-model="editForm.next_seq" :min="1" />
          <div style="font-size:11px;color:var(--el-text-color-secondary)">手动调整流水号（如跳号后修正）</div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  listDocNoRules,
  createDocNoRule,
  updateDocNoRule,
  deleteDocNoRule,
  previewDocNo,
} from '@/api/doc_no_rules'

const loading = ref(false)
const list = ref([])
const previewMap = ref({})

const ALL_CLASSES = [
  { value: 'SOP', label: 'SOP 作业指导书' },
  { value: 'SIP', label: 'SIP 检验标准' },
  { value: 'SPEC', label: 'SPEC 规格书' },
  { value: 'FORM', label: 'FORM 表单模板' },
  { value: 'RECORD', label: 'RECORD 作业记录' },
  { value: 'EXTERN', label: 'EXTERN 外来文件' },
]
const classLabel = (c) => ALL_CLASSES.find((x) => x.value === c)?.label || c

const availableClasses = computed(() => {
  const used = new Set(list.value.map((r) => r.doc_class))
  return ALL_CLASSES.filter((c) => !used.has(c.value))
})

async function load() {
  loading.value = true
  try {
    list.value = await listDocNoRules()
    // 加载预览
    for (const r of list.value) {
      try {
        const p = await previewDocNo(r.doc_class)
        previewMap.value[r.doc_class] = p.doc_no
      } catch (e) {
        // ignore
      }
    }
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// ---- 编辑器 ----
const editorVisible = ref(false)
const saving = ref(false)
const editForm = reactive({
  id: null,
  doc_class: '',
  prefix: '',
  use_year: true,
  use_month: false,
  use_equipment_code: false,
  seq_width: 3,
  next_seq: 1,
  is_active: true,
  description: '',
})

function openEditor(row = null) {
  if (row) {
    Object.assign(editForm, {
      id: row.id,
      doc_class: row.doc_class,
      prefix: row.prefix,
      use_year: row.use_year,
      use_month: row.use_month,
      use_equipment_code: row.use_equipment_code,
      seq_width: row.seq_width,
      next_seq: row.next_seq,
      is_active: row.is_active,
      description: row.description || '',
    })
  } else {
    Object.assign(editForm, {
      id: null,
      doc_class: '',
      prefix: '',
      use_year: true,
      use_month: false,
      use_equipment_code: false,
      seq_width: 3,
      next_seq: 1,
      is_active: true,
      description: '',
    })
  }
  editorVisible.value = true
}

async function onSave() {
  if (!editForm.doc_class) return ElMessage.warning('请选择文控分类')
  if (!editForm.prefix) return ElMessage.warning('请输入前缀')
  saving.value = true
  try {
    const payload = {
      prefix: editForm.prefix,
      use_year: editForm.use_year,
      use_month: editForm.use_month,
      use_equipment_code: editForm.use_equipment_code,
      seq_width: editForm.seq_width,
      is_active: editForm.is_active,
      description: editForm.description || null,
    }
    if (editForm.id) {
      payload.next_seq = editForm.next_seq
      await updateDocNoRule(editForm.id, payload)
      ElMessage.success('已更新')
    } else {
      await createDocNoRule({ ...payload, doc_class: editForm.doc_class })
      ElMessage.success('已创建')
    }
    editorVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除分类【${row.doc_class}】的编号规则？`,
      '危险操作',
      { type: 'error' },
    )
    await deleteDocNoRule(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {}
}

onMounted(() => load())
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
