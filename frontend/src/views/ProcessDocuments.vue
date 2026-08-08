<template>
  <div>
    <el-card shadow="never">
      <div class="card-header">
        <div class="header-left">
          <span style="font-weight:600">工艺文件管理</span>
          <el-tag size="small" type="info">与机台绑定 · 区别于设备维修保养附件</el-tag>
        </div>
        <div class="header-right">
          <el-checkbox v-model="showAllVersions" @change="load" size="small">
            显示全部版本
          </el-checkbox>
          <el-button v-if="canWrite && activeCategory === 'record'" type="primary" size="small" @click="openFillByTemplate()">
            <el-icon><EditPen /></el-icon> 用模板新建（结构化填写）
          </el-button>
          <el-button v-if="canWrite" type="success" size="small" @click="openUploadDialog()">
            上传{{ activeCategoryLabel }}
          </el-button>
        </div>
      </div>

      <!-- 功能说明 -->
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        <template #title>
          <span>
            <b>指导性文件</b>：Recipe 配方、流程图、规格书、作业指导书等，重版本管理。
            <b>作业记录文件</b>：批次记录、参数记录、检验记录、交接班记录等，按批号/班次/生产日期归档。
            <b>版本管理</b>：同文档可多版本，旧版自动归档；<b>状态管理</b>：草稿→生效→作废 单向流转。
          </span>
        </template>
      </el-alert>

      <!-- 大类 Tab -->
      <el-tabs v-model="activeCategory" @tab-change="load" style="margin-bottom:8px">
        <el-tab-pane label="指导性文件" name="guide" />
        <el-tab-pane label="作业记录文件" name="record" />
      </el-tabs>

      <div class="toolbar">
        <el-form :inline="true" :model="query" size="default">
          <el-form-item label="机台">
            <el-select
              v-model="query.equipment_id"
              placeholder="全部机台"
              clearable
              filterable
              style="width:220px"
              @visible-change="onEquipSelectOpen"
            >
              <el-option
                v-for="e in equipmentOptions"
                :key="e.id"
                :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                :value="e.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="query.doc_type" placeholder="全部" clearable style="width:150px">
              <el-option v-for="t in currentDocTypeOptions" :key="t" :label="docTypeLabel(t)" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" placeholder="全部" clearable style="width:130px">
              <el-option v-for="s in statusOptions" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="activeCategory === 'record'" label="批号">
            <el-input v-model="query.batch_no" placeholder="批号" clearable style="width:150px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="query.keyword" placeholder="文件名称" clearable style="width:180px" @keyup.enter="load" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="load">查询</el-button>
            <el-button @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table :data="list" stripe v-loading="loading" border size="small">
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column label="机台" min-width="150">
          <template #default="{ row }">
            <span v-if="row.equipment_name">{{ row.equipment_name }}</span>
            <el-tag v-else size="small" type="warning">#{{ row.equipment_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文件名称" min-width="200">
          <template #default="{ row }">
            <b>{{ row.doc_name }}</b>
            <el-tag v-if="!row.is_latest" size="small" type="info" style="margin-left:6px">历史版本</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.doc_type" size="small">{{ docTypeLabel(row.doc_type) }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <!-- 指导性文件：版本列 -->
        <el-table-column v-if="activeCategory === 'guide'" label="版本" width="120">
          <template #default="{ row }">
            <span>V{{ row.version_seq }}</span>
            <el-tag v-if="row.version" size="small" type="info" style="margin-left:4px">{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <!-- 作业记录：批号/班次/生产日期列 -->
        <el-table-column v-if="activeCategory === 'record'" label="批号" width="130">
          <template #default="{ row }">{{ row.batch_no || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="activeCategory === 'record'" label="班次" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.shift" size="small" :type="shiftTag(row.shift)">{{ row.shift }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="activeCategory === 'record'" label="生产日期" width="120">
          <template #default="{ row }">{{ row.production_date ? formatDate(row.production_date) : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="docStatusTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="activeCategory === 'record'" label="表单来源" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.form_record_id" size="small" type="success" effect="plain">结构化填写</el-tag>
            <el-tag v-else size="small" type="info" effect="plain">附件文件</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="activeCategory === 'guide'" label="生效日期" width="120">
          <template #default="{ row }">{{ row.effective_date ? formatDate(row.effective_date) : '-' }}</template>
        </el-table-column>
        <el-table-column label="大小" width="90">
          <template #default="{ row }">
            <span v-if="row.file_size != null">{{ formatFileSize(row.file_size) }}</span>
            <el-tag v-else-if="row.form_record_id" size="small" type="success" effect="plain">结构化</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="上传人" width="90">
          <template #default="{ row }">{{ row.uploaded_by ? '#' + row.uploaded_by : '-' }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="onDownload(row)">下载</el-button>
            <el-button v-if="row.form_record_id" size="small" link type="success" @click="openViewRecord(row)">查看填写</el-button>
            <el-button v-if="row.form_record_id" size="small" link type="info" @click="onExportRecord(row, 'json')">导出JSON</el-button>
            <el-button v-if="row.form_record_id" size="small" link type="warning" @click="onExportRecord(row, 'csv')">导出CSV</el-button>
            <el-button size="small" link type="info" @click="openVersionDialog(row)">版本</el-button>
            <el-button v-if="canWrite && !row.form_record_id" size="small" link type="success" @click="openNewVersionDialog(row)">新版本</el-button>
            <el-button v-if="canWrite && row.status === '草稿'" size="small" link type="warning" @click="onPublish(row)">发布</el-button>
            <el-button v-if="canWrite && row.status !== '作废'" size="small" link type="danger" @click="onDeprecate(row)">作废</el-button>
            <el-button v-if="canWrite" size="small" link type="primary" @click="openEditDialog(row)">编辑</el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 用模板新建（结构化填写）对话框 -->
    <el-dialog v-model="fillDialogVisible" title="用模板新建作业记录（结构化填写）" width="960px" top="4vh" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        <template #title>
          第 1 步先选<b>表单模板</b>（模板由管理员/工艺员在「表单模板管理」页面定义），
          第 2 步按模板字段填写。<b>保存草稿</b>仅落地；<b>提交</b>后不可修改。
        </template>
      </el-alert>

      <!-- Step 1: 选模板 -->
      <div v-if="!fillForm.template_id">
        <el-form :inline="true" size="default" @submit.prevent>
          <el-form-item label="选择机台">
            <el-select
              v-model="fillForm.equipment_id"
              placeholder="选择机台"
              filterable
              clearable
              style="width:240px"
              @visible-change="onEquipSelectOpen"
              @change="loadTemplateOptions"
            >
              <el-option
                v-for="e in equipmentOptions"
                :key="e.id"
                :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                :value="e.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="fillForm.filter_category" placeholder="全部" clearable style="width:140px" @change="loadTemplateOptions">
              <el-option label="作业记录类" value="record" />
              <el-option label="通用表单类" value="guide" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="fillForm.keyword" placeholder="模板名称/编码" clearable style="width:220px" @keyup.enter="loadTemplateOptions" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="loadTemplateOptions">刷新模板</el-button>
          </el-form-item>
        </el-form>
        <el-table :data="templateOptions" border stripe size="small" max-height="440" empty-text="暂无可用模板，请先在「表单模板管理」中创建并启用">
          <el-table-column type="radio" width="50" align="center" />
          <el-table-column label="名称" min-width="200">
            <template #default="{ row }"><b>{{ row.name }}</b></template>
          </el-table-column>
          <el-table-column label="编码" width="180">
            <template #default="{ row }">{{ row.code || '-' }}</template>
          </el-table-column>
          <el-table-column label="分类" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.category === 'record' ? 'primary' : 'info'">
                {{ row.category === 'record' ? '作业记录类' : '通用表单' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="适用机台" min-width="160">
            <template #default="{ row }">
              <span v-if="eqNameLocal(row.equipment_id)">{{ eqNameLocal(row.equipment_id) }}</span>
              <el-tag v-else size="small" type="success">通用</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="字段数" width="80" align="center">
            <template #default="{ row }">{{ (row.field_schema || []).length }}</template>
          </el-table-column>
          <el-table-column label="参考" width="100" align="center">
            <template #default="{ row }">
              <el-button
                v-if="row.has_ref_file"
                size="small"
                link
                type="primary"
                @click.stop="onDownloadTplRef(row)"
              >下载参考</el-button>
              <span v-else style="color:#c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="pickTemplate(row)">选择</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Step 2: 填写表单 -->
      <div v-else>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div>
            <el-tag type="success" size="small">模板：{{ fillForm._template.name }}</el-tag>
            <el-tag v-if="fillForm._template.code" size="small" style="margin-left:4px">{{ fillForm._template.code }}</el-tag>
            <el-button size="small" link @click="clearTemplate" style="margin-left:8px">← 重选模板</el-button>
          </div>
          <el-button v-if="fillForm._template.has_ref_file" size="small" type="info" plain @click="onDownloadTplRef(fillForm._template)">
            <el-icon><Download /></el-icon> 下载参考模板对照
          </el-button>
        </div>

        <el-form :model="fillForm.meta" label-width="100px" style="background:#f8f9fb;padding:14px;border-radius:6px;margin-bottom:12px">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="关联机台">
                <el-select v-model="fillForm.meta.equipment_id" filterable required style="width:100%" @visible-change="onEquipSelectOpen">
                  <el-option
                    v-for="e in equipmentOptions"
                    :key="e.id"
                    :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
                    :value="e.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="批次号"><el-input v-model="fillForm.meta.batch_no" placeholder="例：B20260807-01" /></el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="班次">
                <el-select v-model="fillForm.meta.shift" placeholder="选择班次" clearable style="width:100%">
                  <el-option label="A 班" value="A" /><el-option label="B 班" value="B" /><el-option label="C 班" value="C" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="生产日期">
                <el-date-picker v-model="fillForm.meta.production_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" />
              </el-form-item>
            </el-col>
            <el-col :span="16">
              <el-form-item label="记录标题">
                <el-input v-model="fillForm.title" placeholder="留空将自动生成：【模板名】-机台-日期/批次" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="备注">
                <el-input v-model="fillForm.remark" type="textarea" :rows="2" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <el-divider content-position="left"><span style="font-weight:600">填写字段</span></el-divider>
        <el-form :model="fillForm.values" label-width="140px" size="default">
          <template v-for="f in fillForm._template.field_schema" :key="f.key">
            <el-form-item
              :label="(f.required ? '* ' : '') + f.label + (f.unit ? ` (${f.unit})` : '')"
              :prop="f.key"
            >
              <el-input
                v-if="f.type === 'text'"
                v-model="fillForm.values[f.key]"
                :placeholder="f.placeholder || `请输入${f.label}`"
                style="width:60%"
              />
              <el-input
                v-else-if="f.type === 'textarea'"
                v-model="fillForm.values[f.key]"
                type="textarea"
                :rows="3"
                :placeholder="f.placeholder || `请输入${f.label}`"
                style="width:60%"
              />
              <el-input-number
                v-else-if="f.type === 'number'"
                v-model="fillForm.values[f.key]"
                :min="f.min !== null ? f.min : undefined"
                :max="f.max !== null ? f.max : undefined"
                controls-position="right"
                style="width:240px"
              />
              <el-select
                v-else-if="f.type === 'select'"
                v-model="fillForm.values[f.key]"
                :placeholder="f.placeholder || `请选择${f.label}`"
                clearable
                style="width:300px"
              >
                <el-option v-for="o in f.options" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
              <el-radio-group v-else-if="f.type === 'radio'" v-model="fillForm.values[f.key]">
                <el-radio v-for="o in f.options" :key="o.value" :label="o.value">{{ o.label }}</el-radio>
              </el-radio-group>
              <el-date-picker
                v-else-if="f.type === 'date'"
                v-model="fillForm.values[f.key]"
                type="date"
                value-format="YYYY-MM-DD"
                :placeholder="f.placeholder || `请选择${f.label}`"
                style="width:240px"
              />
              <el-date-picker
                v-else-if="f.type === 'datetime'"
                v-model="fillForm.values[f.key]"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                :placeholder="f.placeholder || `请选择${f.label}`"
                style="width:260px"
              />
              <el-time-picker
                v-else-if="f.type === 'time'"
                v-model="fillForm.values[f.key]"
                value-format="HH:mm:ss"
                :placeholder="f.placeholder || `请选择${f.label}`"
                style="width:220px"
              />
              <el-switch v-else-if="f.type === 'boolean'" v-model="fillForm.values[f.key]" active-text="是" inactive-text="否" />
              <span v-else style="color:#909399">未知字段类型：{{ f.type }}</span>
            </el-form-item>
          </template>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="fillDialogVisible = false">取消</el-button>
        <template v-if="fillForm.template_id">
          <el-button :loading="fillSubmitting" @click="submitFill(false)">保存草稿</el-button>
          <el-button :loading="fillSubmitting" type="primary" @click="submitFill(true)">提交（不可修改）</el-button>
        </template>
      </template>
    </el-dialog>

    <!-- 查看结构化填写值 对话框 -->
    <el-dialog v-model="viewRecordVisible" title="结构化填写详情" width="760px" top="6vh" destroy-on-close>
      <div v-if="viewRecord">
        <div class="view-header">
          <span><b>{{ viewRecord.title }}</b></span>
          <el-tag size="small" style="margin-left:8px">模板：{{ viewRecord.template_name }}</el-tag>
          <el-tag :type="recordStatusTag(viewRecord.status)" size="small" style="margin-left:4px">{{ viewRecord.status }}</el-tag>
        </div>
        <el-descriptions :column="2" border size="small" style="margin-top:10px">
          <el-descriptions-item label="ID">{{ viewRecord.id }}</el-descriptions-item>
          <el-descriptions-item label="设备">{{ viewRecord.equipment_name || (viewRecord.equipment_id ? '#' + viewRecord.equipment_id : '-') }}</el-descriptions-item>
          <el-descriptions-item label="批次号">{{ viewRecord.batch_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="班次">{{ viewRecord.shift || '-' }}</el-descriptions-item>
          <el-descriptions-item label="生产日期">{{ viewRecord.production_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ viewRecord.created_by ? '#' + viewRecord.created_by : '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(viewRecord.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ viewRecord.submitted_at ? formatTime(viewRecord.submitted_at) : '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-divider content-position="left"><span style="font-weight:600">字段填写值</span></el-divider>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item
            v-for="v in viewRecord.values"
            :key="v.field_key"
            :label="`${v.field_label_snapshot || v.field_key}`"
          >
            <template v-if="v.field_value === null || v.field_value === undefined || v.field_value === ''">
              <span style="color:#c0c4cc">(空)</span>
            </template>
            <template v-else-if="typeof v.field_value === 'boolean'">
              <el-tag :type="v.field_value ? 'success' : 'info'" size="small">{{ v.field_value ? '是' : '否' }}</el-tag>
            </template>
            <template v-else>{{ formatScalar(v.field_value) }}</template>
          </el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="viewRecord.remark" type="info" :closable="false" style="margin-top:10px">
          <template #title><b>备注：</b>{{ viewRecord.remark }}</template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="onExportRecord({form_record_id:viewRecord?.id}, 'json')">导出JSON</el-button>
        <el-button type="primary" @click="onExportRecord({form_record_id:viewRecord?.id}, 'csv')">导出CSV</el-button>
        <el-button @click="viewRecordVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 上传对话框 -->
    <el-dialog v-model="uploadDialogVisible" :title="`上传${activeCategoryLabel}`" width="560px">
      <el-form :model="uploadForm" :rules="uploadRules" ref="uploadFormRef" label-width="100px">
        <el-form-item label="关联机台" prop="equipment_id">
          <el-select
            v-model="uploadForm.equipment_id"
            placeholder="选择机台"
            filterable
            style="width:100%"
            @visible-change="onEquipSelectOpen"
          >
            <el-option
              v-for="e in equipmentOptions"
              :key="e.id"
              :label="`${e.name}${e.asset_no ? ' (' + e.asset_no + ')' : ''}`"
              :value="e.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="文件" prop="file">
          <el-upload
            :show-file-list="false"
            :before-upload="onPickFile"
            action=""
            :auto-upload="false"
          >
            <el-button :type="uploadForm.file ? 'success' : 'primary'">
              {{ uploadForm.file ? uploadForm.file.name : '选择文件' }}
            </el-button>
            <template #tip>
              <div class="upload-tip">支持 PDF/Word/Excel/PPT/图片/压缩包，最大 50MB</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="文件名称">
          <el-input v-model="uploadForm.doc_name" placeholder="留空则使用上传文件名" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="uploadForm.doc_type" placeholder="选择类型" clearable style="width:100%">
            <el-option v-for="t in currentDocTypeOptions" :key="t" :label="docTypeLabel(t)" :value="t" />
          </el-select>
        </el-form-item>
        <!-- 指导性文件字段 -->
        <el-form-item v-if="activeCategory === 'guide'" label="版本号">
          <el-input v-model="uploadForm.version" placeholder="例如 V1.0（留空默认 V1）" />
        </el-form-item>
        <!-- 作业记录字段 -->
        <template v-if="activeCategory === 'record'">
          <el-form-item label="批号">
            <el-input v-model="uploadForm.batch_no" placeholder="例如 B20260807-01" />
          </el-form-item>
          <el-form-item label="班次">
            <el-select v-model="uploadForm.shift" placeholder="选择班次" clearable style="width:100%">
              <el-option label="A 班" value="A" />
              <el-option label="B 班" value="B" />
              <el-option label="C 班" value="C" />
            </el-select>
          </el-form-item>
          <el-form-item label="生产日期">
            <el-date-picker
              v-model="uploadForm.production_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width:100%"
            />
          </el-form-item>
        </template>
        <el-form-item label="说明">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="onUpload">确认上传</el-button>
      </template>
    </el-dialog>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑工艺文件" width="560px">
      <el-form :model="editForm" :rules="editRules" ref="editFormRef" label-width="100px">
        <el-form-item label="文件名称" prop="doc_name">
          <el-input v-model="editForm.doc_name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="editForm.doc_type" placeholder="选择类型" clearable style="width:100%">
            <el-option v-for="t in editDocTypeOptions" :key="t" :label="docTypeLabel(t)" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.category === 'guide'" label="版本号">
          <el-input v-model="editForm.version" placeholder="例如 V1.0" />
        </el-form-item>
        <el-form-item v-if="editForm.category === 'guide'" label="生效日期">
          <el-date-picker
            v-model="editForm.effective_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width:100%"
          />
        </el-form-item>
        <template v-if="editForm.category === 'record'">
          <el-form-item label="批号">
            <el-input v-model="editForm.batch_no" />
          </el-form-item>
          <el-form-item label="班次">
            <el-select v-model="editForm.shift" placeholder="选择班次" clearable style="width:100%">
              <el-option label="A 班" value="A" />
              <el-option label="B 班" value="B" />
              <el-option label="C 班" value="C" />
            </el-select>
          </el-form-item>
          <el-form-item label="生产日期">
            <el-date-picker
              v-model="editForm.production_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width:100%"
            />
          </el-form-item>
        </template>
        <el-form-item label="说明">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="替换文件">
          <el-upload
            :show-file-list="false"
            :before-upload="onPickReplaceFile"
            action=""
            :auto-upload="false"
          >
            <el-button :type="editForm.replaceFile ? 'success' : 'default'">
              {{ editForm.replaceFile ? editForm.replaceFile.name : '重新上传文件' }}
            </el-button>
            <template #tip>
              <div class="upload-tip">替换后将覆盖原文件内容，元数据保留。如需保留旧版本请用"新版本"。</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 版本历史对话框 -->
    <el-dialog v-model="versionDialogVisible" title="版本历史" width="820px">
      <div v-if="versionCurrent" class="version-header">
        <span><b>{{ versionCurrent.doc_name }}</b></span>
        <el-tag size="small" type="info" style="margin-left:8px">{{ docTypeLabel(versionCurrent.doc_type) }}</el-tag>
        <el-tag size="small" style="margin-left:4px">共 {{ versionList.length }} 个版本</el-tag>
      </div>
      <el-table :data="versionList" stripe border size="small" style="margin-top:10px">
        <el-table-column label="版本" width="110">
          <template #default="{ row }">
            <span>V{{ row.version_seq }}</span>
            <el-tag v-if="row.is_latest" size="small" type="success" style="margin-left:4px">最新</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本号" width="100">
          <template #default="{ row }">{{ row.version || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="versionCurrent?.category === 'record'" label="批号" width="130">
          <template #default="{ row }">{{ row.batch_no || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="versionCurrent?.category === 'record'" label="班次" width="70">
          <template #default="{ row }">{{ row.shift || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="versionCurrent?.category === 'record'" label="生产日期" width="120">
          <template #default="{ row }">{{ row.production_date ? formatDate(row.production_date) : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="docStatusTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="versionCurrent?.category === 'guide'" label="生效日期" width="120">
          <template #default="{ row }">{{ row.effective_date ? formatDate(row.effective_date) : '-' }}</template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="上传人" width="90">
          <template #default="{ row }">{{ row.uploaded_by ? '#' + row.uploaded_by : '-' }}</template>
        </el-table-column>
        <el-table-column label="上传时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="onDownload(row)">下载</el-button>
            <el-button v-if="canWrite && row.status === '草稿'" size="small" link type="warning" @click="onPublish(row)">发布</el-button>
            <el-button v-if="canWrite && row.status !== '作废'" size="small" link type="danger" @click="onDeprecate(row)">作废</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 上传新版本对话框 -->
    <el-dialog v-model="newVersionDialogVisible" title="上传新版本" width="520px">
      <div v-if="newVersionTarget" class="version-header">
        <span>为 <b>{{ newVersionTarget.doc_name }}</b> 上传新版本</span>
        <el-tag size="small" style="margin-left:8px">当前版本 V{{ newVersionTarget.version_seq }}</el-tag>
      </div>
      <el-form :model="newVersionForm" :rules="newVersionRules" ref="newVersionFormRef" label-width="100px" style="margin-top:10px">
        <el-form-item label="文件" prop="file">
          <el-upload
            :show-file-list="false"
            :before-upload="onPickNewVersionFile"
            action=""
            :auto-upload="false"
          >
            <el-button :type="newVersionForm.file ? 'success' : 'primary'">
              {{ newVersionForm.file ? newVersionForm.file.name : '选择文件' }}
            </el-button>
          </el-upload>
        </el-form-item>
        <el-form-item v-if="newVersionTarget?.category === 'guide'" label="版本号">
          <el-input v-model="newVersionForm.version" :placeholder="`留空默认 V${(newVersionTarget?.version_seq || 0) + 1}`" />
        </el-form-item>
        <template v-if="newVersionTarget?.category === 'record'">
          <el-form-item label="批号">
            <el-input v-model="newVersionForm.batch_no" :placeholder="newVersionTarget?.batch_no || '批号'" />
          </el-form-item>
          <el-form-item label="班次">
            <el-select v-model="newVersionForm.shift" placeholder="选择班次" clearable style="width:100%">
              <el-option label="A 班" value="A" />
              <el-option label="B 班" value="B" />
              <el-option label="C 班" value="C" />
            </el-select>
          </el-form-item>
          <el-form-item label="生产日期">
            <el-date-picker
              v-model="newVersionForm.production_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width:100%"
            />
          </el-form-item>
        </template>
        <el-form-item v-if="newVersionTarget?.category === 'guide'" label="生效日期">
          <el-date-picker
            v-model="newVersionForm.effective_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width:100%"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="newVersionForm.description" type="textarea" :rows="2" placeholder="本次版本变更说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newVersionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="newVersionUploading" @click="onCreateNewVersion">确认上传</el-button>
      </template>
    </el-dialog>

    <!-- 状态流转(发布)对话框 -->
    <el-dialog v-model="publishDialogVisible" title="发布工艺文件" width="440px">
      <div style="margin-bottom:12px">
        将 <b>{{ statusTarget?.doc_name }}</b>（V{{ statusTarget?.version_seq }}）从
        <el-tag size="small" :type="docStatusTag(statusTarget?.status)">{{ statusTarget?.status }}</el-tag>
        流转为 <el-tag size="small" type="success">生效</el-tag>
      </div>
      <el-form label-width="100px">
        <el-form-item label="生效日期">
          <el-date-picker
            v-model="publishForm.effective_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="留空则默认当前时间"
            style="width:100%"
          />
        </el-form-item>
      </el-form>
      <el-alert type="warning" :closable="false">
        发布后，同文档的其他"生效"版本将自动转为"作废"。
      </el-alert>
      <template #footer>
        <el-button @click="publishDialogVisible = false">取消</el-button>
        <el-button type="success" :loading="statusTransitioning" @click="onConfirmPublish">确认发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen, Download } from '@element-plus/icons-vue'
import {
  listProcessDocuments,
  uploadProcessDocument,
  updateProcessDocument,
  deleteProcessDocument,
  downloadProcessDocument,
  listVersions,
  createNewVersion,
  transitionStatus,
  replaceFile,
} from '@/api/process_document'
import { listEquipments } from '@/api/equipment'
import {
  listFormTemplates,
  createFormRecord,
  getFormRecord,
  exportFormRecord,
  downloadTemplateRefFile,
} from '@/api/form_template'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('process_doc.write'))
const canDelete = computed(() => userStore.can('process_doc.delete'))

// 文件类型选项（按大类区分）
const guideDocTypes = ['Recipe', 'Flowchart', 'Spec', '其他']
const recordDocTypes = ['BatchRecord', 'ParamLog', 'InspectionRecord', 'ShiftHandover', '其他']
const docTypeLabels = {
  Recipe: 'Recipe 配方', Flowchart: '流程图', Spec: '规格书',
  BatchRecord: '批次记录', ParamLog: '参数记录', InspectionRecord: '检验记录', ShiftHandover: '交接班记录',
  其他: '其他',
}
const docTypeLabel = (t) => docTypeLabels[t] || t

const statusOptions = ['草稿', '生效', '作废']
const docStatusTag = (s) => ({ 草稿: 'info', 生效: 'success', 作废: 'danger' }[s] || 'info')
const shiftTag = (s) => ({ A: 'danger', B: 'primary', C: 'warning' }[s] || 'info')

const activeCategory = ref('guide')
const activeCategoryLabel = computed(() => (activeCategory.value === 'guide' ? '指导性文件' : '作业记录文件'))
const currentDocTypeOptions = computed(() => (activeCategory.value === 'guide' ? guideDocTypes : recordDocTypes))
const editDocTypeOptions = computed(() => (editForm.category === 'guide' ? guideDocTypes : recordDocTypes))

const showAllVersions = ref(false)
const query = reactive({ equipment_id: null, doc_type: '', status: '', batch_no: '', keyword: '' })
const list = ref([])
const loading = ref(false)

const equipmentOptions = ref([])
async function onEquipSelectOpen(visible) {
  if (visible && !equipmentOptions.value.length) {
    equipmentOptions.value = await listEquipments({ limit: 500 })
  }
}

async function load() {
  loading.value = true
  try {
    const params = { category: activeCategory.value, latest_only: !showAllVersions.value }
    if (query.equipment_id) params.equipment_id = query.equipment_id
    if (query.doc_type) params.doc_type = query.doc_type
    if (query.status) params.status = query.status
    if (activeCategory.value === 'record' && query.batch_no) params.batch_no = query.batch_no
    if (query.keyword) params.keyword = query.keyword
    const data = await listProcessDocuments(params)
    const eqMap = {}
    equipmentOptions.value.forEach((e) => { eqMap[e.id] = e.name })
    list.value = data.map((d) => ({
      ...d,
      equipment_name: eqMap[d.equipment_id] || (equipmentOptions.value.length ? null : `#${d.equipment_id}`),
    }))
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  Object.assign(query, { equipment_id: null, doc_type: '', status: '', batch_no: '', keyword: '' })
  load()
}

// ---- 上传 ----
const uploadDialogVisible = ref(false)
const uploading = ref(false)
const uploadFormRef = ref(null)
const uploadForm = reactive({
  equipment_id: null, file: null, doc_name: '', doc_type: '', version: '',
  batch_no: '', shift: '', production_date: '', description: '',
})
const uploadRules = {
  equipment_id: [{ required: true, message: '请选择机台', trigger: 'change' }],
  file: [
    {
      validator: (rule, value, cb) => {
        if (!uploadForm.file) cb(new Error('请选择文件'))
        else cb()
      },
      trigger: 'change',
    },
  ],
}

function openUploadDialog() {
  Object.assign(uploadForm, {
    equipment_id: null, file: null, doc_name: '', doc_type: '', version: '',
    batch_no: '', shift: '', production_date: '', description: '',
  })
  uploadDialogVisible.value = true
}

function onPickFile(file) {
  uploadForm.file = file
  if (!uploadForm.doc_name) uploadForm.doc_name = file.name
  return false
}

async function onUpload() {
  try {
    await uploadFormRef.value.validate()
    uploading.value = true
    const meta = { category: activeCategory.value, equipment_id: uploadForm.equipment_id }
    if (uploadForm.doc_name) meta.doc_name = uploadForm.doc_name
    if (uploadForm.doc_type) meta.doc_type = uploadForm.doc_type
    if (uploadForm.version) meta.version = uploadForm.version
    if (uploadForm.batch_no) meta.batch_no = uploadForm.batch_no
    if (uploadForm.shift) meta.shift = uploadForm.shift
    if (uploadForm.production_date) meta.production_date = uploadForm.production_date
    if (uploadForm.description) meta.description = uploadForm.description
    await uploadProcessDocument(uploadForm.file, meta)
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    await load()
  } catch (e) {
  } finally {
    uploading.value = false
  }
}

// ---- 编辑（含文件替换）----
const editDialogVisible = ref(false)
const saving = ref(false)
const editFormRef = ref(null)
const editForm = reactive({
  id: null, category: 'guide', doc_name: '', doc_type: '', version: '', effective_date: '',
  batch_no: '', shift: '', production_date: '', description: '', replaceFile: null,
})
const editRules = {
  doc_name: [{ required: true, message: '请输入文件名称', trigger: 'blur' }],
}

function openEditDialog(row) {
  Object.assign(editForm, {
    id: row.id,
    category: row.category || 'guide',
    doc_name: row.doc_name || '',
    doc_type: row.doc_type || '',
    version: row.version || '',
    effective_date: row.effective_date ? formatDate(row.effective_date) : '',
    batch_no: row.batch_no || '',
    shift: row.shift || '',
    production_date: row.production_date ? formatDate(row.production_date) : '',
    description: row.description || '',
    replaceFile: null,
  })
  editDialogVisible.value = true
}

function onPickReplaceFile(file) {
  editForm.replaceFile = file
  return false
}

async function onSaveEdit() {
  try {
    await editFormRef.value.validate()
    saving.value = true
    const payload = {
      doc_name: editForm.doc_name,
      doc_type: editForm.doc_type || null,
      description: editForm.description || null,
    }
    if (editForm.category === 'guide') {
      payload.version = editForm.version || null
      payload.effective_date = editForm.effective_date || null
    } else {
      payload.batch_no = editForm.batch_no || null
      payload.shift = editForm.shift || null
      payload.production_date = editForm.production_date || null
    }
    await updateProcessDocument(editForm.id, payload)
    if (editForm.replaceFile) {
      await replaceFile(editForm.id, editForm.replaceFile)
      ElMessage.success('元数据已更新，文件已替换')
    } else {
      ElMessage.success('已更新')
    }
    editDialogVisible.value = false
    await load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

// ---- 版本历史 ----
const versionDialogVisible = ref(false)
const versionList = ref([])
const versionCurrent = ref(null)

async function openVersionDialog(row) {
  versionCurrent.value = row
  versionDialogVisible.value = true
  try {
    versionList.value = await listVersions(row.id)
  } catch (e) {
    versionList.value = []
  }
}

// ---- 上传新版本 ----
const newVersionDialogVisible = ref(false)
const newVersionTarget = ref(null)
const newVersionUploading = ref(false)
const newVersionFormRef = ref(null)
const newVersionForm = reactive({
  file: null, version: '', effective_date: '', batch_no: '', shift: '', production_date: '', description: '',
})
const newVersionRules = {
  file: [
    {
      validator: (rule, value, cb) => {
        if (!newVersionForm.file) cb(new Error('请选择文件'))
        else cb()
      },
      trigger: 'change',
    },
  ],
}

function openNewVersionDialog(row) {
  newVersionTarget.value = row
  Object.assign(newVersionForm, {
    file: null, version: '', effective_date: '', batch_no: '', shift: '', production_date: '', description: '',
  })
  newVersionDialogVisible.value = true
}

function onPickNewVersionFile(file) {
  newVersionForm.file = file
  return false
}

async function onCreateNewVersion() {
  try {
    await newVersionFormRef.value.validate()
    newVersionUploading.value = true
    const meta = {}
    if (newVersionForm.version) meta.version = newVersionForm.version
    if (newVersionForm.effective_date) meta.effective_date = newVersionForm.effective_date
    if (newVersionForm.batch_no) meta.batch_no = newVersionForm.batch_no
    if (newVersionForm.shift) meta.shift = newVersionForm.shift
    if (newVersionForm.production_date) meta.production_date = newVersionForm.production_date
    if (newVersionForm.description) meta.description = newVersionForm.description
    await createNewVersion(newVersionTarget.value.id, newVersionForm.file, meta)
    ElMessage.success('新版本已上传')
    newVersionDialogVisible.value = false
    await load()
  } catch (e) {
  } finally {
    newVersionUploading.value = false
  }
}

// ---- 状态流转：发布 ----
const publishDialogVisible = ref(false)
const statusTarget = ref(null)
const statusTransitioning = ref(false)
const publishForm = reactive({ effective_date: '' })

function onPublish(row) {
  statusTarget.value = row
  publishForm.effective_date = row.effective_date ? formatDate(row.effective_date) : ''
  publishDialogVisible.value = true
}

async function onConfirmPublish() {
  statusTransitioning.value = true
  try {
    await transitionStatus(statusTarget.value.id, {
      status: '生效',
      effective_date: publishForm.effective_date || undefined,
    })
    ElMessage.success('已发布为生效状态')
    publishDialogVisible.value = false
    await load()
    if (versionDialogVisible.value && versionCurrent.value) {
      versionList.value = await listVersions(versionCurrent.value.id)
    }
  } catch (e) {
  } finally {
    statusTransitioning.value = false
  }
}

// ---- 状态流转：作废 ----
async function onDeprecate(row) {
  try {
    const { value: remark } = await ElMessageBox.prompt(
      `确认将【${row.doc_name} (V${row.version_seq})】作废？请输入作废原因（可选）：`,
      '作废确认',
      { type: 'warning', inputType: 'textarea', inputPlaceholder: '作废原因（可选）' },
    )
    await transitionStatus(row.id, { status: '作废', remark: remark || undefined })
    ElMessage.success('已作废')
    await load()
    if (versionDialogVisible.value && versionCurrent.value) {
      versionList.value = await listVersions(versionCurrent.value.id)
    }
  } catch (e) {
  }
}

// ---- 下载 / 删除 ----
async function onDownload(row) {
  try {
    await downloadProcessDocument(row.id, row.doc_name)
    ElMessage.success('下载已开始')
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确认删除工艺文件【${row.doc_name} (V${row.version_seq})】？该操作不可恢复。`,
      '危险操作',
      { type: 'error' },
    )
    await deleteProcessDocument(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {}
}

// ---- 工具 ----
function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}
function formatDate(t) {
  return t ? formatTime(t, 'YYYY-MM-DD') : '-'
}
function formatScalar(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}
const recordStatusTag = (s) => ({
  草稿: 'info', 已提交: 'success', 已作废: 'danger',
}[s] || 'info')

// ---------- 用模板新建（结构化填写） ----------
const fillDialogVisible = ref(false)
const fillSubmitting = ref(false)
const templateOptions = ref([])
const eqMapLocal = computed(() => {
  const m = {}
  equipmentOptions.value.forEach((e) => { m[e.id] = e.name })
  return m
})
const eqNameLocal = (id) => (id ? eqMapLocal.value[id] || null : null)

function defaultFillForm() {
  return reactive({
    template_id: null,
    _template: null,
    equipment_id: query.equipment_id || null,
    filter_category: 'record',
    keyword: '',
    title: '',
    remark: '',
    meta: {
      equipment_id: query.equipment_id || null,
      batch_no: '',
      shift: '',
      production_date: '',
    },
    values: {},
  })
}
const fillForm = defaultFillForm()

function openFillByTemplate() {
  Object.assign(fillForm, defaultFillForm())
  fillForm.equipment_id = query.equipment_id || null
  fillForm.meta.equipment_id = query.equipment_id || null
  fillForm.filter_category = 'record'
  fillDialogVisible.value = true
  loadTemplateOptions()
}

async function loadTemplateOptions() {
  const params = { is_active: true }
  if (fillForm.filter_category) params.category = fillForm.filter_category
  if (fillForm.keyword) params.keyword = fillForm.keyword
  // 若指定了设备：查所有模板，然后在前端保留「匹配该设备」或「通用(未绑定设备)」的模板
  const all = await listFormTemplates(params)
  if (fillForm.equipment_id) {
    templateOptions.value = all.filter((x) => !x.equipment_id || x.equipment_id === fillForm.equipment_id)
    // 排序：精确匹配的模板优先，通用在后
    templateOptions.value.sort((a, b) => {
      const aw = a.equipment_id === fillForm.equipment_id ? 0 : 1
      const bw = b.equipment_id === fillForm.equipment_id ? 0 : 1
      return aw - bw
    })
  } else {
    templateOptions.value = all
  }
}

function onDownloadTplRef(row) {
  downloadTemplateRefFile(row.id, row.ref_original_name).catch((e) => {
    ElMessage.error(e?.message || '下载参考模板失败')
  })
}

function pickTemplate(row) {
  fillForm.template_id = row.id
  fillForm._template = row
  // 初始化默认值
  fillForm.values = {}
  ;(row.field_schema || []).forEach((f) => {
    if (f.default_value !== null && f.default_value !== undefined) {
      fillForm.values[f.key] = f.default_value
    } else if (f.type === 'boolean') {
      fillForm.values[f.key] = false
    } else {
      fillForm.values[f.key] = null
    }
  })
  // 若模板绑定了具体机台 → 默认填写元数据
  if (row.equipment_id && !fillForm.meta.equipment_id) {
    fillForm.meta.equipment_id = row.equipment_id
  }
  if (!fillForm.meta.equipment_id && query.equipment_id) {
    fillForm.meta.equipment_id = query.equipment_id
  }
}
function clearTemplate() {
  fillForm.template_id = null
  fillForm._template = null
  fillForm.values = {}
}

async function submitFill(doSubmit) {
  if (!fillForm.template_id) return
  if (!fillForm.meta.equipment_id) {
    ElMessage.error('请先填写关联机台')
    return
  }
  const keys = {}
  ;(fillForm._template.field_schema || []).forEach((f) => { keys[f.key] = f })
  const valuesArr = Object.keys(fillForm.values)
    .filter((k) => fillForm.values[k] !== undefined && fillForm.values[k] !== null && fillForm.values[k] !== '')
    .map((k) => ({ field_key: k, field_value: fillForm.values[k] }))
  const payload = {
    template_id: fillForm.template_id,
    equipment_id: fillForm.meta.equipment_id,
    title: fillForm.title || null,
    batch_no: fillForm.meta.batch_no || null,
    shift: fillForm.meta.shift || null,
    production_date: fillForm.meta.production_date || null,
    remark: fillForm.remark || null,
    values: valuesArr,
    auto_submit: !!doSubmit,
    link_process_doc: true,
  }
  fillSubmitting.value = true
  try {
    const rec = await createFormRecord(payload)
    if (doSubmit) ElMessage.success(`已提交：#${rec.id} ${rec.title}`)
    else ElMessage.success(`已保存草稿：#${rec.id} ${rec.title}`)
    fillDialogVisible.value = false
    load()
  } finally {
    fillSubmitting.value = false
  }
}

// ---------- 查看结构化记录 ----------
const viewRecordVisible = ref(false)
const viewRecord = ref(null)

async function openViewRecord(row) {
  if (!row.form_record_id) return
  viewRecord.value = null
  viewRecordVisible.value = true
  try {
    const r = await getFormRecord(row.form_record_id)
    // 按 seq 排序 values
    const seqMap = {}
    ;(r.field_schema_snapshot || []).forEach((f) => { seqMap[f.key] = f.seq ?? 0 })
    r.values = (r.values || []).sort((a, b) => (seqMap[a.field_key] ?? 999) - (seqMap[b.field_key] ?? 999))
    viewRecord.value = r
  } catch (e) {
    viewRecordVisible.value = false
  }
}

function onExportRecord(row, format = 'csv') {
  const id = row.form_record_id || row.id
  if (!id) return
  exportFormRecord(id, format).catch((e) => ElMessage.error(e?.message || '导出失败'))
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.header-left { display: flex; align-items: center; gap: 8px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.toolbar { margin-bottom: 10px; }
.upload-tip { font-size: 12px; color: #909399; line-height: 1.4; }
.version-header { padding: 4px 0; }
.view-header { padding: 4px 0; line-height: 1.7; }
</style>
