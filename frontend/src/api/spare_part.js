import request from './request'

const base = '/api/v1/spare-parts'

export const listSpareParts = (params = {}) =>
  request({ url: base, method: 'get', params })

export const getSparePart = (id) =>
  request({ url: `${base}/${id}`, method: 'get' })

export const createSparePart = (data) =>
  request({ url: base, method: 'post', data })

export const updateSparePart = (id, data) =>
  request({ url: `${base}/${id}`, method: 'put', data })

export const deleteSparePart = (id) =>
  request({ url: `${base}/${id}`, method: 'delete' })

// 出入库
export const moveStock = (id, data) =>
  request({ url: `${base}/${id}/movement`, method: 'post', data })

export const listMovements = (id, params = {}) =>
  request({ url: `${base}/${id}/movements`, method: 'get', params })

// 库存概览统计 & 全局出入库流水
export const getStockSummary = () =>
  request({ url: `${base}/stock/summary`, method: 'get' })

export const listAllMovements = (params = {}) =>
  request({ url: `${base}/movements/all`, method: 'get', params })

// 设备-易损件关联
export const listEquipmentSpareParts = (eqId) =>
  request({ url: `/api/v1/equipments/${eqId}/spare-parts`, method: 'get' })

export const addEquipmentSparePart = (eqId, data) =>
  request({ url: `/api/v1/equipments/${eqId}/spare-parts`, method: 'post', data })

export const removeEquipmentSparePart = (eqId, sparePartId) =>
  request({ url: `/api/v1/equipments/${eqId}/spare-parts/${sparePartId}`, method: 'delete' })
