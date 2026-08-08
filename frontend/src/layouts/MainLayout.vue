<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <div class="logo">
        <el-icon :size="22" color="#409eff"><Cpu /></el-icon>
        <span v-show="!isCollapse" class="logo-text">SEMS 设备管理</span>
      </div>
      <el-menu
        :default-active="$route.path"
        :collapse="isCollapse"
        router
        class="side-menu"
        background-color="#001529"
        text-color="#b8c4cf"
        active-text-color="#409eff"
      >
        <template v-for="r in menuRoutes" :key="r.path">
          <el-menu-item :index="r.path">
            <el-icon><component :is="r.meta.icon" /></el-icon>
            <template #title>{{ r.meta.title }}</template>
          </el-menu-item>
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
          <el-dropdown @command="onCommand">
            <span class="user-info">
              <el-avatar :size="32" style="background:#409eff">{{ avatarChar }}</el-avatar>
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

const isCollapse = ref(false)
const routerObj = useRouter()
const route = useRoute()
const userStore = useUserStore()

const menuRoutes = computed(() => {
  const children = router.options.routes.find((r) => r.path === '/')?.children || []
  return children
    .filter((c) => c.meta?.title && !c.meta.hidden && (!c.meta.roles || userStore.hasRole(...c.meta.roles)))
    .map((c) => ({ path: '/' + c.path, meta: c.meta }))
})

const currentTitle = computed(() => route.meta.title || '')

const avatarChar = computed(() => (userStore.fullName || 'U').charAt(0).toUpperCase())

const roleLabel = (r) => ({ admin: '管理员', engineer: '工程师', process_engineer: '工艺员', operator: '操作员', viewer: '查看' }[r] || r)
const roleTagType = (r) => ({ admin: 'danger', engineer: 'primary', process_engineer: 'warning', operator: 'success', viewer: 'info' }[r] || 'info')

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
  background: #001529;
  transition: width 0.2s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.logo {
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
  border-bottom: 1px solid #0b2a45;
}
.side-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: none;
}
.side-menu::-webkit-scrollbar {
  width: 6px;
}
.side-menu::-webkit-scrollbar-thumb {
  background: #2a3f52;
  border-radius: 3px;
}
.side-menu::-webkit-scrollbar-track {
  background: transparent;
}
.logo-text {
  font-weight: 600;
  font-size: 16px;
  white-space: nowrap;
}
.header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.left { display: flex; align-items: center; gap: 14px; }
.crumb { font-size: 16px; font-weight: 500; color: #303133; }
.right .user-info {
  display: flex; align-items: center; gap: 10px; cursor: pointer;
}
.right .name { color: #303133; font-weight: 500;
}
.main-body {
  padding: 18px;
  background: #f5f7fa;
  overflow: #f5f7fa;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
:deep(.el-menu) { border-right: none; }
</style>
