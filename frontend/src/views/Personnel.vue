<template>
  <div>
    <el-card shadow="never">
      <el-tabs v-model="tab" type="border-card">
        <!-- 资质考核 -->
        <el-tab-pane label="资质考核" name="qual">
          <div class="toolbar">
            <el-form :inline="true" :model="qualQuery" size="default">
              <el-form-item label="用户">
                <el-select v-model="qualQuery.user_id" filterable clearable placeholder="全部" style="width:220px">
                  <el-option v-for="u in users" :key="u.id" :label="`${u.full_name || u.username} (${u.username})`" :value="u.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="设备">
                <el-select v-model="qualQuery.equipment_id" filterable clearable placeholder="全部" style="width:200px">
                  <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadQual">查询</el-button>
                <el-button v-if="canWriteQual" type="success" @click="openQualDialog()">新增资质</el-button>
              </el-form-item>
            </el-form>
          </div>
          <el-table :data="qualList" stripe v-loading="qualLoading" border size="small">
            <el-table-column label="用户" width="120">
              <template #default="{ row }">{{ userName(row) }}</template>
            </el-table-column>
            <el-table-column label="设备" width="140">
              <template #default="{ row }">{{ eqNameOrGeneral(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column label="技能等级" width="90">
              <template #default="{ row }"><el-tag :type="skillLevelTag(row.skill_level)" size="small">{{ skillLevelLabel(row.skill_level) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="score" label="成绩" width="80" />
            <el-table-column label="取得日期" width="120">
              <template #default="{ row }">{{ formatTime(row.certified_at, 'YYYY-MM-DD') }}</template>
            </el-table-column>
            <el-table-column label="到期日期" width="120">
              <template #default="{ row }">
                <el-tag v-if="isExpired(row.expires_at)" type="danger" size="small">已过期</el-tag>
                <span :class="{ expired: isExpired(row.expires_at) }">{{ formatTime(row.expires_at, 'YYYY-MM-DD') }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="certified_by" label="认证人" width="100" />
            <el-table-column label="状态" width="70">
              <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag></template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canWriteQual" size="small" link type="primary" @click="openQualDialog(row)">编辑</el-button>
                <el-button v-if="canDeleteQual" size="small" link type="danger" @click="onDeleteQual(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 技能矩阵 -->
        <el-tab-pane label="技能矩阵" name="matrix">
          <div class="toolbar">
            <el-button type="primary" size="default" @click="loadMatrix">刷新</el-button>
            <span class="help-text">颜色: 主操作=绿 副操作=蓝 培训中=黄 无=灰</span>
          </div>
          <el-table v-if="matrix.equipments.length" :data="matrix.users" stripe v-loading="matrixLoading" border size="small">
            <el-table-column label="人员" fixed width="140">
              <template #default="{ row }">
                <div>{{ row.full_name || row.username }}
                  <el-tag :type="roleTag(row.role)" size="small" style="margin-left:4px">{{ roleLabel(row.role) }}</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column v-for="eq in matrix.equipments" :key="eq.id" :label="eq.name" min-width="110" align="center">
              <template #default="{ row }">
                <el-tag v-if="findCell(row, eq.id)" :type="skillLevelTag(findCell(row, eq.id).level)" size="small">{{ skillLevelLabel(findCell(row, eq.id).level) }}</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无设备" />
        </el-tab-pane>

        <!-- 培训计划 -->
        <el-tab-pane label="培训计划" name="training">
          <div class="toolbar">
            <el-form :inline="true" :model="trainQuery" size="default">
              <el-form-item label="状态">
                <el-select v-model="trainQuery.status" clearable placeholder="全部" style="width:160px">
                  <el-option v-for="s in TRAINING_STATUS_OPTIONS" :key="s" :label="trainingStatusLabel(s)" :value="s" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="loadTrain">查询</el-button>
                <el-button v-if="canWriteTrain" type="success" @click="openTrainDialog()">新建培训</el-button>
              </el-form-item>
            </el-form>
          </div>
          <el-table :data="trainList" stripe v-loading="trainLoading" border size="small">
            <el-table-column prop="name" label="培训名称" min-width="160" />
            <el-table-column label="设备" width="140">
              <template #default="{ row }">{{ eqNameOrGeneral(row.equipment_id) }}</template>
            </el-table-column>
            <el-table-column label="培训师" width="120">
              <template #default="{ row }">{{ userNameById(row.trainer_id) }}</template>
            </el-table-column>
            <el-table-column label="计划日期" width="140">
              <template #default="{ row }">{{ formatTime(row.planned_date) }}</template>
            </el-table-column>
            <el-table-column label="完成日期" width="140">
              <template #default="{ row }">{{ formatTime(row.completed_date) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }"><el-tag :type="trainingStatusTag(row.status)" size="small">{{ trainingStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="学员数" width="80">
              <template #default="{ row }">{{ (row.attendees || []).length }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canWriteTrain" size="small" link type="primary" @click="openAttendees(row)">学员</el-button>
                <el-dropdown v-if="canWriteTrain" trigger="click" @command="(c) => onChangeStatus(row, c)">
                  <el-button size="small" link type="warning">状态</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-for="s in TRAINING_STATUS_OPTIONS" :key="s" :command="s" :disabled="s === row.status">{{ trainingStatusLabel(s) }}</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button v-if="canDeleteTrain" size="small" link type="danger" @click="onDeleteTrain(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 资质 新增/编辑 -->
    <el-dialog v-model="qualDialogVisible" :title="qualForm.id ? '编辑资质' : '新增资质'" width="640px">
      <el-form :model="qualForm" :rules="qualRules" ref="qualFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用户" prop="user_id">
              <el-select v-model="qualForm.user_id" filterable placeholder="选择用户" style="width:100%">
                <el-option v-for="u in users" :key="u.id" :label="`${u.full_name || u.username} (${u.username})`" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备">
              <el-select v-model="qualForm.equipment_id" clearable placeholder="选择设备" style="width:100%">
                <el-option label="通用资质" :value="0" />
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="技能等级" prop="skill_level">
              <el-select v-model="qualForm.skill_level" style="width:100%">
                <el-option v-for="l in SKILL_LEVEL_OPTIONS" :key="l" :label="skillLevelLabel(l)" :value="l" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="成绩">
              <el-input-number v-model="qualForm.score" :min="0" :max="100" :step="0.1" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="取得日期">
              <el-date-picker v-model="qualForm.certified_at" type="date" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="到期日期">
              <el-date-picker v-model="qualForm.expires_at" type="date" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="认证人"><el-input v-model="qualForm.certified_by" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用"><el-switch v-model="qualForm.is_active" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="qualForm.remark" type="textarea" :rows="2" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="qualDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="qualSaving" @click="onSaveQual">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建培训 -->
    <el-dialog v-model="trainDialogVisible" title="新建培训" width="720px">
      <el-form :model="trainForm" :rules="trainRules" ref="trainFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="培训名称" prop="name"><el-input v-model="trainForm.name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备">
              <el-select v-model="trainForm.equipment_id" clearable placeholder="选择设备" style="width:100%">
                <el-option label="通用" :value="0" />
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="培训师">
              <el-select v-model="trainForm.trainer_id" clearable filterable placeholder="可选" style="width:100%">
                <el-option v-for="u in users" :key="u.id" :label="`${u.full_name || u.username} (${u.username})`" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划日期">
              <el-date-picker v-model="trainForm.planned_date" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="培训内容"><el-input v-model="trainForm.content" type="textarea" :rows="3" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注"><el-input v-model="trainForm.remark" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="trainDialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="trainSaving" @click="onSaveTrain">保存</el-button>
      </template>
    </el-dialog>

    <!-- 学员管理 -->
    <el-dialog v-model="attDialogVisible" :title="`学员管理 - ${attTraining?.name || ''}`" width="800px">
      <div class="toolbar">
        <el-button v-if="canWriteTrain" type="success" size="small" @click="openAttForm()">添加学员</el-button>
      </div>
      <el-form v-if="attFormVisible" :model="attForm" :rules="attRules" ref="attFormRef" :inline="true" size="small" class="att-form">
        <el-form-item label="学员" prop="user_id">
          <el-select v-model="attForm.user_id" filterable placeholder="选择学员" style="width:180px">
            <el-option v-for="u in users" :key="u.id" :label="`${u.full_name || u.username} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="出席">
          <el-select v-model="attForm.attendance" style="width:100px">
            <el-option label="出席" value="PRESENT" />
            <el-option label="缺席" value="ABSENT" />
          </el-select>
        </el-form-item>
        <el-form-item label="成绩">
          <el-input-number v-model="attForm.score" :min="0" :max="100" :step="0.1" style="width:120px" />
        </el-form-item>
        <el-form-item label="通过">
          <el-switch v-model="attForm.passed" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="attForm.remark" style="width:160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="attSaving" @click="onSaveAtt">保存</el-button>
          <el-button @click="attFormVisible=false">取消</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="attendees" stripe v-loading="attLoading" border size="small">
        <el-table-column label="用户" width="120">
          <template #default="{ row }">{{ userNameById(row.user_id) }}</template>
        </el-table-column>
        <el-table-column label="出席" width="90">
          <template #default="{ row }"><el-tag :type="row.attendance === 'PRESENT' ? 'success' : 'info'" size="small">{{ row.attendance === 'PRESENT' ? '出席' : '缺席' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="score" label="成绩" width="80" />
        <el-table-column label="通过" width="80">
          <template #default="{ row }"><el-tag :type="row.passed ? 'success' : 'info'" size="small">{{ row.passed ? '通过' : '不通过' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="120" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="canWriteTrain" size="small" link type="primary" @click="openAttForm(row)">编辑</el-button>
            <el-button v-if="canDeleteTrain" size="small" link type="danger" @click="onDeleteAtt(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="attDialogVisible=false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listQualifications, createQualification, updateQualification, deleteQualification,
  getSkillMatrix,
  listTrainings, getTraining, createTraining, updateTrainingStatus, deleteTraining,
  addAttendee, updateAttendee, deleteAttendee,
} from '@/api/personnel'
import { listEquipments } from '@/api/equipment'
import { listUsers } from '@/api/auth'
import { useUserStore } from '@/stores'
import {
  formatTime, skillLevelLabel, skillLevelTag, SKILL_LEVEL_OPTIONS,
  trainingStatusLabel, trainingStatusTag, TRAINING_STATUS_OPTIONS,
} from '@/utils'
import dayjs from 'dayjs'

const userStore = useUserStore()
const canWriteQual = computed(() => userStore.can('personnel.qualification_write'))
const canDeleteQual = computed(() => userStore.can('personnel.qualification_delete'))
const canWriteTrain = computed(() => userStore.can('personnel.training_write'))
const canDeleteTrain = computed(() => userStore.can('personnel.training_delete'))

const tab = ref('qual')
const equipments = ref([])
const users = ref([])

function eqName(id) {
  if (!id) return '-'
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}
function eqNameOrGeneral(id) {
  if (!id) return '通用'
  return eqName(id)
}
function userNameById(id) {
  if (!id) return '-'
  const u = users.value.find((x) => x.id === id)
  return u ? (u.full_name || u.username) : `#${id}`
}
function userName(qual) {
  return userNameById(qual.user_id)
}
function roleLabel(r) {
  return ({ admin: '管理员', engineer: '工程师', operator: '操作员' }[r]) || r
}
function roleTag(r) {
  return ({ admin: 'danger', engineer: 'warning', operator: 'primary' }[r]) || 'info'
}
function isExpired(d) {
  return d && dayjs(d).isBefore(dayjs())
}

// ---- 资质考核 ----
const qualQuery = reactive({ user_id: null, equipment_id: null })
const qualList = ref([])
const qualLoading = ref(false)
async function loadQual() {
  qualLoading.value = true
  try {
    const params = {}
    if (qualQuery.user_id) params.user_id = qualQuery.user_id
    if (qualQuery.equipment_id) params.equipment_id = qualQuery.equipment_id
    qualList.value = await listQualifications(params)
  } finally {
    qualLoading.value = false
  }
}

const qualDialogVisible = ref(false)
const qualSaving = ref(false)
const qualFormRef = ref(null)
const qualForm = reactive({
  id: null, user_id: null, equipment_id: 0, skill_level: 'TRAINING', score: null,
  certified_at: null, expires_at: null, certified_by: '', is_active: true, remark: '',
})
const qualRules = {
  user_id: [{ required: true, message: '请选择用户', trigger: 'change' }],
  skill_level: [{ required: true, message: '请选择技能等级', trigger: 'change' }],
}
function openQualDialog(row = null) {
  Object.assign(qualForm, {
    id: null, user_id: null, equipment_id: 0, skill_level: 'TRAINING', score: null,
    certified_at: null, expires_at: null, certified_by: '', is_active: true, remark: '',
  })
  if (row) {
    Object.assign(qualForm, JSON.parse(JSON.stringify(row)))
    qualForm.equipment_id = row.equipment_id || 0
  }
  qualDialogVisible.value = true
}
async function onSaveQual() {
  try {
    await qualFormRef.value.validate()
    qualSaving.value = true
    const payload = JSON.parse(JSON.stringify(qualForm))
    payload.equipment_id = payload.equipment_id || null
    if (payload.id) {
      const { id, ...rest } = payload
      await updateQualification(id, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createQualification(payload)
      ElMessage.success('已创建')
    }
    qualDialogVisible.value = false
    loadQual()
  } catch (e) {} finally {
    qualSaving.value = false
  }
}
async function onDeleteQual(row) {
  try {
    await ElMessageBox.confirm(`确认删除【${userName(row)}】的资质？`, '提示', { type: 'warning' })
    await deleteQualification(row.id)
    ElMessage.success('已删除')
    loadQual()
  } catch (e) {}
}

// ---- 技能矩阵 ----
const matrix = reactive({ equipments: [], users: [] })
const matrixLoading = ref(false)
async function loadMatrix() {
  matrixLoading.value = true
  try {
    const m = await getSkillMatrix()
    matrix.equipments = m.equipments || []
    matrix.users = m.users || []
  } finally {
    matrixLoading.value = false
  }
}
function findCell(row, eqId) {
  return (row.cells || []).find((c) => c.equipment_id === eqId)
}

// ---- 培训计划 ----
const trainQuery = reactive({ status: null })
const trainList = ref([])
const trainLoading = ref(false)
async function loadTrain() {
  trainLoading.value = true
  try {
    const params = {}
    if (trainQuery.status) params.status = trainQuery.status
    trainList.value = await listTrainings(params)
  } finally {
    trainLoading.value = false
  }
}

const trainDialogVisible = ref(false)
const trainSaving = ref(false)
const trainFormRef = ref(null)
const trainForm = reactive({
  id: null, name: '', equipment_id: 0, trainer_id: null, planned_date: null,
  completed_date: null, content: '', remark: '',
})
const trainRules = {
  name: [{ required: true, message: '请输入培训名称', trigger: 'blur' }],
}
function openTrainDialog(row = null) {
  Object.assign(trainForm, {
    id: null, name: '', equipment_id: 0, trainer_id: null, planned_date: null,
    completed_date: null, content: '', remark: '',
  })
  if (row) {
    Object.assign(trainForm, JSON.parse(JSON.stringify(row)))
    trainForm.equipment_id = row.equipment_id || 0
  }
  trainDialogVisible.value = true
}
async function onSaveTrain() {
  try {
    await trainFormRef.value.validate()
    trainSaving.value = true
    const payload = JSON.parse(JSON.stringify(trainForm))
    payload.equipment_id = payload.equipment_id || null
    delete payload.id
    await createTraining(payload)
    ElMessage.success('已创建')
    trainDialogVisible.value = false
    loadTrain()
  } catch (e) {} finally {
    trainSaving.value = false
  }
}
async function onDeleteTrain(row) {
  try {
    await ElMessageBox.confirm(`确认删除培训【${row.name}】？`, '提示', { type: 'warning' })
    await deleteTraining(row.id)
    ElMessage.success('已删除')
    loadTrain()
  } catch (e) {}
}
async function onChangeStatus(row, status) {
  try {
    await updateTrainingStatus(row.id, status)
    ElMessage.success('状态已更新')
    loadTrain()
  } catch (e) {}
}

// ---- 学员管理 ----
const attDialogVisible = ref(false)
const attTraining = ref(null)
const attendees = ref([])
const attLoading = ref(false)
const attFormVisible = ref(false)
const attSaving = ref(false)
const attFormRef = ref(null)
const attForm = reactive({ id: null, user_id: null, attendance: 'PRESENT', score: null, passed: false, remark: '' })
const attRules = {
  user_id: [{ required: true, message: '请选择学员', trigger: 'change' }],
}
async function openAttendees(row) {
  attTraining.value = row
  attDialogVisible.value = true
  attFormVisible.value = false
  await refreshAttendees()
}
async function refreshAttendees() {
  if (!attTraining.value) return
  attLoading.value = true
  try {
    const t = await getTraining(attTraining.value.id)
    attendees.value = t.attendees || []
    const idx = trainList.value.findIndex((x) => x.id === t.id)
    if (idx >= 0) {
      Object.assign(trainList.value[idx], t)
      attTraining.value = trainList.value[idx]
    }
  } finally {
    attLoading.value = false
  }
}
function openAttForm(att = null) {
  Object.assign(attForm, { id: null, user_id: null, attendance: 'PRESENT', score: null, passed: false, remark: '' })
  if (att) Object.assign(attForm, JSON.parse(JSON.stringify(att)))
  attFormVisible.value = true
}
async function onSaveAtt() {
  try {
    await attFormRef.value.validate()
    attSaving.value = true
    const payload = JSON.parse(JSON.stringify(attForm))
    if (attForm.id) {
      await updateAttendee(attTraining.value.id, attForm.id, payload)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await addAttendee(attTraining.value.id, payload)
      ElMessage.success('已添加')
    }
    attFormVisible.value = false
    await refreshAttendees()
  } catch (e) {} finally {
    attSaving.value = false
  }
}
async function onDeleteAtt(att) {
  try {
    await ElMessageBox.confirm(`确认删除学员【${userNameById(att.user_id)}】？`, '提示', { type: 'warning' })
    await deleteAttendee(attTraining.value.id, att.id)
    ElMessage.success('已删除')
    await refreshAttendees()
  } catch (e) {}
}

watch(tab, (v) => {
  if (v === 'qual') loadQual()
  else if (v === 'matrix') loadMatrix()
  else if (v === 'training') loadTrain()
})

onMounted(async () => {
  try { equipments.value = await listEquipments({ limit: 500 }) } catch (e) {}
  try { users.value = await listUsers() } catch (e) {}
  await loadQual()
  await loadMatrix()
})
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
.help-text { margin-left: 12px; color: #909399; font-size: 12px; }
.expired { color: #f56c6c; }
.att-form { margin-bottom: 10px; border: 1px dashed #ebeef5; padding: 10px; }
</style>
