<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">备份与恢复</span>
          <el-tag size="small" type="warning">恢复后需重启服务</el-tag>
        </div>
        <div class="header-right">
          <el-input
            v-model="subDir"
            placeholder="子目录名（可选），如 2026-08-07-upgrade"
            style="width:260px"
          />
          <el-button type="primary" :loading="creating" style="margin-left:8px" @click="onCreateBackup">
            <el-icon style="margin-right:4px"><FolderAdd /></el-icon>创建备份
          </el-button>
        </div>
      </div>
    </template>

    <!-- 备份统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-num">{{ stats.count || 0 }}</div>
        <div class="stat-label">备份数量</div>
      </div>
      <div class="stat-card success">
        <div class="stat-num">{{ stats.total_size_human || '0 B' }}</div>
        <div class="stat-label">占用空间</div>
      </div>
      <div class="stat-card">
        <div class="stat-num-sm">{{ stats.latest_backup_at || '从未备份' }}</div>
        <div class="stat-label">最近备份</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ stats.auto_snapshot_count || 0 }}</div>
        <div class="stat-label">自动快照数</div>
      </div>
      <div class="stat-card wide">
        <div class="stat-label-sm">备份根目录：</div>
        <code class="dir-code">{{ stats.backup_root || 'data/backups/' }}</code>
      </div>
    </div>

    <!-- 备份内容说明 -->
    <el-divider content-position="left">
      <span style="font-weight:600">备份内容说明</span>
    </el-divider>

    <div class="backup-content-info">
      <div class="content-item">
        <div class="content-head">
          <el-tag type="success" size="small">数据库</el-tag>
          <span class="content-title">app.db（SQLite 一致性快照）</span>
        </div>
        <div class="content-desc">
          使用 SQLite Backup API 生成事务一致性快照，避免 WAL 模式下数据不一致。包含系统全部业务数据：
          <ul class="content-list">
            <li><b>用户与权限</b>：用户账号、角色、权限配置、IP 白名单</li>
            <li><b>设备管理</b>：设备台账、状态变更日志、设备附件记录</li>
            <li><b>工单与维修</b>：工单（PM/维修/报修）、故障分析（Five-Why）、报修单</li>
            <li><b>PM 计划</b>：维护计划、周期、下次到期日</li>
            <li><b>备件管理</b>：备件库存、出入库流水、设备-备件关联、工单领用记录</li>
            <li><b>点检巡检</b>：点检模板、检查项、点检记录及结果</li>
            <li><b>品管工具</b>：8D 报告、FMEA 分析项</li>
            <li><b>环境核查</b>：温湿度/洁净度/粒子/气压等环境监测日志</li>
            <li><b>人员管理</b>：人员资质、培训记录、参训人员</li>
            <li><b>资产管理</b>：资产盘点单及明细、调拨/报废申请</li>
            <li><b>生产数据</b>：产品信息、生产记录（OEE 计算依据）</li>
            <li><b>系统配置</b>：字典项、系统设置、角色权限映射</li>
          </ul>
        </div>
      </div>

      <div class="content-item">
        <div class="content-head">
          <el-tag type="primary" size="small">上传文件</el-tag>
          <span class="content-title">uploads.tar.gz（tar.gz 压缩包）</span>
        </div>
        <div class="content-desc">
          将 <code>data/uploads/</code> 目录下所有用户上传文件打包压缩为单个 tar.gz 归档，写入备份 ZIP。包含：
          <ul class="content-list">
            <li>设备附件文档（SOP 作业指导书、说明书、图纸等）</li>
            <li>其他通过系统上传的所有文件</li>
          </ul>
          <span class="content-note">
            压缩存储，备份列表中标注 <el-tag type="primary" size="small">[压缩]</el-tag> 标签。
            恢复时自动解压还原至 <code>data/uploads/</code> 目录。
          </span>
        </div>
      </div>

      <div class="content-item">
        <div class="content-head">
          <el-tag type="info" size="small">配置.env</el-tag>
          <span class="content-title">环境配置文件</span>
        </div>
        <div class="content-desc">
          备份 <code>.env</code> 文件全部内容，包含系统级运行配置：
          <ul class="content-list">
            <li>服务端口（PORT）、数据库路径（DATABASE_URL）</li>
            <li>JWT 密钥（SECRET_KEY）、令牌过期时间</li>
            <li>CORS 跨域配置</li>
            <li>IP 白名单开关（IP_WHITELIST_ENABLED）</li>
            <li>其他自定义环境变量</li>
          </ul>
        </div>
      </div>

      <div class="content-item">
        <div class="content-head">
          <el-tag size="small" type="warning">清单</el-tag>
          <span class="content-title">_backup_manifest.json（备份元数据）</span>
        </div>
        <div class="content-desc">
          自动生成的备份清单文件，记录备份版本、创建时间、各内容项的文件名/大小/数量/哈希等信息。用于恢复时校验备份完整性。
        </div>
      </div>
    </div>

    <el-alert
      title="恢复说明"
      type="warning"
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #default>
        恢复时支持选择性恢复（可单独勾选数据库 / 上传文件 / 配置）。恢复前系统会自动创建当前状态快照，存入
        <code>auto-snapshots/</code> 子目录，恢复失败时可手动回滚。恢复完成后需重启服务使新数据生效。
      </template>
    </el-alert>

    <!-- 定时备份配置 -->
    <el-divider content-position="left">
      <span style="font-weight:600">定时备份</span>
    </el-divider>

    <div class="schedule-section">
      <div class="schedule-status">
        <el-tag :type="schedule.enabled ? 'success' : 'info'" size="small">
          {{ schedule.enabled ? '已启用' : '未启用' }}
        </el-tag>
        <el-tag v-if="schedule.running" type="success" size="small">调度器运行中</el-tag>
        <span v-if="schedule.next_run" class="status-item">
          下次执行: <b>{{ schedule.next_run }}</b>
        </span>
        <span v-if="schedule.last_run" class="status-item">
          上次执行: <b>{{ schedule.last_run }}</b>
        </span>
        <span
          v-if="schedule.last_status"
          class="status-item"
          :class="{ 'status-error': schedule.last_status?.startsWith('失败') }"
        >
          {{ schedule.last_status }}
        </span>
      </div>

      <div class="schedule-form" style="margin-top:12px">
        <div class="form-row">
          <el-switch v-model="scheduleForm.enabled" active-text="启用定时备份" />
        </div>
        <div class="form-row">
          <el-select
            v-model="cronPreset"
            placeholder="选择预设频率"
            style="width:200px"
            @change="onCronPresetChange"
          >
            <el-option label="每天 02:00" value="0 2 * * *" />
            <el-option label="每天 12:00" value="0 12 * * *" />
            <el-option label="每12小时" value="0 */12 * * *" />
            <el-option label="每周日 02:00" value="0 2 * * 0" />
            <el-option label="每月1日 02:00" value="0 2 1 * *" />
            <el-option label="自定义" value="custom" />
          </el-select>
          <el-input
            v-model="scheduleForm.cron"
            placeholder="cron 表达式（分 时 日 月 周）"
            style="width:260px"
          />
          <span class="cron-hint">如 <code>0 2 * * *</code> = 每天2点</span>
        </div>
        <div class="form-row">
          <el-input v-model="scheduleForm.subDir" placeholder="备份子目录" style="width:200px" />
          <el-input-number
            v-model="scheduleForm.keepCount"
            :min="0"
            :max="999"
            controls-position="right"
            style="width:160px"
          />
          <span class="cron-hint">保留最近 N 个（0=不限制）</span>
          <el-checkbox v-model="scheduleForm.includeUploads">包含上传文件</el-checkbox>
          <el-checkbox v-model="scheduleForm.includeEnv">包含 .env</el-checkbox>
        </div>
        <div class="form-row">
          <el-button type="primary" :loading="savingSchedule" @click="onSaveSchedule">
            保存配置
          </el-button>
          <el-button
            type="warning"
            plain
            :loading="triggering"
            @click="onTriggerNow"
          >
            立即执行一次
          </el-button>
        </div>
      </div>
    </div>

    <!-- 创建备份选项（折叠） -->
    <el-collapse style="margin-bottom:16px">
      <el-collapse-item title="备份选项" name="options">
        <div class="form-row">
          <el-input
            v-model="backupNote"
            placeholder="备注（可选），描述此备份目的"
            style="flex:1; max-width:420px"
          />
          <el-checkbox v-model="includeUploads">包含上传文件</el-checkbox>
          <el-checkbox v-model="includeEnv">包含 .env 配置</el-checkbox>
        </div>
      </el-collapse-item>
    </el-collapse>

    <!-- 备份列表表格 -->
    <div class="list-header">
      <span style="font-weight:600">备份列表</span>
      <el-button size="small" @click="loadAll">刷新</el-button>
    </div>

    <el-table :data="backups" stripe border size="small">
      <el-table-column prop="created_at" label="备份时间" width="180" />
      <el-table-column prop="file_name" label="文件名" min-width="240" show-overflow-tooltip />
      <el-table-column label="大小" width="100" align="right">
        <template #default="{ row }">{{ row.size_human }}</template>
      </el-table-column>
      <el-table-column label="内容" min-width="260">
        <template #default="{ row }">
          <el-tag v-if="row.items?.db" size="small" type="success" style="margin-right:4px">数据库</el-tag>
          <el-tag v-if="row.items?.uploads" size="small" type="primary" style="margin-right:4px">
            上传文件({{ row.items.uploads.count || 0 }})
            <template v-if="row.items.uploads.compressed_size">
              [压缩]
            </template>
          </el-tag>
          <el-tag v-if="row.items?.env" size="small" type="info">配置.env</el-tag>
          <el-tag v-if="!row.valid" size="small" type="danger">损坏</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span :style="{ color: row.note ? '' : '#c0c4cc' }">{{ row.note || '(无备注)' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="onRestore(row)">恢复</el-button>
          <el-button size="small" type="primary" plain @click="onDownload(row)">下载</el-button>
          <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!backups.length && !loading" description="暂无备份，点击右上角“创建备份”开始。" />

    <!-- 恢复对话框 -->
    <el-dialog v-model="restoreDialog" title="从备份恢复" width="520px" :close-on-click-modal="false">
      <div style="line-height:1.8">
        <p style="color:#f56c6c">
          <b>警告：</b>覆盖式恢复将<b>不可撤销</b>。系统会自动先做一个当前状态快照，失败时可回滚。
        </p>
        <el-divider content-position="left">恢复范围</el-divider>
        <el-checkbox v-model="restoreOpt.restoreDb">恢复数据库（用户、工单、备件、PM、字典等全部业务数据）</el-checkbox>
        <el-checkbox v-model="restoreOpt.restoreUploads">恢复上传文件目录</el-checkbox>
        <el-checkbox v-model="restoreOpt.restoreEnv">恢复 .env 配置（端口、密钥、白名单开关等）</el-checkbox>
        <el-divider content-position="left">安全选项</el-divider>
        <el-checkbox v-model="restoreOpt.skipAutoSnapshot" style="color:#f56c6c">
          跳过自动快照（危险，不推荐）
        </el-checkbox>
        <p style="color:#909399;font-size:12px;margin-top:8px">
          目标备份：<code>{{ restoreOpt.fileName }}</code>
        </p>
      </div>
      <template #footer>
        <el-button @click="restoreDialog = false">取消</el-button>
        <el-button type="danger" :loading="restoring" @click="confirmRestore">
          <el-icon style="margin-right:4px"><Warning /></el-icon>确认恢复
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderAdd, Warning } from '@element-plus/icons-vue'
import {
  getBackupStats,
  listBackups,
  createBackup,
  deleteBackup,
  restoreBackup as apiRestore,
  buildBackupDownloadUrl,
  getBackupSchedule,
  updateBackupSchedule,
  triggerBackupNow,
} from '@/api/system'

const loading = ref(false)
const creating = ref(false)
const restoring = ref(false)
const subDir = ref('')
const backupNote = ref('')
const includeUploads = ref(true)
const includeEnv = ref(true)
const stats = reactive({})
const backups = ref([])

// 定时备份
const schedule = reactive({
  enabled: false,
  running: false,
  next_run: null,
  last_run: null,
  last_status: null,
})
const scheduleForm = reactive({
  enabled: false,
  cron: '0 2 * * *',
  subDir: 'scheduled',
  keepCount: 30,
  includeUploads: true,
  includeEnv: true,
})
const cronPreset = ref('0 2 * * *')
const savingSchedule = ref(false)
const triggering = ref(false)

const CRON_PRESETS = ['0 2 * * *', '0 12 * * *', '0 */12 * * *', '0 2 * * 0', '0 2 1 * *']

const restoreDialog = ref(false)
const restoreOpt = reactive({
  fileName: '',
  restoreDb: true,
  restoreUploads: true,
  restoreEnv: true,
  skipAutoSnapshot: false,
})

async function loadAll() {
  loading.value = true
  try {
    const [s, lst] = await Promise.all([getBackupStats(subDir.value), listBackups(subDir.value)])
    Object.assign(stats, s)
    backups.value = lst.items || []
  } finally {
    loading.value = false
  }
}

async function onCreateBackup() {
  creating.value = true
  try {
    const info = await createBackup(subDir.value, backupNote.value, includeUploads.value, includeEnv.value)
    ElMessage.success(
      `备份创建成功：${info.file_name}（${info.size_human}）已保存到 ${info.file_path}`
    )
    backupNote.value = ''
    await loadAll()
  } finally {
    creating.value = false
  }
}

async function onDownload(row) {
  try {
    await buildBackupDownloadUrl(row.file_name, subDir.value)
    ElMessage.success(`开始下载 ${row.file_name}`)
  } catch (e) {
    // request 拦截器已提示
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除备份 ${row.file_name}？此操作不可撤销。`, '提示', { type: 'warning' })
  } catch { return }
  await deleteBackup(row.file_name, subDir.value)
  ElMessage.success('已删除')
  await loadAll()
}

function onRestore(row) {
  if (!row.valid) {
    ElMessage.error('此备份包已损坏或不合法，无法恢复')
    return
  }
  restoreOpt.fileName = row.file_name
  restoreOpt.restoreDb = !!row.items?.db
  restoreOpt.restoreUploads = !!row.items?.uploads
  restoreOpt.restoreEnv = !!row.items?.env
  restoreOpt.skipAutoSnapshot = false
  restoreDialog.value = true
}

async function confirmRestore() {
  if (!restoreOpt.restoreDb && !restoreOpt.restoreUploads && !restoreOpt.restoreEnv) {
    ElMessage.warning('至少勾选一项恢复内容')
    return
  }
  try {
    await ElMessageBox.confirm(
      `真的要恢复吗？系统会先做自动快照，<br/>然后<b>覆盖写入</b>当前数据库、上传文件和/或配置。<br/>恢复后需要<b>重启服务</b>。`,
      '最终确认',
      { type: 'error', dangerouslyUseHTMLString: true }
    )
  } catch { return }

  restoring.value = true
  try {
    const r = await apiRestore({
      fileName: restoreOpt.fileName,
      subDir: subDir.value,
      restoreDb: restoreOpt.restoreDb,
      restoreUploads: restoreOpt.restoreUploads,
      restoreEnv: restoreOpt.restoreEnv,
      skipAutoSnapshot: restoreOpt.skipAutoSnapshot,
    })
    restoreDialog.value = false
    ElMessageBox.alert(
      `恢复已完成。<br/>${r.message}<br/><br/>` +
      (r.auto_snapshot
        ? `自动快照：<code>${r.auto_snapshot.file_name}</code><br/>若需要回滚可手动恢复该快照。`
        : '(已跳过自动快照)') +
      `<br/><br/><b>请立即重启服务使恢复生效</b>。`,
      '恢复成功',
      { dangerouslyUseHTMLString: true, type: 'success' }
    )
    await loadAll()
  } catch {
    // request 拦截器已提示
  } finally {
    restoring.value = false
  }
}

// ---------- 定时备份 ----------

async function loadSchedule() {
  try {
    const s = await getBackupSchedule()
    Object.assign(schedule, s)
    // 回填表单
    scheduleForm.enabled = s.enabled
    scheduleForm.cron = s.cron
    scheduleForm.subDir = s.sub_dir
    scheduleForm.keepCount = s.keep_count
    scheduleForm.includeUploads = s.include_uploads
    scheduleForm.includeEnv = s.include_env
    // 匹配预设
    cronPreset.value = CRON_PRESETS.includes(s.cron) ? s.cron : 'custom'
  } catch {
    // request 拦截器已提示
  }
}

function onCronPresetChange(val) {
  if (val !== 'custom') {
    scheduleForm.cron = val
  }
}

async function onSaveSchedule() {
  savingSchedule.value = true
  try {
    const s = await updateBackupSchedule({
      enabled: scheduleForm.enabled,
      cron: scheduleForm.cron,
      subDir: scheduleForm.subDir,
      keepCount: scheduleForm.keepCount,
      includeUploads: scheduleForm.includeUploads,
      includeEnv: scheduleForm.includeEnv,
    })
    Object.assign(schedule, s)
    ElMessage.success(
      scheduleForm.enabled
        ? `定时备份已启用，下次执行: ${s.next_run || '计算中'}`
        : '定时备份已停用'
    )
  } finally {
    savingSchedule.value = false
  }
}

async function onTriggerNow() {
  triggering.value = true
  try {
    const r = await triggerBackupNow()
    ElMessage.success(`定时备份已执行: ${r.backup.file_name}（${r.backup.size_human}）`)
    await Promise.all([loadSchedule(), loadAll()])
  } catch {
    // request 拦截器已提示
  } finally {
    triggering.value = false
  }
}

onMounted(() => {
  loadAll()
  loadSchedule()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 8px; }

.stats-row { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card {
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  min-width: 130px;
}
.stat-card.success { background: #f0f9eb; border-color: #c2e7b0; }
.stat-card.wide { min-width: 320px; flex: 1; }
.stat-num { font-size: 24px; font-weight: 600; color: #303133; }
.stat-num-sm { font-size: 14px; font-weight: 500; color: #303133; line-height: 28px; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.stat-label-sm { font-size: 12px; color: #909399; }
.dir-code {
  font-size: 12px;
  background: #fff;
  padding: 2px 8px;
  border-radius: 3px;
  color: #606266;
  display: inline-block;
  margin-top: 4px;
  word-break: break-all;
}

.form-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

.schedule-section { margin-bottom: 16px; }
.schedule-status { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.status-item { font-size: 13px; color: #606266; }
.status-error { color: #f56c6c; }
.cron-hint { font-size: 12px; color: #909399; }
.cron-hint code { background: #f5f7fa; padding: 1px 4px; border-radius: 3px; }

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.backup-content-info {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.content-item {
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}
.content-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.content-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}
.content-desc {
  font-size: 12px;
  color: #606266;
  line-height: 1.8;
}
.content-list {
  margin: 4px 0 0 0;
  padding-left: 18px;
}
.content-list li {
  line-height: 1.7;
}
.content-note {
  display: inline-block;
  margin-top: 4px;
  color: #909399;
}
.content-desc code {
  background: #fff;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}
</style>
