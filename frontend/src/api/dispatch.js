import request from './request'

export const getDispatches = (params) => request.get('/api/v1/dispatches', { params })
export const getDispatch = (id) => request.get(`/api/v1/dispatches/${id}`)
export const createDispatch = (data) => request.post('/api/v1/dispatches', data)
export const updateDispatch = (id, data) => request.put(`/api/v1/dispatches/${id}`, data)
export const deleteDispatch = (id) => request.delete(`/api/v1/dispatches/${id}`)
