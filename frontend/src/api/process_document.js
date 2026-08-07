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
  const token = localStorage.getItem('token')
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

// 状态流转：草稿→生效、草稿→作废、生效→作废
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
