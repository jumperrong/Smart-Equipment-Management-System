import request from './request'

export const getProcessSections = (params) => request.get('/api/v1/process-sections', { params })
export const getProcessSection = (id) => request.get(`/api/v1/process-sections/${id}`)
export const createProcessSection = (data) => request.post('/api/v1/process-sections', data)
export const updateProcessSection = (id, data) => request.put(`/api/v1/process-sections/${id}`, data)
export const deleteProcessSection = (id) => request.delete(`/api/v1/process-sections/${id}`)
