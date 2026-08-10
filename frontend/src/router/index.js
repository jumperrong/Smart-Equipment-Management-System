import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '@/layouts/MainLayout.vue'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: () => import('@/views/ChangePassword.vue'),
    meta: { title: '修改密码', requiresAuth: true },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      // 总览
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '看板总览', icon: 'DataAnalysis' },
      },
      // 设备基础
      {
        path: 'equipment',
        name: 'Equipment',
        component: () => import('@/views/Equipment.vue'),
        meta: { title: '设备台账', icon: 'Tools' },
      },
      {
        path: 'equipment/:id',
        name: 'EquipmentDetail',
        component: () => import('@/views/EquipmentDetail.vue'),
        meta: { title: '设备档案', hidden: true },
      },
      // 日常运维（高频）
      {
        path: 'inspection',
        name: 'Inspection',
        component: () => import('@/views/Inspection.vue'),
        meta: { title: '点检巡检', icon: 'List' },
      },
      {
        path: 'work-orders',
        name: 'WorkOrders',
        component: () => import('@/views/WorkOrders.vue'),
        meta: { title: '工单管理', icon: 'Tickets' },
      },
      {
        path: 'work-orders/:id',
        name: 'WorkOrderDetail',
        component: () => import('@/views/WorkOrderDetail.vue'),
        meta: { title: '工单详情', hidden: true },
      },
      {
        path: 'pm-plans',
        name: 'PMPlans',
        component: () => import('@/views/PMPlans.vue'),
        meta: { title: 'PM维护计划', icon: 'SetUp' },
      },
      // 支撑资源
      {
        path: 'spare-parts',
        name: 'SpareParts',
        component: () => import('@/views/SpareParts.vue'),
        meta: { title: '备件管理', icon: 'Box' },
      },
      {
        path: 'process-documents',
        name: 'ProcessDocuments',
        component: () => import('@/views/ProcessDocuments.vue'),
        meta: { title: '工艺文件', icon: 'Document' },
      },
      // 合规安全
      {
        path: 'safety-inspection',
        name: 'SafetyInspection',
        component: () => import('@/views/SafetyInspection.vue'),
        meta: { title: '安全检查', icon: 'Warning' },
      },
      // 设备全生命周期
      {
        path: 'equipment-lifecycle',
        name: 'EquipmentLifecycle',
        component: () => import('@/views/EquipmentLifecycle.vue'),
        meta: { title: '生命周期', icon: 'Connection' },
      },
      {
        path: 'lubrication',
        name: 'Lubrication',
        component: () => import('@/views/Lubrication.vue'),
        meta: { title: '润滑管理', icon: 'MagicStick' },
      },
      // 数据价值
      {
        path: 'knowledge-base',
        name: 'KnowledgeBase',
        component: () => import('@/views/KnowledgeBase.vue'),
        meta: { title: '故障知识库', icon: 'Collection' },
      },
      {
        path: 'equipment-cost',
        name: 'EquipmentCost',
        component: () => import('@/views/EquipmentCost.vue'),
        meta: { title: '设备成本LCC', icon: 'Money' },
      },
      {
        path: 'form-templates',
        name: 'FormTemplates',
        component: () => import('@/views/FormTemplates.vue'),
        meta: { title: '表单模板管理', icon: 'Tickets', roles: ['admin'] },
      },
      // 分析改进
      {
        path: 'oee',
        name: 'OEE',
        component: () => import('@/views/Placeholder.vue'),
        meta: { title: 'OEE 分析', icon: 'TrendCharts' },
      },
      {
        path: 'quality',
        name: 'Quality',
        component: () => import('@/views/Quality.vue'),
        meta: { title: '品管工具', icon: 'Document' },
      },
      // 辅助管理（低频）
      {
        path: 'environment-logs',
        name: 'EnvironmentLogs',
        component: () => import('@/views/EnvironmentLogs.vue'),
        meta: { title: '环境核查', icon: 'Cloudy' },
      },
      {
        path: 'personnel',
        name: 'Personnel',
        component: () => import('@/views/Personnel.vue'),
        meta: { title: '人员管理', icon: 'Avatar' },
      },
      {
        path: 'asset-mgmt',
        name: 'AssetMgmt',
        component: () => import('@/views/AssetMgmt.vue'),
        meta: { title: '资产管理', icon: 'Coin' },
      },
      // 系统配置
      {
        path: 'system-config',
        name: 'SystemConfig',
        component: () => import('@/views/SystemConfig.vue'),
        meta: { title: '系统配置', icon: 'Setting', roles: ['admin'] },
      },
      {
        path: 'doc-no-rules',
        name: 'DocNoRules',
        component: () => import('@/views/DocNoRules.vue'),
        meta: { title: '文档编号规则', icon: 'Postcard', roles: ['admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const token = userStore.token
  if (to.meta.public) {
    next()
  } else if (!token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name !== 'ChangePassword' && userStore.must_change_password) {
    // 使用默认弱密码/首次登录 → 强制跳改密页
    next({ name: 'ChangePassword' })
  } else {
    next()
  }
})

export default router
