<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="厂区">
            <el-input v-model="query.factory" placeholder="厂区" clearable style="width:140px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item label="区域">
            <el-input v-model="query.area" placeholder="区域" clearable style="width:140px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item label="结果">
            <el-select v-model="query.result" clearable placeholder="全部" style="width:120px">
              <el-option :label="envResultLabel('OK')" value="OK" />
              <el-option :label="envResultLabel('NG')" value="NG" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="query.range"
              type="daterange"
              value-format="YYYY-MM-DDTHH:mm:ss"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width:340px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button v-if="canWrite" type="success" @click="openDialog()">新增记录</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column label="核查时间" width="160">
          <template #default="{ row }">{{ formatTime(row.log_date) }}</template>
        </el-table-column>
        <el-table-column prop="factory" label="厂区" width="90" />
        <el-table-column prop="area" label="区域" width="100" />
        <el-table-column prop="shift" label="班次" width="70" />
        <el-table-column label="温度" width="90">
          <template #default="{ row }">{{ row.temperature ?? '-' }}℃</template>
        </el-table-column>
        <el-table-column label="湿度" width="90">
          <template #default="{ row }">{{ row.humidity ?? '-' }}%</template>
        </el-table-column>
        <el-table-column prop="cleanliness" label="洁净度等级" width="110" />
        <el-table-column prop="particles" label="粒子数" width="100" />
        <el-table-column label="压差" width="90">
          <template #default="{ row }">{{ row.pressure ?? '-' }}Pa</template>
        </el-table-column>
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="envResultTag(row.result)" size="small">{{ envResultLabel(row.result) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite" size="small" link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑环境核查记录' : '新增环境核查记录'" width="720px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="核查时间" prop="log_date">
              <el-date-picker
                v-model="form.log_date"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="选择核查时间"
                style="width:100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结果" prop="result">
              <el-radio-group v-model="form.result">
                <el-radio value="OK">{{ envResultLabel('OK') }}</el-radio>
                <el-radio value="NG">{{ envResultLabel('NG') }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12"><el-form-item label="厂区" prop="factory"><el-input v-model="form.factory" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="区域" prop="area"><el-input v-model="form.area" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="班次"><el-input v-model="form.shift" placeholder="A/B/C" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="洁净度等级"><el-input v-model="form.cleanliness" placeholder="ISO 7" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="温度(℃)"><el-input-number v-model="form.temperature" :step="0.1" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="湿度(%)"><el-input-number v-model="form.humidity" :step="0.1" :min="0" :max="100" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="粒子数"><el-input-number v-model="form.particles" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="压差(Pa)"><el-input-number v-model="form.pressure" :step="1" style="width:100%" /></el-form-item></el-col>
          <el-col :span="24"><el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listEnvLogs, getEnvLog, createEnvLog, updateEnvLog, deleteEnvLog,
} from '@/api/environment'
import { useUserStore } from '@/stores'
import { formatTime, envResultLabel, envResultTag } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('environment.write'))
const canDelete = computed(() => userStore.can('environment.delete'))

const query = reactive({ factory: '', area: '', result: '', range: null })
const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const params = { limit: 100 }
    if (query.factory) params.factory = query.factory
    if (query.area) params.area = query.area
    if (query.result) params.result = query.result
    if (query.range && query.range.length === 2) {
      params.start = query.range[0]
      params.end = query.range[1]
    }
    list.value = await listEnvLogs(params)
  } catch (e) {} finally {
    loading.value = false
  }
}

// 新增/编辑
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const form = reactive({
  id: null,
  log_date: '',
  factory: '',
  area: '',
  shift: '',
  temperature: null,
  humidity: null,
  cleanliness: '',
  particles: null,
  pressure: null,
  result: 'OK',
  remark: '',
})
const formRules = {
  log_date: [{ required: true, message: '请选择核查时间', trigger: 'change' }],
  result: [{ required: true, message: '请选择结果', trigger: 'change' }],
}
function openDialog(row = null) {
  Object.assign(form, {
    id: null,
    log_date: '',
    factory: '',
    area: '',
    shift: '',
    temperature: null,
    humidity: null,
    cleanliness: '',
    particles: null,
    pressure: null,
    result: 'OK',
    remark: '',
  })
  if (row) Object.assign(form, JSON.parse(JSON.stringify(row)))
  dialogVisible.value = true
}
async function onSave() {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = JSON.parse(JSON.stringify(form))
    if (payload.id) {
      const { id, ...rest } = payload
      await updateEnvLog(id, rest)
      ElMessage.success('已更新')
    } else {
      delete payload.id
      await createEnvLog(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {} finally {
    saving.value = false
  }
}
async function onDelete(row) {
  try {
    await ElMessageBox.confirm('确认删除该环境核查记录？', '危险操作', { type: 'error' })
    await deleteEnvLog(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {}
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 10px; }
</style>
