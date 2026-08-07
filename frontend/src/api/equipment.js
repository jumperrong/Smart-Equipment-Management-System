import request from './request'

export const listEquipments = (params = {}) =>
  request({ url: '/api/v1/equipments', method: 'get', params })

export const getEquipment = (id) =>
  request({ url: `/api/v1/equipments/${id}`, method: 'get' })

export const createEquipment = (data) =>
  request({ url: '/api/v1/equipments', method: 'post', data })

export const updateEquipment = (id, data) =>
  request({ url: `/api/v1/equipments/${id}`, method: 'put', data })

export const deleteEquipment = (id) =>
  request({ url: `/api/v1/equipments/${id}`, method: 'delete' })

export const changeStatus = (id, data) =>
  request({ url: `/api/v1/equipments/${id}/status`, method: 'post', data })

export const closeStatus = (id, data = {}) =>
  request({ url: `/api/v1/equipments/${id}/status/close`, method: 'post', data })

export const listStatusLogs = (id) =>
  request({ url: `/api/v1/equipments/${id}/status/logs`, method: 'get' })

export const getCurrentStatus = (id) =>
  request({ url: `/api/v1/equipments/${id}/status/current`, method: 'get' })
