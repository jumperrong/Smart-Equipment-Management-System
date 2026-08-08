import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useUserStore } from '@/stores/user'

const service = axios.create({
  baseURL: '/',
  timeout: 15000,
})

// token 刷新锁，避免并发 401 同时触发多次刷新
let _refreshPromise = null

service.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

service.interceptors.response.use(
  (resp) => resp.data,
  async (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail || error.message
    const reqConfig = error.config || {}
    const silent = !!reqConfig.silent

    // 401 自动刷新一次 access_token（避免并发重复刷新）
    if (status === 401 && !reqConfig.__retried) {
      const userStore = useUserStore()
      try {
        if (!_refreshPromise) _refreshPromise = userStore.refresh()
        await _refreshPromise
        reqConfig.__retried = true
        // 重新携带新 token 发起
        const token = userStore.token
        if (token) reqConfig.headers = { ...(reqConfig.headers || {}), Authorization: `Bearer ${token}` }
        return service.request(reqConfig)
      } catch (_e) {
        // refresh 也失败 → 走下面的登出流程
      } finally {
        _refreshPromise = null
      }
    }

    if (status === 401) {
      const userStore = useUserStore()
      try { userStore.logout({ notifyServer: false }) } catch {}
      if (router.currentRoute.value.name !== 'Login') {
        router.push({ name: 'Login' })
      }
      if (!silent) ElMessage.warning('登录已过期，请重新登录')
    } else {
      if (!silent) ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  }
)

export default service
