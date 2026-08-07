import request from './request'

// 获取角色×功能权限矩阵（仅 admin）
export const getPermissionMatrix = () =>
  request({ url: '/api/v1/system/permissions', method: 'get' })

// 批量更新权限（仅 admin）
// updates: [{role, feature_key, allowed}]
export const updatePermissions = (updates) =>
  request({ url: '/api/v1/system/permissions', method: 'put', data: { updates } })

// 当前用户的权限字典（任意登录用户）
export const getMyPermissions = () =>
  request({ url: '/api/v1/system/my-permissions', method: 'get' })

// ===== 系统设置（环境变量可视化编辑） =====

// 获取所有系统配置项（仅 admin）
export const getSystemSettings = () =>
  request({ url: '/api/v1/system/settings', method: 'get' })

// 批量更新系统配置项（仅 admin）
// updates: [{key, value}]
export const updateSystemSettings = (updates) =>
  request({ url: '/api/v1/system/settings', method: 'put', data: { updates } })

// 重新生成 JWT 签名密钥（仅 admin）
export const regenerateSecretKey = () =>
  request({ url: '/api/v1/system/settings/regenerate-secret-key', method: 'post' })

// ===== 重启服务 =====

// 重启后端服务（仅 admin）
export const restartServer = () =>
  request({ url: '/api/v1/system/settings/restart-server', method: 'post' })

// ===== IP 白名单 =====

// 获取 IP 白名单列表与统计
export const getIpWhitelist = (includeInactive = false) =>
  request({ url: '/api/v1/system/ip-whitelist', method: 'get', params: { include_inactive: includeInactive } })

// 添加 IP 到白名单
export const addIpToWhitelist = (ip, label) =>
  request({ url: '/api/v1/system/ip-whitelist', method: 'post', data: { ip, label } })

// 删除白名单条目
export const removeIpFromWhitelist = (id) =>
  request({ url: `/api/v1/system/ip-whitelist/${id}`, method: 'delete' })

// 启用/停用白名单条目
export const toggleIpWhitelistEntry = (id, isActive) =>
  request({ url: `/api/v1/system/ip-whitelist/${id}`, method: 'put', data: { is_active: isActive } })

// 启用/禁用 IP 白名单总开关
export const setWhitelistEnabled = (enabled) =>
  request({ url: '/api/v1/system/ip-whitelist-enabled', method: 'put', data: { enabled } })

// ===== IP 访问日志（待审 IP） =====

// 获取访问日志
export const getIpAccessLogs = (status, limit = 100) =>
  request({ url: '/api/v1/system/ip-access-logs', method: 'get', params: { status, limit } })

// 批准待审 IP（加入白名单）
export const approvePendingIp = (logId, label) =>
  request({ url: `/api/v1/system/ip-access-logs/${logId}/approve`, method: 'post', data: { label } })

// 拒绝待审 IP
export const rejectPendingIp = (logId) =>
  request({ url: `/api/v1/system/ip-access-logs/${logId}/reject`, method: 'post' })

// 一键批准所有待审 IP
export const approveAllPendingIps = () =>
  request({ url: '/api/v1/system/ip-access-logs/approve-all', method: 'post' })

// ===== 系统备份与恢复 =====

// 备份统计
export const getBackupStats = (subDir = '') =>
  request({ url: '/api/v1/system/backup/stats', method: 'get', params: { sub_dir: subDir } })

// 列出备份
export const listBackups = (subDir = '') =>
  request({ url: '/api/v1/system/backup/list', method: 'get', params: { sub_dir: subDir } })

// 创建备份
export const createBackup = (subDir = '', note = '', includeUploads = true, includeEnv = true) =>
  request({
    url: '/api/v1/system/backup/create',
    method: 'post',
    data: { sub_dir: subDir, note, include_uploads: includeUploads, include_env: includeEnv },
  })

// 删除备份
export const deleteBackup = (fileName, subDir = '') =>
  request({
    url: '/api/v1/system/backup/delete',
    method: 'delete',
    data: { file_name: fileName, sub_dir: subDir },
  })

// 从备份恢复
export const restoreBackup = (payload) =>
  request({
    url: '/api/v1/system/backup/restore',
    method: 'post',
    data: {
      file_name: payload.fileName,
      sub_dir: payload.subDir || '',
      restore_db: payload.restoreDb ?? true,
      restore_uploads: payload.restoreUploads ?? true,
      restore_env: payload.restoreEnv ?? true,
      skip_auto_snapshot: payload.skipAutoSnapshot ?? false,
    },
  })

// 下载备份文件（返回可直接下载的 URL，由浏览器点击触发下载）
export function buildBackupDownloadUrl(fileName, subDir = '') {
  // 用 axios 响应类型 blob，后端已鉴权
  return request({
    url: '/api/v1/system/backup/download',
    method: 'get',
    params: { file_name: fileName, sub_dir: subDir },
    responseType: 'blob',
  }).then((blob) => {
    const url = window.URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', fileName)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  })
}

// ===== 定时备份配置 =====

// 获取定时备份配置和状态
export const getBackupSchedule = () =>
  request({ url: '/api/v1/system/backup/schedule', method: 'get' })

// 更新定时备份配置
export const updateBackupSchedule = (config) =>
  request({
    url: '/api/v1/system/backup/schedule',
    method: 'put',
    data: {
      enabled: config.enabled,
      cron: config.cron,
      sub_dir: config.subDir,
      keep_count: config.keepCount,
      include_uploads: config.includeUploads,
      include_env: config.includeEnv,
    },
  })

// 立即触发一次定时备份
export const triggerBackupNow = () =>
  request({ url: '/api/v1/system/backup/schedule/trigger', method: 'post' })


