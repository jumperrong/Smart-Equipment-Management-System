<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">PM 维护计划</span>
          <el-tabs v-model="activeTab" size="default" @tab-change="onTabChange">
            <el-tab-pane label="列表视图" name="list" />
            <el-tab-pane label="日历视图" name="calendar" />
          </el-tabs>
        </div>
      </template>

      <!-- 列表视图 -->
      <div v-if="activeTab === 'list'">
        <div class="toolbar">
          <el-form :inline="true" :model="query" size="default">
            <el-form-item label="设备">
              <el-select v-model="query.equipment_id" filterable placeholder="全部设备" clearable style="width:200px">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadList">查询</el-button>
              <el-button v-if="canWrite" type="success" @click="openDialog()">新建 PM 计划</el-button>
              <el-button v-if="canWrite" type="warning" plain @click="onGenerateDue">生成到期工单</el-button>
            </el-form-item>
          </el-form>
        </div>

        <el-table :data="list" stripe v-loading="loading" border size="small">
          <el-table-column prop="name" label="计划名称" min-width="160" />
          <el-table-column label="设备" width="160">
            <template #default="{ row }">{{ eqName(row.equipment_id) }}</template>
          </el-table-column>
          <el-table-column prop="cycle_days" label="周期(天)" width="90" align="center" />
          <el-table-column label="计划时段" width="170">
            <template #default="{ row }">
              <div class="plan-time">
                <el-icon><Clock /></el-icon>
                <span>{{ row.planned_start_hour }}:00</span>
                <span class="sep">|</span>
                <span>{{ Math.floor((row.planned_duration_minutes||0)/60) }}h{{ (row.planned_duration_minutes||0)%60 ? (row.planned_duration_minutes%60)+'m' : '' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="维护项目" min-width="200">
            <template #default="{ row }">
              <el-tag v-for="(it, i) in (row.items || [])" :key="i" size="small" style="margin:2px">{{ it }}</el-tag>
              <span v-if="!(row.items || []).length">-</span>
            </template>
          </el-table-column>
          <el-table-column label="下次到期" width="160">
            <template #default="{ row }">
              <el-tag v-if="isOverdue(row.next_due_date)" type="danger" size="small">已到期</el-tag>
              {{ formatTime(row.next_due_date) }}
            </template>
          </el-table-column>
          <el-table-column label="上次执行" width="160">
            <template #default="{ row }">{{ formatTime(row.last_executed_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button v-if="canWrite" size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
              <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 日历视图 -->
      <div v-else>
        <div class="toolbar">
          <el-form :inline="true" size="default">
            <el-form-item label="视图">
              <el-radio-group v-model="viewMode" size="default" @change="loadCalendar">
                <el-radio-button value="week">周</el-radio-button>
                <el-radio-button value="day">日</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="范围">
              <el-button-group>
                <el-button :icon="ArrowLeft" @click="onPrevRange" />
                <el-button @click="onToday">今日</el-button>
                <el-button :icon="ArrowRight" @click="onNextRange" />
              </el-button-group>
              <span style="margin-left:10px; color:#606266; font-size:13px">{{ rangeLabel }}</span>
            </el-form-item>
            <el-form-item label="设备">
              <el-select v-model="calendarEquipmentId" filterable placeholder="全部设备" clearable style="width:200px" @change="loadCalendar">
                <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadCalendar">刷新</el-button>
              <span style="margin-left:8px;display:inline-flex;gap:12px;font-size:12px;align-items:center">
                <span><i class="swatch planned" /> 计划 PM</span>
                <span><i class="swatch actual" /> 实际 PM</span>
                <span><i class="swatch overtime" /> 超时 PM</span>
              </span>
            </el-form-item>
          </el-form>
        </div>

        <div v-loading="calendarLoading" class="calendar-wrap">
          <!-- 周视图: 7天 x 18小时 (6:00-24:00) -->
          <template v-if="viewMode === 'week'">
            <div class="week-cal">
              <div class="week-cal-head">
                <div class="hour-label">时</div>
                <div v-for="d in weekDays" :key="d.dateKey" class="day-head">
                  <div class="date-text" :class="{ today: d.isToday }">{{ d.md }}</div>
                  <div class="week-text" :class="{ today: d.isToday }">{{ d.weekDay }}</div>
                </div>
              </div>
              <div class="week-cal-body" ref="bodyRef">
                <div
                  v-for="h in dayHours"
                  :key="h.h"
                  class="hour-row"
                  :style="{ height: HOUR_HEIGHT + 'px' }"
                >
                  <div class="hour-label">{{ `${String(h.h).padStart(2,'0')}:00` }}</div>
                  <div v-for="d in weekDays" :key="d.dateKey+'-'+h.h" class="day-cell" :style="cellStyle(d, h.h)">
                    <!-- 该时段的事件（超时事件被拆为 base + overtime 段） -->
                    <template v-for="seg in eventsAtSegments(d, h.h)" :key="seg.id">
                      <div
                        class="event-bar"
                        :class="[seg.type, { 'overtime-seg': seg._seg === 'overtime' }]"
                        :style="eventStyle(seg)"
                        :title="eventTooltip(seg)"
                        @click="onEventClick(seg)"
                      >
                        <div class="ev-title">{{ seg.equipment_name }} · {{ seg.type === 'planned' ? seg.plan_name : (seg._seg === 'overtime' ? '⚠超时' : seg.reason_detail) }}</div>
                        <div class="ev-sub">
                          {{ fmtHour(seg.start_time) }}-{{ fmtHour(seg.end_time || new Date()) }}
                          <span v-if="seg.duration_minutes" class="dur">· {{ Math.round(seg.duration_minutes) }}m</span>
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- 日视图: 设备行 x 小时列 -->
          <template v-else>
            <div class="day-cal">
              <div class="day-cal-scroll" ref="bodyRef">
                <!-- sticky 表头 -->
                <div class="day-cal-head">
                  <div class="eq-head">设备</div>
                  <div class="hours-head">
                    <div v-for="h in dayHours" :key="h.h" class="hour-col" :style="{ width: HOUR_WIDTH + 'px' }">
                      {{ `${String(h.h).padStart(2,'0')}:00` }}
                    </div>
                  </div>
                </div>
                <!-- 设备行 -->
                <div v-for="e in calendarEquipments" :key="e.id" class="eq-row">
                  <div class="eq-name">
                    <div class="nm">{{ e.name }}</div>
                    <div class="no">{{ e.asset_no }}</div>
                  </div>
                  <div class="hours-track">
                    <div v-for="h in dayHours" :key="h.h" class="hour-cell" :style="{ width: HOUR_WIDTH + 'px' }"></div>
                    <!-- 事件定位 -->
                    <template v-for="ev in eventsByEquipment[e.id]" :key="ev.id">
                      <div
                        class="event-bar day-ev"
                        :class="[ev.type, { 'overtime-seg': ev._seg === 'overtime' }]"
                        :style="dayEventStyle(ev)"
                        :title="eventTooltip(ev)"
                        @click="onEventClick(ev)"
                      >
                        <span class="ev-title-sm">{{ ev.type === 'planned' ? ev.plan_name : (ev._seg === 'overtime' ? '⚠' : 'PM') }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </el-card>

    <!-- 新建 / 编辑 PM 计划 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-form-item label="设备" prop="equipment_id">
          <el-select v-model="form.equipment_id" filterable placeholder="选择设备" style="width:100%" :disabled="!!form.id">
            <el-option v-for="e in equipments" :key="e.id" :label="`${e.asset_no || ''} ${e.name}`" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="周期(天)" prop="cycle_days">
          <el-input-number v-model="form.cycle_days" :min="1" :max="3650" style="width:100%" />
        </el-form-item>
        <el-form-item label="计划开始">
          <el-time-picker v-model="form.planned_start_hour" format="HH:00" value-format="H" style="width:45%" />
          <span style="margin:0 6px; color:#909399">持续</span>
          <el-select v-model="form.planned_duration_minutes" style="width:45%">
            <el-option :value="30" label="0.5 小时" />
            <el-option :value="60" label="1 小时" />
            <el-option :value="90" label="1.5 小时" />
            <el-option :value="120" label="2 小时" />
            <el-option :value="180" label="3 小时" />
            <el-option :value="240" label="4 小时" />
            <el-option :value="300" label="5 小时" />
            <el-option :value="360" label="6 小时" />
            <el-option :value="480" label="8 小时" />
          </el-select>
        </el-form-item>
        <el-form-item label="维护项目">
          <div v-for="(it, i) in form.items" :key="i" style="display:flex;margin-bottom:6px">
            <el-input v-model="form.items[i]" placeholder="例如：更换滤芯" style="flex:1" />
            <el-button size="small" link type="danger" @click="form.items.splice(i,1)" style="margin-left:6px">删</el-button>
          </div>
          <el-button size="small" type="primary" plain @click="form.items.push('')">+ 添加项目</el-button>
        </el-form-item>
        <el-form-item label="下次到期">
          <el-date-picker
            v-model="form.next_due_date" type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%"
          />
        </el-form-item>
        <el-form-item label="启用" v-if="form.id">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Clock, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { listPMPlans, createPMPlan, updatePMPlan, deletePMPlan, generateDuePM, getPMCalendar } from '@/api/work_order'
import { listEquipments } from '@/api/equipment'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'
import dayjs from 'dayjs'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('pm_plan.write'))
const canDelete = computed(() => userStore.can('pm_plan.delete'))

const HOUR_HEIGHT = 42
const HOUR_WIDTH = 56
const FIRST_HOUR = 6
const LAST_HOUR = 23

const activeTab = ref('list')
const query = reactive({ equipment_id: null })
const list = ref([])
const loading = ref(false)
const equipments = ref([])
const bodyRef = ref(null)

// 日历视图
const calendarLoading = ref(false)
const viewMode = ref('week')
const cursor = ref(dayjs().startOf('week').add(1, 'day'))  // 本周周一
const calendarEquipmentId = ref(null)
const plannedEvents = ref([])
const actualEvents = ref([])

// 范围展示
const rangeLabel = computed(() => {
  if (viewMode.value === 'week') {
    const mon = cursor.value.startOf('week').add(1, 'day')
    const sun = mon.add(6, 'day')
    return `${mon.format('YYYY-MM-DD')}  ~  ${sun.format('YYYY-MM-DD')}`
  } else {
    return cursor.value.format('YYYY-MM-DD dddd')
  }
})

function onTabChange(tab) {
  if (tab === 'calendar') loadCalendar()
  else loadList()
}

function onPrevRange() {
  cursor.value = viewMode.value === 'week' ? cursor.value.subtract(1, 'week') : cursor.value.subtract(1, 'day')
  loadCalendar()
}
function onNextRange() {
  cursor.value = viewMode.value === 'week' ? cursor.value.add(1, 'week') : cursor.value.add(1, 'day')
  loadCalendar()
}
function onToday() {
  cursor.value = viewMode.value === 'week' ? dayjs().startOf('week').add(1, 'day') : dayjs()
  loadCalendar()
}

const weekDays = computed(() => {
  const mon = cursor.value.startOf('week').add(1, 'day')
  const wdNames = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const today = dayjs().format('YYYY-MM-DD')
  return Array.from({ length: 7 }, (_, i) => {
    const d = mon.add(i, 'day')
    return {
      dateKey: d.format('YYYY-MM-DD'),
      dateObj: d,
      md: d.format('MM-DD'),
      weekDay: wdNames[i],
      isToday: d.format('YYYY-MM-DD') === today,
    }
  })
})
const dayHours = computed(() => {
  const arr = []
  for (let h = FIRST_HOUR; h <= LAST_HOUR; h++) arr.push({ h })
  return arr
})
const rangeStart = computed(() => {
  if (viewMode.value === 'week') {
    return weekDays.value[0].dateObj.hour(0).minute(0).second(0)
  }
  return cursor.value.hour(0).minute(0).second(0)
})
const rangeEnd = computed(() => {
  if (viewMode.value === 'week') {
    return weekDays.value[6].dateObj.hour(23).minute(59).second(59)
  }
  return cursor.value.hour(23).minute(59).second(59)
})

function fmtHour(iso) {
  if (!iso) return '?'
  const d = dayjs(iso)
  return `${String(d.hour()).padStart(2, '0')}:${String(d.minute()).padStart(2, '0')}`
}

function allEvents() {
  return [...plannedEvents.value, ...actualEvents.value]
}

// 将超时事件拆分为两段：[计划内基础段, 超时段]
// 非超时事件返回 [ev]
function splitEventSegments(ev) {
  if (ev.type !== 'actual' || !ev.is_overtime || !ev.planned_end_time) return [ev]
  const plannedEnd = dayjs(ev.planned_end_time)
  const actualEnd = ev.end_time ? dayjs(ev.end_time) : dayjs(ev.start_time).add(ev.duration_minutes || 0, 'minute')
  // 基础段：从 start 到 planned_end
  const base = { ...ev, _seg: 'base', end_time: plannedEnd.toISOString(), duration_minutes: ev.planned_duration_minutes }
  // 超时段：从 planned_end 到 actual_end
  const over = {
    ...ev,
    _seg: 'overtime',
    id: ev.id + '-OT',
    start_time: plannedEnd.toISOString(),
    end_time: actualEnd.toISOString(),
    duration_minutes: ev.overtime_minutes || ev.duration_minutes - ev.planned_duration_minutes,
  }
  return [base, over]
}

// 周视图：某一天某小时起始行内对应的事件（超时事件拆分后）
function eventsAtSegments(d, h) {
  const day0 = d.dateObj.hour(h).minute(0).second(0).valueOf()
  const day1 = d.dateObj.hour(h + 1).minute(0).second(0).valueOf()
  const out = []
  for (const ev of allEvents()) {
    for (const seg of splitEventSegments(ev)) {
      const s = dayjs(seg.start_time).valueOf()
      if (dayjs(seg.start_time).format('YYYY-MM-DD') !== d.dateKey) continue
      if (s >= day0 && s < day1) out.push(seg)
    }
  }
  return out
}

// 周视图：某一天某小时起始行内对应的事件（未拆分）
function eventsAt(d, h) {
  const day0 = d.dateObj.hour(h).minute(0).second(0).valueOf()
  const day1 = d.dateObj.hour(h + 1).minute(0).second(0).valueOf()
  // 只展示 起始时间落在该小时内 的事件（同一个事件只渲染一次，避免重复）
  return allEvents().filter((ev) => {
    const s = dayjs(ev.start_time).valueOf()
    // 当天
    if (dayjs(ev.start_time).format('YYYY-MM-DD') !== d.dateKey) return false
    return s >= day0 && s < day1
  })
}

function cellStyle(d, h) {
  // 仅作视觉分隔
  const isToday = d.isToday
  return {
    background: isToday ? 'rgba(64,158,255,0.04)' : undefined,
  }
}

// 周视图中事件条的定位样式（绝对定位放在 day-cell 上）
function eventStyle(ev) {
  const start = dayjs(ev.start_time)
  const end = ev.end_time ? dayjs(ev.end_time) : dayjs().add(1, 'hour')
  // 计算距离小时行起始的偏移(分钟比例)，以及持续高度
  const minutesPastHour = start.minute()
  const topPx = (minutesPastHour / 60) * HOUR_HEIGHT
  let spanMinutes = (end.valueOf() - start.valueOf()) / 60000
  if (spanMinutes < 5) spanMinutes = 5
  const heightPx = Math.max(18, Math.round((spanMinutes / 60) * HOUR_HEIGHT) - 2)
  return {
    top: `${topPx + 1}px`,
    height: `${heightPx}px`,
    left: '3px',
    right: '3px',
  }
}

// 日视图：按设备分组（展开超时分段）
const eventsByEquipment = computed(() => {
  const map = {}
  for (const ev of allEvents()) {
    for (const seg of splitEventSegments(ev)) {
      (map[seg.equipment_id] ||= []).push(seg)
    }
  }
  return map
})
const calendarEquipments = computed(() => {
  // 只有在范围内有事件的设备 + 用户选择的设备过滤
  let eqList = equipments.value
  if (calendarEquipmentId.value) {
    eqList = eqList.filter((e) => e.id === calendarEquipmentId.value)
  } else {
    const eqIds = new Set()
    for (const ev of allEvents()) eqIds.add(ev.equipment_id)
    eqList = eqList.filter((e) => eqIds.has(e.id))
  }
  return eqList.sort((a, b) => a.id - b.id)
})
function dayEventStyle(ev) {
  const start = dayjs(ev.start_time)
  const end = ev.end_time ? dayjs(ev.end_time) : dayjs().add(1, 'hour')
  // 小时从 FIRST_HOUR 开始算
  const startMinFrom = Math.max(0, start.hour() - FIRST_HOUR) * 60 + start.minute()
  const widthMin = Math.max(5, (end.valueOf() - start.valueOf()) / 60000)
  const left = (startMinFrom / 60) * HOUR_WIDTH
  const width = Math.max(30, (widthMin / 60) * HOUR_WIDTH)
  return {
    left: `${left}px`,
    width: `${width}px`,
    top: '4px',
    height: 'calc(100% - 8px)',
  }
}

function eventTooltip(ev) {
  if (ev.type === 'planned') {
    const items = (ev.plan_items || []).length ? `\n维护项: ${ev.plan_items.join('、')}` : ''
    return [
      `计划 PM: ${ev.plan_name}`,
      `设备: ${ev.equipment_asset || ''} ${ev.equipment_name}`,
      `时间: ${dayjs(ev.start_time).format('YYYY-MM-DD HH:mm')} ~ ${dayjs(ev.end_time).format('HH:mm')}`,
      `计划时长: ${ev.duration_minutes} 分钟`,
      items,
    ].filter(Boolean).join('\n')
  }
  return [
    `实际 PM 执行${ev.is_overtime ? '（⚠ 超时）' : ''}`,
    `设备: ${ev.equipment_asset || ''} ${ev.equipment_name}`,
    `时段: ${dayjs(ev.start_time).format('YYYY-MM-DD HH:mm')} ~ ${ev.end_time ? dayjs(ev.end_time).format('HH:mm') : '进行中'}`,
    ev.duration_minutes ? `实际时长: ${Math.round(ev.duration_minutes)} 分钟` : '',
    ev.planned_duration_minutes ? `计划时长: ${Math.round(ev.planned_duration_minutes)} 分钟` : '',
    ev.is_overtime
      ? `超出: ${ev.overtime_minutes || (ev.duration_minutes && ev.planned_duration_minutes ? Math.round(ev.duration_minutes - ev.planned_duration_minutes) : '?')} 分钟`
      : '',
    ev.reason_code ? `原因码: ${ev.reason_code}` : '',
    ev.reason_detail ? `详情: ${ev.reason_detail}` : '',
  ].filter(Boolean).join('\n')
}

function onEventClick(ev) {
  if (ev.type === 'planned') {
    // 找对应 plan 打开编辑
    const plan = list.value.find((p) => p.id === ev.plan_id)
    if (plan) openDialog(plan)
    else ElMessage.info(`计划 ID ${ev.plan_id}`)
  } else {
    ElMessage.info({
      message: [
        `实际 PM 执行`,
        `设备: ${ev.equipment_name}`,
        `时段: ${dayjs(ev.start_time).format('YYYY-MM-DD HH:mm')} ~ ${ev.end_time ? dayjs(ev.end_time).format('HH:mm') : '进行中'}`,
        ev.reason_detail ? `原因: ${ev.reason_detail}` : '',
      ].filter(Boolean).join('｜'),
      duration: 4000,
    })
  }
}

function eqName(id) {
  const e = equipments.value.find((x) => x.id === id)
  return e ? `${e.asset_no || ''} ${e.name}` : `#${id}`
}
function isOverdue(d) {
  return d && dayjs(d).isBefore(dayjs())
}

async function loadEquipments() {
  equipments.value = await listEquipments({ limit: 500 })
}
async function loadList() {
  loading.value = true
  try {
    const params = {}
    if (query.equipment_id) params.equipment_id = query.equipment_id
    list.value = await listPMPlans(params)
  } finally {
    loading.value = false
  }
}

async function loadCalendar() {
  calendarLoading.value = true
  try {
    const params = {
      start: rangeStart.value.toISOString(),
      end: rangeEnd.value.toISOString(),
    }
    if (calendarEquipmentId.value) params.equipment_id = calendarEquipmentId.value
    const r = await getPMCalendar(params)
    plannedEvents.value = r.planned_events || []
    actualEvents.value = r.actual_events || []
    await nextTick()
    if (bodyRef.value) bodyRef.value.scrollTop = 0
  } finally {
    calendarLoading.value = false
  }
}

// 表单
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const dialogTitle = computed(() => form.id ? '编辑 PM 计划' : '新建 PM 计划')
const form = reactive({
  id: null,
  equipment_id: null,
  name: '',
  cycle_days: 90,
  items: [],
  next_due_date: null,
  planned_start_hour: 9,
  planned_duration_minutes: 120,
  is_active: true,
})
const formRules = {
  equipment_id: [{ required: true, message: '请选择设备', trigger: 'change' }],
  name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  cycle_days: [{ required: true, message: '请输入周期', trigger: 'blur' }],
}
function openDialog(row) {
  if (row) {
    Object.assign(form, {
      id: row.id,
      equipment_id: row.equipment_id,
      name: row.name,
      cycle_days: row.cycle_days,
      items: Array.isArray(row.items) ? [...row.items] : [],
      next_due_date: row.next_due_date,
      planned_start_hour: row.planned_start_hour ?? 9,
      planned_duration_minutes: row.planned_duration_minutes ?? 120,
      is_active: row.is_active !== false,
    })
  } else {
    Object.assign(form, {
      id: null,
      equipment_id: null,
      name: '',
      cycle_days: 90,
      items: [],
      next_due_date: dayjs().add(7, 'day').format('YYYY-MM-DDTHH:mm:ss'),
      planned_start_hour: 9,
      planned_duration_minutes: 120,
      is_active: true,
    })
  }
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = { ...form, items: form.items.filter((x) => x) }
    delete payload.id
    if (form.id) {
      await updatePMPlan(form.id, payload)
      ElMessage.success('已更新')
    } else {
      await createPMPlan(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadList()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除 PM 计划【${row.name}】？`, '提示', { type: 'warning' })
    await deletePMPlan(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e) {}
}
async function onGenerateDue() {
  try {
    const r = await generateDuePM()
    ElMessage.success(`已生成 ${r.generated} 个到期 PM 工单`)
    loadList()
  } catch (e) {}
}

onMounted(async () => {
  await loadEquipments()
  if (activeTab.value === 'list') await loadList()
  else await loadCalendar()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.toolbar { margin-bottom: 10px; }
.plan-time { display: flex; align-items: center; gap: 4px; font-size: 13px; color: #606266; }
.plan-time .sep { color: #c0c4cc; margin: 0 2px; }

/* 日历样式 */
.calendar-wrap { overflow: hidden; border: 1px solid #ebeef5; border-radius: 4px; }
.swatch { display: inline-block; width: 12px; height: 12px; border-radius: 2px; vertical-align: middle; margin-right: 4px; border: 1px solid transparent; }
.swatch.planned { background: #ecf5ff; border-color: #409eff; }
.swatch.actual { background: #67c23a; }
.swatch.overtime { background: repeating-linear-gradient(45deg, #f56c6c, #f56c6c 4px, #fef0f0 4px, #fef0f0 8px); border-color: #f56c6c; }

/* 周视图 */
.week-cal { display: flex; flex-direction: column; }
.week-cal-head, .hour-row {
  display: grid;
  grid-template-columns: 56px repeat(7, 1fr);
}
.week-cal-head {
  background: #fafafa; border-bottom: 1px solid #ebeef5; position: sticky; top: 0; z-index: 2;
}
.week-cal-head .hour-label, .hour-row .hour-label {
  padding: 6px 8px; border-right: 1px solid #ebeef5;
  text-align: right; color: #909399; font-size: 12px;
  border-bottom: 1px solid #ebeef5;
}
.day-head {
  text-align: center; padding: 6px 4px; border-right: 1px solid #ebeef5;
  border-bottom: 1px solid #ebeef5;
}
.day-head.today { background: #ecf5ff; }
.day-head .date-text { font-weight: 600; font-size: 13px; }
.day-head.today .date-text { color: #409eff; }
.day-head .week-text { font-size: 11px; color: #909399; margin-top: 2px; }
.week-cal-body { overflow-y: auto; max-height: 70vh; }
.hour-row .day-cell {
  position: relative; border-right: 1px solid #f2f6fc;
  border-bottom: 1px dashed #f2f6fc;
}
.event-bar {
  position: absolute;
  z-index: 1;
  border-radius: 4px;
  padding: 2px 6px;
  overflow: hidden;
  cursor: pointer;
  box-sizing: border-box;
  transition: filter .15s;
}
.event-bar:hover { filter: brightness(.95); }
.event-bar.planned {
  background: #ecf5ff; color: #409eff;
  border: 1px solid #409eff;
}
.event-bar.actual {
  background: linear-gradient(135deg, #67c23a, #85ce61);
  color: #fff;
  border: 1px solid #529b2e;
}
/* 超时段警示：橙红斜纹（仅事件中超出的部分） */
.event-bar.actual.overtime-seg {
  background: repeating-linear-gradient(135deg, #f56c6c 0, #f56c6c 6px, #fef0f0 6px, #fef0f0 12px);
  color: #b8392b;
  border: 2px solid #f56c6c;
  box-shadow: 0 0 0 1px rgba(245, 108, 108, 0.4) inset;
  font-weight: 600;
  z-index: 2;
}
.event-bar.actual.overtime-seg::before {
  content: "⚠";
  margin-right: 3px;
  font-size: 11px;
}
.event-bar .ev-title { font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event-bar .ev-sub { font-size: 11px; opacity: .9; margin-top: 2px; font-variant-numeric: tabular-nums; }
.event-bar.planned .ev-sub { opacity: .75; }
.event-bar .dur { margin-left: 4px; opacity: .85; }

/* 日视图 */
.day-cal { width: 100%; overflow: hidden; }
.day-cal-scroll { overflow: auto; max-height: 70vh; }
.day-cal-head {
  display: flex; background: #fafafa;
  border-bottom: 1px solid #ebeef5;
  position: sticky; top: 0; z-index: 3;
}
.eq-head {
  width: 200px; flex-shrink: 0;
  padding: 8px 10px; border-right: 1px solid #ebeef5; font-weight: 600; color: #606266;
  position: sticky; left: 0; z-index: 4; background: #fafafa;
}
.hours-head { display: flex; }
.hour-col {
  flex-shrink: 0; padding: 8px 0; text-align: center;
  border-right: 1px solid #ebeef5; color: #909399; font-size: 12px;
}
.eq-row {
  display: flex; border-bottom: 1px solid #ebeef5;
}
.eq-row .eq-name {
  width: 200px; flex-shrink: 0;
  padding: 8px 10px; border-right: 1px solid #ebeef5;
  display: flex; flex-direction: column; justify-content: center;
  position: sticky; left: 0; z-index: 2; background: #fff;
}
.eq-row .nm { font-weight: 600; font-size: 13px; }
.eq-row .no { font-size: 11px; color: #909399; margin-top: 2px; }
.hours-track {
  position: relative; display: flex;
}
.hour-cell {
  flex-shrink: 0; height: 54px;
  border-right: 1px dashed #f2f6fc;
}
.day-ev {
  height: calc(100% - 8px) !important; top: 4px !important;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px;
}
.ev-title-sm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600; }
</style>
