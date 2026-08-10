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
          <el-button v-if="canFill && activeCategory === 'record'" type="primary" size="small" @click="openCreateFormDialog()">
            <el-icon><EditPen /></el-icon> 新建电子表单
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
            <div v-if="row.doc_no" style="font-size:11px;color:var(--el-text-color-secondary);margin-top:2px">{{ row.doc_no }}</div>
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
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <el-tag :type="docStatusTag(row.status)" size="small">{{ row.status }}</el-tag>
            <el-tag
              v-if="row.status === '生效' && isReviewDue(row)"
              size="small"
              type="danger"
              effect="dark"
              style="margin-left:4px;margin-top:2px"
            >
              复审 {{ reviewDueLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="activeCategory === 'record'" label="表单来源" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.form_record_id" size="small" type="success" effect="plain">结构化填写</el-tag>
            <el-tag v-else size="small" type="info" effect="plain">附件文件</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="activeCategory === 'guide'" label="生效日期 / 复审" width="170">
          <template #default="{ row }">
            <div>{{ row.effective_date ? formatDate(row.effective_date) : '-' }}</div>
            <div v-if="row.next_review_date" style="font-size:11px;color:var(--el-text-color-secondary)">
              下次复审: {{ formatDate(row.next_review_date) }}
            </div>
          </template>
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
        <el-table-column label="操作" width="520" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="onDownload(row)">下载(水印)</el-button>
            <el-button
              v-if="row.form_record_id && canFill"
              size="small"
              link
              type="success"
              @click="openFillDialog(row)"
            >
              <el-icon><EditPen /></el-icon> 填写
            </el-button>
            <el-button v-if="row.form_record_id" size="small" link type="info" @click="openViewRecord(row)">查看填写</el-button>
            <el-button v-if="row.form_record_id" size="small" link type="warning" @click="onExportRecord(row, 'json')">导出JSON</el-button>
            <el-button v-if="row.form_record_id" size="small" link type="warning" @click="onExportRecord(row, 'csv')">导出CSV</el-button>
            <el-button size="small" link type="info" @click="openVersionDialog(row)">版本</el-button>
            <!-- 文控操作：提交审核 / 审核 / 批准 -->
            <el-button
              v-if="canSubmitReview && row.status === '草稿' && !row.form_record_id"
              size="small"
              link
              type="warning"
              @click="openApprovalDialog(row, 'prepare')"
            >提交审核</el-button>
            <el-button
              v-if="canApprove && row.status === '审核中'"
              size="small"
              link
              type="warning"
              @click="openApprovalDialog(row, 'review')"
            >审核</el-button>
            <el-button
              v-if="canApprove && row.status === '审核中'"
              size="small"
              link
              type="success"
              @click="openApprovalDialog(row, 'approve')"
            >批准</el-button>
            <el-button
              v-if="canAuditForm && row.form_record_id && (row.status === '已提交' || row.status === '草稿')"
              size="small"
              link
              type="success"
              @click="openAuditDialog(row)"
            >文控审核</el-button>
            <el-button
              v-if="canAmendForm && row.form_record_id"
              size="small"
              link
              type="warning"
              @click="openAmendmentDialog(row)"
            >附加修正</el-button>
            <!-- 文控：修订记录 / 分发记录 -->
            <el-button size="small" link type="primary" @click="openChangeLogDialog(row)">修订</el-button>
            <el-button size="small" link type="primary" @click="openDistDialog(row)">分发</el-button>
            <el-button v-if="canWrite && !row.form_record_id" size="small" link type="success" @click="openNewVersionDialog(row)">新版本</el-button>
            <el-button v-if="canWrite && row.status === '草稿'" size="small" link type="warning" @click="onPublish(row)">发布</el-button>
            <el-button v-if="canWrite && row.status !== '作废'" size="small" link type="danger" @click="onDeprecate(row)">作废</el-button>
            <el-button v-if="canWrite" size="small" link type="primary" @click="openEditDialog(row)">编辑</el-button>
            <el-button v-if="canDelete" size="small" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 选择模板对话框（新建电子表单） -->
    <el-dialog v-model="tplSelectVisible" title="选择表单模板" width="820px" top="6vh" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        <template #title>
          选择一个<b>启用中</b>的作业记录模板，基于它创建一条新的电子表单记录。
        </template>
      </el-alert>
      <el-table :data="tplOptions" v-loading="tplLoading" stripe border size="small" @row-dblclick="onTplConfirm">
        <el-table-column prop="code" label="编码" width="140">
          <template #default="{ row }">{{ row.code || '-' }}</template>
        </el-table-column>
        <el-table-column label="名称" min-width="200">
          <template #default="{ row }"><b>{{ row.name }}</b></template>
        </el-table-column>
        <el-table-column label="适用机台" min-width="140">
          <template #default="{ row }">
            <span v-if="eqNameById(row.equipment_id)">{{ eqNameById(row.equipment_id) }}</span>
            <el-tag v-else size="small" type="success">通用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="字段数" width="70" align="center">
          <template #default="{ row }">{{ (row.field_schema || []).length }}</template>
        </el-table-column>
        <el-table-column label="参考模板" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.has_ref_file" size="small" type="success" effect="plain">有</el-tag>
            <span v-else style="color:#c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="onTplConfirm(row)">选择</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="tplSelectVisible = false">取消</el-button>
      </template>
    </el-dialog>

    <!-- 填写电子表单对话框（编辑已有结构化记录） -->
    <el-dialog v-model="fillDialogVisible" :title="fillForm._record ? '填写电子表单' : '基于模板新建电子表单'" width="960px" top="4vh" destroy-on-close>
      <div v-if="fillForm._template">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div>
            <el-tag type="success" size="small">模板：{{ fillForm._template.name }}</el-tag>
            <el-tag v-if="fillForm._template.code" size="small" style="margin-left:4px">{{ fillForm._template.code }}</el-tag>
            <el-tag v-if="fillForm._record" :type="recordStatusTag(fillForm._record.status)" size="small" style="margin-left:6px">{{ fillForm._record.status }}</el-tag>
            <el-tag v-else size="small" type="warning" style="margin-left:6px">新建草稿</el-tag>
          </div>
          <el-button v-if="fillForm._template.has_ref_file" size="small" type="info" plain @click="onDownloadTplRef(fillForm._template)">
            <el-icon><Download /></el-icon> 下载参考模板对照
          </el-button>
        </div>

        <el-alert
          v-if="fillForm._record && fillForm._record.status === '已提交'"
          type="info"
          :closable="false"
          style="margin-bottom:10px"
          show-icon
        >
          <template #title>该记录已提交，仍可修改填写值和元数据（修改后状态保留"已提交"）。</template>
        </el-alert>
        <el-alert
          v-else-if="fillForm._record && fillForm._record.status === '已作废'"
          type="error"
          :closable="false"
          style="margin-bottom:10px"
          show-icon
        >
          <template #title>该记录已作废，不允许编辑。</template>
        </el-alert>

        <el-form :model="fillForm.meta" label-width="100px" style="background:#f8f9fb;padding:14px;border-radius:6px;margin-bottom:12px" :disabled="fillForm._record && fillForm._record.status === '已作废'">
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
        <el-form :model="fillForm.values" label-width="140px" size="default" :disabled="fillForm._record && fillForm._record.status === '已作废'">
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
        <el-button @click="fillDialogVisible = false">关闭</el-button>
        <template v-if="!fillForm._record || fillForm._record.status !== '已作废'">
          <el-button :loading="fillSubmitting" @click="saveFill(false)">
            {{ fillForm._record ? (fillForm._record.status === '草稿' ? '保存草稿' : '保存修改') : '保存草稿' }}
          </el-button>
          <el-button
            :loading="fillSubmitting"
            type="primary"
            :disabled="fillForm._record && fillForm._record.status !== '草稿'"
            @click="saveFill(true)"
          >
            {{ fillForm._record ? '提交（仅草稿可执行）' : '保存并提交' }}
          </el-button>
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
        <el-form-item label="文控分类">
          <el-select v-model="uploadForm.doc_class" placeholder="选择分类" clearable style="width:100%" @change="onDocClassChange">
            <el-option v-for="c in docClassOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="文档编号">
          <div style="display:flex;gap:8px;width:100%">
            <el-input v-model="uploadForm.doc_no" placeholder="可点击右侧按钮按规则生成" />
            <el-button type="info" plain :disabled="!uploadForm.doc_class" :loading="generatingNo" @click="onGenerateDocNo">生成</el-button>
          </div>
          <div v-if="previewNo" class="upload-tip" style="color:var(--el-color-primary)">预览: {{ previewNo }}</div>
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
        <el-form-item v-if="activeCategory === 'guide'" label="复审周期">
          <el-input-number v-model="uploadForm.review_cycle_month" :min="0" :max="60" placeholder="月" style="width:100%" />
          <div class="upload-tip">0 或留空 = 不需要定期复审；发布时自动计算下次复审日期</div>
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
        <el-form-item label="文控分类">
          <el-select v-model="editForm.doc_class" placeholder="选择分类" clearable style="width:100%">
            <el-option v-for="c in docClassOptions" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="文档编号">
          <el-input v-model="editForm.doc_no" placeholder="体系文控编号" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="editForm.doc_type" placeholder="选择类型" clearable style="width:100%">
            <el-option v-for="t in editDocTypeOptions" :key="t" :label="docTypeLabel(t)" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editForm.category === 'guide'" label="版本号">
          <el-input v-model="editForm.version" placeholder="例如 V1.0" />
        </el-form-item>
        <el-form-item v-if="editForm.category === 'guide'" label="复审周期">
          <el-input-number v-model="editForm.review_cycle_month" :min="0" :max="60" style="width:100%" />
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
        <el-form-item v-if="statusTarget?.review_cycle_month > 0" label="复审周期">
          <span>{{ statusTarget.review_cycle_month }} 个月</span>
          <el-tag size="small" type="warning" style="margin-left:8px">发布后自动计算下次复审日期</el-tag>
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

    <!-- 审批链对话框 -->
    <el-dialog v-model="approvalDialogVisible" :title="`${stageLabelMap[approvalStage]} - ${approvalTarget?.doc_name || ''}`" width="560px" top="6vh">
      <el-alert type="info" :closable="false" style="margin-bottom:12px">
        <template #title>电子签名需二次校验密码，确保签署人身份真实性。</template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="签署阶段">
          <el-tag :type="approvalStage === 'prepare' ? 'info' : approvalStage === 'review' ? 'warning' : 'success'">{{ stageLabelMap[approvalStage] }}</el-tag>
        </el-form-item>
        <el-form-item label="签署意见" prop="comment">
          <el-input v-model="approvalForm.comment" type="textarea" :rows="3" placeholder="请输入签署意见（驳回时必填）" />
        </el-form-item>
        <el-form-item label="密码校验" prop="password">
          <el-input v-model="approvalForm.password" type="password" placeholder="请输入当前登录密码" show-password />
        </el-form-item>
      </el-form>
      <el-divider content-position="left">历史签署记录</el-divider>
      <el-timeline>
        <el-timeline-item v-for="a in approvalList" :key="a.id" :timestamp="formatTime(a.signed_at)">
          <el-card shadow="never" style="width:100%">
            <div style="display:flex;justify-content:space-between">
              <div>
                <div><b>{{ a.signer_display_name || a.signer_username }}</b> <small>({{ a.signer_role }})</small></div>
                <div>{{ a.stage === 'prepare' ? '编制提交' : a.stage === 'review' ? '审核通过' : a.stage === 'approve' ? '批准生效' : a.stage?.startsWith('reject') ? '驳回' : a.stage }}</div>
              </div>
              <div style="text-align:right">
                <div v-if="a.comment" style="font-size:13px;color:#606266">{{ a.comment }}</div>
                <div style="font-size:11px;color:#909399;margin-top:4px">签名: {{ a.signature_tail || 'N/A' }}</div>
              </div>
            </div>
          </el-card>
        </el-timeline-item>
        <el-timeline-item v-if="!approvalList.length">暂无签署记录</el-timeline-item>
      </el-timeline>
      <template #footer>
        <el-button @click="approvalDialogVisible = false">取消</el-button>
        <el-button v-if="['prepare', 'review'].includes(approvalStage)" type="danger" @click="onConfirmApproval(true)">驳回</el-button>
        <el-button type="primary" :loading="approvalLoading" @click="onConfirmApproval(false)">确认签署</el-button>
      </template>
    </el-dialog>

    <!-- 修订记录对话框 -->
    <el-dialog v-model="changeLogDialogVisible" :title="`修订记录 - ${changeLogTarget?.doc_name || ''}`" width="760px" top="6vh">
      <el-form :inline="true" :model="changeLogForm" label-width="90px" style="background:#f8f9fb;padding:12px;border-radius:6px;margin-bottom:12px">
        <el-form-item label="变更原因">
          <el-select v-model="changeLogForm.change_reason" style="width:200px">
            <el-option v-for="r in changeReasonOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="变更摘要">
          <el-input v-model="changeLogForm.change_summary" placeholder="简要说明本次变更" style="width:300px" />
        </el-form-item>
        <el-form-item label="详细项">
          <el-input v-model="changeLogForm.detail_text" type="textarea" :rows="3" placeholder="每行一条变更明细（可选）" style="width:100%" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="changeLogSaving" @click="onSaveChangeLog">新增修订记录</el-button>
        </el-form-item>
      </el-form>
      <el-divider content-position="left">历史修订记录</el-divider>
      <el-table :data="changeLogList" stripe border size="small">
        <el-table-column label="版本" width="80">
          <template #default="{ row }">{{ row.version || '-' }}</template>
        </el-table-column>
        <el-table-column label="变更原因" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ (changeReasonOptions.find(r => r.value === row.change_reason) || {}).label || row.change_reason }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="变更摘要" min-width="180">
          <template #default="{ row }">{{ row.change_summary }}</template>
        </el-table-column>
        <el-table-column label="变更人" width="90">
          <template #default="{ row }">{{ row.changed_by_username || '#' + (row.changed_by_id || '') }}</template>
        </el-table-column>
        <el-table-column label="变更日期" width="160">
          <template #default="{ row }">{{ formatTime(row.changed_at) }}</template>
        </el-table-column>
        <el-table-column label="明细" width="60" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.detail_items && row.detail_items.length" size="small" type="info">{{ row.detail_items.length }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!changeLogList.length" style="text-align:center;padding:20px;color:#909399">暂无修订记录</div>
    </el-dialog>

    <!-- 分发记录对话框 -->
    <el-dialog v-model="distDialogVisible" :title="`分发记录 - ${distTarget?.doc_name || ''}`" width="820px" top="6vh">
      <el-form :inline="true" :model="distForm" label-width="80px" style="background:#f8f9fb;padding:12px;border-radius:6px;margin-bottom:12px">
        <el-form-item label="接收类型">
          <el-select v-model="distForm.recipient_type" style="width:110px">
            <el-option v-for="r in recipientTypeOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="接收人">
          <el-input v-model="distForm.recipient_ref" placeholder="用户名/角色名/部门名" style="width:180px" />
        </el-form-item>
        <el-form-item label="份数">
          <el-input-number v-model="distForm.hold_copies" :min="1" :max="999" style="width:110px" />
        </el-form-item>
        <el-form-item label="介质">
          <el-select v-model="distForm.medium" style="width:90px">
            <el-option v-for="m in mediumOptions" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="distSaving" @click="onSaveDistribution">登记分发</el-button>
        </el-form-item>
      </el-form>
      <div style="margin-bottom:10px;display:flex;gap:8px;align-items:center">
        <el-button size="small" type="warning" :disabled="!distSelected.length" @click="() => { ElMessageBox.prompt('请输入收回备注（可选）', '批量收回', { inputType: 'textarea' }).then(r => onReturnBatch(r.value || '')).catch(() => {}) }">批量收回选中</el-button>
        <span style="color:#909399;font-size:12px">已选中 {{ distSelected.length }} 条</span>
      </div>
      <el-table :data="distList" stripe border size="small" @selection-change="v => distSelected = v.map(x => x.id)">
        <el-table-column type="selection" width="42" />
        <el-table-column label="接收类型" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ (recipientTypeOptions.find(r => r.value === row.recipient_type) || {}).label || row.recipient_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="接收方" min-width="130">
          <template #default="{ row }">{{ row.recipient_ref }}<span v-if="row.recipient_name" style="color:#909399;margin-left:4px">({{ row.recipient_name }})</span></template>
        </el-table-column>
        <el-table-column label="份数" width="60" align="center">{{ row.hold_copies }}</el-table-column>
        <el-table-column label="介质" width="70">
          <template #default="{ row }">
            <el-tag size="small" :type="row.medium === 'P' ? 'warning' : 'info'">{{ row.medium === 'P' ? '纸质' : '电子' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'DISTRIBUTED' ? 'success' : row.status === 'RETURNED' ? 'info' : 'danger'">
              {{ row.status === 'DISTRIBUTED' ? '持有中' : row.status === 'RETURNED' ? '已收回' : '已作废' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分发人" width="80">{{ row.distributed_by_username || '' }}</el-table-column>
        <el-table-column label="分发日期" width="160">
          <template #default="{ row }">{{ formatTime(row.distributed_at) }}</template>
        </el-table-column>
        <el-table-column label="收回备注" min-width="120">
          <template #default="{ row }">{{ row.return_note || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="danger" @click="onDeleteDistribution(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!distList.length" style="text-align:center;padding:20px;color:#909399">暂无分发记录</div>
    </el-dialog>

    <!-- 表单记录审核对话框 -->
    <el-dialog v-model="auditDialogVisible" title="文控审核（表单记录锁定）" width="640px" top="6vh">
      <el-alert :type="auditForm.reject ? 'error' : 'info'" :closable="false" style="margin-bottom:12px">
        <template #title>审核通过后，记录将被锁定，禁止原地修改，仅允许通过"附加修正"留痕变更。驳回将退回填写状态。</template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="审核动作">
          <el-radio-group v-model="auditForm.reject">
            <el-radio :label="false"><el-tag type="success">审核通过（锁定）</el-tag></el-radio>
            <el-radio :label="true"><el-tag type="danger">驳回（退回修改）</el-tag></el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input v-model="auditForm.comment" type="textarea" :rows="2" :placeholder="auditForm.reject ? '驳回原因必填' : '审核意见（可选）'" />
        </el-form-item>
        <el-form-item label="密码校验">
          <el-input v-model="auditForm.password" type="password" show-password placeholder="请输入登录密码进行二次校验" />
        </el-form-item>
      </el-form>
      <el-divider content-position="left">附加修正历史</el-divider>
      <el-table :data="amendmentList" stripe border size="small" max-height="220">
        <el-table-column label="字段" width="140">
          <template #default="{ row }">{{ row.field_label || row.field_key }}</template>
        </el-table-column>
        <el-table-column label="原值" min-width="120">
          <template #default="{ row }"><span style="color:#909399">{{ row.original_value || '(空)' }}</span></template>
        </el-table-column>
        <el-table-column label="修正值" min-width="120">
          <template #default="{ row }"><span style="color:var(--el-color-success)">{{ row.corrected_value || '(空)' }}</span></template>
        </el-table-column>
        <el-table-column label="原因" min-width="140">
          <template #default="{ row }">{{ row.reason }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'APPROVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'warning'">
              {{ row.status === 'APPROVED' ? '已批' : row.status === 'REJECTED' ? '已驳' : '待批' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="修正人" width="80">{{ row.amended_by_username || '' }}</el-table-column>
        <el-table-column label="操作" width="120" v-if="canAuditForm">
          <template #default="{ row }">
            <template v-if="row.status === 'PENDING'">
              <el-button size="small" link type="success" @click="onApproveAmendment(row.id, true)">批准</el-button>
              <el-button size="small" link type="danger" @click="onApproveAmendment(row.id, false)">驳回</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!amendmentList.length" style="text-align:center;padding:14px;color:#909399">暂无附加修正记录</div>
      <template #footer>
        <el-button @click="auditDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="auditLoading" @click="onConfirmAudit">确认审核</el-button>
      </template>
    </el-dialog>

    <!-- 附加修正对话框 -->
    <el-dialog v-model="amendmentDialogVisible" title="附加修正（已审核记录的留痕变更）" width="560px" top="6vh">
      <el-alert type="warning" :closable="false" style="margin-bottom:12px">
        <template #title>修正记录永久留痕，需二次密码校验，提交后需审核人批准方可生效。</template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="字段标识">
          <el-input v-model="amendmentForm.field_key" placeholder="字段key，*=综合说明" />
        </el-form-item>
        <el-form-item label="字段标签">
          <el-input v-model="amendmentForm.field_label" placeholder="字段显示名，例如：温度设定值" />
        </el-form-item>
        <el-form-item label="原值">
          <el-input v-model="amendmentForm.original_value" type="textarea" :rows="2" placeholder="修正前的值（可选）" />
        </el-form-item>
        <el-form-item label="修正值">
          <el-input v-model="amendmentForm.corrected_value" type="textarea" :rows="2" placeholder="修正后的值" />
        </el-form-item>
        <el-form-item label="修正原因" required>
          <el-input v-model="amendmentForm.reason" type="textarea" :rows="2" placeholder="必填：为什么需要修正" />
        </el-form-item>
        <el-form-item label="密码校验" required>
          <el-input v-model="amendmentForm.password" type="password" show-password placeholder="请输入登录密码进行二次校验" />
        </el-form-item>
      </el-form>
      <el-divider content-position="left">已有修正记录</el-divider>
      <el-table :data="amendmentList" stripe border size="small" max-height="200">
        <el-table-column label="字段" width="130">
          <template #default="{ row }">{{ row.field_label || row.field_key }}</template>
        </el-table-column>
        <el-table-column label="原值">{{ row.original_value || '-' }}</el-table-column>
        <el-table-column label="修正值">{{ row.corrected_value || '-' }}</el-table-column>
        <el-table-column label="状态" width="70">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'APPROVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'warning'">
              {{ row.status === 'APPROVED' ? '已批' : row.status === 'REJECTED' ? '已驳' : '待批' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!amendmentList.length" style="text-align:center;padding:12px;color:#909399">暂无附加修正记录</div>
      <template #footer>
        <el-button @click="amendmentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="amendmentSaving" @click="onSaveAmendment">提交修正留痕</el-button>
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
  approvalSign,
  listApprovals,
  createChangeLog,
  listChangeLogs,
  createDistributions,
  listDistributions,
  returnDistributionsBatch,
  deleteDistribution,
} from '@/api/process_document'
import { listEquipments } from '@/api/equipment'
import { generateDocNo, previewDocNo } from '@/api/doc_no_rules'
import {
  getFormRecord,
  getFormTemplate,
  updateFormRecord,
  submitFormRecord,
  createFormRecord,
  exportFormRecord,
  downloadTemplateRefFile,
  auditFormRecord,
  listAmendments,
  createAmendment,
  approveAmendment,
} from '@/api/form_template'
import { listFormTemplates } from '@/api/form_template'
import { useUserStore } from '@/stores'
import { formatTime } from '@/utils'

const userStore = useUserStore()
const canWrite = computed(() => userStore.can('process_doc.write'))
const canDelete = computed(() => userStore.can('process_doc.delete'))
const canFill = computed(() => userStore.can('form_record.fill'))
// 文控扩展权限
const canSubmitReview = computed(() => userStore.can('process_doc.submit_review'))
const canApprove = computed(() => userStore.can('process_doc.approve'))
const canAuditForm = computed(() => userStore.can('form_record.audit'))
const canAmendForm = computed(() => userStore.can('form_record.amend'))

// 文件类型选项（按大类区分）
const guideDocTypes = ['Recipe', 'Flowchart', 'Spec', '其他']
const recordDocTypes = ['BatchRecord', 'ParamLog', 'InspectionRecord', 'ShiftHandover', '其他']
const docTypeLabels = {
  Recipe: 'Recipe 配方', Flowchart: '流程图', Spec: '规格书',
  BatchRecord: '批次记录', ParamLog: '参数记录', InspectionRecord: '检验记录', ShiftHandover: '交接班记录',
  其他: '其他',
}
const docTypeLabel = (t) => docTypeLabels[t] || t

const statusOptions = ['草稿', '审核中', '生效', '作废']
const docStatusTag = (s) => ({ 草稿: 'info', 审核中: 'warning', 生效: 'success', 作废: 'danger', 已审核: 'success' }[s] || 'info')
const shiftTag = (s) => ({ A: 'danger', B: 'primary', C: 'warning' }[s] || 'info')

// 复审告警：是否即将到期
function isReviewDue(row) {
  if (!row.next_review_date) return false
  const d = new Date(row.next_review_date)
  const now = new Date()
  const diffDays = (d - now) / (1000 * 60 * 60 * 24)
  return diffDays <= 30
}
function reviewDueLabel(row) {
  if (!row.next_review_date) return ''
  const d = new Date(row.next_review_date)
  const now = new Date()
  const diffDays = Math.ceil((d - now) / (1000 * 60 * 60 * 24))
  if (diffDays < 0) return `已过期${-diffDays}天`
  if (diffDays === 0) return '今日到期'
  return `${diffDays}天后到期`
}

// 文控分类选项
const docClassOptions = [
  { value: 'SOP', label: 'SOP 作业指导书' },
  { value: 'SIP', label: 'SIP 检验标准' },
  { value: 'SPEC', label: 'SPEC 规格书' },
  { value: 'FORM', label: 'FORM 表单模板' },
  { value: 'RECORD', label: 'RECORD 作业记录' },
  { value: 'EXTERN', label: 'EXTERN 外来文件' },
]

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

// 设备名查找
function eqNameById(id) {
  if (!id) return null
  const eq = equipmentOptions.value.find((e) => e.id === id)
  return eq ? `${eq.name}${eq.asset_no ? ' (' + eq.asset_no + ')' : ''}` : null
}

// ---- 上传 ----
const uploadDialogVisible = ref(false)
const uploading = ref(false)
const uploadFormRef = ref(null)
const uploadForm = reactive({
  equipment_id: null, file: null, doc_name: '', doc_type: '', version: '',
  batch_no: '', shift: '', production_date: '', description: '',
  doc_no: '', doc_class: '', review_cycle_month: null,
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

// 编号生成
const generatingNo = ref(false)
const previewNo = ref('')

function openUploadDialog() {
  Object.assign(uploadForm, {
    equipment_id: null, file: null, doc_name: '', doc_type: '', version: '',
    batch_no: '', shift: '', production_date: '', description: '',
    doc_no: '', doc_class: '', review_cycle_month: null,
  })
  previewNo.value = ''
  uploadDialogVisible.value = true
}

async function onDocClassChange() {
  previewNo.value = ''
  if (!uploadForm.doc_class) return
  try {
    const res = await previewDocNo(uploadForm.doc_class, uploadForm.equipment_id)
    previewNo.value = res.doc_no
  } catch (e) {
    // 规则未配置时静默
  }
}

async function onGenerateDocNo() {
  generatingNo.value = true
  try {
    const res = await generateDocNo(uploadForm.doc_class, uploadForm.equipment_id)
    uploadForm.doc_no = res.doc_no
    ElMessage.success(`编号已生成: ${res.doc_no}`)
    previewNo.value = ''
  } catch (e) {
    ElMessage.error(e?.detail || '编号生成失败，请先在系统配置中定义编号规则')
  } finally {
    generatingNo.value = false
  }
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
    if (uploadForm.doc_no) meta.doc_no = uploadForm.doc_no
    if (uploadForm.doc_class) meta.doc_class = uploadForm.doc_class
    if (uploadForm.review_cycle_month) meta.review_cycle_month = uploadForm.review_cycle_month
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
  doc_no: '', doc_class: '', review_cycle_month: null,
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
    doc_no: row.doc_no || '',
    doc_class: row.doc_class || '',
    review_cycle_month: row.review_cycle_month ?? null,
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
      doc_no: editForm.doc_no || null,
      doc_class: editForm.doc_class || null,
    }
    if (editForm.category === 'guide') {
      payload.version = editForm.version || null
      payload.effective_date = editForm.effective_date || null
      payload.review_cycle_month = editForm.review_cycle_month ?? null
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

// ---------- 新建电子表单（选择模板 → 填写 → 创建记录） ----------
const tplSelectVisible = ref(false)
const tplOptions = ref([])
const tplLoading = ref(false)

async function openCreateFormDialog() {
  tplSelectVisible.value = true
  tplLoading.value = true
  try {
    if (!equipmentOptions.value.length) await onEquipSelectOpen(true)
    const rows = await listFormTemplates({ category: 'record', is_active: true })
    tplOptions.value = (rows || []).map((r) => { r.field_schema = r.field_schema || []; return r })
  } catch (e) {
    ElMessage.error('加载模板列表失败')
  } finally {
    tplLoading.value = false
  }
}

function onTplConfirm(tpl) {
  tplSelectVisible.value = false
  // 用选中模板初始化填写表单（新建模式：_record = null）
  fillForm._record = null
  fillForm._template = tpl
  fillForm.title = ''
  fillForm.remark = ''
  fillForm.meta = {
    equipment_id: tpl.equipment_id || null,
    batch_no: '',
    shift: '',
    production_date: '',
  }
  fillForm.values = {}
  ;(tpl.field_schema || []).forEach((f) => {
    if (f.default_value !== null && f.default_value !== undefined) {
      fillForm.values[f.key] = f.default_value
    } else if (f.type === 'boolean') {
      fillForm.values[f.key] = false
    } else {
      fillForm.values[f.key] = null
    }
  })
  fillDialogVisible.value = true
}

// ---------- 填写电子表单（编辑已有结构化记录 / 新建记录） ----------
const fillDialogVisible = ref(false)
const fillSubmitting = ref(false)
const fillForm = reactive({
  _record: null,
  _template: null,
  title: '',
  remark: '',
  meta: { equipment_id: null, batch_no: '', shift: '', production_date: '' },
  values: {},
})

async function openFillDialog(row) {
  if (!row.form_record_id) return
  // 预加载设备列表
  if (!equipmentOptions.value.length) await onEquipSelectOpen(true)
  fillDialogVisible.value = true
  fillForm._record = null
  fillForm._template = null
  try {
    const rec = await getFormRecord(row.form_record_id)
    const tpl = await getFormTemplate(rec.template_id)
    fillForm._record = rec
    fillForm._template = tpl
    fillForm.title = rec.title || ''
    fillForm.remark = rec.remark || ''
    fillForm.meta = {
      equipment_id: rec.equipment_id || null,
      batch_no: rec.batch_no || '',
      shift: rec.shift || '',
      production_date: rec.production_date ? formatTime(rec.production_date, 'YYYY-MM-DD') : '',
    }
    // 初始化字段值：先按 schema 设默认值，再用已有 values 覆盖
    fillForm.values = {}
    ;(tpl.field_schema || []).forEach((f) => {
      if (f.default_value !== null && f.default_value !== undefined) {
        fillForm.values[f.key] = f.default_value
      } else if (f.type === 'boolean') {
        fillForm.values[f.key] = false
      } else {
        fillForm.values[f.key] = null
      }
    })
    ;(rec.values || []).forEach((v) => {
      fillForm.values[v.field_key] = v.field_value
    })
  } catch (e) {
    ElMessage.error(e?.message || '加载记录失败')
    fillDialogVisible.value = false
  }
}

function onDownloadTplRef(tpl) {
  downloadTemplateRefFile(tpl.id, tpl.ref_original_name).catch((e) => {
    ElMessage.error(e?.message || '下载参考模板失败')
  })
}

async function saveFill(doSubmit) {
  if (!fillForm._template) return
  if (!fillForm.meta.equipment_id) {
    ElMessage.error('请先填写关联机台')
    return
  }
  const valuesArr = Object.keys(fillForm.values)
    .filter((k) => fillForm.values[k] !== undefined && fillForm.values[k] !== null && fillForm.values[k] !== '')
    .map((k) => ({ field_key: k, field_value: fillForm.values[k] }))
  fillSubmitting.value = true
  try {
    if (fillForm._record) {
      // 编辑已有记录
      const recordId = fillForm._record.id
      const payload = {
        equipment_id: fillForm.meta.equipment_id,
        title: fillForm.title || null,
        batch_no: fillForm.meta.batch_no || null,
        shift: fillForm.meta.shift || null,
        production_date: fillForm.meta.production_date || null,
        remark: fillForm.remark || null,
        values: valuesArr,
      }
      let rec = await updateFormRecord(recordId, payload)
      fillForm._record = rec
      if (doSubmit && rec.status === '草稿') {
        rec = await submitFormRecord(recordId)
        fillForm._record = rec
      }
      if (doSubmit) ElMessage.success(`已提交：#${rec.id} ${rec.title}`)
      else ElMessage.success(`已保存：#${rec.id} ${rec.title}`)
    } else {
      // 新建记录
      const payload = {
        template_id: fillForm._template.id,
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
      const rec = await createFormRecord(payload)
      if (doSubmit) ElMessage.success(`已提交：#${rec.id} ${rec.title}`)
      else ElMessage.success(`已保存草稿：#${rec.id} ${rec.title}`)
    }
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

// ==================== 文控：审批链对话框 ====================
const approvalDialogVisible = ref(false)
const approvalLoading = ref(false)
const approvalTarget = ref(null)
const approvalStage = ref('prepare')
const approvalForm = reactive({
  password: '',
  comment: '',
})
const approvalList = ref([])

const stageLabelMap = {
  prepare: '编制签名 / 提交审核',
  review: '审核（QA 审核）',
  approve: '批准（最终批准生效）',
}

async function openApprovalDialog(row, stage) {
  approvalTarget.value = row
  approvalStage.value = stage
  approvalForm.password = ''
  approvalForm.comment = ''
  approvalList.value = []
  approvalDialogVisible.value = true
  try {
    approvalList.value = await listApprovals(row.id)
  } catch (e) { /* 静默 */ }
}

const approvalStageOptions = [
  { value: 'prepare', label: '通过（提交审核）' },
  { value: 'review', label: '通过（审核通过）' },
  { value: 'approve', label: '通过（批准生效）' },
  { value: 'reject_prepare', label: '驳回（退回草稿）' },
  { value: 'reject_review', label: '驳回（审核退回）' },
]

async function onConfirmApproval(reject = false) {
  try {
    if (!approvalForm.password) throw new Error('请输入二次校验密码（电子签名要求）')
    approvalLoading.value = true
    let stage = approvalStage.value
    if (reject) stage = stage === 'prepare' ? 'reject_prepare' : 'reject_review'
    if (reject && !approvalForm.comment) throw new Error('驳回必须填写意见')
    await approvalSign({
      process_document_id: approvalTarget.value.id,
      stage,
      password: approvalForm.password,
      comment: approvalForm.comment || null,
    })
    ElMessage.success(reject ? '已驳回' : '电子签名成功，状态已更新')
    approvalDialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '签名失败')
  } finally {
    approvalLoading.value = false
  }
}

// ==================== 文控：修订记录对话框 ====================
const changeLogDialogVisible = ref(false)
const changeLogTarget = ref(null)
const changeLogList = ref([])
const changeLogSaving = ref(false)
const changeLogForm = reactive({
  change_reason: 'ENG_CHG',
  change_summary: '',
  detail_text: '', // 每行一条变更，前端转成 detail_items 数组
})

const changeReasonOptions = [
  { value: 'NEW', label: '新建发布' },
  { value: 'REV_VOID', label: '作废换版' },
  { value: 'REV_SPEC', label: '规格变更' },
  { value: 'REV_STEP', label: '步骤/参数修订' },
  { value: 'ENG_CHG', label: '工程变更(ECN)' },
  { value: 'QC_NC', label: '品质不符合纠正' },
  { value: 'CUSTOMER', label: '客户要求' },
]

async function openChangeLogDialog(row) {
  changeLogTarget.value = row
  changeLogForm.change_reason = 'ENG_CHG'
  changeLogForm.change_summary = ''
  changeLogForm.detail_text = ''
  changeLogList.value = []
  changeLogDialogVisible.value = true
  try {
    changeLogList.value = await listChangeLogs(row.id)
  } catch (e) { /* 静默 */ }
}

async function onSaveChangeLog() {
  try {
    if (!changeLogForm.change_summary) throw new Error('请填写变更摘要')
    changeLogSaving.value = true
    const detail_items = (changeLogForm.detail_text || '')
      .split('\n').map((s) => s.trim()).filter(Boolean)
      .map((line, idx) => ({
        seq: idx + 1,
        change_type: 'M',
        before: '',
        after: line,
        impact: '',
      }))
    await createChangeLog({
      process_document_id: changeLogTarget.value.id,
      change_reason: changeLogForm.change_reason,
      change_summary: changeLogForm.change_summary,
      detail_items: detail_items.length ? detail_items : null,
    })
    ElMessage.success('修订记录已保存')
    changeLogForm.change_summary = ''
    changeLogForm.detail_text = ''
    changeLogList.value = await listChangeLogs(changeLogTarget.value.id)
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '保存失败')
  } finally {
    changeLogSaving.value = false
  }
}

// ==================== 文控：分发记录对话框 ====================
const distDialogVisible = ref(false)
const distTarget = ref(null)
const distList = ref([])
const distSaving = ref(false)
const distForm = reactive({
  recipient_type: 'USER',
  recipient_ref: '',
  hold_copies: 1,
  medium: 'E',
})
const distSelected = ref([])

const recipientTypeOptions = [
  { value: 'USER', label: '按用户' },
  { value: 'ROLE', label: '按角色' },
  { value: 'DEPARTMENT', label: '按部门' },
]
const mediumOptions = [
  { value: 'E', label: '电子' },
  { value: 'P', label: '纸质' },
]

async function openDistDialog(row) {
  distTarget.value = row
  distForm.recipient_type = 'USER'
  distForm.recipient_ref = ''
  distForm.hold_copies = 1
  distForm.medium = 'E'
  distList.value = []
  distSelected.value = []
  distDialogVisible.value = true
  try {
    distList.value = await listDistributions(row.id)
  } catch (e) { /* 静默 */ }
}

async function onSaveDistribution() {
  try {
    if (!distForm.recipient_ref) throw new Error('请填写接收人/角色/部门')
    distSaving.value = true
    await createDistributions({
      process_document_id: distTarget.value.id,
      recipient_type: distForm.recipient_type,
      recipient_ref: distForm.recipient_ref,
      hold_copies: distForm.hold_copies,
      medium: distForm.medium,
    })
    ElMessage.success('分发已登记')
    distForm.recipient_ref = ''
    distSelected.value = []
    distList.value = await listDistributions(distTarget.value.id)
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '保存失败')
  } finally {
    distSaving.value = false
  }
}

async function onReturnBatch(note = '') {
  try {
    if (!distSelected.value.length) throw new Error('请勾选要收回的分发记录')
    await returnDistributionsBatch({ ids: distSelected.value, return_note: note })
    ElMessage.success('已收回选中的分发文件')
    distSelected.value = []
    distList.value = await listDistributions(distTarget.value.id)
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '收回失败')
  }
}

async function onDeleteDistribution(id) {
  try {
    await ElMessageBox.confirm('确认删除该条分发明细？', '确认', { type: 'warning' })
    await deleteDistribution(id)
    distList.value = await listDistributions(distTarget.value.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.detail || e?.message || '删除失败')
  }
}

// ==================== 文控：表单记录审核锁定 + 附加修正 ====================
const auditDialogVisible = ref(false)
const auditLoading = ref(false)
const auditTarget = ref(null)
const auditForm = reactive({ password: '', comment: '', reject: false })
const amendmentList = ref([])
const amendmentDialogVisible = ref(false)
const amendmentSaving = ref(false)
const amendmentForm = reactive({
  field_key: '*',
  field_label: '',
  original_value: '',
  corrected_value: '',
  reason: '',
  password: '',
})

async function openAuditDialog(row) {
  if (!row.form_record_id) return
  auditTarget.value = { form_record_id: row.form_record_id }
  auditForm.password = ''
  auditForm.comment = ''
  auditForm.reject = false
  amendmentList.value = []
  auditDialogVisible.value = true
  try {
    amendmentList.value = await listAmendments(row.form_record_id)
  } catch (e) { /* 静默 */ }
}

async function onConfirmAudit() {
  try {
    if (!auditForm.password) throw new Error('请输入二次校验密码')
    auditLoading.value = true
    await auditFormRecord({
      record_id: auditTarget.value.form_record_id,
      password: auditForm.password,
      comment: auditForm.comment || null,
      reject: !!auditForm.reject,
    })
    ElMessage.success(auditForm.reject ? '已驳回' : '审核通过，记录已锁定')
    auditDialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '审核失败')
  } finally {
    auditLoading.value = false
  }
}

async function openAmendmentDialog(row) {
  if (!row.form_record_id) return
  auditTarget.value = { form_record_id: row.form_record_id }
  amendmentForm.field_key = '*'
  amendmentForm.field_label = '附加说明'
  amendmentForm.original_value = ''
  amendmentForm.corrected_value = ''
  amendmentForm.reason = ''
  amendmentForm.password = ''
  amendmentList.value = []
  amendmentDialogVisible.value = true
  try {
    amendmentList.value = await listAmendments(row.form_record_id)
  } catch (e) { /* 静默 */ }
}

async function onSaveAmendment() {
  try {
    if (!amendmentForm.reason) throw new Error('请填写修正原因')
    if (!amendmentForm.password) throw new Error('请输入二次校验密码')
    amendmentSaving.value = true
    await createAmendment({
      record_id: auditTarget.value.form_record_id,
      field_key: amendmentForm.field_key,
      field_label: amendmentForm.field_label || null,
      original_value: amendmentForm.original_value || null,
      corrected_value: amendmentForm.corrected_value || null,
      reason: amendmentForm.reason,
      password: amendmentForm.password,
    })
    ElMessage.success('附加修正已留痕')
    amendmentForm.reason = ''
    amendmentForm.password = ''
    amendmentList.value = await listAmendments(auditTarget.value.form_record_id)
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '修正失败')
  } finally {
    amendmentSaving.value = false
  }
}

async function onApproveAmendment(id, approve) {
  try {
    await approveAmendment(id, approve)
    ElMessage.success(approve ? '已批准修正' : '已驳回修正')
    amendmentList.value = await listAmendments(auditTarget.value.form_record_id)
  } catch (e) {
    ElMessage.error(e?.detail || e?.message || '操作失败')
  }
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
