<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab" type="border-card">
        <!-- ============ 8D 报告 ============ -->
        <el-tab-pane label="8D报告" name="d8">
          <div class="toolbar">
            <el-form :inline="true" :model="d8Query" size="default">
              <el-form-item label="设备">
                <el-select v-model="d8Query.equipment_id" filterable placeholder="全部设备" clearable style="width:200px">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="d8Query.status" placeholder="全部" clearable style="width:140px">
                  <el-option v-for="s in D8_STATUS_OPTIONS" :key="s" :label="d8StatusLabel(s)" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadD8">查询</el-button>
                <el-button v-if="canWriteD8" type="success" @click="openD8Dialog()">新建8D</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="d8List" stripe v-loading="d8Loading" border size="small">
            <el-table-column prop="report_no" label="报告编号" width="150" />
            <el-table-column label="设备" width="140">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="200" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="d8StatusTag(row.status)" size="small">{{ d8StatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canWriteD8" size="small" link type="primary" @click="openD8Dialog(row)">编辑</el-button>
                <el-button v-if="canWriteD8" size="small" link type="warning" :disabled="row.status === 'CLOSED'" @click="onD8Close(row)">关闭</el-button>
                <el-button v-if="canDeleteD8" size="small" link type="danger" @click="onD8Delete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ============ FMEA 分析 ============ -->
        <el-tab-pane label="FMEA分析" name="fmea">
          <div class="toolbar">
            <el-form :inline="true" :model="fmeaQuery" size="default">
              <el-form-item label="设备">
                <el-select v-model="fmeaQuery.equipment_id" filterable placeholder="全部设备" clearable style="width:200px">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadFmea">查询</el-button>
                <el-button v-if="canWriteFmea" type="success" @click="openFmeaDialog()">新建FMEA</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table :data="fmeaList" stripe v-loading="fmeaLoading" border size="small">
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column label="设备" width="140">
              <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column prop="version" label="版本" width="80" />
            <el-table-column label="条目数" width="90">
              <template #default="{ row }">{{ (row.items || []).length }} 条</template>
            </el-table-column>
            <el-table-column label="启用" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="160">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="openItemsDialog(row)">查看条目</el-button>
                <el-button v-if="canWriteFmea" size="small" link type="primary" @click="openFmeaDialog(row)">编辑</el-button>
                <el-button v-if="canDeleteFmea" size="small" link type="danger" @click="onFmeaDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ============ 可靠性指标 ============ -->
        <el-tab-pane label="可靠性指标(MTBF/MTTR)" name="reliability">
          <div class="toolbar">
            <el-form :inline="true" :model="relQuery" size="default">
              <el-form-item label="设备">
                <el-select v-model="relQuery.equipment_id" filterable placeholder="全部设备" clearable style="width:200px">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="时间范围">
                <el-date-picker
                  v-model="relQuery.range"
                  type="daterange"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  style="width:360px"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="relLoading" @click="loadReliability">查询</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-row :gutter="16" v-loading="relLoading">
            <el-col :span="8">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-value">{{ fmtNum(reliability && reliability.failure_count) }}</div>
                <div class="stat-label">故障次数</div>
                <div class="stat-tip">统计区间内故障总数</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-value">{{ fmtNum(reliability && reliability.mtbf_hours) }}</div>
                <div class="stat-label">MTBF(小时)</div>
                <div class="stat-tip">MTBF = (观测时长 - 总停机) / 故障次数</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-value">{{ fmtNum(reliability && reliability.mttr_hours) }}</div>
                <div class="stat-label">MTTR(小时)</div>
                <div class="stat-tip">MTTR = 总修复时长 / 故障次数</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-value">{{ fmtNum(reliability && reliability.total_repair_hours) }}</div>
                <div class="stat-label">总修复时长(小时)</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-value">{{ fmtNum(reliability && reliability.total_downtime_hours) }}</div>
                <div class="stat-label">总停机时长(小时)</div>
              </el-card>
            </el-col>
            <el-col :span="8">
              <el-card shadow="hover" class="stat-card">
                <div class="stat-value">{{ fmtNum(reliability && reliability.spare_cost) }}</div>
                <div class="stat-label">备件消耗成本(元)</div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑 8D -->
    <el-dialog v-model="d8DialogVisible" :title="d8Form.id ? '编辑8D报告' : '新建8D报告'" width="760px">
      <el-form :model="d8Form" :rules="d8Rules" ref="d8FormRef" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="d8Form.equipment_id" filterable placeholder="选择设备" style="width:100%" @change="d8Form.work_order_id = null">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联工单">
              <el-select v-model="d8Form.work_order_id" filterable clearable placeholder="可选" style="width:100%">
                <el-option v-for="wo in d8WoOptions" :key="wo.id" :label="wo.order_no" :value="wo.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="标题" prop="title"><el-input v-model="d8Form.title" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="d8Form.status" style="width:100%">
                <el-option v-for="s in D8_STATUS_OPTIONS" :key="s" :label="d8StatusLabel(s)" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-collapse v-model="d8Collapse">
          <el-collapse-item title="8D 详细步骤" name="steps">
            <el-form-item label="D0 问题描述"><el-input v-model="d8Form.problem" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D1 团队"><el-input v-model="d8Form.d1_team" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D2 问题定义"><el-input v-model="d8Form.d2_problem_desc" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D3 临时围堵"><el-input v-model="d8Form.d3_interim" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D4 根本原因"><el-input v-model="d8Form.d4_root_cause" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D5 永久纠正"><el-input v-model="d8Form.d5_permanent" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D6 实施验证"><el-input v-model="d8Form.d6_implement" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D7 预防再发"><el-input v-model="d8Form.d7_prevent" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="D8 团队致谢"><el-input v-model="d8Form.d8_recognition" type="textarea" :rows="2" /></el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="d8DialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="d8Saving" @click="onD8Save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑 FMEA -->
    <el-dialog v-model="fmeaDialogVisible" :title="fmeaForm.id ? '编辑FMEA' : '新建FMEA'" width="900px">
      <el-form :model="fmeaForm" :rules="fmeaRules" ref="fmeaFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备" prop="equipment_id">
              <el-select v-model="fmeaForm.equipment_id" filterable placeholder="选择设备" style="width:100%">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" prop="name"><el-input v-model="fmeaForm.name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本"><el-input v-model="fmeaForm.version" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用"><el-switch v-model="fmeaForm.is_active" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="fmeaDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="fmeaSaving" @click="onFmeaSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- FMEA 条目 -->
    <el-dialog v-model="itemsDialogVisible" :title="`FMEA条目 - ${currentFmea && currentFmea.name || ''}`" width="95%">
      <div class="toolbar">
        <el-button v-if="canWriteFmea" type="success" size="small" @click="openItemDialog()">添加条目</el-button>
      </div>
      <el-table :data="fmeaItems" stripe v-loading="itemsLoading" border size="small">
        <el-table-column prop="seq" label="序" width="50" />
        <el-table-column prop="process_step" label="过程/功能" width="120" />
        <el-table-column prop="failure_mode" label="失效模式" min-width="140" />
        <el-table-column prop="failure_effect" label="失效影响" min-width="140" />
        <el-table-column prop="cause" label="失效原因" min-width="140" />
        <el-table-column label="S" width="60">
          <template #default="{ row }"><el-tag size="small">{{ row.severity }}</el-tag></template>
        </el-table-column>
        <el-table-column label="O" width="60">
          <template #default="{ row }"><el-tag size="small">{{ row.occurrence }}</el-tag></template>
        </el-table-column>
        <el-table-column label="D" width="60">
          <template #default="{ row }"><el-tag size="small">{{ row.detection }}</el-tag></template>
        </el-table-column>
        <el-table-column label="RPN" width="80">
          <template #default="{ row }"><el-tag :type="rpnTag(row.rpn)" size="small">{{ row.rpn }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="recommended_action" label="建议措施" min-width="160" />
        <el-table-column label="措施状态" width="90">
          <template #default="{ row }"><el-tag :type="fmeaActionTag(row.action_status)" size="small">{{ fmeaActionLabel(row.action_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite" size="small" link type="primary" @click="openItemDialog(row)">编辑行</el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click="onItemDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- FMEA 条目编辑 -->
    <el-dialog v-model="itemDialogVisible" :title="itemForm.id ? '编辑条目' : '添加条目'" width="720px">
      <el-form :model="itemForm" :rules="itemRules" ref="itemFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="过程/功能" prop="process_step"><el-input v-model="itemForm.process_step" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="失效模式" prop="failure_mode"><el-input v-model="itemForm.failure_mode" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="失效影响"><el-input v-model="itemForm.failure_effect" type="textarea" :rows="2" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="失效原因"><el-input v-model="itemForm.cause" type="textarea" :rows="2" /></el-form-item></el-col>
          <el-col :span="8">
            <el-form-item label="严重度 S">
              <el-input-number v-model="itemForm.severity" :min="1" :max="10" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="频度 O">
              <el-input-number v-model="itemForm.occurrence" :min="1" :max="10" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="探测度 D">
              <el-input-number v-model="itemForm.detection" :min="1" :max="10" controls-position="right" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="RPN 预览">
              <el-tag :type="rpnTag(itemRpn)" size="large">{{ itemRpn }}</el-tag>
              <span class="rpn-hint">（S × O × D，最终值由后端计算）</span>
            </el-form-item>
          </el-col>
          <el-col :span="24"><el-form-item label="建议措施"><el-input v-model="itemForm.recommended_action" type="textarea" :rows="2" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="措施状态">
              <el-select v-model="itemForm.action_status" style="width:100%">
                <el-option v-for="s in FMEA_ACTION_STATUS_OPTIONS" :key="s" :label="fmeaActionLabel(s)" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24"><el-form-item label="措施结果"><el-input v-model="itemForm.action_result" type="textarea" :rows="2" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="itemForm.remark" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="itemSaving" @click="onItemSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listD8, getD8, createD8, updateD8, deleteD8,
  listFmeas, getFmea, createFmea, updateFmea, deleteFmea,
  addFmeaItem, updateFmeaItem, deleteFmeaItem,
  getReliability,
} from '@/api/quality'
import { listEquipments } from '@/api/equipment'
import { listWorkOrders } from '@/api/work_order'
import { useUserStore } from '@/stores'
import {
  formatTime, formatDuration,
  d8StatusLabel, d8StatusTag, D8_STATUS_OPTIONS,
  fmeaActionLabel, fmeaActionTag, FMEA_ACTION_STATUS_OPTIONS,
  rpnTag,
} from '@/utils'

const userStore = useUserStore()
const canWriteD8 = computed(() => userStore.can('quality.d8_write'))
const canDeleteD8 = computed(() => userStore.can('quality.d8_delete'))
const canWriteFmea = computed(() => userStore.can('quality.fmea_write'))
const canDeleteFmea = computed(() => userStore.can('quality.fmea_delete'))

const tab = ref('d8')
const equipments = ref([])
const workOrders = ref([])

function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}

async function loadEquipments() {
  equipments.value = await listEquipments({ limit: 500 })
}
async function loadWorkOrders() {
  workOrders.value = await listWorkOrders({ limit: 500 })
}

// ---------- 8D 报告 ----------
const d8Query = reactive({ equipment_id: null, status: null })
const d8List = ref([])
const d8Loading = ref(false)
async function loadD8() {
  d8Loading.value = true
  try {
    const params = {}
    if (d8Query.equipment_id) params.equipment_id = d8Query.equipment_id
    if (d8Query.status) params.status = d8Query.status
    d8List.value = await listD8(params)
  } finally {
    d8Loading.value = false
  }
}

const D8_KEYS = [
  'equipment_id', 'work_order_id', 'title', 'problem', 'd1_team', 'd2_problem_desc',
  'd3_interim', 'd4_root_cause', 'd5_permanent', 'd6_implement', 'd7_prevent', 'd8_recognition', 'status',
]
const d8DialogVisible = ref(false)
const d8Saving = ref(false)
const d8FormRef = ref(null)
const d8Collapse = ref(['steps'])
const d8Form = reactive({
  id: null, equipment_id: null, work_order_id: null, title: '', problem: '', d1_team: '',
  d2_problem_desc: '', d3_interim: '', d4_root_cause: '', d5_permanent: '', d6_implement: '',
  d7_prevent: '', d8_recognition: '', status: 'OPEN',
})
const d8Rules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}
const d8WoOptions = computed(() => {
  if (!d8Form.equipment_id) return workOrders.value
  return workOrders.value.filter((w) => w.equipment_id === d8Form.equipment_id)
})
function resetD8Form() {
  Object.assign(d8Form, {
    id: null, equipment_id: null, work_order_id: null, title: '', problem: '', d1_team: '',
    d2_problem_desc: '', d3_interim: '', d4_root_cause: '', d5_permanent: '', d6_implement: '',
    d7_prevent: '', d8_recognition: '', status: 'OPEN',
  })
}
async function openD8Dialog(row = null) {
  resetD8Form()
  if (row) {
    try {
      const d = await getD8(row.id)
      D8_KEYS.forEach((k) => { d8Form[k] = d[k] != null ? d[k] : d8Form[k] })
      d8Form.id = d.id
    } catch (e) {}
  }
  d8DialogVisible.value = true
}
async function onD8Save() {
  try {
    await d8FormRef.value.validate()
    d8Saving.value = true
    const payload = JSON.parse(JSON.stringify(d8Form))
    if (payload.id) {
      const { id, ...rest } = payload
      await updateD8(id, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createD8(payload)
      ElMessage.success('已创建')
    }
    d8DialogVisible.value = false
    loadD8()
  } catch (e) {} finally {
    d8Saving.value = false
  }
}
async function onD8Delete(row) {
  try {
    await ElMessageBox.confirm(`确认删除 8D 报告【${row.report_no || row.title}】？`, '提示', { type: 'warning' })
    await deleteD8(row.id)
    ElMessage.success('已删除')
    loadD8()
  } catch (e) {}
}
async function onD8Close(row) {
  try {
    await ElMessageBox.confirm(`确认关闭 8D 报告【${row.report_no || row.title}】？`, '提示', { type: 'warning' })
    await updateD8(row.id, { status: 'CLOSED' })
    ElMessage.success('已关闭')
    loadD8()
  } catch (e) {}
}

// ---------- FMEA ----------
const fmeaQuery = reactive({ equipment_id: null })
const fmeaList = ref([])
const fmeaLoading = ref(false)
async function loadFmea() {
  fmeaLoading.value = true
  try {
    const params = {}
    if (fmeaQuery.equipment_id) params.equipment_id = fmeaQuery.equipment_id
    fmeaList.value = await listFmeas(params)
  } finally {
    fmeaLoading.value = false
  }
}

const fmeaDialogVisible = ref(false)
const fmeaSaving = ref(false)
const fmeaFormRef = ref(null)
const fmeaForm = reactive({ id: null, equipment_id: null, name: '', version: '1.0', is_active: true })
const fmeaRules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}
function openFmeaDialog(row = null) {
  Object.assign(fmeaForm, { id: null, equipment_id: null, name: '', version: '1.0', is_active: true })
  if (row) Object.assign(fmeaForm, { id: row.id, equipment_id: row.equipment_id, name: row.name, version: row.version, is_active: row.is_active })
  fmeaDialogVisible.value = true
}
async function onFmeaSave() {
  try {
    await fmeaFormRef.value.validate()
    fmeaSaving.value = true
    const payload = JSON.parse(JSON.stringify(fmeaForm))
    if (payload.id) {
      const { id, ...rest } = payload
      await updateFmea(id, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createFmea(payload)
      ElMessage.success('已创建')
    }
    fmeaDialogVisible.value = false
    loadFmea()
  } catch (e) {} finally {
    fmeaSaving.value = false
  }
}
async function onFmeaDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除 FMEA【${row.name}】？`, '提示', { type: 'warning' })
    await deleteFmea(row.id)
    ElMessage.success('已删除')
    loadFmea()
  } catch (e) {}
}

// FMEA 条目
const itemsDialogVisible = ref(false)
const itemsLoading = ref(false)
const currentFmea = ref(null)
const fmeaItems = ref([])
async function openItemsDialog(row) {
  currentFmea.value = row
  itemsDialogVisible.value = true
  await loadItems(row.id)
}
async function loadItems(fmeaId) {
  itemsLoading.value = true
  try {
    const d = await getFmea(fmeaId)
    fmeaItems.value = d.items || []
    if (currentFmea.value) currentFmea.value = { ...currentFmea.value, name: d.name }
  } finally {
    itemsLoading.value = false
  }
}

const ITEM_KEYS = [
  'seq', 'process_step', 'failure_mode', 'failure_effect', 'cause',
  'severity', 'occurrence', 'detection', 'recommended_action', 'action_status', 'action_result', 'remark',
]
const itemDialogVisible = ref(false)
const itemSaving = ref(false)
const itemFormRef = ref(null)
const itemForm = reactive({
  id: null, seq: 1, process_step: '', failure_mode: '', failure_effect: '', cause: '',
  severity: 5, occurrence: 5, detection: 5, recommended_action: '', action_status: 'OPEN', action_result: '', remark: '',
})
const itemRules = {
  process_step: [{ required: true, message: '请输入过程/功能', trigger: 'blur' }],
  failure_mode: [{ required: true, message: '请输入失效模式', trigger: 'blur' }],
}
const itemRpn = computed(
  () => (Number(itemForm.severity) || 0) * (Number(itemForm.occurrence) || 0) * (Number(itemForm.detection) || 0)
)
function openItemDialog(item = null) {
  Object.assign(itemForm, {
    id: null, seq: (fmeaItems.value.length || 0) + 1, process_step: '', failure_mode: '', failure_effect: '',
    cause: '', severity: 5, occurrence: 5, detection: 5, recommended_action: '', action_status: 'OPEN', action_result: '', remark: '',
  })
  if (item) {
    ITEM_KEYS.forEach((k) => { itemForm[k] = item[k] != null ? item[k] : itemForm[k] })
    itemForm.id = item.id
  }
  itemDialogVisible.value = true
}
async function onItemSave() {
  try {
    await itemFormRef.value.validate()
    itemSaving.value = true
    const fmeaId = currentFmea.value.id
    const payload = {}
    ITEM_KEYS.forEach((k) => { payload[k] = itemForm[k] })
    if (itemForm.id) {
      await updateFmeaItem(fmeaId, itemForm.id, payload)
      ElMessage.success('已更新')
    } else {
      await addFmeaItem(fmeaId, payload)
      ElMessage.success('已添加')
    }
    itemDialogVisible.value = false
    await loadItems(fmeaId)
  } catch (e) {} finally {
    itemSaving.value = false
  }
}
async function onItemDelete(item) {
  try {
    await ElMessageBox.confirm(`确认删除条目 #${item.seq}？`, '提示', { type: 'warning' })
    await deleteFmeaItem(currentFmea.value.id, item.id)
    ElMessage.success('已删除')
    await loadItems(currentFmea.value.id)
  } catch (e) {}
}

// ---------- 可靠性指标 ----------
const relQuery = reactive({ equipment_id: null, range: [] })
const reliability = ref(null)
const relLoading = ref(false)
async function loadReliability() {
  relLoading.value = true
  try {
    const params = {}
    if (relQuery.equipment_id) params.equipment_id = relQuery.equipment_id
    if (relQuery.range && relQuery.range.length === 2) {
      params.start = relQuery.range[0]
      params.end = relQuery.range[1]
    }
    reliability.value = await getReliability(params)
  } finally {
    relLoading.value = false
  }
}
function fmtNum(n, digits = 2) {
  if (n == null || n === '') return '-'
  const num = Number(n)
  if (Number.isNaN(num)) return n
  return Number.isInteger(num) ? String(num) : num.toFixed(digits)
}

watch(tab, (v) => {
  if (v === 'd8') loadD8()
  else if (v === 'fmea') loadFmea()
  else if (v === 'reliability') loadReliability()
})

onMounted(async () => {
  await loadEquipments()
  await loadWorkOrders()
  await Promise.all([loadD8(), loadFmea(), loadReliability()])
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.stat-card { text-align: center; margin-bottom: 16px; }
.stat-value { font-size: 28px; font-weight: 600; color: #303133; line-height: 1.4; }
.stat-label { font-size: 14px; color: #606266; margin-top: 4px; }
.stat-tip { font-size: 12px; color: #909399; margin-top: 6px; min-height: 16px; }
.rpn-hint { font-size: 12px; color: #909399; margin-left: 8px; }
</style>
