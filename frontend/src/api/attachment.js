import request from './request'

const base = (eqId) => `/api/v1/equipments/${eqId}/attachments`

export const listAttachments = (eqId) =>
  request({ url: base(eqId), method: 'get' })

export const uploadAttachment = (eqId, file, meta = {}) => {
  const form = new FormData()
  form.append('file', file)
  if (meta.category) form.append('category', meta.category)
  if (meta.description) form.append('description', meta.description)
  return request({
    url: base(eqId),
    method: 'post',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const deleteAttachment = (eqId, attId) =>
  request({ url: `${base(eqId)}/${attId}`, method: 'delete' })

export const downloadAttachmentUrl = (eqId, attId) =>
  `${base(eqId)}/${attId}/download`
