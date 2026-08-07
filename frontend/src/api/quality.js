import request from './request'

const base = '/api/v1/quality'

// 8D 报告
export const listD8 = (params = {}) =>
  request({ url: `${base}/d8-reports`, method: 'get', params })

export const getD8 = (id) =>
  request({ url: `${base}/d8-reports/${id}`, method: 'get' })

export const createD8 = (data) =>
  request({ url: `${base}/d8-reports`, method: 'post', data })

export const updateD8 = (id, data) =>
  request({ url: `${base}/d8-reports/${id}`, method: 'put', data })

export const deleteD8 = (id) =>
  request({ url: `${base}/d8-reports/${id}`, method: 'delete' })

// FMEA
export const listFmeas = (params = {}) =>
  request({ url: `${base}/fmeas`, method: 'get', params })

export const getFmea = (id) =>
  request({ url: `${base}/fmeas/${id}`, method: 'get' })

export const createFmea = (data) =>
  request({ url: `${base}/fmeas`, method: 'post', data })

export const updateFmea = (id, data) =>
  request({ url: `${base}/fmeas/${id}`, method: 'put', data })

export const deleteFmea = (id) =>
  request({ url: `${base}/fmeas/${id}`, method: 'delete' })

export const addFmeaItem = (fmeaId, data) =>
  request({ url: `${base}/fmeas/${fmeaId}/items`, method: 'post', data })

export const updateFmeaItem = (fmeaId, itemId, data) =>
  request({ url: `${base}/fmeas/${fmeaId}/items/${itemId}`, method: 'put', data })

export const deleteFmeaItem = (fmeaId, itemId) =>
  request({ url: `${base}/fmeas/${fmeaId}/items/${itemId}`, method: 'delete' })

// 可靠性指标 MTBF/MTTR
export const getReliability = (params = {}) =>
  request({ url: `${base}/reliability`, method: 'get', params })
