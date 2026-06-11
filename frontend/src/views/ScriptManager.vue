<template>
  <div class="script-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-clipboard-list"></i> 脚本管理</span>
          <div class="header-actions">
            <el-select
              v-model="typeFilter"
              placeholder="类型筛选"
              clearable
              style="width: 140px; margin-right: 12px"
              @change="filterByType"
            >
              <el-option value="query" label="查询选项" />
              <el-option value="export" label="导出选项" />
              <el-option value="system" label="系统脚本" />
            </el-select>
            <el-select
              v-model="tagFilter"
              placeholder="标签筛选"
              clearable
              style="width: 160px; margin-right: 12px"
              @change="filterByTag"
            >
              <el-option v-for="tag in tags" :key="tag" :label="tag" :value="tag" />
            </el-select>
            <el-button v-if="store.hasButtonPermission('script:create')" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建脚本
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="filteredScripts" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="脚本名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" size="small">
              {{ typeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="参数数量" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ getParamCount(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tag" label="标签" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.tag" size="small" effect="plain">{{ row.tag }}</el-tag>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column v-if="showQueryColumns" prop="query_mode" label="查询模式" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.query_mode === 'in' ? 'primary' : 'success'" size="small">
              {{ row.query_mode === 'in' ? '批量' : '逐行' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="SQL模板" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_template" type="warning" size="small">动态</el-tag>
            <el-tag v-else type="info" size="small">静态</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="showQueryColumns" prop="batch_size" label="批量大小" width="100" align="center" />
        <el-table-column prop="timeout" label="超时(秒)" width="100" align="center" />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="280" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="store.hasButtonPermission('script:edit')" size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-button size="small" type="success" text @click="handleValidate(row)">
              <i class="fas fa-check-circle"></i> 验证
            </el-button>
            <el-popconfirm
              v-if="store.hasButtonPermission('script:delete')"
              :title="`确定要删除此${typeLabel(row.type)}吗？`"
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
      <el-empty v-if="!loading && filteredScripts.length === 0" :description="`暂无${typeLabel(typeFilter || 'query')}脚本`" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑脚本' : '新建脚本'"
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
              <el-form-item label="脚本名称" prop="name">
                <el-input v-model="form.name" placeholder="请输入脚本名称" />
              </el-form-item>

              <div class="form-row">
                <el-form-item label="脚本类型" prop="type" class="form-row-item">
                  <el-select v-model="form.type" style="width: 100%">
                    <el-option value="query" label="查询选项" />
                    <el-option value="export" label="导出选项" />
                    <el-option value="system" label="系统脚本" />
                  </el-select>
                </el-form-item>
                <el-form-item label="标签" class="form-row-item">
                  <el-input v-model="form.tag" placeholder="请输入标签" clearable />
                </el-form-item>
              </div>

              <div v-if="form.type !== 'system'" class="form-row">
                <el-form-item label="查询模式" prop="query_mode" class="form-row-item">
                  <el-select v-model="form.query_mode" style="width: 100%">
                    <el-option value="in" label="批量模式" />
                    <el-option value="batch" label="逐行模式" />
                  </el-select>
                </el-form-item>
              </div>

              <el-form-item label="描述">
                <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述此查询选项" />
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

          <div v-if="form.type === 'export' || form.type === 'system'" class="sidebar-section">
            <div class="section-label">
              <i class="fas fa-sliders-h"></i> 参数配置
              <el-button size="small" type="primary" text @click="addParam" style="margin-left: auto">
                <i class="fas fa-plus"></i> 添加
              </el-button>
            </div>
            <div v-if="!form.params_config || form.params_config.length === 0" class="empty-vars">
              暂无参数，点击"添加"配置参数
            </div>

            <!-- Export type: rich UI matching ExportManager -->
            <div v-if="form.type === 'export'" class="params-list">
              <div v-for="(param, index) in form.params_config" :key="index" class="param-item">
                <div class="param-row">
                  <el-input v-model="param.name" placeholder="参数名" size="small" style="flex: 1" />
                  <el-input v-model="param.label" placeholder="显示标签" size="small" style="flex: 1" />
                  <el-select v-model="param.type" placeholder="类型" size="small" style="width: 110px" @change="onParamTypeChange(param)">
                    <el-option value="text" label="文本" />
                    <el-option value="number" label="数字" />
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
                <div v-if="param.type === 'text' || param.type === 'number'" class="param-row param-row-sub">
                  <el-checkbox v-model="param.allow_all" size="small" class="allow-all-checkbox">
                    <span class="allow-all-label">允许「全部」选项（不筛选此参数）</span>
                  </el-checkbox>
                </div>
                <div v-if="param.type === 'text' || param.type === 'number'" class="param-row param-row-sub param-enum-section">
                  <el-checkbox v-model="param.enum_enabled" size="default" label="启用枚举参数" class="enum-enable-checkbox" />
                  <template v-if="param.enum_enabled">
                    <div class="enum-mode-selector">
                      <el-radio-group v-model="param.enum_mode" size="default">
                        <el-radio-button value="list">
                          <i class="fas fa-list-ul"></i> 列表选择
                        </el-radio-button>
                        <el-radio-button value="neq">
                          <i class="fas fa-not-equal"></i> 非即不等于
                        </el-radio-button>
                      </el-radio-group>
                    </div>
                    <div v-if="param.enum_mode === 'list'" class="enum-list-config">
                      <div class="enum-list-header">
                        <span class="enum-list-title">枚举值列表</span>
                        <el-button size="small" type="primary" @click="(param.enum_values = param.enum_values || []).push({ label: '', value: '' })">
                          <i class="fas fa-plus"></i> 添加
                        </el-button>
                      </div>
                      <div v-if="!param.enum_values || param.enum_values.length === 0" class="enum-empty-tip">
                        暂无枚举值，请点击上方"添加"按钮
                      </div>
                      <div v-for="(item, idx) in (param.enum_values || [])" :key="idx" class="enum-value-row">
                        <span class="enum-value-index">{{ idx + 1 }}</span>
                        <el-input v-model="item.label" placeholder="显示名称" size="small" class="enum-input-label" />
                        <span class="enum-value-separator">→</span>
                        <el-input v-model="item.value" placeholder="实际值" size="small" class="enum-input-value" />
                        <el-button size="small" type="danger" text @click="param.enum_values.splice(idx, 1)" class="enum-value-remove">
                          <i class="fas fa-trash"></i>
                        </el-button>
                      </div>
                    </div>
                    <div v-if="param.enum_mode === 'neq'" class="enum-neq-config">
                      <div class="neq-config-row">
                        <span class="neq-config-label">预设值：</span>
                        <el-input v-model="param.neq_value" placeholder="等于时的值（如：1）" size="small" class="neq-input" />
                      </div>
                      <div class="neq-config-row">
                        <el-checkbox v-model="param.default_checked" size="small">
                          默认勾选「是」
                        </el-checkbox>
                      </div>
                      <div class="neq-hint">
                        <i class="fas fa-info-circle"></i>
                        勾选「是」时：字段 = 预设值 ｜ 勾选「否」时：字段 != 预设值
                      </div>
                    </div>
                  </template>
                </div>
                <div v-if="param.type === 'date' || param.type === 'datetime'" class="param-row param-row-sub">
                  <el-select v-model="param.date_format" placeholder="日期格式" size="small" style="width: 140px">
                    <el-option value="year" label="年" />
                    <el-option value="month" label="年-月" />
                    <el-option value="day" label="年-月-日" />
                    <el-option value="datetime" label="年-月-日 时:分" />
                  </el-select>
                  <el-checkbox v-model="param.range" size="small" label="范围" style="margin-left: 8px" />
                  <el-checkbox v-model="param.allow_all" size="small" label="允许全部（不筛选）" style="margin-left: 8px" />
                </div>
                <div class="param-row param-row-sub">
                  <el-input v-model="param.default_value" :placeholder="param.multi ? '默认值（多个以逗号分隔）' : '默认值（可选）'" size="small" style="flex: 1" />
                </div>
              </div>
              <el-button type="primary" text size="small" @click="addParam" style="width: 100%">
                <i class="fas fa-plus"></i> 添加参数
              </el-button>
            </div>

            <!-- System type: simple UI -->
            <div v-if="form.type === 'system'" v-for="(param, idx) in form.params_config" :key="idx" class="var-config-item">
              <div class="var-config-header">
                <el-input v-model="param.name" placeholder="参数名" size="small" style="width: 120px" />
                <el-input v-model="param.label" placeholder="显示名称" size="small" style="width: 120px" />
                <el-select v-model="param.type" placeholder="类型" size="small" style="width: 90px">
                  <el-option value="text" label="文本" />
                  <el-option value="number" label="数字" />
                  <el-option value="textarea" label="多行文本" />
                  <el-option value="date" label="日期" />
                </el-select>
                <el-button size="small" text type="danger" @click="removeParam(idx)">
                  <i class="fas fa-trash"></i>
                </el-button>
              </div>
            </div>
          </div>

          <div v-if="form.type !== 'system'" class="sidebar-section">
            <div class="section-label">
              <i class="fas fa-cog"></i> 执行参数
            </div>
            <el-form
              :model="form"
              label-position="top"
              class="sidebar-form"
            >
              <div class="form-row">
                <el-form-item label="批量大小" class="form-row-item">
                  <el-input-number v-model="form.batch_size" :min="1" :max="10000" style="width: 100%" controls-position="right" />
                </el-form-item>
                <el-form-item label="超时(秒)" class="form-row-item">
                  <el-input-number v-model="form.timeout" :min="10" :max="3600" style="width: 100%" controls-position="right" />
                </el-form-item>
              </div>

              <el-form-item label="结果Sheet名">
                <el-input v-model="form.result_sheet_name" placeholder="结果Sheet" />
              </el-form-item>

              <div class="form-row">
                <el-form-item label="合并策略" class="form-row-item">
                  <el-select v-model="form.merge_strategy" style="width: 100%">
                    <el-option value="concat" label="合并 (Concat)" />
                    <el-option value="separate" label="分列 (Separate)" />
                  </el-select>
                </el-form-item>
                <el-form-item label="新建Sheet" class="form-row-item">
                  <el-switch v-model="form.new_sheet" active-text="是" inactive-text="否" style="margin-top: 6px" />
                </el-form-item>
              </div>

              <el-form-item v-if="!form.new_sheet" label="主键字段">
                <el-select v-model="form.primary_key" placeholder="选择主键字段" clearable style="width: 100%">
                  <el-option v-for="f in sqlFields" :key="f" :label="f" :value="f" />
                </el-select>
                <div class="field-hint">用于匹配Excel行，将查询结果回写到对应行</div>
              </el-form-item>
            </el-form>
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
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage } from 'element-plus'
import SqlEditor from '../components/SqlEditor.vue'

const store = useAppStore()
const route = useRoute()
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const scriptList = ref([])
const tags = ref([])
const tagFilter = ref('')
const typeFilter = ref('')
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
  type: 'query',
  query_mode: 'in',
  batch_size: 100,
  timeout: 300,
  result_sheet_name: '',
  merge_strategy: 'concat',
  new_sheet: true,
  primary_key: '',
  database_ids: [],
  params_config: []
}

const form = reactive({ ...defaultForm })
const templateVars = ref([])

const sqlFields = ref([])
let sqlFieldsTimer = null

// 监听SQL文本变化提取字段
watch(() => form.sql_text, (val) => {
  if (form.is_template) return
  if (sqlFieldsTimer) clearTimeout(sqlFieldsTimer)
  if (!val || !val.trim()) {
    sqlFields.value = []
    return
  }
  sqlFieldsTimer = setTimeout(async () => {
    try {
      const res = await api.scripts.extractColumns({ sql: val })
      sqlFields.value = res.columns || []
    } catch {
      sqlFields.value = []
    }
  }, 500)
}, { immediate: false })

// 监听模板SQL变化提取字段
watch(() => form.sql_template, (val) => {
  if (!form.is_template) return
  if (sqlFieldsTimer) clearTimeout(sqlFieldsTimer)
  if (!val || !val.trim()) {
    sqlFields.value = []
    return
  }
  sqlFieldsTimer = setTimeout(async () => {
    try {
      // 对模板先尝试渲染再提取字段
      const res = await api.scripts.renderTemplate({
        template: val,
        template_config: templateVars.value
      })
      if (res.success && res.rendered_sql) {
        const colRes = await api.scripts.extractColumns({ sql: res.rendered_sql })
        sqlFields.value = colRes.columns || []
      }
    } catch {
      sqlFields.value = []
    }
  }, 800)
}, { immediate: false })

const rules = {
  name: [{ required: true, message: '请输入选项名称', trigger: 'blur' }],
  sql_text: [{ required: true, message: '请输入SQL语句', trigger: 'blur' }],
  query_mode: [{ required: true, message: '请选择查询模式', trigger: 'change' }]
}

const filteredScripts = computed(() => {
  let list = scriptList.value
  if (tagFilter.value) {
    list = list.filter((s) => s.tag === tagFilter.value)
  }
  return list
})

const showQueryColumns = computed(() => {
  return !typeFilter.value || typeFilter.value !== 'system'
})

function typeTag(type) {
  const map = { query: 'primary', export: 'success', system: 'warning' }
  return map[type] || 'info'
}

function getParamCount(row) {
  if (!row.params_config) return 0
  try {
    const config = typeof row.params_config === 'string' ? JSON.parse(row.params_config) : row.params_config
    return Array.isArray(config) ? config.length : 0
  } catch {
    return 0
  }
}

function typeLabel(type) {
  const map = { query: '查询选项', export: '导出选项', system: '系统脚本' }
  return map[type] || '脚本'
}

function filterByTag() {}
function filterByType() {
  fetchList()
}

function getVarTypeTag(type) {
  const map = { date_range: 'warning', date: 'success', text: '', number: 'info' }
  return map[type] || ''
}

function addParam() {
  if (!form.params_config) form.params_config = []
  if (form.type === 'export') {
    form.params_config.push({
      name: '',
      label: '',
      type: 'text',
      date_format: 'day',
      required: false,
      multi: false,
      range: false,
      default_value: '',
      enum_enabled: false,
      enum_mode: 'list',
      enum_values: [],
      neq_value: '',
      default_checked: false,
      allow_all: false
    })
  } else {
    form.params_config.push({ name: '', label: '', type: 'text' })
  }
}

function removeParam(idx) {
  form.params_config.splice(idx, 1)
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

async function fetchList() {
  loading.value = true
  try {
    const params = {}
    if (typeFilter.value) {
      params.type = typeFilter.value
    }
    const res = await api.scripts.list(params)
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
    Object.assign(form, { ...defaultForm, ...row })
    // 加载参数配置
    if (!form.params_config) form.params_config = []
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
    // 编辑时加载已有SQL的字段列表
    if (form.type !== 'system') {
      const sqlToExtract = form.is_template ? form.sql_template : form.sql_text
      if (sqlToExtract && sqlToExtract.trim()) {
        if (form.is_template) {
          // 模板模式先渲染再提取
          api.scripts.renderTemplate({
            template: form.sql_template,
            template_config: templateVars.value
          }).then(res => {
            if (res.success && res.rendered_sql) {
              return api.scripts.extractColumns({ sql: res.rendered_sql })
            }
            return { columns: [] }
          }).then(res => {
            sqlFields.value = res.columns || []
          }).catch(() => {
            sqlFields.value = []
          })
        } else {
          api.scripts.extractColumns({ sql: form.sql_text }).then(res => {
            sqlFields.value = res.columns || []
          }).catch(() => {
            sqlFields.value = []
          })
        }
      } else {
        sqlFields.value = []
      }
    }
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm })
    templateVars.value = []
    sqlFields.value = []
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = { ...form }
    // 参数配置
    payload.params_config = form.params_config || []
    // 模板模式时设置template_config
    if (payload.is_template) {
      payload.template_config = templateVars.value
      // 模板模式下sql_text也保存一份渲染后的预览SQL（用于列提取等）
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
    ElMessage.info('正在验证查询选项...')
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
  const queryType = route.query.type
  if (queryType && ['query', 'export', 'system'].includes(queryType)) {
    typeFilter.value = queryType
  }
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.field-hint {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
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

/* ===== Export Params Rich UI (from ExportManager) ===== */
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

.param-enum-section {
  margin-top: 10px;
  padding: 12px 14px;
  background: #f5f8ff;
  border: 1px solid #d9e8fc;
  border-radius: 8px;
  flex-direction: column;
  align-items: stretch;
}

.enum-enable-checkbox {
  font-weight: 500;
  flex-shrink: 0;
}

.allow-all-checkbox {
  flex: 1;
  justify-content: flex-end;
}

.allow-all-label {
  color: #606266;
}

.enum-mode-selector {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #c9d8f0;
}

.enum-mode-selector :deep(.el-radio-button__inner) {
  padding: 8px 16px;
}

.enum-mode-selector :deep(.el-radio-button__inner i) {
  margin-right: 4px;
}

.enum-list-config {
  margin-top: 12px;
}

.enum-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.enum-list-title {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
}

.enum-empty-tip {
  font-size: 12px;
  color: #c0c4cc;
  text-align: center;
  padding: 16px 0;
}

.enum-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 6px;
  transition: box-shadow 0.2s;
}

.enum-value-row:hover {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.enum-value-index {
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  background: #e8edf5;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  color: #909399;
  flex-shrink: 0;
}

.enum-input-label,
.enum-input-value {
  flex: 1;
  min-width: 0;
}

.enum-value-separator {
  color: #c0c4cc;
  font-weight: bold;
  flex-shrink: 0;
  font-size: 14px;
}

.enum-value-remove {
  flex-shrink: 0;
  padding: 4px;
}

.enum-neq-config {
  margin-top: 12px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.neq-config-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.neq-config-row:last-child {
  margin-bottom: 0;
}

.neq-config-label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  flex-shrink: 0;
}

.neq-input {
  flex: 1;
}

.neq-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  background: #f5f7fa;
  border-radius: 4px;
  padding: 6px 10px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  line-height: 1.5;
}

.neq-hint i {
  color: #e6a23c;
  margin-top: 2px;
  flex-shrink: 0;
}
</style>
