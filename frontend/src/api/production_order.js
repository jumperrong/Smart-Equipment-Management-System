import request from './request'

export const getProductionOrders = (params) => request.get('/api/v1/production-orders', { params })
export const getProductionOrder = (id) => request.get(`/api/v1/production-orders/${id}`)
export const createProductionOrder = (data) => request.post('/api/v1/production-orders', data)
export const updateProductionOrder = (id, data) => request.put(`/api/v1/production-orders/${id}`, data)
export const deleteProductionOrder = (id) => request.delete(`/api/v1/production-orders/${id}`)
