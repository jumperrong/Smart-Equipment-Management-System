import request from './request'

const base = '/api/v1/assets'

// 资产盘点
export const listInventories = (params = {}) =>
  request({ url: `${base}/inventories`, method: 'get', params })

export const getInventory = (id) =>
  request({ url: `${base}/inventories/${id}`, method: 'get' })

export const createInventory = (data) =>
  request({ url: `${base}/inventories`, method: 'post', data })

export const updateInventoryLine = (invId, lineId, data) =>
  request({ url: `${base}/inventories/${invId}/lines/${lineId}`, method: 'put', data })

export const completeInventory = (id) =>
  request({ url: `${base}/inventories/${id}/complete`, method: 'post' })

export const deleteInventory = (id) =>
  request({ url: `${base}/inventories/${id}`, method: 'delete' })

// 调拨 / 报废申请
export const listApplications = (params = {}) =>
  request({ url: `${base}/applications`, method: 'get', params })

export const getApplication = (id) =>
  request({ url: `${base}/applications/${id}`, method: 'get' })

export const createApplication = (data) =>
  request({ url: `${base}/applications`, method: 'post', data })

export const approveApplication = (id, data) =>
  request({ url: `${base}/applications/${id}/approve`, method: 'post', data })

export const completeApplication = (id) =>
  request({ url: `${base}/applications/${id}/complete`, method: 'post' })
