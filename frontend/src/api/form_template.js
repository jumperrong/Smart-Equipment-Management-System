import request from './request'

const tplBase = '/api/v1/form-templates'
const recBase = '/api/v1/form-records'

// ============== 表单模板 ==============

export const listFormTemplates = (params = {}) =>
  request({ url: tplBase, method: 'get', params })

export const getFormTemplate = (id) =>
  request({ url: `${tplBase}/${id}`, method: 'get' })

export const createFormTemplate = (data) =>
  request({ url: tplBase, method: 'post', data })

export const updateFormTemplate = (id, data) =>
  request({ url: `${tplBase}/${id}`, method: 'put', data })

export const deleteFormTemplate = (id) =>
  request({ url: `${tplBase}/${id}`, method: 'delete' })

// 上传参考模板文件（空白PDF/Excel/图片）
export const uploadTemplateRefFile = (id, file) => {
  const form = new FormData()
  form.append('file', file)
  return request({
    url: `${tplBase}/${id}/ref-file`,
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// 下载参考模板文件（携带 token）
export function downloadTemplateRefFile(id, filename) {
  const token = localStorage.getItem('token')
  return fetch(`/api/v1/form-templates/${id}/ref-file`, { headers: { Authorization: `Bearer ${token}` } })
    .then((r) => {
      if (!r.ok) throw new Error('下载参考模板失败')
      return r.blob()
    })
    .then((b) => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b)
      a.download = filename || 'form_template_ref'
      a.click()
      URL.revokeObjectURL(a.href)
    })
}

// ============== 结构化表单记录 ==============

export const listFormRecords = (params = {}) =>
  request({ url: recBase, method: 'get', params })

export const getFormRecord = (id) =>
  request({ url: `${recBase}/${id}`, method: 'get' })

// 创建表单记录（含自动创建关联工艺条目、auto_submit）
export const createFormRecord = (data) =>
  request({ url: recBase, method: 'post', data })

// 更新标题/批次/班次/日期/备注 + values 增量覆盖
export const updateFormRecord = (id, data) =>
  request({ url: `${recBase}/${id}`, method: 'put', data })

export const submitFormRecord = (id) =>
  request({ url: `${recBase}/${id}/submit`, method: 'patch' })

export const voidFormRecord = (id) =>
  request({ url: `${recBase}/${id}/void`, method: 'patch' })

export const deleteFormRecord = (id) =>
  request({ url: `${recBase}/${id}`, method: 'delete' })

// 导出：浏览器直接打开带 token 的 URL
export function exportFormRecord(id, format = 'json') {
  const token = localStorage.getItem('token')
  const url = `/api/v1/form-records/${id}/export/${format}`
  return fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(async (r) => {
      if (!r.ok) throw new Error(`导出失败: HTTP ${r.status}`)
      const blob = await r.blob()
      const cd = r.headers.get('Content-Disposition') || ''
      let name = `form_record_${id}.${format}`
      const m = cd.match(/filename="?([^"]+)"?/)
      if (m && m[1]) name = m[1]
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = name
      a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 5000)
    })
}
