import request from './request'

const base = '/api/v1/inspections'

// 模板
export const listTemplates = (params = {}) =>
  request({ url: `${base}/templates`, method: 'get', params })

export const createTemplate = (data) =>
  request({ url: `${base}/templates`, method: 'post', data })

export const updateTemplate = (id, data) =>
  request({ url: `${base}/templates/${id}`, method: 'put', data })

export const deleteTemplate = (id) =>
  request({ url: `${base}/templates/${id}`, method: 'delete' })

// 记录
export const listRecords = (params = {}) =>
  request({ url: `${base}/records`, method: 'get', params })

export const getRecord = (id) =>
  request({ url: `${base}/records/${id}`, method: 'get' })

export const createRecord = (data) =>
  request({ url: `${base}/records`, method: 'post', data })
