import request from './request'

const base = '/api/v1/personnel'

// 资质
export const listQualifications = (params = {}) =>
  request({ url: `${base}/qualifications`, method: 'get', params })

export const createQualification = (data) =>
  request({ url: `${base}/qualifications`, method: 'post', data })

export const updateQualification = (id, data) =>
  request({ url: `${base}/qualifications/${id}`, method: 'put', data })

export const deleteQualification = (id) =>
  request({ url: `${base}/qualifications/${id}`, method: 'delete' })

// 技能矩阵
export const getSkillMatrix = () =>
  request({ url: `${base}/skill-matrix`, method: 'get' })

// 培训
export const listTrainings = (params = {}) =>
  request({ url: `${base}/trainings`, method: 'get', params })

export const getTraining = (id) =>
  request({ url: `${base}/trainings/${id}`, method: 'get' })

export const createTraining = (data) =>
  request({ url: `${base}/trainings`, method: 'post', data })

export const updateTrainingStatus = (id, status) =>
  request({ url: `${base}/trainings/${id}/status`, method: 'put', data: { status } })

export const deleteTraining = (id) =>
  request({ url: `${base}/trainings/${id}`, method: 'delete' })

export const addAttendee = (trainingId, data) =>
  request({ url: `${base}/trainings/${trainingId}/attendees`, method: 'post', data })

export const updateAttendee = (trainingId, attendeeId, data) =>
  request({ url: `${base}/trainings/${trainingId}/attendees/${attendeeId}`, method: 'put', data })

export const deleteAttendee = (trainingId, attendeeId) =>
  request({ url: `${base}/trainings/${trainingId}/attendees/${attendeeId}`, method: 'delete' })
