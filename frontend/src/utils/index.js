import dayjs from 'dayjs'
export { dayjs }

export const STATUS_OPTIONS = [
  'RUN',
  'IDLE',
  'DOWN',
  'PM',
  'ENGINEERING',
  'PROCESS_VALIDATION',
  'OTHER',
  'OFFLINE',
]

export function statusLabel(s) {
  return (
    {
      RUN: '运行 RUN',
      IDLE: '待机 IDLE',
      DOWN: '故障 DOWN',
      PM: '维护 PM',
      ENGINEERING: '工程 ENGINEERING',
      PROCESS_VALIDATION: '工艺验证 PV',
      OTHER: '其他 OTHER',
      OFFLINE: '离线 OFFLINE',
    }[s] || s
  )
}

export function statusType(s) {
  return (
    {
      RUN: 'success',
      DOWN: 'danger',
      PM: 'warning',
      IDLE: 'info',
      ENGINEERING: 'primary',
      PROCESS_VALIDATION: 'warning',
      OTHER: 'info',
      OFFLINE: 'info',
    }[s] || 'info'
  )
}

// 切换到该状态时是否必须填写"详细原因"
export function requiresDetail(s) {
  return s === 'OTHER'
}

// ---------- 工单 ----------
export const WORK_ORDER_TYPE_OPTIONS = ['PM', 'REPAIR']
export function woTypeLabel(t) {
  return ({ PM: '预防性维护', REPAIR: '故障维修' }[t]) || t
}
export function woTypeTag(t) {
  return ({ PM: 'warning', REPAIR: 'danger' }[t]) || 'info'
}

export const WORK_ORDER_STATUS_OPTIONS = [
  'CREATED', 'ASSIGNED', 'IN_PROGRESS', 'PENDING_REVIEW', 'COMPLETED', 'CANCELLED',
]
export function woStatusLabel(s) {
  return ({
    CREATED: '已创建',
    ASSIGNED: '已派工',
    IN_PROGRESS: '执行中',
    PENDING_REVIEW: '待验收',
    COMPLETED: '已完成',
    CANCELLED: '已取消',
  }[s]) || s
}
export function woStatusTag(s) {
  return ({
    CREATED: 'info',
    ASSIGNED: 'primary',
    IN_PROGRESS: 'warning',
    PENDING_REVIEW: 'warning',
    COMPLETED: 'success',
    CANCELLED: 'info',
  }[s]) || 'info'
}

export const FAULT_CATEGORY_OPTIONS = [
  'MECHANICAL', 'ELECTRICAL', 'PROCESS', 'SOFTWARE', 'CONSUMABLE', 'OTHER',
]
export function faultCategoryLabel(c) {
  return ({
    MECHANICAL: '机械',
    ELECTRICAL: '电气',
    PROCESS: '工艺',
    SOFTWARE: '软件',
    CONSUMABLE: '耗材/备件',
    OTHER: '其他',
  }[c]) || c
}

export const URGENCY_OPTIONS = ['LOW', 'NORMAL', 'HIGH', 'CRITICAL']
export function urgencyLabel(u) {
  return ({ LOW: '低', NORMAL: '普通', HIGH: '高', CRITICAL: '紧急' }[u]) || u
}
export function urgencyTag(u) {
  return ({ LOW: 'info', NORMAL: '', HIGH: 'warning', CRITICAL: 'danger' }[u]) || 'info'
}

// ---------- 点检 ----------
export const FREQUENCY_OPTIONS = ['DAILY', 'WEEKLY', 'MONTHLY']
export function frequencyLabel(f) {
  return ({ DAILY: '日检', WEEKLY: '周检', MONTHLY: '月检' }[f]) || f
}

// ---------- 备件出入库 ----------
export const MOVEMENT_TYPE_OPTIONS = ['IN', 'OUT', 'ADJUST']
export function movementLabel(m) {
  return ({ IN: '入库', OUT: '出库', ADJUST: '调整' }[m]) || m
}
export function movementTag(m) {
  return ({ IN: 'success', OUT: 'danger', ADJUST: 'warning' }[m]) || 'info'
}

// ---------- 8D 报告 ----------
export const D8_STATUS_OPTIONS = ['OPEN', 'IN_PROGRESS', 'CLOSED']
export function d8StatusLabel(s) {
  return ({ OPEN: '进行中', IN_PROGRESS: '处理中', CLOSED: '已关闭' }[s]) || s
}
export function d8StatusTag(s) {
  return ({ OPEN: 'warning', IN_PROGRESS: 'primary', CLOSED: 'success' }[s]) || 'info'
}

// ---------- FMEA 措施状态 ----------
export const FMEA_ACTION_STATUS_OPTIONS = ['OPEN', 'IN_PROGRESS', 'DONE']
export function fmeaActionLabel(s) {
  return ({ OPEN: '待处理', IN_PROGRESS: '处理中', DONE: '已完成' }[s]) || s
}
export function fmeaActionTag(s) {
  return ({ OPEN: 'info', IN_PROGRESS: 'warning', DONE: 'success' }[s]) || 'info'
}
export function rpnTag(rpn) {
  if (rpn == null) return 'info'
  if (rpn >= 100) return 'danger'
  if (rpn >= 50) return 'warning'
  return 'success'
}

// ---------- 环境核查结果 ----------
export function envResultLabel(r) {
  return ({ OK: '正常', NG: '异常' }[r]) || r
}
export function envResultTag(r) {
  return ({ OK: 'success', NG: 'danger' }[r]) || 'info'
}

// ---------- 技能等级 ----------
export const SKILL_LEVEL_OPTIONS = ['PRIMARY', 'SECONDARY', 'TRAINING', 'NONE']
export function skillLevelLabel(l) {
  return ({ PRIMARY: '主操作', SECONDARY: '副操作', TRAINING: '培训中', NONE: '无' }[l]) || l
}
export function skillLevelTag(l) {
  return ({ PRIMARY: 'success', SECONDARY: 'primary', TRAINING: 'warning', NONE: 'info' }[l]) || 'info'
}

// ---------- 培训状态 ----------
export const TRAINING_STATUS_OPTIONS = ['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED']
export function trainingStatusLabel(s) {
  return ({ PLANNED: '已计划', IN_PROGRESS: '进行中', COMPLETED: '已完成', CANCELLED: '已取消' }[s]) || s
}
export function trainingStatusTag(s) {
  return ({ PLANNED: 'info', IN_PROGRESS: 'warning', COMPLETED: 'success', CANCELLED: 'info' }[s]) || 'info'
}

// ---------- 盘点 ----------
export const INVENTORY_STATUS_OPTIONS = ['PLANNED', 'IN_PROGRESS', 'COMPLETED']
export function inventoryStatusLabel(s) {
  return ({ PLANNED: '已计划', IN_PROGRESS: '进行中', COMPLETED: '已完成' }[s]) || s
}
export function inventoryStatusTag(s) {
  return ({ PLANNED: 'info', IN_PROGRESS: 'warning', COMPLETED: 'success' }[s]) || 'info'
}
export function invLineResultLabel(r) {
  return ({ PENDING: '待盘', MATCH: '账实相符', MISMATCH: '位置不符', MISSING: '盘亏' }[r]) || r
}
export function invLineResultTag(r) {
  return ({ PENDING: 'info', MATCH: 'success', MISMATCH: 'warning', MISSING: 'danger' }[r]) || 'info'
}

// ---------- 调拨/报废申请 ----------
export const APPLICATION_TYPE_OPTIONS = ['TRANSFER', 'SCRAP']
export function applicationTypeLabel(t) {
  return ({ TRANSFER: '调拨', SCRAP: '报废' }[t]) || t
}
export function applicationTypeTag(t) {
  return ({ TRANSFER: 'primary', SCRAP: 'danger' }[t]) || 'info'
}
export function applicationStatusLabel(s) {
  return ({ PENDING: '待审批', APPROVED: '已批准', REJECTED: '已驳回', COMPLETED: '已完成' }[s]) || s
}
export function applicationStatusTag(s) {
  return ({ PENDING: 'warning', APPROVED: 'primary', REJECTED: 'danger', COMPLETED: 'success' }[s]) || 'info'
}

// ---------- 通用格式化 ----------
export function formatTime(t, fmt = 'YYYY-MM-DD HH:mm:ss') {
  return t ? dayjs(t).format(fmt) : '-'
}
export function formatDuration(min) {
  if (min == null) return '-'
  if (min < 60) return `${min} 分`
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return m ? `${h} 时 ${m} 分` : `${h} 时`
}

