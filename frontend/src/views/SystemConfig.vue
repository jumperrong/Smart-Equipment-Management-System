<template>
  <el-tabs v-model="activeTab" type="border-card" class="system-tabs">
    <el-tab-pane label="字典管理" name="dictionary">
      <DictionaryPanel v-if="loaded.dictionary" />
    </el-tab-pane>
    <el-tab-pane label="角色权限" name="permissions">
      <RolePermissionsPanel v-if="loaded.permissions" />
    </el-tab-pane>
    <el-tab-pane label="用户管理" name="users">
      <UserManagePanel v-if="loaded.users" />
    </el-tab-pane>
    <el-tab-pane label="系统设置" name="settings">
      <SystemSettingsPanel v-if="loaded.settings" />
    </el-tab-pane>
    <el-tab-pane label="IP 白名单" name="ip-whitelist">
      <IpWhitelistPanel v-if="loaded['ip-whitelist']" />
    </el-tab-pane>
    <el-tab-pane label="备份/恢复" name="backup">
      <BackupPanel v-if="loaded.backup" />
    </el-tab-pane>
  </el-tabs>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import DictionaryPanel from './system/DictionaryPanel.vue'
import RolePermissionsPanel from './system/RolePermissionsPanel.vue'
import UserManagePanel from './system/UserManagePanel.vue'
import SystemSettingsPanel from './system/SystemSettingsPanel.vue'
import IpWhitelistPanel from './system/IpWhitelistPanel.vue'
import BackupPanel from './system/BackupPanel.vue'

// 延迟挂载：切到某 Tab 才首次加载对应组件，避免一次性加载全部
const activeTab = ref('dictionary')
const loaded = reactive({
  dictionary: true,
  permissions: false,
  users: false,
  settings: false,
  'ip-whitelist': false,
  backup: false,
})

watch(activeTab, (t) => {
  loaded[t] = true
})
</script>

<style scoped>
.system-tabs :deep(.el-tabs__content) {
  padding: 16px;
}
</style>
