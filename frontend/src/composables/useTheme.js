/**
 * 主题管理 composable
 * 支持三种模式：light（明色青绿）/ dark（暗色霓虹）/ auto（跟随系统）
 * - localStorage 持久化用户选择
 * - auto 模式下监听 prefers-color-scheme 变化自动切换
 * - 通过给 <html> 添加/移除 .dark 类来切换皮肤
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'sems-theme-mode'

const mode = ref('auto')          // 'light' | 'dark' | 'auto'
const systemDark = ref(false)     // 系统当前是否暗色
let mediaQuery = null
let mediaListener = null

/** 当前实际是否暗色 */
const isDark = computed(() => {
  if (mode.value === 'dark') return true
  if (mode.value === 'light') return false
  return systemDark.value // auto
})

/** 给 <html> 加/移 dark 类 */
function applyDarkClass() {
  const html = document.documentElement
  if (isDark.value) {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
}

/** 初始化系统偏好监听 */
function initSystemListener() {
  if (typeof window === 'undefined' || !window.matchMedia) return
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemDark.value = mediaQuery.matches
  mediaListener = (e) => { systemDark.value = e.matches }
  // 兼容旧版 Safari
  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', mediaListener)
  } else if (mediaQuery.addListener) {
    mediaQuery.addListener(mediaListener)
  }
}

/** 从 localStorage 恢复 */
function restoreMode() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark' || saved === 'auto') {
      mode.value = saved
    }
  } catch (e) { /* ignore */ }
}

/** 保存到 localStorage */
function persistMode() {
  try {
    localStorage.setItem(STORAGE_KEY, mode.value)
  } catch (e) { /* ignore */ }
}

/** 初始化（在 App.vue 或 main.js 中调用一次即可） */
function initTheme() {
  restoreMode()
  initSystemListener()
  applyDarkClass()
}

/** 切换模式 */
function setMode(newMode) {
  if (newMode !== 'light' && newMode !== 'dark' && newMode !== 'auto') return
  mode.value = newMode
  persistMode()
  applyDarkClass()
}

/** 在明/暗之间快速切换（auto 时按系统反色） */
function toggleTheme() {
  if (mode.value === 'auto') {
    setMode(isDark.value ? 'light' : 'dark')
  } else {
    setMode(mode.value === 'dark' ? 'light' : 'dark')
  }
}

/** 主题模式中文标签 */
const modeLabel = computed(() => ({
  light: '明色青绿',
  dark: '暗色霓虹',
  auto: '跟随系统',
}[mode.value]))

/** 主题图标名 */
const modeIcon = computed(() => ({
  light: 'Sunny',
  dark: 'Moon',
  auto: 'Monitor',
}[mode.value]))

// 监听 isDark 变化自动应用
watch(isDark, () => applyDarkClass())

export {
  mode,
  isDark,
  modeLabel,
  modeIcon,
  initTheme,
  setMode,
  toggleTheme,
}

/**
 * 组合式函数：在组件中使用
 * 注意：initTheme() 只需在 main.js 或 App.vue setup 中调用一次
 */
export default function useTheme() {
  return {
    mode,
    isDark,
    modeLabel,
    modeIcon,
    setMode,
    toggleTheme,
  }
}
