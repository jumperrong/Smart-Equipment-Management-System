import { defineStore } from 'pinia'
import { login as apiLogin, getMe, refreshToken, logout as apiLogout } from '@/api/auth'
import { getMyPermissions } from '@/api/system'

/** 安全存储封装：局域网系统仍用 localStorage，但加前缀 & 提供统一清理。*/
const LS_PREFIX = 'sems_'
const K_TOKEN = LS_PREFIX + 'token'
const K_REFRESH = LS_PREFIX + 'refresh_token'
const K_USER = LS_PREFIX + 'user'
const K_PERMS = LS_PREFIX + 'permissions'
const K_MUST_CHANGE = LS_PREFIX + 'must_change_pwd'
// 防止 XSS 读取：对需要展示的 user 对象里敏感字段（hashed_password 等）后端已不返回，
// 此处不额外加密。生产建议启用 HttpOnly Cookie。

function _get(k, fallback = null) {
  try {
    const v = localStorage.getItem(k)
    return v == null ? fallback : v
  } catch { return fallback }
}
function _set(k, v) {
  try { localStorage.setItem(k, v) } catch {}
}
function _rm(k) {
  try { localStorage.removeItem(k) } catch {}
}
function _getJSON(k, fallback = null) {
  const v = _get(k)
  if (v == null) return fallback
  try { return JSON.parse(v) } catch { return fallback }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: _get(K_TOKEN, ''),
    refresh_token: _get(K_REFRESH, ''),
    user: _getJSON(K_USER, null),
    permissions: _getJSON(K_PERMS, {}),
    must_change_password: _get(K_MUST_CHANGE, '') === '1',
    // 令牌过期前多久主动刷新（毫秒）
    _refreshAheadMs: 5 * 60 * 1000,
    _refreshTimer: null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    role: (s) => s.user?.role || '',
    fullName: (s) => s.user?.full_name || s.user?.username || '',
    /** 从 JWT 中解析过期时间（毫秒），失败返回 0。*/
    tokenExpireAt() {
      const t = this.token
      if (!t) return 0
      try {
        const body = t.split('.')[1]
        const payload = JSON.parse(atob(body.replace(/-/g, '+').replace(/_/g, '/')))
        return (payload.exp || 0) * 1000
      } catch { return 0 }
    },
  },
  actions: {
    _scheduleAutoRefresh() {
      // 计划一次：临近过期时自动刷新
      if (this._refreshTimer) clearTimeout(this._refreshTimer)
      const exp = this.tokenExpireAt
      if (!exp) return
      const delay = Math.max(30 * 1000, exp - Date.now() - this._refreshAheadMs)
      this._refreshTimer = setTimeout(async () => {
        try { await this.refresh() } catch { /* 失败不处理：后续 401 会自然跳登录 */ }
        this._scheduleAutoRefresh()
      }, delay)
    },

    _persistTokens(access, refresh, must_change) {
      this.token = access || ''
      this.refresh_token = refresh || ''
      if (access) _set(K_TOKEN, access); else _rm(K_TOKEN)
      if (refresh) _set(K_REFRESH, refresh); else _rm(K_REFRESH)
      this.must_change_password = !!must_change
      _set(K_MUST_CHANGE, must_change ? '1' : '0')
    },

    async doLogin({ username, password }) {
      const resp = await apiLogin({ username, password })
      this._persistTokens(resp.access_token, resp.refresh_token, resp.must_change_password)
      await this.fetchMe()
      this._scheduleAutoRefresh()
      return resp
    },
    async refresh() {
      if (!this.refresh_token) throw new Error('no refresh_token')
      const resp = await refreshToken(this.refresh_token)
      this._persistTokens(resp.access_token, resp.refresh_token, resp.must_change_password)
      return resp
    },
    async fetchMe() {
      const me = await getMe()
      this.user = me
      _set(K_USER, JSON.stringify(me))
      // 同步后端强制改密标记
      if (me.must_change_password) {
        this.must_change_password = true
        _set(K_MUST_CHANGE, '1')
      }
      // 拉取当前用户的功能权限矩阵
      try {
        const data = await getMyPermissions()
        this.permissions = data.permissions || {}
        _set(K_PERMS, JSON.stringify(this.permissions))
      } catch (e) {
        // 权限拉取失败不清空，保留旧值
      }
      return me
    },
    async logout({ notifyServer = true } = {}) {
      if (notifyServer) {
        try { await apiLogout() } catch {}
      }
      this.token = ''
      this.refresh_token = ''
      this.user = null
      this.permissions = {}
      this.must_change_password = false
      if (this._refreshTimer) { clearTimeout(this._refreshTimer); this._refreshTimer = null }
      _rm(K_TOKEN); _rm(K_REFRESH); _rm(K_USER); _rm(K_PERMS); _rm(K_MUST_CHANGE)
      // 额外清掉同源其它可能敏感的存储
      try { sessionStorage.clear() } catch {}
    },
    /** 改密成功：重写 token + 取消强制改密。 */
    onPasswordChanged(resp) {
      if (resp && resp.access_token) {
        this._persistTokens(resp.access_token, resp.refresh_token, resp.must_change_password)
      } else {
        this.must_change_password = false
        _rm(K_MUST_CHANGE)
      }
      this._scheduleAutoRefresh()
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
        return this.role === 'admin' || this.role === 'engineer'
      }
      return !!perms[featureKey]
    },
  },
})
