import { defineStore } from 'pinia'
import { login, getMe } from '@/api/auth'
import { getMyPermissions } from '@/api/system'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    permissions: JSON.parse(localStorage.getItem('permissions') || '{}'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    fullName: (s) => s.user?.full_name || s.user?.username || '',
  },
  actions: {
    async doLogin({ username, password }) {
      const resp = await login({ username, password })
      this.token = resp.access_token
      localStorage.setItem('token', resp.access_token)
      await this.fetchMe()
      return resp
    },
    async fetchMe() {
      const me = await getMe()
      this.user = me
      localStorage.setItem('user', JSON.stringify(me))
      // 拉取当前用户的功能权限矩阵
      try {
        const data = await getMyPermissions()
        this.permissions = data.permissions || {}
        localStorage.setItem('permissions', JSON.stringify(this.permissions))
      } catch (e) {
        // 权限拉取失败不清空，保留旧值
      }
      return me
    },
    logout() {
      this.token = ''
      this.user = null
      this.permissions = {}
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem('permissions')
    },
    hasRole(...roles) {
      if (!roles.length) return true
      return roles.includes(this.role)
    },
    /**
     * 判断当前用户对某 feature_key 是否有权限。
     * - 未拉取到 permissions（空对象）时，回退到 hasRole 兼容老逻辑
     * - 已拉取到时按 permissions[featureKey] 判断
     */
    can(featureKey) {
      const perms = this.permissions
      if (!perms || Object.keys(perms).length === 0) {
        // 未拉取权限矩阵时回退：admin/engineer 视为可写，operator/viewer 视为只读
        return this.role === 'admin' || this.role === 'engineer'
      }
      return !!perms[featureKey]
    },
  },
})
