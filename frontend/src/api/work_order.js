import request from './request'

const base = '/api/v1/work-orders'

// 工单
export const listWorkOrders = (params = {}) =>
  request({ url: base, method: 'get', params })

export const getWorkOrder = (id) =>
  request({ url: `${base}/${id}`, method: 'get' })

export const createWorkOrder = (data) =>
  request({ url: base, method: 'post', data })

export const updateWorkOrder = (id, data) =>
  request({ url: `${base}/${id}`, method: 'put', data })

export const saveFaultAnalysis = (id, data) =>
  request({ url: `${base}/${id}/fault-analysis`, method: 'put', data })

export const listFiveWhys = (id) =>
  request({ url: `${base}/${id}/five-whys`, method: 'get' })

// 备件领用
export const addSpareUsage = (id, data) =>
  request({ url: `${base}/${id}/spare-usages`, method: 'post', data })

export const listSpareUsages = (id) =>
  request({ url: `${base}/${id}/spare-usages`, method: 'get' })

// 报修单
export const listReports = (params = {}) =>
  request({ url: `${base}/reports`, method: 'get', params })

export const createReport = (data) =>
  request({ url: `${base}/reports`, method: 'post', data })

export const convertReport = (id) =>
  request({ url: `${base}/reports/${id}/convert`, method: 'post' })

// PM 计划
export const listPMPlans = (params = {}) =>
  request({ url: `${base}/pm-plans`, method: 'get', params })

export const createPMPlan = (data) =>
  request({ url: `${base}/pm-plans`, method: 'post', data })

export const updatePMPlan = (id, data) =>
  request({ url: `${base}/pm-plans/${id}`, method: 'put', data })

export const deletePMPlan = (id) =>
  request({ url: `${base}/pm-plans/${id}`, method: 'delete' })

export const generateDuePM = () =>
  request({ url: `${base}/pm-plans/generate-due`, method: 'post' })

export const getPMCalendar = (params) =>
  request({ url: `${base}/pm-plans/calendar`, method: 'get', params })
