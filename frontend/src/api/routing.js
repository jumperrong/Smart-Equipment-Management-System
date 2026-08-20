import request from './request'

export const getRoutings = (params) => request.get('/api/v1/routings', { params })
export const getRouting = (id) => request.get(`/api/v1/routings/${id}`)
export const createRouting = (data) => request.post('/api/v1/routings', data)
export const updateRouting = (id, data) => request.put(`/api/v1/routings/${id}`, data)
export const deleteRouting = (id) => request.delete(`/api/v1/routings/${id}`)
export const releaseRouting = (id) => request.post(`/api/v1/routings/${id}/release`)
