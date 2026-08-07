import request from './request'

export const getDashboard = () =>
  request({ url: '/api/v1/dashboard', method: 'get' })

// 产品
export const listProducts = (params = {}) =>
  request({ url: '/api/v1/products', method: 'get', params })

export const createProduct = (data) =>
  request({ url: '/api/v1/products', method: 'post', data })

export const updateProduct = (id, data) =>
  request({ url: `/api/v1/products/${id}`, method: 'put', data })

export const deleteProduct = (id) =>
  request({ url: `/api/v1/products/${id}`, method: 'delete' })

// 生产记录
export const listProductionRecords = (params = {}) =>
  request({ url: '/api/v1/production-records', method: 'get', params })

export const createProductionRecord = (data) =>
  request({ url: '/api/v1/production-records', method: 'post', data })

export const updateProductionRecord = (id, data) =>
  request({ url: `/api/v1/production-records/${id}`, method: 'put', data })

export const deleteProductionRecord = (id) =>
  request({ url: `/api/v1/production-records/${id}`, method: 'delete' })
