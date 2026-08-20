import request from './request'

export const getProducts = (params) => request.get('/api/v1/products', { params })
export const getProduct = (id) => request.get(`/api/v1/products/${id}`)
export const createProduct = (data) => request.post('/api/v1/products', data)
export const updateProduct = (id, data) => request.put(`/api/v1/products/${id}`, data)
export const deleteProduct = (id) => request.delete(`/api/v1/products/${id}`)
export const batchImportProducts = (rows) => request.post('/api/v1/products/batch-import', rows)
