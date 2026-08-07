<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">IP 白名单</span>
          <el-tag v-if="stats.whitelist_enabled" size="small" type="success">已启用</el-tag>
          <el-tag v-else size="small" type="info">未启用（允许所有 IP）</el-tag>
        </div>
        <div class="header-right">
          <el-switch
            :model-value="stats.whitelist_enabled"
            active-text="启用白名单"
            inactive-text=""
            @change="onToggleEnabled"
          />
        </div>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom:12px"
    >
      <template #title>
        <span>启用后，<b>不在白名单的 IP 将返回 403 并记录到下方"待审 IP"</b>。本机 127.0.0.1/::1 永远允许，不会被锁死。</span>
      </template>
    </el-alert>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-num">{{ stats.whitelist_count || 0 }}</div>
        <div class="stat-label">白名单条目</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-num">{{ stats.pending_count || 0 }}</div>
        <div class="stat-label">待审 IP</div>
      </div>
      <div class="stat-card">
        <div class="stat-label-sm">永远允许：</div>
        <div class="stat-list">{{ (stats.always_allowed || []).join(', ') }}</div>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 白名单列表 -->
      <el-tab-pane :label="`白名单 (${whitelist.length})`" name="whitelist">
        <div class="toolbar">
          <el-input
            v-model="newIp"
            placeholder="IP 或 CIDR，如 192.168.1.100 或 10.0.0.0/8"
            style="width:320px"
            @keyup.enter="onAdd"
          />
          <el-input
            v-model="newLabel"
            placeholder="备注名（可选）"
            style="width:200px; margin-left:8px"
          />
          <el-button type="primary" style="margin-left:8px" @click="onAdd">添加</el-button>
          <el-button @click="loadWhitelist">刷新</el-button>
        </div>

        <el-table :data="whitelist" stripe border size="small" style="margin-top:12px">
          <el-table-column prop="ip" label="IP / CIDR" min-width="180" />
          <el-table-column prop="label" label="备注" min-width="150" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="onToggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
              <el-button size="small" type="danger" @click="onRemove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 待审 IP -->
      <el-tab-pane name="pending">
        <template #label>
          待审 IP
          <el-badge v-if="stats.pending_count > 0" :value="stats.pending_count" type="danger" style="margin-left:4px" />
        </template>

        <div class="toolbar">
          <el-button type="success" :disabled="!pending.length" @click="onApproveAll">一键批准全部</el-button>
          <el-button @click="loadPending">刷新</el-button>
        </div>

        <el-table :data="pending" stripe border size="small" style="margin-top:12px">
          <el-table-column prop="ip" label="IP" min-width="140" />
          <el-table-column prop="attempt_count" label="尝试次数" width="100" align="center" />
          <el-table-column prop="path" label="最后访问路径" min-width="180" show-overflow-tooltip />
          <el-table-column prop="method" label="方法" width="80" align="center" />
          <el-table-column prop="user_agent" label="User-Agent" min-width="180" show-overflow-tooltip />
          <el-table-column prop="first_attempt_at" label="首次尝试" width="160">
            <template #default="{ row }">{{ formatTime(row.first_attempt_at) }}</template>
          </el-table-column>
          <el-table-column prop="last_attempt_at" label="最近尝试" width="160">
            <template #default="{ row }">{{ formatTime(row.last_attempt_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="onApprove(row)">批准加入</el-button>
              <el-button size="small" type="warning" plain @click="onReject(row)">拒绝</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!pending.length" description="暂无待审 IP" />
      </el-tab-pane>

      <!-- 历史日志 -->
      <el-tab-pane label="历史日志" name="history">
        <div class="toolbar">
          <el-select v-model="historyFilter" placeholder="状态" clearable style="width:140px" @change="loadHistory">
            <el-option label="全部" value="" />
            <el-option label="待审" value="PENDING" />
            <el-option label="已批准" value="APPROVED" />
            <el-option label="已拒绝" value="REJECTED" />
          </el-select>
          <el-button @click="loadHistory" style="margin-left:8px">刷新</el-button>
        </div>

        <el-table :data="history" stripe border size="small" style="margin-top:12px">
          <el-table-column prop="ip" label="IP" min-width="140" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="attempt_count" label="尝试" width="80" align="center" />
          <el-table-column prop="path" label="路径" min-width="160" show-overflow-tooltip />
          <el-table-column prop="last_attempt_at" label="最近尝试" width="160">
            <template #default="{ row }">{{ formatTime(row.last_attempt_at) }}</template>
          </el-table-column>
          <el-table-column prop="approved_at" label="处理时间" width="160">
            <template #default="{ row }">{{ formatTime(row.approved_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!history.length" description="暂无访问日志" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getIpWhitelist,
  addIpToWhitelist,
  removeIpFromWhitelist,
  toggleIpWhitelistEntry,
  setWhitelistEnabled,
  getIpAccessLogs,
  approvePendingIp,
  rejectPendingIp,
  approveAllPendingIps,
} from '@/api/system'

const loading = ref(false)
const activeTab = ref('whitelist')
const stats = reactive({ whitelist_enabled: false, whitelist_count: 0, pending_count: 0, always_allowed: [] })
const whitelist = ref([])
const pending = ref([])
const history = ref([])
const historyFilter = ref('')
const newIp = ref('')
const newLabel = ref('')

async function loadWhitelist() {
  loading.value = true
  try {
    const r = await getIpWhitelist()
    whitelist.value = r.items || []
    Object.assign(stats, r.stats || {})
  } finally {
    loading.value = false
  }
}

async function loadPending() {
  try {
    const r = await getIpAccessLogs('PENDING')
    pending.value = r.items || []
    Object.assign(stats, r.stats || {})
  } catch {}
}

async function loadHistory() {
  try {
    const r = await getIpAccessLogs(historyFilter.value || undefined)
    history.value = r.items || []
    Object.assign(stats, r.stats || {})
  } catch {}
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadWhitelist(), loadPending(), loadHistory()])
  } finally {
    loading.value = false
  }
}

async function onAdd() {
  if (!newIp.value.trim()) {
    ElMessage.warning('请输入 IP')
    return
  }
  try {
    await addIpToWhitelist(newIp.value.trim(), newLabel.value.trim() || null)
    ElMessage.success(`已添加 ${newIp.value}`)
    newIp.value = ''
    newLabel.value = ''
    await loadWhitelist()
  } catch {}
}

async function onRemove(row) {
  try {
    await ElMessageBox.confirm(`确认删除白名单 ${row.ip}？`, '提示', { type: 'warning' })
  } catch { return }
  await removeIpFromWhitelist(row.id)
  ElMessage.success('已删除')
  await loadWhitelist()
}

async function onToggle(row) {
  await toggleIpWhitelistEntry(row.id, !row.is_active)
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  await loadWhitelist()
}

async function onToggleEnabled(val) {
  try {
    await ElMessageBox.confirm(
      val
        ? '启用 IP 白名单？启用后未在白名单的 IP 将无法访问。'
        : '禁用 IP 白名单？禁用后所有 IP 都可访问。',
      '确认',
      { type: val ? 'warning' : 'info' }
    )
  } catch {
    // 撤销
    stats.whitelist_enabled = !val
    return
  }
  const r = await setWhitelistEnabled(val)
  ElMessage.success(val ? '已启用 IP 白名单' : '已禁用 IP 白名单')
  Object.assign(stats, r.stats || {})
}

async function onApprove(row) {
  try {
    await approvePendingIp(row.id)
    ElMessage.success(`已批准 ${row.ip} 加入白名单`)
    await Promise.all([loadWhitelist(), loadPending()])
  } catch {}
}

async function onReject(row) {
  try {
    await ElMessageBox.confirm(`确认拒绝 IP ${row.ip}？`, '提示', { type: 'warning' })
  } catch { return }
  await rejectPendingIp(row.id)
  ElMessage.success('已拒绝')
  await loadPending()
}

async function onApproveAll() {
  try {
    await ElMessageBox.confirm('一键批准所有待审 IP 加入白名单？', '确认', { type: 'warning' })
  } catch { return }
  const r = await approveAllPendingIps()
  ElMessage.success(`已批准 ${r.approved} 个 IP，跳过 ${(r.skipped || []).length} 个`)
  await Promise.all([loadWhitelist(), loadPending()])
}

function formatTime(s) {
  if (!s) return ''
  return s.replace('T', ' ').replace(/\.\d+$/, '').replace('Z', '')
}

function statusLabel(s) {
  return { PENDING: '待审', APPROVED: '已批准', REJECTED: '已拒绝' }[s] || s
}

function statusTagType(s) {
  return { PENDING: 'warning', APPROVED: 'success', REJECTED: 'info' }[s] || ''
}

onMounted(loadAll)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 8px; }

.stats-row { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-card {
  flex: 1;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}
.stat-card.pending { background: #fdf6ec; border-color: #f5dab1; }
.stat-num { font-size: 24px; font-weight: 600; color: #303133; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.stat-label-sm { font-size: 12px; color: #909399; }
.stat-list { font-size: 12px; color: #606266; margin-top: 4px; word-break: break-all; }

.toolbar { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
</style>
