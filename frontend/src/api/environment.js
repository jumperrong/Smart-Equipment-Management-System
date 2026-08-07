import request from './request'

const base = '/api/v1/environment-logs'

export const listEnvLogs = (params = {}) =>
  request({ url: base, method: 'get', params })

export const getEnvLog = (id) =>
  request({ url: `${base}/${id}`, method: 'get' })

export const createEnvLog = (data) =>
  request({ url: base, method: 'post', data })

export const updateEnvLog = (id, data) =>
  request({ url: `${base}/${id}`, method: 'put', data })

export const deleteEnvLog = (id) =>
  request({ url: `${base}/${id}`, method: 'delete' })
