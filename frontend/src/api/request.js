import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service = axios.create({
  baseURL: '/',
  timeout: 15000,
})

service.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

service.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.message
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (router.currentRoute.value.name !== 'Login') {
        router.push({ name: 'Login' })
      }
      ElMessage.warning('登录已过期，请重新登录')
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  }
)

export default service
