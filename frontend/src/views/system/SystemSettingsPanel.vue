<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">系统设置（环境变量）</span>
          <el-tag size="small" type="warning">修改后重启服务才生效</el-tag>
        </div>
        <div class="header-right">
          <el-button size="small" @click="loadSettings">重置未保存</el-button>
          <el-button
            size="small"
            type="danger"
            plain
            :loading="restarting"
            @click="onRestartServer"
          >
            <el-icon style="margin-right:4px"><Refresh /></el-icon>重启服务
          </el-button>
          <el-button size="small" type="success" :disabled="!dirty" :loading="saving" @click="onSave">
            保存修改<span v-if="dirty" style="margin-left:4px">({{ dirtyCount }})</span>
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom:12px"
    >
      <template #title>
        <span>此处的配置项对应后端环境变量。保存后会写入 <code>.env</code> 文件，<b>需重启服务后生效</b>。</span>
      </template>
    </el-alert>

    <!-- 按分组展示配置项 -->
    <div v-for="g in groupedItems" :key="g.name" class="setting-group">
      <div class="group-title">
        <span class="group-name">{{ g.name }}</span>
        <span class="group-count">{{ g.items.length }} 项</span>
      </div>

      <el-form label-width="200px" label-position="right" size="default">
        <div v-for="item in g.items" :key="item.key" class="setting-row">
          <el-form-item :label="item.label">
            <div class="form-row">
              <!-- 只读项 -->
              <el-input
                v-if="item.is_readonly"
                :model-value="displayValue(item, form[item.key])"
                disabled
                size="default"
                style="max-width:420px"
              />
              <!-- 整数 -->
              <el-input-number
                v-else-if="item.value_type === 'int'"
                v-model="form[item.key]"
                :min="0"
                :step="1"
                controls-position="right"
                size="default"
                style="max-width:200px"
              />
              <!-- 浮点 -->
              <el-input-number
                v-else-if="item.value_type === 'float'"
                v-model="form[item.key]"
                :step="0.1"
                controls-position="right"
                size="default"
                style="max-width:200px"
              />
              <!-- 布尔 -->
              <el-switch
                v-else-if="item.value_type === 'bool'"
                v-model="form[item.key]"
              />
              <!-- JSON 数组/对象（用 textarea 编辑） -->
              <el-input
                v-else-if="item.value_type === 'json'"
                v-model="jsonStrings[item.key]"
                type="textarea"
                :rows="2"
                placeholder='例如：["http://localhost:5173"]'
                size="default"
                style="max-width:520px"
              />
              <!-- 敏感字符串：用密码框 + 重新生成 -->
              <template v-else-if="item.is_sensitive">
                <el-input
                  :model-value="displayValue(item, form[item.key])"
                  disabled
                  size="default"
                  style="max-width:380px"
                />
                <el-button
                  size="default"
                  type="warning"
                  plain
                  @click="onRegenerateKey(item)"
                >重新生成</el-button>
              </template>
              <!-- 普通字符串 -->
              <el-input
                v-else
                v-model="form[item.key]"
                  size="default"
                  style="max-width:420px"
              />

              <el-tag v-if="item.needs_restart" size="small" type="warning" effect="plain" style="margin-left:8px">
                待重启生效
              </el-tag>
              <el-tag v-else-if="item.requires_restart" size="small" type="success" effect="plain" style="margin-left:8px">
                已生效
              </el-tag>

              <el-tooltip v-if="item.is_readonly" :content="'只读项：' + (item.description || '')">
                <el-icon style="margin-left:8px;color:#909399"><Lock /></el-icon>
              </el-tooltip>
            </div>
            <div class="form-tip">
              <code class="env-key">{{ item.key }}</code>
              <span v-if="item.description">{{ item.description }}</span>
            </div>
          </el-form-item>
        </div>
      </el-form>
    </div>

    <div class="tip-text">
      <el-icon><InfoFilled /></el-icon>
      <span>"系统设置"本身固定仅 admin 可访问。修改后会写入 <code>.env</code> 文件，需重启服务（exe 或 uvicorn 进程）后生效。</span>
    </div>
  </el-card>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled, Lock, Refresh } from '@element-plus/icons-vue'
import {
  getSystemSettings,
  updateSystemSettings,
  regenerateSecretKey,
  restartServer,
} from '@/api/system'

const loading = ref(false)
const saving = ref(false)
const restarting = ref(false)
const items = ref([])        // 后端返回的完整定义
const form = reactive({})    // 表单值 {key: value}
const original = reactive({})    // 原始值（用于比对 dirty）
const jsonStrings = reactive({}) // json 类型用字符串编辑

const groupedItems = computed(() => {
  const groups = {}
  items.value.forEach((it) => {
    if (!groups[it.group]) groups[it.group] = { name: it.group, items: [] }
    groups[it.group].items.push(it)
  })
  // 按分组顺序排列
  return Object.values(groups)
})

const dirty = computed(() => {
  for (const it of items.value) {
    if (it.is_readonly || it.is_sensitive) continue
    const cur = form[it.key]
    const orig = original[it.key]
    if (it.value_type === 'json') {
      if ((jsonStrings[it.key] || '') !== (orig?._jsonStr || '')) return true
    } else if (cur !== orig) {
      return true
    }
  }
  return false
})

const dirtyCount = computed(() => {
  let n = 0
  for (const it of items.value) {
    if (it.is_readonly || it.is_sensitive) continue
    const cur = form[it.key]
    const orig = original[it.key]
    if (it.value_type === 'json') {
      if ((jsonStrings[it.key] || '') !== (orig?._jsonStr || '')) n++
    } else if (cur !== orig) {
      n++
    }
  }
  return n
})

function displayValue(item, val) {
  if (val === null || val === undefined || val === '') return ''
  if (item.value_type === 'json') {
    try {
      return JSON.stringify(val)
    } catch {
      return String(val)
    }
  }
  return String(val)
}

function setOriginal(item, val) {
  if (item.value_type === 'json') {
    let s = ''
    try {
      s = val ? JSON.stringify(val) : ''
    } catch { s = '' }
    original[item.key] = { _jsonStr: s }
  } else {
    original[item.key] = val
  }
}

async function loadSettings() {
  loading.value = true
  try {
    const data = await getSystemSettings()
    items.value = data.items || []
    // 重置表单
    Object.keys(form).forEach((k) => delete form[k])
    Object.keys(original).forEach((k) => delete original[k])
    Object.keys(jsonStrings).forEach((k) => delete jsonStrings[k])

    items.value.forEach((it) => {
      // 用 db_value 作为表单回填值
      const v = it.db_value !== undefined ? it.db_value : it.effective_value
      form[it.key] = v
      setOriginal(it, v)
      if (it.value_type === 'json') {
        let s = ''
        try {
          s = v ? JSON.stringify(v, null, 0) : ''
        } catch { s = '' }
        jsonStrings[it.key] = s
      }
    })
  } catch (e) {
    ElMessage.error('加载系统设置失败')
  } finally {
    loading.value = false
  }
}

async function onSave() {
  const updates = []
  for (const it of items.value) {
    if (it.is_readonly || it.is_sensitive) continue
    let val
    if (it.value_type === 'json') {
      // 解析 textarea
      const s = (jsonStrings[it.key] || '').trim()
      if (!s) {
        val = it.default
      } else {
        try {
          val = JSON.parse(s)
          if (!Array.isArray(val) && typeof val !== 'object') {
            ElMessage.error(`${it.label} 需要数组或对象，例如 ["http://localhost:5173"]`)
            return
          }
        } catch (e) {
          ElMessage.error(`${it.label} JSON 格式错误: ${e.message}`)
          return
        }
      }
    } else {
      val = form[it.key]
    }
    updates.push({ key: it.key, value: val })
  }

  if (!updates.length) return
  saving.value = true
  try {
    const r = await updateSystemSettings(updates)
    const updated = r.updated || []
    const skipped = r.skipped || []
    let msg = `已保存 ${updated.length} 项`
    if (skipped.length) msg += `，跳过 ${skipped.length} 项`
    if (r.env_file?.ok) msg += `，已写入 ${r.env_file.path}`
    ElMessage.success(msg)
    if (r.requires_restart) {
      ElMessageBox.alert(
        '修改已保存到 .env 文件。<b>需重启服务后才能生效</b>。<br/>开发模式：重启 uvicorn 进程<br/>打包模式：关闭并重新运行 sems.exe',
        '需要重启服务',
        { dangerouslyUseHTMLString: true, type: 'warning' }
      )
    }
    await loadSettings()  // 重新加载查看最新状态
  } catch (e) {
    // 错误已由 request 拦截器提示
  } finally {
    saving.value = false
  }
}

async function onRegenerateKey(item) {
  try {
    await ElMessageBox.confirm(
      '重新生成 JWT 签名密钥后，所有现有登录会立即失效，需重新登录。是否继续？',
      '确认重新生成密钥',
      { type: 'warning', confirmButtonText: '确认生成', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  try {
    const r = await regenerateSecretKey()
    ElMessage.success(`已生成新密钥：${r.new_key_masked}`)
    if (r.env_file?.ok) {
      ElMessageBox.alert(
        '新密钥已写入 .env 文件。<b>需重启服务后生效</b>，重启后所有用户需重新登录。',
        '需要重启服务',
        { dangerouslyUseHTMLString: true, type: 'warning' }
      )
    }
    await loadSettings()
  } catch (e) {
    // 错误已由 request 拦截器提示
  }
}

async function onRestartServer() {
  try {
    await ElMessageBox.confirm(
      '确认重启后端服务？<br/>服务将断开约 5-10 秒，期间所有请求会失败。<br/>保存过但未重启的配置会在重启后生效。',
      '确认重启服务',
      {
        type: 'warning',
        confirmButtonText: '确认重启',
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: true,
      }
    )
  } catch {
    return
  }

  restarting.value = true
  try {
    const r = await restartServer()
    if (r.ok) {
      ElMessage.success('重启指令已发出，服务正在重启...')
      // 等待 5 秒后自动重新加载
      setTimeout(async () => {
        // 尝试重新加载设置（验证服务已恢复）
        try {
          await loadSettings()
          ElMessage.success('服务已恢复，重新加载完成')
        } catch (e) {
          // 服务还没起来，再等 3 秒
          setTimeout(async () => {
            try {
              await loadSettings()
              ElMessage.success('服务已恢复')
            } catch {
              ElMessage.warning('服务尚未恢复，请稍后手动刷新页面')
            }
          }, 3000)
        }
      }, 5000)
    } else {
      ElMessage.error(`重启失败：${r.error || '未知错误'}`)
    }
  } catch (e) {
    // 错误已由 request 拦截器提示
  } finally {
    // 因为后端会退出，restarting 状态保持几秒后自动归零
    setTimeout(() => { restarting.value = false }, 8000)
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 8px; }

.setting-group { margin-bottom: 24px; }
.group-title {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px dashed #e4e7ed;
}
.group-name { font-weight: 600; font-size: 14px; color: #303133; }
.group-count { font-size: 12px; color: #909399; }

.form-row { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
}
.env-key {
  font-size: 11px;
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 3px;
  color: #606266;
}

.tip-text {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  font-size: 12px;
}
.tip-text code {
  background: #f5f7fa;
  padding: 1px 4px;
  border-radius: 3px;
}
</style>
