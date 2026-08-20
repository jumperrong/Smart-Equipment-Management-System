import request from './request'

const base = '/api/v1/process-documents'

// 列表（支持 equipment_id / category / doc_type / status / batch_no / keyword / latest_only 过滤）
export const listProcessDocuments = (params = {}) =>
  request({ url: base, method: 'get', params })

// 上传工艺文件（FormData，文件 + 元信息）
export const uploadProcessDocument = (file, meta = {}) => {
  const form = new FormData()
  form.append('file', file)
  form.append('equipment_id', meta.equipment_id)
  form.append('category', meta.category || 'guide')
  if (meta.doc_name) form.append('doc_name', meta.doc_name)
  if (meta.doc_type) form.append('doc_type', meta.doc_type)
  if (meta.version) form.append('version', meta.version)
  if (meta.effective_date) form.append('effective_date', meta.effective_date)
  if (meta.batch_no) form.append('batch_no', meta.batch_no)
  if (meta.shift) form.append('shift', meta.shift)
  if (meta.production_date) form.append('production_date', meta.production_date)
  if (meta.description) form.append('description', meta.description)
  if (meta.doc_no) form.append('doc_no', meta.doc_no)
  if (meta.doc_class) form.append('doc_class', meta.doc_class)
  if (meta.review_cycle_month) form.append('review_cycle_month', meta.review_cycle_month)
  // 外来文件字段
  if (meta.source_type) form.append('source_type', meta.source_type)
  if (meta.source_ref_no) form.append('source_ref_no', meta.source_ref_no)
  if (meta.received_date) form.append('received_date', meta.received_date)
  return request({
    url: base,
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 更新工艺文件元信息（不含状态、文件）
export const updateProcessDocument = (id, data) =>
  request({ url: `${base}/${id}`, method: 'put', data })

// 删除工艺文件
export const deleteProcessDocument = (id) =>
  request({ url: `${base}/${id}`, method: 'delete' })

// 下载工艺文件（携带 token，返回 blob）
export function downloadProcessDocument(id, filename) {
  const token = localStorage.getItem('sems_token')
  return fetch(`${base}/${id}/download`, { headers: { Authorization: `Bearer ${token}` } })
    .then((r) => {
      if (!r.ok) throw new Error('下载失败')
      return r.blob()
    })
    .then((b) => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b)
      a.download = filename || 'process_document'
      a.click()
      URL.revokeObjectURL(a.href)
    })
}

// ============ 版本管理 ============

// 列出某文档的所有版本
export const listVersions = (id) =>
  request({ url: `${base}/${id}/versions`, method: 'get' })

// 为现有文档上传新版本
export const createNewVersion = (id, file, meta = {}) => {
  const form = new FormData()
  form.append('file', file)
  if (meta.version) form.append('version', meta.version)
  if (meta.effective_date) form.append('effective_date', meta.effective_date)
  if (meta.batch_no) form.append('batch_no', meta.batch_no)
  if (meta.shift) form.append('shift', meta.shift)
  if (meta.production_date) form.append('production_date', meta.production_date)
  if (meta.description) form.append('description', meta.description)
  return request({
    url: `${base}/${id}/versions`,
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ============ 状态管理 ============

// 状态流转：草稿→审核中→生效→作废 等
export const transitionStatus = (id, payload) =>
  request({ url: `${base}/${id}/status`, method: 'patch', data: payload })

// ============ 文件替换 ============

// 替换文件内容（保留元数据）
export const replaceFile = (id, file) => {
  const form = new FormData()
  form.append('file', file)
  return request({
    url: `${base}/${id}/file`,
    method: 'put',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ============ 文控扩展：审批链 ============

// 签署电子签名（prepare编制提交审核/review审核/approve批准 + 驳回）
export const approvalSign = (data) =>
  request({ url: `${base}/approvals/sign`, method: 'post', data })

// 列出某文档的审批链
export const listApprovals = (docId) =>
  request({ url: `${base}/${docId}/approvals`, method: 'get' })

// ============ 文控扩展：修订记录 ============

// 新增修订记录
export const createChangeLog = (data) =>
  request({ url: `${base}/change-logs`, method: 'post', data })

// 列出某文档的修订记录
export const listChangeLogs = (docId) =>
  request({ url: `${base}/${docId}/change-logs`, method: 'get' })

// ============ 文控扩展：分发记录 ============

// 批量新增分发（支持单条或数组）
export const createDistributions = (data) =>
  request({ url: `${base}/distributions`, method: 'post', data })

// 列出某文档的分发记录
export const listDistributions = (docId) =>
  request({ url: `${base}/${docId}/distributions`, method: 'get' })

// 批量作废收回分发明细
export const returnDistributionsBatch = (data) =>
  request({ url: `${base}/distributions/return-batch`, method: 'post', data })

// 删除单条分发明细
export const deleteDistribution = (distId) =>
  request({ url: `${base}/distributions/${distId}`, method: 'delete' })

// ============ 文控扩展：复审告警 ============

// 获取复审到期统计 + 预警列表
export const reviewAlerts = () =>
  request({ url: `${base}/review-alerts`, method: 'get' })
