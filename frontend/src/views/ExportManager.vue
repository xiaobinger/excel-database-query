<template>
  <div class="script-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-file-export"></i> 导出选项管理</span>
          <div class="header-actions">
            <el-select
              v-model="tagFilter"
              placeholder="标签筛选"
              clearable
              style="width: 160px; margin-right: 12px"
              @change="filterByTag"
            >
              <el-option v-for="tag in tags" :key="tag" :label="tag" :value="tag" />
            </el-select>
            <el-button v-if="store.hasButtonPermission('export:create')" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建导出选项
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="filteredScripts" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="选项名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="tag" label="标签" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.tag" size="small" effect="plain">{{ row.tag }}</el-tag>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="参数数量" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ getParamCount(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SQL模板" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_template" type="warning" size="small">动态</el-tag>
            <el-tag v-else type="info" size="small">静态</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="timeout" label="超时(秒)" width="100" align="center" />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="280" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="store.hasButtonPermission('export:edit')" size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-button size="small" type="success" text @click="handleValidate(row)">
              <i class="fas fa-check-circle"></i> 验证
            </el-button>
            <el-popconfirm
              v-if="store.hasButtonPermission('export:delete')"
              title="确定要删除此导出选项吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" text>
                  <i class="fas fa-trash"></i> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && filteredScripts.length === 0" description="暂无导出选项" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑导出选项' : '新建导出选项'"
      width="90%"
      destroy-on-close
      :close-on-click-modal="false"
      top="3vh"
      class="script-dialog"
    >
      <div class="editor-container">
        <div class="editor-main">
          <!-- 模板开关 -->
          <div class="template-toggle-bar">
            <el-switch
              v-model="form.is_template"
              active-text="SQL模板模式"
              inactive-text="静态SQL模式"
              style="margin-right: 12px"
            />
            <el-button
              v-if="form.is_template"
              size="small"
              type="primary"
              plain
              @click="previewTemplate"
              :loading="previewing"
            >
              <i class="fas fa-eye"></i> 预览渲染结果
            </el-button>
            <el-tag v-if="form.is_template" size="small" type="info" style="margin-left: 8px">
              使用 Jinja2 语法，支持 {% for %} 循环、<span v-pre>{{ var }}</span> 变量等
            </el-tag>
          </div>

          <!-- 静态SQL编辑器 -->
          <template v-if="!form.is_template">
            <div class="section-label" style="margin-top: 8px">
              <i class="fas fa-code"></i> SQL 语句
            </div>
            <div class="sql-editor-wrap">
              <sql-editor v-model="form.sql_text" height="100%" />
            </div>
          </template>

          <!-- 模板SQL编辑器 -->
          <template v-else>
            <div class="template-editor-area">
              <div class="section-label" style="margin-top: 8px">
                <i class="fas fa-magic"></i> SQL 模板
                <span style="font-weight: 400; font-size: 11px; color: #909399; margin-left: 8px" v-pre>
                  例: {% for m in months %} SELECT * FROM table_{{ m }} {% if not loop.last %} UNION ALL {% endif %} {% endfor %}
                </span>
              </div>
              <div class="sql-editor-wrap">
                <sql-editor v-model="form.sql_template" height="100%" />
              </div>
            </div>

            <!-- 模板渲染预览 -->
            <div v-if="renderedPreview" class="preview-area">
              <div class="section-label">
                <i class="fas fa-eye"></i> 渲染预览
                <el-button size="small" text type="danger" @click="renderedPreview = ''" style="margin-left: auto">
                  <i class="fas fa-times"></i> 关闭
                </el-button>
              </div>
              <pre class="preview-sql">{{ renderedPreview }}</pre>
            </div>
          </template>
        </div>

        <div class="editor-sidebar">
          <div class="sidebar-section">
            <div class="section-label">
              <i class="fas fa-info-circle"></i> 基本信息
            </div>
            <el-form
              ref="formRef"
              :model="form"
              :rules="rules"
              label-position="top"
              class="sidebar-form"
            >
              <el-form-item label="选项名称" prop="name">
                <el-input v-model="form.name" placeholder="请输入选项名称" />
              </el-form-item>

              <div class="form-row">
                <el-form-item label="标签" class="form-row-item">
                  <el-input v-model="form.tag" placeholder="请输入标签" clearable />
                </el-form-item>
                <el-form-item label="超时(秒)" class="form-row-item">
                  <el-input-number v-model="form.timeout" :min="10" :max="3600" style="width: 100%" controls-position="right" />
                </el-form-item>
              </div>

              <el-form-item label="描述">
                <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述此导出选项" />
              </el-form-item>

              <el-form-item label="结果Sheet名">
                <el-input v-model="form.result_sheet_name" placeholder="结果Sheet" />
              </el-form-item>
            </el-form>
          </div>

          <!-- 模板变量配置 -->
          <div v-if="form.is_template" class="sidebar-section">
            <div class="section-label">
              <i class="fas fa-sliders-h"></i> 模板变量
              <el-button size="small" type="primary" text @click="addTemplateVar" style="margin-left: auto">
                <i class="fas fa-plus"></i> 添加
              </el-button>
            </div>
            <div v-if="templateVars.length === 0" class="empty-vars">
              暂无变量，点击"添加"配置模板变量
            </div>
            <div v-for="(v, idx) in templateVars" :key="idx" class="var-config-item">
              <div class="var-config-header">
                <el-tag size="small" :type="getVarTypeTag(v.type)">{{ v.type }}</el-tag>
                <span class="var-config-name">{{ v.name || '未命名' }}</span>
                <el-button size="small" text type="danger" @click="removeTemplateVar(idx)">
                  <i class="fas fa-trash"></i>
                </el-button>
              </div>
              <div class="var-config-body">
                <div class="form-row">
                  <el-input v-model="v.name" placeholder="变量名" size="small" class="form-row-item" />
                  <el-input v-model="v.label" placeholder="显示名称" size="small" class="form-row-item" />
                </div>
                <el-select v-model="v.type" placeholder="变量类型" size="small" style="width: 100%; margin-bottom: 8px">
                  <el-option value="date_range" label="日期范围 (生成列表)" />
                  <el-option value="date" label="日期" />
                  <el-option value="text" label="文本" />
                  <el-option value="number" label="数字" />
                </el-select>

                <!-- date_range 配置 -->
                <template v-if="v.type === 'date_range'">
                  <div class="form-row">
                    <el-select v-model="v.config.period" size="small" class="form-row-item" placeholder="周期">
                      <el-option value="month" label="按月" />
                      <el-option value="year" label="按年" />
                      <el-option value="day" label="按天" />
                    </el-select>
                    <el-input-number v-model="v.config.count" :min="1" :max="120" size="small" class="form-row-item" controls-position="right" placeholder="数量" />
                  </div>
                  <div class="form-row">
                    <el-select v-model="v.config.direction" size="small" class="form-row-item" placeholder="方向">
                      <el-option value="past" label="过去" />
                      <el-option value="future" label="未来" />
                    </el-select>
                    <el-input v-model="v.config.format" size="small" class="form-row-item" placeholder="格式 如 %Y%m" />
                  </div>
                  <el-input-number v-model="v.config.offset" :min="0" :max="12" size="small" style="width: 100%" controls-position="right" placeholder="偏移(0=含当月,1=从上月)" />
                </template>

                <!-- date 配置 -->
                <template v-if="v.type === 'date'">
                  <div class="form-row">
                    <el-select v-model="v.config.default" size="small" class="form-row-item" placeholder="默认值">
                      <el-option value="today" label="今天" />
                      <el-option value="now" label="现在" />
                      <el-option value="yesterday" label="昨天" />
                      <el-option value="first_day_of_month" label="月初" />
                      <el-option value="last_day_of_month" label="月末" />
                    </el-select>
                    <el-input v-model="v.config.format" size="small" class="form-row-item" placeholder="格式 如 %Y-%m-%d" />
                  </div>
                </template>

                <!-- text 配置 -->
                <template v-if="v.type === 'text'">
                  <el-input v-model="v.config.default" size="small" placeholder="默认值" />
                </template>

                <!-- number 配置 -->
                <template v-if="v.type === 'number'">
                  <el-input-number v-model="v.config.default" size="small" style="width: 100%" controls-position="right" />
                </template>
              </div>
            </div>
          </div>

          <!-- 导出参数配置（非模板模式） -->
          <div v-if="!form.is_template" class="sidebar-section">
            <div class="section-label">
              <i class="fas fa-sliders-h"></i> 参数配置
            </div>
            <div class="params-list">
              <div v-for="(param, index) in form.params_config" :key="index" class="param-item">
                <div class="param-row">
                  <el-input v-model="param.name" placeholder="参数名" size="small" style="flex: 1" />
                  <el-input v-model="param.label" placeholder="显示标签" size="small" style="flex: 1" />
                  <el-select v-model="param.type" placeholder="类型" size="small" style="width: 110px" @change="onParamTypeChange(param)">
                    <el-option value="text" label="文本" />
                    <el-option value="date" label="日期" />
                    <el-option value="datetime" label="日期时间" />
                  </el-select>
                  <el-checkbox v-model="param.required" size="small" label="必填" style="margin-left: 4px" />
                  <el-button size="small" type="danger" text @click="removeParam(index)">
                    <i class="fas fa-times"></i>
                  </el-button>
                </div>
                <div v-if="param.type === 'text'" class="param-row param-row-sub">
                  <el-checkbox v-model="param.multi" size="small" label="IN参数（支持多个值）" />
                </div>
                <div v-if="param.type === 'date' || param.type === 'datetime'" class="param-row param-row-sub">
                  <el-select v-model="param.date_format" placeholder="日期格式" size="small" style="width: 140px">
                    <el-option value="year" label="年" />
                    <el-option value="month" label="年-月" />
                    <el-option value="day" label="年-月-日" />
                    <el-option value="datetime" label="年-月-日 时:分" />
                  </el-select>
                  <el-checkbox v-model="param.range" size="small" label="范围" style="margin-left: 8px" />
                </div>
                <div class="param-row param-row-sub">
                  <el-input v-model="param.default_value" :placeholder="param.multi ? '默认值（多个以逗号分隔）' : '默认值（可选）'" size="small" style="flex: 1" />
                </div>
              </div>
              <el-button type="primary" text size="small" @click="addParam" style="width: 100%">
                <i class="fas fa-plus"></i> 添加参数
              </el-button>
            </div>
          </div>

          <div class="sidebar-section">
            <div class="section-label">
              <i class="fas fa-database"></i> 目标数据库
            </div>
            <el-form
              :model="form"
              label-position="top"
              class="sidebar-form"
            >
              <el-form-item>
                <el-select
                  v-model="form.database_ids"
                  multiple
                  placeholder="选择目标数据库（可多选）"
                  style="width: 100%"
                >
                  <el-option
                    v-for="db in store.databases"
                    :key="db.id"
                    :label="db.name"
                    :value="db.id"
                  />
                </el-select>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            <i class="fas fa-check"></i> {{ isEdit ? '保存修改' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage } from 'element-plus'
import SqlEditor from '../components/SqlEditor.vue'

const store = useAppStore()
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const scriptList = ref([])
const tags = ref([])
const tagFilter = ref('')
const previewing = ref(false)
const renderedPreview = ref('')

const defaultForm = {
  name: '',
  description: '',
  sql_text: '',
  sql_template: '',
  is_template: false,
  template_config: [],
  tag: '',
  timeout: 300,
  result_sheet_name: '',
  database_ids: [],
  params_config: []
}

const form = reactive({ ...defaultForm, params_config: [] })
const templateVars = ref([])

const rules = {
  name: [{ required: true, message: '请输入选项名称', trigger: 'blur' }],
  sql_text: [{ required: true, message: '请输入SQL语句', trigger: 'blur' }]
}

const filteredScripts = computed(() => {
  if (!tagFilter.value) return scriptList.value
  return scriptList.value.filter((s) => s.tag === tagFilter.value)
})

function filterByTag() {}

function getParamCount(row) {
  if (!row.params_config) return 0
  try {
    const config = typeof row.params_config === 'string' ? JSON.parse(row.params_config) : row.params_config
    return Array.isArray(config) ? config.length : 0
  } catch {
    return 0
  }
}

function getVarTypeTag(type) {
  const map = { date_range: 'warning', date: 'success', text: '', number: 'info' }
  return map[type] || ''
}

function addTemplateVar() {
  templateVars.value.push({
    name: '',
    label: '',
    type: 'date_range',
    config: {
      period: 'month',
      count: 12,
      direction: 'past',
      format: '%Y%m',
      offset: 0,
      default: 'today',
    }
  })
}

function removeTemplateVar(idx) {
  templateVars.value.splice(idx, 1)
}

async function previewTemplate() {
  if (!form.sql_template || !form.sql_template.trim()) {
    ElMessage.warning('请先输入SQL模板')
    return
  }
  previewing.value = true
  try {
    const res = await api.scripts.renderTemplate({
      template: form.sql_template,
      template_config: templateVars.value
    })
    if (res.success) {
      renderedPreview.value = res.rendered_sql || ''
      ElMessage.success('渲染成功')
    } else {
      ElMessage.error(res.message || '渲染失败')
    }
  } catch (e) {
    ElMessage.error('渲染失败: ' + (e?.response?.data?.message || e.message || '未知错误'))
  } finally {
    previewing.value = false
  }
}

function addParam() {
  form.params_config.push({
    name: '',
    label: '',
    type: 'text',
    date_format: 'day',
    required: false,
    multi: false,
    range: false,
    default_value: ''
  })
}

function removeParam(index) {
  form.params_config.splice(index, 1)
}

function onParamTypeChange(param) {
  if (param.type === 'date' || param.type === 'datetime') {
    if (!param.date_format) {
      param.date_format = 'day'
    }
  } else {
    param.date_format = ''
  }
}

async function fetchList() {
  loading.value = true
  try {
    const res = await api.scripts.list({ type: 'export' })
    scriptList.value = res.data || res || []
  } catch {
    scriptList.value = []
  } finally {
    loading.value = false
  }
}

async function fetchTags() {
  try {
    const res = await api.scripts.getTags()
    tags.value = res.data || res || []
  } catch {
    tags.value = []
  }
}

function openDialog(row) {
  renderedPreview.value = ''
  if (row) {
    isEdit.value = true
    editId.value = row.id
    let paramsConfig = []
    if (row.params_config) {
      try {
        paramsConfig = typeof row.params_config === 'string' ? JSON.parse(row.params_config) : row.params_config
        if (!Array.isArray(paramsConfig)) paramsConfig = []
      } catch {
        paramsConfig = []
      }
    }
    Object.assign(form, { ...defaultForm, ...row, params_config: paramsConfig.map(p => ({ ...p })) })
    // 加载模板变量配置
    templateVars.value = (row.template_config || []).map(v => ({
      ...v,
      config: {
        period: 'month',
        count: 12,
        direction: 'past',
        format: '%Y%m',
        offset: 0,
        default: 'today',
        ...v.config
      }
    }))
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm, params_config: [] })
    templateVars.value = []
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      ...form,
      type: 'export',
      params_config: form.params_config
    }
    // 模板模式时设置template_config
    if (payload.is_template) {
      payload.template_config = templateVars.value
      // 模板模式下sql_text也保存一份渲染后的预览SQL
      if (!payload.sql_text && payload.sql_template) {
        try {
          const res = await api.scripts.renderTemplate({
            template: payload.sql_template,
            template_config: payload.template_config
          })
          if (res.success) {
            payload.sql_text = res.rendered_sql
          }
        } catch {}
      }
    }
    if (isEdit.value) {
      await api.scripts.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.scripts.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
    store.fetchScripts()
  } catch {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await api.scripts.delete(id)
    ElMessage.success('删除成功')
    fetchList()
    store.fetchScripts()
  } catch {
  }
}

async function handleValidate(row) {
  try {
    ElMessage.info('正在验证导出选项...')
    const res = await api.scripts.validate(row.id)
    if (res.valid || res.data?.valid) {
      ElMessage.success('验证通过')
    } else {
      ElMessage.error(res.message || res.error || '验证失败')
    }
  } catch {
  }
}

onMounted(() => {
  fetchList()
  fetchTags()
  store.fetchDatabases()
  store.fetchScripts()
})
</script>

<style scoped>
.script-manager {
  max-width: 1400px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
}

.card-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.header-actions {
  display: flex;
  align-items: center;
}

.editor-container {
  display: flex;
  gap: 24px;
  height: calc(88vh - 130px);
  min-height: 500px;
}

.editor-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.template-toggle-bar {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 4px;
}

.sql-editor-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.sql-editor-wrap :deep(.sql-editor) {
  flex: 1;
  min-height: 0;
}

.template-editor-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.preview-area {
  border-top: 1px solid #ebeef5;
  margin-top: 8px;
  flex-shrink: 0;
}

.preview-sql {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px 16px;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.editor-sidebar {
  width: 380px;
  flex-shrink: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.editor-sidebar::-webkit-scrollbar {
  width: 4px;
}

.editor-sidebar::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 2px;
}

.sidebar-section {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 14px;
  transition: box-shadow 0.2s;
}

.sidebar-section:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.sidebar-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-label i {
  color: var(--primary-color, #409eff);
  font-size: 13px;
}

.sidebar-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.sidebar-form :deep(.el-form-item__label) {
  font-size: 12px;
  color: #606266;
  padding-bottom: 4px;
  font-weight: 500;
}

.sidebar-form :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.form-row {
  display: flex;
  gap: 12px;
}

.form-row-item {
  flex: 1;
  min-width: 0;
}

.params-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-item {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-row-sub {
  margin-top: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.empty-vars {
  font-size: 12px;
  color: #909399;
  text-align: center;
  padding: 12px 0;
}

.var-config-item {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.var-config-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.var-config-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  flex: 1;
}

.var-config-body {
  padding-left: 2px;
}
</style>
