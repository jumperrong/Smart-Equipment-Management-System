import request from './request'

export const login = (data) =>
  request({
    url: '/api/v1/auth/login',
    method: 'post',
    data,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    transformRequest: [
      (d) => {
        const p = new URLSearchParams()
        Object.keys(d).forEach((k) => p.append(k, d[k]))
        return p.toString()
      },
    ],
  })

export const getMe = () =>
  request({ url: '/api/v1/auth/me', method: 'get' })

export const listUsers = () =>
  request({ url: '/api/v1/auth/users', method: 'get' })

export const createUser = (data) =>
  request({ url: '/api/v1/auth/users', method: 'post', data })

export const updateUser = (id, data) =>
  request({ url: `/api/v1/auth/users/${id}`, method: 'put', data })

export const deleteUser = (id) =>
  request({ url: `/api/v1/auth/users/${id}`, method: 'delete' })

export const resetPassword = (id, new_password) =>
  request({ url: `/api/v1/auth/users/${id}/reset-password`, method: 'post', data: { new_password } })
