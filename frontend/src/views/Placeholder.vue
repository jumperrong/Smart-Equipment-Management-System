<template>
  <el-card shadow="never">
    <el-result icon="info" :title="title" sub-title="模块开发中，下一阶段将实现">
      <template #extra>
        <el-button type="primary" @click="$router.push('/dashboard')">返回看板</el-button>
      </template>
    </el-result>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute()
const title = computed(() => route.meta.title || '待开发')
</script>
