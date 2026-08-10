import request from './request'

const base = '/api/v1/doc-no-rules'

// 列出所有编号规则
export const listDocNoRules = () =>
  request({ url: base, method: 'get' })

// 创建编号规则
export const createDocNoRule = (data) =>
  request({ url: base, method: 'post', data })

// 更新编号规则
export const updateDocNoRule = (id, data) =>
  request({ url: `${base}/${id}`, method: 'put', data })

// 删除编号规则
export const deleteDocNoRule = (id) =>
  request({ url: `${base}/${id}`, method: 'delete' })

// 生成文档编号（消耗流水号）
export const generateDocNo = (doc_class, equipment_id = null) =>
  request({ url: `${base}/generate`, method: 'post', data: { doc_class, equipment_id } })

// 预览编号格式（不消耗流水号）
export const previewDocNo = (doc_class, equipment_id = null) =>
  request({ url: `${base}/preview`, method: 'get', params: { doc_class, equipment_id } })
