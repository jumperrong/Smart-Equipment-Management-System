<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo">
        <el-icon :size="22" class="logo-icon"><Cpu /></el-icon>
        <span v-show="!isCollapse" class="logo-text">SEMS · 半导体制造执行系统</span>
      </div>
      <el-menu
        :default-active="$route.path"
        :collapse="isCollapse"
        :default-openeds="defaultOpeneds"
        router
        class="side-menu"
      >
        <template v-for="g in menuGroups" :key="g.key">
          <!-- 单项分组：直接渲染为菜单项（如总览、系统配置） -->
          <el-menu-item v-if="g.items.length === 1" :index="g.items[0].path">
            <el-icon><component :is="g.items[0].meta.icon" /></el-icon>
            <template #title>{{ g.items[0].meta.title }}</template>
          </el-menu-item>
          <!-- 多项分组：折叠子菜单 -->
          <el-sub-menu v-else :index="g.key">
            <template #title>
              <el-icon><component :is="g.icon" /></el-icon>
              <span>{{ g.title }}</span>
            </template>
            <el-menu-item
              v-for="it in g.items"
              :key="it.path"
              :index="it.path"
            >
              <el-icon><component :is="it.meta.icon" /></el-icon>
              <template #title>{{ it.meta.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="left">
          <el-button text @click="isCollapse = !isCollapse">
            <el-icon :size="18"><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
          </el-button>
          <span class="crumb">{{ currentTitle }}</span>
        </div>
        <div class="right">
          <!-- 主题切换：明 / 暗 / 自动 -->
          <el-dropdown @command="onThemeCommand" trigger="click">
            <el-button text class="theme-btn">
              <el-icon :size="18"><component :is="modeIcon" /></el-icon>
              <span class="theme-label">{{ modeLabel }}</span>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="light" :class="{ 'is-active': mode === 'light' }">
                  <el-icon><Sunny /></el-icon>&nbsp;明色青绿
                </el-dropdown-item>
                <el-dropdown-item command="dark" :class="{ 'is-active': mode === 'dark' }">
                  <el-icon><Moon /></el-icon>&nbsp;暗色霓虹
                </el-dropdown-item>
                <el-dropdown-item command="auto" :class="{ 'is-active': mode === 'auto' }" divided>
                  <el-icon><Monitor /></el-icon>&nbsp;跟随系统
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-dropdown @command="onCommand">
            <span class="user-info">
              <el-avatar :size="32" class="user-avatar">{{ avatarChar }}</el-avatar>
              <span class="name">{{ userStore.fullName || '未登录' }}</span>
              <el-tag :type="roleTagType(userStore.role)" size="small" effect="dark">{{ roleLabel(userStore.role) }}</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="change-password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main-body">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
          <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useUserStore } from '@/stores'
import router from '@/router'
import useTheme from '@/composables/useTheme'

const isCollapse = ref(false)
const routerObj = useRouter()
const route = useRoute()
const userStore = useUserStore()

const { mode, modeLabel, modeIcon, setMode } = useTheme()

function onThemeCommand(cmd) {
  setMode(cmd)
}

// 分级菜单配置：按职能域分组，系统配置永远最后（alwaysLast）
// 单项分组渲染为直接菜单项；多项分组渲染为折叠子菜单
const MENU_GROUPS = [
  {
    key: 'overview',
    title: '总览',
    icon: 'DataAnalysis',
    names: ['Dashboard'],
  },
  {
    key: 'equipment',
    title: '设备管理',
    icon: 'Tools',
    names: ['Equipment', 'EquipmentLifecycle', 'Lubrication'],
  },
  {
    key: 'maintenance',
    title: '运维工单',
    icon: 'Tickets',
    names: ['WorkOrders', 'PMPlans', 'Inspection'],
    defaultOpen: true,
  },
  {
    key: 'safety',
    title: '安全与环境',
    icon: 'Warning',
    names: ['SafetyInspection', 'EnvironmentLogs'],
  },
  {
    key: 'spare',
    title: '备件与人员',
    icon: 'Box',
    names: ['SpareParts', 'AssetMgmt', 'Personnel'],
  },
  {
    key: 'process',
    title: '工艺文控',
    icon: 'Document',
    names: ['ProcessDocuments', 'FormTemplates', 'DocNoRules'],
    defaultOpen: true,
  },
  {
    key: 'analysis',
    title: '分析改进',
    icon: 'TrendCharts',
    names: ['OEE', 'Quality', 'KnowledgeBase', 'EquipmentCost'],
  },
  {
    key: 'production',
    title: '生产管理',
    icon: 'Operation',
    names: ['Products', 'ProcessSections', 'Routings', 'ProductionOrders', 'Dispatches', 'LaborReports'],
    defaultOpen: true,
  },
  {
    key: 'system',
    title: '系统配置',
    icon: 'Setting',
    names: ['SystemConfig'],
    alwaysLast: true,
  },
]

const menuGroups = computed(() => {
  const children = router.options.routes.find((r) => r.path === '/')?.children || []
  const byName = {}
  children.forEach((c) => {
    if (c.meta?.title && !c.meta.hidden) byName[c.name] = c
  })
  const groups = MENU_GROUPS.map((g) => {
    const items = g.names
      .filter((n) => byName[n])
      .filter((n) => {
        const c = byName[n]
        return !c.meta.roles || userStore.hasRole(...c.meta.roles)
      })
      .map((n) => {
        const c = byName[n]
        return { path: '/' + c.path, meta: c.meta, name: c.name }
      })
    return { key: g.key, title: g.title, icon: g.icon, items, defaultOpen: g.defaultOpen, alwaysLast: !!g.alwaysLast }
  })
  // alwaysLast 的分组（系统配置）固定排到末尾
  const normal = groups.filter((g) => !g.alwaysLast)
  const last = groups.filter((g) => g.alwaysLast)
  return [...normal, ...last].filter((g) => g.items.length > 0)
})

const defaultOpeneds = computed(() => {
  return menuGroups.value.filter((g) => g.defaultOpen).map((g) => g.key)
})

const currentTitle = computed(() => route.meta.title || '')

const avatarChar = computed(() => (userStore.fullName || 'U').charAt(0).toUpperCase())

const roleLabel = (r) => ({ admin: '管理员', engineer: '工程师', process_engineer: '工艺员', qa: 'QA审核员', production_manager: '生产主管', team_leader: '班组长', operator: '操作员', viewer: '查看' }[r] || r)
const roleTagType = (r) => ({ admin: 'danger', engineer: 'primary', process_engineer: 'warning', qa: 'danger', production_manager: 'primary', team_leader: 'success', operator: 'success', viewer: 'info' }[r] || 'info')

function onCommand(cmd) {
  if (cmd === 'change-password') {
    routerObj.push({ name: 'ChangePassword' })
    return
  }
  if (cmd === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
      .then(() => {
        userStore.logout()
        routerObj.push({ name: 'Login' })
        ElMessage.success('已退出')
      })
      .catch(() => {})
  }
}
</script>

<style scoped>
.main-layout {
  height: 100%;
}
.aside {
  background: var(--app-sidebar-bg);
  transition: width 0.2s, background 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--app-sidebar-border);
}
.logo {
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--app-text-primary);
  border-bottom: 1px solid var(--app-sidebar-border);
}
.logo-icon {
  color: var(--app-primary);
}
.side-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: none;
  background: var(--app-sidebar-bg);
}
.side-menu::-webkit-scrollbar {
  width: 6px;
}
.side-menu::-webkit-scrollbar-thumb {
  background: var(--app-sidebar-scroll);
  border-radius: 3px;
}
.side-menu::-webkit-scrollbar-track {
  background: transparent;
}
.logo-text {
  font-weight: 600;
  font-size: 16px;
  white-space: nowrap;
  color: var(--app-text-primary);
}
.header {
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-header-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  transition: background 0.3s, border-color 0.3s;
}
.left { display: flex; align-items: center; gap: 14px; }
.crumb { font-size: 16px; font-weight: 500; color: var(--app-header-text); }
.right { display: flex; align-items: center; gap: 16px; }
.theme-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--app-text-secondary);
}
.theme-label {
  font-size: 13px;
}
.theme-btn:hover {
  color: var(--app-primary);
}
.right .user-info {
  display: flex; align-items: center; gap: 10px; cursor: pointer;
}
.user-avatar {
  background: var(--app-primary);
  color: #fff;
}
.right .name { color: var(--app-header-text); font-weight: 500; }
.main-body {
  padding: 18px;
  background: var(--app-page-bg);
  overflow: auto;
  transition: background 0.3s;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
:deep(.el-menu) {
  border-right: none;
  background: var(--app-sidebar-bg);
}
:deep(.el-menu-item) {
  color: var(--app-sidebar-text);
}
:deep(.el-menu-item:hover) {
  background: var(--app-sidebar-hover);
}
:deep(.el-menu-item.is-active) {
  color: var(--app-sidebar-active);
}
/* 暗色模式选中项霓虹发光 */
html.dark :deep(.el-menu-item.is-active) {
  text-shadow: var(--app-glow-primary);
}
/* 折叠分组标题样式 */
:deep(.el-sub-menu__title) {
  color: var(--app-sidebar-text);
  font-weight: 600;
  font-size: 13px;
  letter-spacing: 0.3px;
}
:deep(.el-sub-menu__title:hover) {
  background: var(--app-sidebar-hover);
}
:deep(.el-sub-menu .el-menu-item) {
  font-size: 13px;
  padding-left: 48px !important;
}
/* 折叠态下隐藏分组标题文字，仅显示图标 */
:deep(.el-menu--collapse .el-sub-menu__title span) {
  display: none;
}
</style>
