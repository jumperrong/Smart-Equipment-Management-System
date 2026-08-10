<template>
  <div>
    <!-- 角色标识 -->
    <div class="role-banner">
      <el-tag :type="roleTagType" effect="dark" size="default">
        <el-icon style="vertical-align:middle"><User /></el-icon>
        {{ roleLabel }} 看板
      </el-tag>
      <span class="role-hint">{{ roleHint }}</span>
    </div>

    <!-- 顶部 KPI 方块（按角色定制） -->
    <div class="status-tiles">
      <div
        v-for="t in kpiTiles"
        :key="t.key"
        class="tile"
        :class="[t.cls, { 'has-count': t.value > 0 }]"
        @click="onTileClick(t)"
      >
        <div class="tile-num">{{ t.value ?? 0 }}</div>
        <div class="tile-label">{{ t.label }}</div>
        <div v-if="t.sub" class="tile-sub">{{ t.sub }}</div>
      </div>
    </div>

    <!-- 主区块：按 role_widgets 顺序渲染 -->
    <!-- 设备实时状态表 -->
    <el-card v-if="widgets.includes('equipment_status') || widgets.includes('process_validation_equipment')" shadow="never">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span style="font-weight:600">
              {{ widgets.includes('process_validation_equipment') && role === 'process_engineer'
                 ? '工艺验证中设备' : '设备实时状态' }}
            </span>
            <el-tag size="small" type="info">显示 {{ filteredEquipments.length }} / {{ equipments.length }} 台</el-tag>
          </div>
          <div class="header-right">
            <el-select v-model="filterStatus" placeholder="全部状态" clearable size="small" style="width:150px" @change="onFilter">
              <el-option v-for="s in statusOptionList" :key="s" :label="statusLabel(s)" :value="s" />
            </el-select>
            <el-select v-model="filterFactory" placeholder="全部厂区" clearable size="small" style="width:140px;margin-left:8px" @change="onFilter">
              <el-option v-for="f in factoryOptions" :key="f" :label="f" :value="f" />
            </el-select>
            <el-select v-model="filterArea" placeholder="全部区域" clearable size="small" style="width:120px;margin-left:8px" @change="onFilter">
              <el-option v-for="a in areaOptions" :key="a" :label="a" :value="a" />
            </el-select>
            <el-input v-model="filterKeyword" placeholder="设备名/编号" clearable size="small" style="width:160px;margin-left:8px" @input="onFilter" />
            <el-button size="small" style="margin-left:8px" @click="resetFilter">重置</el-button>
          </div>
        </div>
      </template>
      <el-table :data="filteredEquipments" stripe v-loading="loading" border size="small" @row-click="onRowClick">
        <el-table-column label="设备" width="160">
          <template #default="{ row }">
            <div class="eq-cell" :title="`${row.name}${row.asset_no ? ' / ' + row.asset_no : ''}`">
              <span class="eq-name">{{ truncate(row.name, 20) }}</span>
              <span class="eq-asset">{{ row.asset_no ? truncate(row.asset_no, 10) : '-' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前状态" width="190" align="center">
          <template #default="{ row }">
            <div class="status-now-cell">
              <el-tag :type="statusType(row.current_status)" size="default" effect="dark" class="main-tag">
                {{ statusLabel(row.current_status) }}
              </el-tag>
              <div class="status-track" v-if="row.last_from_status">
                <el-tag :type="statusType(row.last_from_status)" size="small" effect="plain">{{ shortStatusLabel(row.last_from_status) }}</el-tag>
                <span class="track-arrow">→</span>
                <span class="track-to muted">{{ shortStatusLabel(row.last_to_status || row.current_status) }}</span>
              </div>
              <div class="status-track muted" v-else>首次记录</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态持续" width="120" align="center">
          <template #default="{ row }">
            <span :class="{'status-duration': true, 'danger': row.current_status === 'DOWN'}">
              {{ formatDuration(row.status_duration_minutes) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="变更原因 & 操作人" min-width="260">
          <template #default="{ row }">
            <div v-if="row.last_reason_code || row.last_reason_detail || row.last_operator_name">
              <div class="reason-row">
                <span class="reason" v-if="row.last_reason_code">{{ row.last_reason_code }}</span>
                <span class="op" v-if="row.last_operator_name" :title="'操作人: ' + row.last_operator_name">👤 {{ truncate(row.last_operator_name, 10) }}</span>
              </div>
              <div class="detail-row" v-if="row.last_reason_detail" :title="row.last_reason_detail">
                {{ truncate(row.last_reason_detail, 30) }}
              </div>
            </div>
            <span v-else class="muted">暂无变更原因</span>
          </template>
        </el-table-column>
        <el-table-column label="变更时间" width="160">
          <template #default="{ row }">{{ row.last_change_time ? formatTime(row.last_change_time) : '-' }}</template>
        </el-table-column>
      </el-table>
      <div class="tip-text">点击行可查看设备档案</div>
    </el-card>

    <!-- 我处理中的工单（engineer / operator） -->
    <el-card v-if="widgets.includes('my_open_work_orders')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">📋 我处理中的工单</span>
          <el-tag size="small" type="warning">{{ summary.my_open_work_orders || 0 }} 条</el-tag>
        </div>
      </template>
      <el-table :data="myOpenWorkOrders" border size="small" empty-text="暂无待处理工单">
        <el-table-column prop="order_no" label="工单号" width="130" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="equipment_name" label="设备" width="150" />
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ row.created_at ? formatTime(row.created_at) : '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 待审核文档清单（QA / 工艺员） -->
    <el-card v-if="widgets.includes('pending_review_docs')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">📑 待审核文档</span>
          <el-tag size="small" type="danger">{{ summary.docs_pending_review || 0 }} 份待审</el-tag>
        </div>
      </template>
      <el-table :data="pendingReviewDocs" border size="small" empty-text="暂无待审核文档">
        <el-table-column prop="doc_no" label="文档编号" width="160" />
        <el-table-column prop="doc_name" label="文档名称" min-width="240" show-overflow-tooltip />
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }">{{ row.updated_at ? formatTime(row.updated_at) : '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 复审到期文档清单（admin / qa / 工艺员） -->
    <el-card v-if="widgets.includes('review_overdue_docs')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">⚠ 复审到期文档</span>
          <el-tag size="small" type="warning">{{ summary.docs_review_overdue || 0 }} 份到期/即将到期</el-tag>
        </div>
      </template>
      <el-table :data="reviewOverdueDocs" border size="small" empty-text="暂无复审到期文档">
        <el-table-column prop="doc_no" label="文档编号" width="160" />
        <el-table-column prop="doc_name" label="文档名称" min-width="240" show-overflow-tooltip />
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column label="下次复审日" width="160">
          <template #default="{ row }">
            <span :class="{ 'alert-text': row.is_overdue }">
              {{ row.next_review_date ? formatTime(row.next_review_date) : '-' }}
            </span>
            <el-tag v-if="row.is_overdue" type="danger" size="small" effect="plain" style="margin-left:6px">已过期</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 故障复发 TOP（engineer） -->
    <el-card v-if="widgets.includes('top_recurrence')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">🔁 故障复发 TOP 5</span>
          <el-tag size="small" type="info">高频根因追踪</el-tag>
        </div>
      </template>
      <el-table :data="topRecurrence" border size="small" empty-text="暂无复发记录">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="fault_category" label="故障分类" width="120" />
        <el-table-column prop="symptom" label="现象" min-width="200" show-overflow-tooltip />
        <el-table-column prop="recurrence_count" label="复发次数" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="danger" size="small" effect="dark">{{ row.recurrence_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览数" width="90" align="center" />
      </el-table>
    </el-card>

    <!-- 低库存备件清单（admin / engineer） -->
    <el-card v-if="widgets.includes('low_stock_parts')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">📦 低于安全库存备件</span>
          <el-tag size="small" type="danger">{{ summary.low_stock_parts || 0 }} 种</el-tag>
        </div>
      </template>
      <el-table :data="lowStockParts" border size="small" empty-text="库存充足">
        <el-table-column prop="sku" label="编号" width="140" />
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" min-width="180" show-overflow-tooltip />
        <el-table-column label="当前/安全" width="120" align="center">
          <template #default="{ row }">
            <span class="alert-text">{{ row.current_stock }}</span>
            <span class="muted"> / {{ row.safety_stock }} {{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="库位" width="120" />
      </el-table>
    </el-card>

    <!-- 安全检查告警清单（admin / engineer / qa） -->
    <el-card v-if="widgets.includes('safety_alerts')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">🛡 安全检查告警</span>
          <el-tag size="small" type="warning">检查到期 {{ summary.safety_check_due || 0 }} / 证书到期 {{ summary.safety_certificate_expiring || 0 }}</el-tag>
        </div>
      </template>
      <el-table :data="safetyAlerts" border size="small" empty-text="无到期项">
        <el-table-column prop="check_name" label="检查项目" min-width="180" show-overflow-tooltip />
        <el-table-column prop="check_type" label="类型" width="120" />
        <el-table-column label="下次检查" width="160">
          <template #default="{ row }">
            <span :class="{ 'alert-text': isPast(row.next_check_date) }">
              {{ row.next_check_date ? formatTime(row.next_check_date) : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="证书到期" width="160">
          <template #default="{ row }">
            <span :class="{ 'alert-text': isPast(row.certificate_expiry) }">
              {{ row.certificate_expiry ? formatTime(row.certificate_expiry) : '-' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 润滑到期清单（engineer） -->
    <el-card v-if="widgets.includes('lubrication_due')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">🛢 润滑到期（7天内）</span>
          <el-tag size="small" type="warning">{{ summary.lubrication_due || 0 }} 项</el-tag>
        </div>
      </template>
      <el-table :data="lubricationDue" border size="small" empty-text="暂无到期">
        <el-table-column prop="point_name" label="润滑点" min-width="160" show-overflow-tooltip />
        <el-table-column prop="position" label="位置" width="140" />
        <el-table-column prop="oil_type" label="油品" width="140" />
        <el-table-column prop="responsible_person" label="负责人" width="120" />
        <el-table-column label="下次润滑日" width="160">
          <template #default="{ row }">
            <span :class="{ 'alert-text': isPast(row.next_lubrication_date) }">
              {{ row.next_lubrication_date ? formatTime(row.next_lubrication_date) : '-' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 最近工单（admin） -->
    <el-card v-if="widgets.includes('recent_work_orders')" shadow="never" class="block-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight:600">📝 最近工单</span>
          <el-tag size="small" type="info">{{ recentWorkOrders.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="recentWorkOrders" border size="small" empty-text="暂无工单">
        <el-table-column prop="order_no" label="工单号" width="130" />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="equipment_name" label="设备" width="150" />
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ row.created_at ? formatTime(row.created_at) : '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getDashboard } from '@/api/dashboard'
import { useUserStore } from '@/stores'
import {
  statusLabel, statusType, STATUS_OPTIONS,
  formatTime, formatDuration,
} from '@/utils'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

const equipments = ref([])
const summary = ref({})
const widgets = ref([])
const pendingReviewDocs = ref([])
const reviewOverdueDocs = ref([])
const myOpenWorkOrders = ref([])
const topRecurrence = ref([])
const lowStockParts = ref([])
const safetyAlerts = ref([])
const lubricationDue = ref([])
const recentWorkOrders = ref([])

// 设备表筛选
const filterFactory = ref('')
const filterArea = ref('')
const filterStatus = ref('')
const filterKeyword = ref('')

const statusOptionList = STATUS_OPTIONS

const factoryOptions = computed(() => {
  const set = new Set()
  equipments.value.forEach((e) => { if (e.factory) set.add(e.factory) })
  return Array.from(set).sort()
})
const areaOptions = computed(() => {
  const set = new Set()
  equipments.value.forEach((e) => { if (e.area) set.add(e.area) })
  return Array.from(set).sort()
})
const filteredEquipments = computed(() => {
  let list = equipments.value
  // 工艺员：默认只显示 ENGINEERING + PROCESS_VALIDATION
  if (userStore.role === 'process_engineer' && !filterStatus.value && !filterFactory.value && !filterArea.value && !filterKeyword.value) {
    list = list.filter((e) => ['ENGINEERING', 'PROCESS_VALIDATION'].includes(e.current_status))
  }
  return list.filter((e) => {
    if (filterFactory.value && e.factory !== filterFactory.value) return false
    if (filterArea.value && e.area !== filterArea.value) return false
    if (filterStatus.value && e.current_status !== filterStatus.value) return false
    if (filterKeyword.value) {
      const kw = filterKeyword.value.toLowerCase()
      if (!(e.name || '').toLowerCase().includes(kw) && !(e.asset_no || '').toLowerCase().includes(kw)) return false
    }
    return true
  })
})
function onFilter() { /* 计算属性自动响应 */ }
function resetFilter() {
  filterFactory.value = ''
  filterArea.value = ''
  filterStatus.value = ''
  filterKeyword.value = ''
}

function truncate(text, max) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '…' : text
}
function shortStatusLabel(s) {
  return (
    { RUN: 'RUN', IDLE: 'IDLE', DOWN: 'DOWN', PM: 'PM',
      ENGINEERING: 'ENG', PROCESS_VALIDATION: 'PV',
      OTHER: 'OTHER', OFFLINE: 'OFF' }[s]
  ) || s
}

// 角色标识
const roleLabel = computed(() => ({
  admin: '管理员', engineer: '设备工程师', process_engineer: '工艺工程师',
  qa: 'QA审核员', operator: '操作员', viewer: '查看者',
}[userStore.role] || userStore.role || ''))

const roleTagType = computed(() => ({
  admin: 'danger', engineer: 'primary', process_engineer: 'warning',
  qa: 'danger', operator: 'success', viewer: 'info',
}[userStore.role] || 'info'))

const roleHint = computed(() => ({
  admin: '全局视野：设备/工单/文控/备件/安全全维度',
  engineer: '聚焦设备健康与维修执行',
  process_engineer: '聚焦工艺验证与文控审批',
  qa: '聚焦文控审核与合规告警',
  operator: '聚焦我的点检与工单执行',
  viewer: '只读概览',
}[userStore.role] || ''))

// KPI 方块按角色定制
const kpiTiles = computed(() => {
  const s = summary.value || {}
  const role = userStore.role
  const tiles = []
  const make = (key, label, value, cls = '', sub = '') => ({ key, label, value, cls, sub })

  if (role === 'admin') {
    tiles.push(make('total', '设备总数', s.total, 'tile-info'))
    tiles.push(make('running', 'RUN 运行', s.running, 'tile-success'))
    tiles.push(make('down', 'DOWN 机', s.down, 'tile-danger'))
    tiles.push(make('pm_ot', 'PM 超时', s.pm_overtime, 'tile-warning'))
    tiles.push(make('oee', 'OEE %', s.oee, 'tile-primary'))
    tiles.push(make('sla', 'SLA 违约', s.sla_breached_count, 'tile-danger'))
    tiles.push(make('low_stock', '低库存备件', s.low_stock_parts, 'tile-warning'))
    tiles.push(make('docs_review', '复审到期文档', s.docs_review_overdue, 'tile-warning'))
    tiles.push(make('safety', '安全检查到期', s.safety_check_due, 'tile-danger'))
  } else if (role === 'engineer') {
    tiles.push(make('down', 'DOWN 机', s.down, 'tile-danger'))
    tiles.push(make('pm', 'PM 进行中', s.pm, 'tile-success', s.pm_overtime > 0 ? `⚠ 超时 ${s.pm_overtime}` : ''))
    tiles.push(make('my_wo', '我处理中工单', s.my_open_work_orders, 'tile-warning'))
    tiles.push(make('sla', 'SLA 违约', s.sla_breached_count, 'tile-danger'))
    tiles.push(make('low_stock', '低库存备件', s.low_stock_parts, 'tile-warning'))
    tiles.push(make('lub', '润滑到期', s.lubrication_due, 'tile-warning'))
    tiles.push(make('safety', '安全检查到期', s.safety_check_due, 'tile-danger'))
  } else if (role === 'process_engineer') {
    tiles.push(make('pv', '工艺验证中设备', s.process_validation_count, 'tile-warning'))
    tiles.push(make('my_draft', '我的草稿文档', s.my_draft_docs, 'tile-info'))
    tiles.push(make('docs_review', '复审到期文档', s.docs_review_overdue, 'tile-warning'))
    tiles.push(make('docs_pend', '待审核文档', s.docs_pending_review, 'tile-danger'))
    tiles.push(make('my_wo', '我的工单', s.my_process_work_orders, 'tile-info'))
  } else if (role === 'qa') {
    tiles.push(make('docs_pend', '待审核文档', s.docs_pending_review, 'tile-danger'))
    tiles.push(make('docs_approve', '待批准文档', s.docs_pending_approve, 'tile-warning'))
    tiles.push(make('docs_review', '复审到期文档', s.docs_review_overdue, 'tile-warning'))
    tiles.push(make('form_audit', '表单待审核', s.form_records_pending_audit, 'tile-danger'))
    tiles.push(make('amend', '附加修正待审批', s.amendments_pending, 'tile-warning'))
    tiles.push(make('safety_cert', '证书到期', s.safety_certificate_expiring, 'tile-danger'))
  } else if (role === 'operator') {
    tiles.push(make('down', 'DOWN 机', s.down, 'tile-danger'))
    tiles.push(make('pm', 'PM 进行中', s.pm, 'tile-success'))
    tiles.push(make('my_wo', '我处理中工单', s.my_open_work_orders, 'tile-warning'))
    tiles.push(make('insp', '我未完成点检', s.my_inspection_pending, 'tile-danger'))
  } else {
    // viewer
    tiles.push(make('total', '设备总数', s.total, 'tile-info'))
    tiles.push(make('running', 'RUN 运行', s.running, 'tile-success'))
    tiles.push(make('down', 'DOWN 机', s.down, 'tile-danger'))
    tiles.push(make('oee', 'OEE %', s.oee, 'tile-primary'))
  }
  return tiles
})

function onTileClick(t) {
  // 点击方块联动筛选（仅对设备状态类有效）
  if (t.key === 'down') filterStatus.value = 'DOWN'
  else if (t.key === 'pm' || t.key === 'pm_ot') filterStatus.value = 'PM'
  else if (t.key === 'running') filterStatus.value = 'RUN'
}

function isPast(dateStr) {
  if (!dateStr) return false
  return new Date(dateStr) <= new Date()
}

async function load() {
  loading.value = true
  try {
    const data = await getDashboard()
    equipments.value = data.equipments || []
    summary.value = data.summary || {}
    widgets.value = data.role_widgets || []
    pendingReviewDocs.value = data.pending_review_docs || []
    reviewOverdueDocs.value = data.review_overdue_docs || []
    myOpenWorkOrders.value = data.my_open_work_orders_list || []
    topRecurrence.value = data.top_recurrence_knowledge || []
    lowStockParts.value = data.low_stock_parts_list || []
    safetyAlerts.value = data.safety_alerts_list || []
    lubricationDue.value = data.lubrication_due_list || []
    recentWorkOrders.value = data.recent_work_orders || []
  } finally {
    loading.value = false
  }
}

function onRowClick(row) {
  router.push(`/equipment/${row.id}`)
}

onMounted(load)
</script>

<style scoped>
/* 角色标识 */
.role-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.role-hint {
  font-size: 12px;
  color: var(--app-text-secondary);
}
/* 顶部 KPI 方块 */
.status-tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}
.tile {
  flex: 1 1 110px;
  min-width: 110px;
  max-width: 200px;
  padding: 12px 14px;
  border-radius: 6px;
  background: var(--app-info-bg);
  border: 1px solid var(--app-border);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: all .15s;
  user-select: none;
}
.tile:hover {
  transform: translateY(-2px);
  box-shadow: var(--app-shadow-hover);
}
.tile-num {
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  color: var(--app-text-secondary);
}
.tile-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--app-text-secondary);
  text-align: center;
}
.tile-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--app-danger);
  font-weight: 600;
}
.tile.has-count.tile-danger { background: var(--app-danger-bg); border-color: var(--app-danger); }
.tile.has-count.tile-danger .tile-num,
.tile.has-count.tile-danger .tile-label { color: var(--app-danger); }
.tile.has-count.tile-warning { background: var(--app-warning-bg); border-color: var(--app-warning); }
.tile.has-count.tile-warning .tile-num,
.tile.has-count.tile-warning .tile-label { color: var(--app-warning); }
.tile.has-count.tile-success { background: var(--app-success-bg); border-color: var(--app-success); }
.tile.has-count.tile-success .tile-num,
.tile.has-count.tile-success .tile-label { color: var(--app-success); }
.tile.has-count.tile-primary { background: var(--app-primary-light); border-color: var(--app-primary); }
.tile.has-count.tile-primary .tile-num,
.tile.has-count.tile-primary .tile-label { color: var(--app-primary); }

.block-card { margin-top: 12px; }
.card-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; }
.eq-cell { display: flex; flex-direction: column; line-height: 1.4; }
.eq-name {
  font-weight: 600; color: var(--app-text-primary); font-size: 13px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;
}
.eq-asset {
  font-size: 12px; color: var(--app-text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;
}
.status-now-cell {
  display: flex; flex-direction: column; align-items: center; gap: 4px; line-height: 1.2;
}
.status-now-cell .main-tag {
  font-weight: 600; padding: 2px 10px;
}
.status-now-cell .status-track {
  display: flex; align-items: center; gap: 3px; font-size: 12px;
}
.status-now-cell .track-arrow { color: var(--app-text-muted); }
.status-now-cell .track-to {
  font-size: 11px; color: var(--app-text-secondary); font-weight: 500;
}
.status-duration { font-weight: 600; color: var(--app-text-primary); font-variant-numeric: tabular-nums; }
.status-duration.danger { color: var(--app-danger); }
.reason-row {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  line-height: 1.4;
}
.reason-row .reason {
  font-size: 12px;
  background: var(--app-primary-light);
  color: var(--app-primary);
  border-radius: 3px; padding: 1px 6px; font-weight: 500;
}
.reason-row .op {
  font-size: 12px; color: var(--app-text-regular);
}
.detail-row {
  margin-top: 3px;
  font-size: 12px; color: var(--app-text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 280px;
}
.muted { color: var(--app-text-muted); font-size: 12px; }
.tip-text { margin-top: 8px; color: var(--app-text-secondary); font-size: 12px; }
.alert-text { color: var(--app-danger); font-weight: 600; }
</style>
