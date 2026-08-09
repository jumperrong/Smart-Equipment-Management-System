<template>
  <div>
    <!-- 顶部状态小方块：DOWN 机 / PM 进行中（含超时） -->
    <div class="status-tiles">
      <div class="tile tile-down" :class="{ 'has-count': summary.down > 0 }" @click="filterByStatus('DOWN')">
        <div class="tile-num">{{ summary.down || 0 }}</div>
        <div class="tile-label">DOWN 机</div>
      </div>
      <div
        class="tile tile-pm"
        :class="{ 'has-count': summary.pm > 0, 'has-overtime': summary.pm_overtime > 0 }"
        @click="filterByStatus('PM')"
      >
        <div class="tile-num">{{ summary.pm || 0 }}</div>
        <div class="tile-label">
          PM 进行中
          <span v-if="summary.pm_overtime > 0" class="ot-sub">⚠ 超时 {{ summary.pm_overtime }}</span>
        </div>
      </div>
    </div>
    <!-- 设备实时状态（标题栏带筛选） -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span style="font-weight:600">设备实时状态</span>
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
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { getDashboard } from '@/api/dashboard'
import {
  statusLabel, statusType, STATUS_OPTIONS,
  formatTime, formatDuration,
} from '@/utils'

const router = useRouter()
const loading = ref(false)

const equipments = ref([])
const summary = ref({})

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
  return equipments.value.filter((e) => {
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
function onFilter() { /* 计算属性自动响应，此处占位以便绑定事件 */ }
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
  // 表格内空间有限：只保留状态码
  return (
    { RUN: 'RUN', IDLE: 'IDLE', DOWN: 'DOWN', PM: 'PM',
      ENGINEERING: 'ENG', PROCESS_VALIDATION: 'PV',
      OTHER: 'OTHER', OFFLINE: 'OFF' }[s]
  ) || s
}

async function load() {
  loading.value = true
  try {
    const data = await getDashboard()
    equipments.value = data.equipments || []
    summary.value = data.summary || {}
  } finally {
    loading.value = false
  }
}

function onRowClick(row) {
  router.push(`/equipment/${row.id}`)
}

// 点击小方块：按状态筛选
function filterByStatus(status) {
  filterStatus.value = status
}

onMounted(load)
</script>

<style scoped>
/* 顶部状态小方块 */
.status-tiles {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.tile {
  flex: 1;
  max-width: 240px;
  padding: 14px 16px;
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
  font-size: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  color: var(--app-text-secondary);
}
.tile-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.tile-down.has-count { background: var(--app-danger-bg); border-color: var(--app-danger); }
.tile-down.has-count .tile-num,
.tile-down.has-count .tile-label { color: var(--app-danger); }
.tile-pm.has-count { background: var(--app-success-bg); border-color: var(--app-success); }
.tile-pm.has-count .tile-num,
.tile-pm.has-count .tile-label { color: var(--app-success); }
/* PM 进行中且其中存在超时：边框转红 + 红斜纹背景提示风险 */
.tile-pm.has-overtime {
  background: repeating-linear-gradient(135deg, var(--app-success-bg) 0, var(--app-success-bg) 10px, var(--app-danger-bg) 10px, var(--app-danger-bg) 20px);
  border-color: var(--app-danger);
}
.tile-pm.has-overtime .ot-sub {
  margin-left: 6px;
  color: var(--app-danger);
  font-weight: 600;
  font-size: 11px;
}

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
</style>
