<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" class="mb-12">
      <template #content>
        <span class="ph-title">{{ wo.order_no }}</span>
        <el-tag :type="woTypeTag(wo.type)" size="small" effect="dark" style="margin-left:8px">{{ woTypeLabel(wo.type) }}</el-tag>
        <el-tag :type="woStatusTag(wo.status)" size="small" style="margin-left:6px">{{ woStatusLabel(wo.status) }}</el-tag>
        <span class="ph-sub">设备: {{ eqName }}</span>
      </template>
      <template #extra>
        <el-button v-if="canWrite" size="small" @click="openStatusDialog">流转状态</el-button>
      </template>
    </el-page-header>

    <el-row :gutter="14">
      <!-- 左：工单信息 + 故障分析 + 5Why -->
      <el-col :span="15">
        <el-card shadow="never" class="mb-12">
          <template #header><span class="card-title">工单信息</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="标题">{{ wo.title }}</el-descriptions-item>
            <el-descriptions-item label="工单号">{{ wo.order_no }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ woTypeLabel(wo.type) }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ woStatusLabel(wo.status) }}</el-descriptions-item>
            <el-descriptions-item label="紧急度">
              <el-tag :type="urgencyTag(wo.urgency)" effect="light" size="small">{{ urgencyLabel(wo.urgency) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(wo.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="计划开始">{{ formatTime(wo.planned_start) }}</el-descriptions-item>
            <el-descriptions-item label="计划结束">{{ formatTime(wo.planned_end) }}</el-descriptions-item>
            <el-descriptions-item label="实际开始">{{ formatTime(wo.actual_start) }}</el-descriptions-item>
            <el-descriptions-item label="实际结束">{{ formatTime(wo.actual_end) }}</el-descriptions-item>
            <el-descriptions-item label="完成时间">{{ formatTime(wo.completed_at) }}</el-descriptions-item>
            <el-descriptions-item label="持续时长">
              <el-tag
                v-if="wo.duration_text"
                :type="wo.status === 'COMPLETED' || wo.status === 'CANCELLED' ? 'success' : (wo.duration_hours >= 48 ? 'danger' : wo.duration_hours >= 24 ? 'warning' : 'success')"
                effect="light"
                size="small"
              >{{ wo.duration_text }}</el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ wo.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ wo.remark || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never" class="mb-12">
          <template #header>
            <div class="card-head">
              <span class="card-title">故障根因分析 (5Why)</span>
              <el-button v-if="canWrite" size="small" type="primary" @click="openAnalysisDialog">编辑分析</el-button>
            </div>
          </template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="故障分类">{{ wo.fault_category ? faultCategoryLabel(wo.fault_category) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="根因">{{ wo.root_cause || '-' }}</el-descriptions-item>
            <el-descriptions-item label="处置措施">{{ wo.solution || '-' }}</el-descriptions-item>
            <el-descriptions-item label="预防措施">{{ wo.prevention || '-' }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="analysis.five_whys.length" class="why-block">
            <div v-for="(fw, i) in analysis.five_whys" :key="i" class="why-item">
              <div class="why-q">Q{{ fw.seq }}: {{ fw.question }}</div>
              <div class="why-a">A: {{ fw.answer || '-' }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无 5Why 分析" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右：备件领用 -->
      <el-col :span="9">
        <el-card shadow="never" class="mb-12">
          <template #header>
            <div class="card-head">
              <span class="card-title">备件领用</span>
              <el-button v-if="canWrite" size="small" type="primary" @click="openUsageDialog">领用备件</el-button>
            </div>
          </template>
          <el-table :data="wo.spare_usages || []" stripe size="small" border>
            <el-table-column label="备件" min-width="140">
              <template #default="{ row }">{{ row.spare_part ? `${row.spare_part.sku} ${row.spare_part.name}` : `#${row.spare_part_id}` }}</template>
            </el-table-column>
            <el-table-column prop="qty" label="数量" width="70" />
            <el-table-column prop="remark" label="备注" min-width="100" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 流转状态 -->
    <el-dialog v-model="statusDialogVisible" title="流转工单状态" width="440px">
      <el-form :model="statusForm" label-width="90px">
        <el-form-item label="当前状态">
          <el-tag :type="woStatusTag(wo.status)">{{ woStatusLabel(wo.status) }}</el-tag>
        </el-form-item>
        <el-form-item label="目标状态">
          <el-select v-model="statusForm.status" style="width:100%">
            <el-option v-for="s in WORK_ORDER_STATUS_OPTIONS" :key="s" :label="woStatusLabel(s)" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="statusForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="statusSaving" @click="onStatus">确认</el-button>
      </template>
    </el-dialog>

    <!-- 故障分析 -->
    <el-dialog v-model="analysisDialogVisible" title="故障根因分析 (5Why)" width="760px">
      <el-form :model="analysis" label-width="100px">
        <el-form-item label="故障分类">
          <el-select v-model="analysis.fault_category" clearable placeholder="选择分类" style="width:100%">
            <el-option v-for="c in FAULT_CATEGORY_OPTIONS" :key="c" :label="faultCategoryLabel(c)" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="根因"><el-input v-model="analysis.root_cause" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="处置措施"><el-input v-model="analysis.solution" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="预防措施"><el-input v-model="analysis.prevention" type="textarea" :rows="2" /></el-form-item>
        <el-divider>5 Why 追问</el-divider>
        <div v-for="(fw, i) in analysis.five_whys" :key="i" class="why-edit-row">
          <el-input v-model="fw.seq" placeholder="序号" style="width:70px" />
          <el-input v-model="fw.question" placeholder="为什么...?" style="flex:1;margin:0 8px" />
          <el-input v-model="fw.answer" placeholder="原因" style="flex:1" />
          <el-button size="small" link type="danger" @click="analysis.five_whys.splice(i,1)" style="margin-left:6px">删</el-button>
        </div>
        <el-button size="small" type="primary" plain @click="addWhy" style="margin-top:8px">+ 添加一条追问</el-button>
      </el-form>
      <template #footer>
        <el-button @click="analysisDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="analysisSaving" @click="onSaveAnalysis">保存分析</el-button>
      </template>
    </el-dialog>

    <!-- 领用备件 -->
    <el-dialog v-model="usageDialogVisible" title="领用备件" width="460px">
      <el-form :model="usageForm" :rules="usageRules" ref="usageFormRef" label-width="90px">
        <el-form-item label="备件" prop="spare_part_id">
          <el-select v-model="usageForm.spare_part_id" filterable placeholder="搜索备件" style="width:100%" @visible-change="onUsageSelectOpen">
            <el-option v-for="p in partOptions" :key="p.id" :label="`${p.sku} - ${p.name} (库存:${p.current_stock})`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="qty"><el-input-number v-model="usageForm.qty" :min="1" style="width:100%" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="usageForm.remark" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="usageDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="usageSaving" @click="onUsage">确认领用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getWorkOrder, updateWorkOrder, saveFaultAnalysis, addSpareUsage,
} from '@/api/work_order'
import { listEquipments } from '@/api/equipment'
import { listSpareParts } from '@/api/spare_part'
import { useUserStore } from '@/stores'
import {
  WORK_ORDER_STATUS_OPTIONS, FAULT_CATEGORY_OPTIONS,
  woTypeLabel, woTypeTag, woStatusLabel, woStatusTag, faultCategoryLabel, formatTime,
  urgencyLabel, urgencyTag,
} from '@/utils'

const route = useRoute()
const userStore = useUserStore()
const canWrite = computed(() => userStore.can('work_order.write'))
const woId = Number(route.params.id)

const loading = ref(false)
const wo = ref({})
const equipments = ref([])
const eqName = computed(() => {
  const e = equipments.value.find((x) => x.id === wo.value.equipment_id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${wo.value.equipment_id || ''}`
})
const analysis = reactive({ fault_category: null, root_cause: '', solution: '', prevention: '', five_whys: [] })

async function load() {
  loading.value = true
  try {
    wo.value = await getWorkOrder(woId)
    Object.assign(analysis, {
      fault_category: wo.value.fault_category || null,
      root_cause: wo.value.root_cause || '',
      solution: wo.value.solution || '',
      prevention: wo.value.prevention || '',
      five_whys: (wo.value.five_whys || []).map((f) => ({ seq: f.seq, question: f.question, answer: f.answer || '' })),
    })
  } finally {
    loading.value = false
  }
}

// ---- 流转状态 ----
const statusDialogVisible = ref(false)
const statusSaving = ref(false)
const statusForm = reactive({ status: '', remark: '' })
function openStatusDialog() {
  statusForm.status = wo.value.status
  statusForm.remark = wo.value.remark || ''
  statusDialogVisible.value = true
}
async function onStatus() {
  statusSaving.value = true
  try {
    const payload = { status: statusForm.status }
    if (statusForm.remark) payload.remark = statusForm.remark
    await updateWorkOrder(woId, payload)
    ElMessage.success('状态已更新')
    statusDialogVisible.value = false
    await load()
  } catch (e) {} finally {
    statusSaving.value = false
  }
}

// ---- 故障分析 ----
const analysisDialogVisible = ref(false)
const analysisSaving = ref(false)
function openAnalysisDialog() {
  analysisDialogVisible.value = true
}
function addWhy() {
  const nextSeq = (analysis.five_whys.length || 0) + 1
  if (nextSeq > 5) { ElMessage.warning('最多 5 条追问'); return }
  analysis.five_whys.push({ seq: nextSeq, question: '', answer: '' })
}
async function onSaveAnalysis() {
  analysisSaving.value = true
  try {
    await saveFaultAnalysis(woId, {
      fault_category: analysis.fault_category || undefined,
      root_cause: analysis.root_cause || undefined,
      solution: analysis.solution || undefined,
      prevention: analysis.prevention || undefined,
      five_whys: analysis.five_whys.filter((f) => f.question),
    })
    ElMessage.success('分析已保存')
    analysisDialogVisible.value = false
    await load()
  } catch (e) {} finally {
    analysisSaving.value = false
  }
}

// ---- 领用备件 ----
const usageDialogVisible = ref(false)
const usageSaving = ref(false)
const usageFormRef = ref(null)
const partOptions = ref([])
const usageForm = reactive({ spare_part_id: null, qty: 1, remark: '' })
const usageRules = {
  spare_part_id: [{ required: true, message: '请选择备件', trigger: 'change' }],
  qty: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}
async function onUsageSelectOpen(visible) {
  if (visible) {
    partOptions.value = await listSpareParts({ limit: 200 })
  }
}
function openUsageDialog() {
  Object.assign(usageForm, { spare_part_id: null, qty: 1, remark: '' })
  usageDialogVisible.value = true
}
async function onUsage() {
  try {
    await usageFormRef.value.validate()
    usageSaving.value = true
    await addSpareUsage(woId, { ...usageForm })
    ElMessage.success('领用成功，库存已自动扣减')
    usageDialogVisible.value = false
    await load()
  } catch (e) {} finally {
    usageSaving.value = false
  }
}

onMounted(async () => {
  equipments.value = await listEquipments({ limit: 500 })
  await load()
})
</script>

<style scoped>
.mb-12 { margin-bottom: 12px; }
.ph-title { font-weight: 600; font-size: 16px; }
.ph-sub { color: #909399; font-size: 13px; margin-left: 12px; }
.card-title { font-weight: 600; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.why-block { margin-top: 12px; }
.why-item { padding: 8px 12px; background: #f5f7fa; border-radius: 4px; margin-bottom: 8px; }
.why-q { font-weight: 600; color: #303133; }
.why-a { color: #606266; margin-top: 4px; }
.why-edit-row { display: flex; align-items: center; margin-bottom: 8px; }
</style>
