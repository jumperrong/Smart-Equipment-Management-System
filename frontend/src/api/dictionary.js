import request from './request'

const base = '/api/v1/dictionaries'

export const listCategories = () =>
  request({ url: `${base}/categories`, method: 'get' })

export const listDictItems = (params = {}) =>
  request({ url: base, method: 'get', params })

export const createDictItem = (data) =>
  request({ url: base, method: 'post', data })

export const updateDictItem = (id, data) =>
  request({ url: `${base}/${id}`, method: 'put', data })

export const deleteDictItem = (id) =>
  request({ url: `${base}/${id}`, method: 'delete' })
