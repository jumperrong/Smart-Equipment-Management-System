import request from './request'

export const getLaborReports = (params) => request.get('/api/v1/labor-reports', { params })
export const getLaborReport = (id) => request.get(`/api/v1/labor-reports/${id}`)
export const createLaborReport = (data) => request.post('/api/v1/labor-reports', data)
export const updateLaborReport = (id, data) => request.put(`/api/v1/labor-reports/${id}`, data)
export const deleteLaborReport = (id) => request.delete(`/api/v1/labor-reports/${id}`)
