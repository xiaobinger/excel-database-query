<template>
  <div class="auto-export-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-clock"></i> 自动导出任务</span>
          <div class="header-actions">
            <el-button v-hasPermi="['auto_export:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
            </el-button>
            <el-button v-hasPermi="['auto_export:delete']" type="danger" size="small" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
            <el-button v-if="store.hasButtonPermission('auto_export:create')" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建任务
            </el-button>
          </div>
        </div>
      </template>

      <el-table ref="tableRef" :data="taskList" stripe v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="name" label="任务名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="cron_expression" label="Cron表达式" width="130" show-overflow-tooltip />
        <el-table-column label="导出选项" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.script_names && row.script_names.length > 0">
              <el-tag
                v-for="name in row.script_names"
                :key="name"
                size="small"
                effect="plain"
                style="margin: 2px 4px 2px 0"
              >
                {{ name }}
              </el-tag>
            </template>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="输出格式" width="130" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.output_format === 'sheets' ? 'primary' : 'success'">
              {{ row.output_format === 'sheets' ? '多工作表' : '多文件压缩' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
              {{ row.is_enabled ? '启用' : '禁用' }}
            </el-tag>
            <i v-if="row.notify_enabled" class="fas fa-bell notify-bell-icon" title="邮件通知已启用"></i>
          </template>
        </el-table-column>
        <el-table-column prop="last_run_at" label="上次执行时间" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.last_run_at || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="上次执行状态" width="120" align="center">
          <template #default="{ row }">
            <template v-if="row.last_run_status">
              <el-tag :type="lastStatusType(row.last_run_status)" size="small">
                {{ lastStatusLabel(row.last_run_status) }}
              </el-tag>
            </template>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="next_run_at" label="下次执行时间" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.next_run_at || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="store.hasButtonPermission('auto_export:edit')" size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-button v-if="store.hasButtonPermission('auto_export:edit')" size="small" :type="row.is_enabled ? 'warning' : 'success'" text @click="handleToggle(row)">
              {{ row.is_enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button v-if="store.hasButtonPermission('auto_export:execute')" size="small" type="primary" text @click="handleRunNow(row)">
              <i class="fas fa-play"></i> 立即执行
            </el-button>
            <el-popconfirm
              v-if="store.hasButtonPermission('auto_export:delete')"
              title="确定要删除此任务吗？"
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
      <el-empty v-if="!loading && taskList.length === 0" description="暂无自动导出任务" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑自动导出任务' : '新建自动导出任务'"
      width="1000px"
      destroy-on-close
      :close-on-click-modal="false"
      top="5vh"
    >
      <div class="dialog-body">
        <div class="dialog-left">
          <div class="section-label">
            <i class="fas fa-info-circle"></i> 基本信息
          </div>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            class="dialog-form"
          >
            <el-form-item label="任务名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入任务名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="form.description" type="textarea" :rows="3" placeholder="简要描述此任务" />
            </el-form-item>
            <el-form-item label="Cron表达式" prop="cron_expression">
              <el-input v-model="form.cron_expression" placeholder="如: 0 8 1 * *" />
              <div class="cron-helper">
                常用示例：0 8 * * * = 每天8点 ｜ 0 8 1 * * = 每月1日8点 ｜ 0 8 * * 1 = 每周一8点 ｜ 0 0 1 1 * = 每月1日0点
              </div>
            </el-form-item>
            <el-form-item label="输出格式">
              <el-radio-group v-model="form.output_format">
                <el-radio value="sheets">多工作表</el-radio>
                <el-radio value="zip">多文件压缩</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="是否启用">
              <el-switch v-model="form.is_enabled" />
            </el-form-item>
          </el-form>

          <div class="section-label" style="margin-top: 20px">
            <i class="fas fa-bell"></i> 通知配置
          </div>
          <el-form label-position="top" class="dialog-form">
            <el-form-item label="启用邮件通知">
              <el-switch v-model="form.notify_enabled" />
            </el-form-item>
            <template v-if="form.notify_enabled">
              <el-form-item label="通知邮箱">
                <el-input v-model="form.notify_emails" type="textarea" :rows="2" placeholder="多个邮箱用逗号分隔" />
              </el-form-item>
              <el-form-item label="附件发送结果文件">
                <el-switch v-model="form.notify_attach_file" />
              </el-form-item>
            </template>
          </el-form>
        </div>

        <div class="dialog-right">
          <div class="section-label">
            <i class="fas fa-sliders-h"></i> 导出选项与参数
          </div>
          <el-form label-position="top" class="dialog-form">
            <el-form-item label="导出选项">
              <el-checkbox-group v-model="form.script_ids" @change="onScriptChange">
                <div class="script-checkbox-list">
                  <el-checkbox
                    v-for="s in exportScripts"
                    :key="s.id"
                    :value="s.id"
                    :label="s.name"
                  />
                </div>
              </el-checkbox-group>
              <el-empty v-if="exportScripts.length === 0" description="暂无导出选项" :image-size="40" />
            </el-form-item>

            <div v-if="selectedScriptParams.length > 0" class="params-section">
              <div class="params-section-title">参数配置</div>
              <div v-for="sp in selectedScriptParams" :key="sp.scriptId" class="script-params-block">
                <div class="script-params-name">{{ sp.scriptName }}</div>
                <div v-if="sp.params.length === 0" class="no-params-hint">无参数</div>
                <div v-for="param in sp.params" :key="param.name" class="param-config-row">
                  <div class="param-config-label">
                    {{ param.label || param.name }}
                    <el-tag v-if="param.range" size="small" type="warning" effect="plain" style="margin-left:4px;font-size:11px">范围</el-tag>
                  </div>
                  <div class="param-config-control">
                    <!-- 枚举list模式：下拉选择 -->
                    <template v-if="param.enum_enabled && param.enum_mode === 'list' && param.enum_values && param.enum_values.length > 0">
                      <el-select
                        :model-value="getParamValue(sp.scriptId, param.name)"
                        :multiple="param.multi"
                        :collapse-tags="param.multi"
                        :collapse-tags-tooltip="param.multi"
                        placeholder="请选择枚举值"
                        size="small"
                        style="flex: 1"
                        @change="(val) => setParamValue(sp.scriptId, param.name, val ?? '')"
                      >
                        <el-option
                          v-if="param.allow_all"
                          value=""
                          label="全部（不筛选）"
                        />
                        <el-option
                          v-for="item in param.enum_values"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                    </template>
                    <!-- 枚举neq模式：是/否开关 -->
                    <template v-else-if="param.enum_enabled && param.enum_mode === 'neq' && param.neq_value">
                      <el-switch
                        :model-value="getParamValue(sp.scriptId, param.name)"
                        active-text="是"
                        inactive-text="否"
                        active-color="#67c23a"
                        inactive-color="#f56c6c"
                        :disabled="param.allow_all && allChecked[getParamKey(sp.scriptId, param.name)]"
                        @change="(val) => setParamValue(sp.scriptId, param.name, val)"
                      />
                      <el-checkbox
                        v-if="param.allow_all"
                        :model-value="allChecked[getParamKey(sp.scriptId, param.name)]"
                        size="small"
                        style="margin-left: 8px"
                        @change="(val) => setAllChecked(sp.scriptId, param.name, val)"
                      >全部</el-checkbox>
                    </template>
                    <!-- 非枚举参数：mode选择器 + 动态/自定义 -->
                    <template v-else>
                      <el-select
                        :model-value="getParamMode(sp.scriptId, param.name)"
                        placeholder="选择方式"
                        size="small"
                        style="width: 140px"
                        @update:model-value="(val) => onParamModeChange(sp.scriptId, param.name, val)"
                      >
                        <el-option value="dynamic" label="动态表达式" />
                        <el-option value="custom" label="自定义固定值" />
                      </el-select>
                      <el-select
                        v-if="getParamMode(sp.scriptId, param.name) === 'dynamic'"
                        :model-value="getParamValue(sp.scriptId, param.name)"
                        placeholder="选择动态值"
                        size="small"
                        style="flex: 1"
                        @change="(val) => setParamValue(sp.scriptId, param.name, val)"
                      >
                        <el-option-group v-if="param.range" label="时间范围（自动拆分开始/结束）">
                          <el-option
                            v-for="opt in rangeDynamicOptions"
                            :key="opt.value"
                            :label="opt.label"
                            :value="opt.value"
                          />
                        </el-option-group>
                        <el-option-group v-if="!param.range" label="时间动态值">
                          <el-option
                            v-for="opt in timeDynamicOptions"
                            :key="opt.value"
                            :label="opt.label"
                            :value="opt.value"
                          />
                        </el-option-group>
                        <el-option-group label="固定值">
                          <el-option
                            v-for="opt in fixedParamOptions"
                            :key="opt.value"
                            :label="opt.label"
                            :value="opt.value"
                          />
                        </el-option-group>
                      </el-select>
                      <template v-else-if="getParamMode(sp.scriptId, param.name) === 'custom' && param.range">
                        <el-date-picker
                          :model-value="getParamValue(sp.scriptId, param.name)"
                          type="daterange"
                          range-separator="至"
                          start-placeholder="开始日期"
                          end-placeholder="结束日期"
                          size="small"
                          style="flex: 1"
                          value-format="YYYY-MM-DD"
                          @change="(val) => setParamValue(sp.scriptId, param.name, val || '')"
                        />
                      </template>
                      <el-input
                        v-else-if="getParamMode(sp.scriptId, param.name) === 'custom'"
                        :model-value="getParamValue(sp.scriptId, param.name)"
                        :type="param.type === 'number' ? 'number' : 'text'"
                        :disabled="param.allow_all && allChecked[getParamKey(sp.scriptId, param.name)]"
                        :placeholder="param.multi ? '输入多个值，以逗号分隔' : '输入固定值'"
                        size="small"
                        style="flex: 1"
                        @input="(val) => setParamValue(sp.scriptId, param.name, val)"
                      />
                      <el-checkbox
                        v-if="param.allow_all && (param.type === 'text' || param.type === 'number' || param.type === 'date' || param.type === 'datetime')"
                        :model-value="allChecked[getParamKey(sp.scriptId, param.name)]"
                        size="small"
                        style="margin-left: 8px"
                        @change="(val) => setAllChecked(sp.scriptId, param.name, val)"
                      >全部</el-checkbox>
                    </template>
                  </div>
                  <div v-if="param.range && getParamMode(sp.scriptId, param.name) === 'dynamic' && getParamValue(sp.scriptId, param.name)" class="param-range-preview">
                    <i class="fas fa-info-circle"></i>
                    {{ getRangePreview(getParamValue(sp.scriptId, param.name)) }}
                  </div>
                </div>
              </div>
            </div>
          </el-form>
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
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useAppStore()
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const tableRef = ref(null)
const selectedRows = ref([])
const taskList = ref([])
const exportScripts = ref([])
const paramOptionsData = ref({ time: [], fixed: [] })

const defaultForm = {
  name: '',
  description: '',
  cron_expression: '',
  output_format: 'sheets',
  is_enabled: true,
  script_ids: [],
  auto_params: {},
  notify_enabled: false,
  notify_emails: '',
  notify_attach_file: false
}

const form = reactive({ ...defaultForm, script_ids: [], auto_params: {} })
const paramModes = reactive({})
const allChecked = reactive({})

const rules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  cron_expression: [{ required: true, message: '请输入Cron表达式', trigger: 'blur' }]
}

const timeDynamicOptions = computed(() => paramOptionsData.value.time || [])
const rangeDynamicOptions = computed(() => paramOptionsData.value.range || [])
const fixedParamOptions = computed(() => paramOptionsData.value.fixed || [])

const selectedScriptParams = computed(() => {
  return form.script_ids.map(sid => {
    const script = exportScripts.value.find(s => s.id === sid)
    if (!script) return { scriptId: sid, scriptName: '', params: [] }
    let paramsConfig = []
    if (script.params_config) {
      try {
        paramsConfig = typeof script.params_config === 'string'
          ? JSON.parse(script.params_config)
          : script.params_config
        if (!Array.isArray(paramsConfig)) paramsConfig = []
      } catch {
        paramsConfig = []
      }
    }
    return { scriptId: sid, scriptName: script.name, params: paramsConfig }
  })
})

function lastStatusType(status) {
  const map = { completed: 'success', failed: 'danger', running: 'warning', pending: 'info' }
  return map[status] || 'info'
}

function lastStatusLabel(status) {
  const map = { completed: '成功', failed: '失败', running: '执行中', pending: '等待中' }
  return map[status] || status
}

function getParamKey(scriptId, paramName) {
  return `${scriptId}__${paramName}`
}

function setAllChecked(scriptId, paramName, val) {
  const key = getParamKey(scriptId, paramName)
  allChecked[key] = !!val
}

function getParamMode(scriptId, paramName) {
  const key = getParamKey(scriptId, paramName)
  return paramModes[key] || ''
}

function getParamValue(scriptId, paramName) {
  const key = getParamKey(scriptId, paramName)
  return form.auto_params[key] || ''
}

function setParamValue(scriptId, paramName, value) {
  const key = getParamKey(scriptId, paramName)
  form.auto_params[key] = value
}

function onParamModeChange(scriptId, paramName, mode) {
  const key = getParamKey(scriptId, paramName)
  paramModes[key] = mode
  form.auto_params[key] = ''
}

function getRangePreview(expr) {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  const pad = (n) => String(n).padStart(2, '0')
  const lastDay = (year, month) => new Date(year, month, 0).getDate()

  const previews = {
    range_current_month: `${y}-${pad(m)}-01 ~ ${y}-${pad(m)}-${lastDay(y, m)}`,
    range_last_month: m === 1
      ? `${y - 1}-12-01 ~ ${y - 1}-12-31`
      : `${y}-${pad(m - 1)}-01 ~ ${y}-${pad(m - 1)}-${lastDay(y, m - 1)}`,
    range_current_year: `${y}-01-01 ~ ${y}-12-31`,
    range_last_year: `${y - 1}-01-01 ~ ${y - 1}-12-31`,
    range_current_quarter: (() => {
      const q = Math.floor((m - 1) / 3)
      const qs = q * 3 + 1, qe = qs + 2
      return `${y}-${pad(qs)}-01 ~ ${y}-${pad(qe)}-${lastDay(y, qe)}`
    })(),
    range_last_quarter: (() => {
      const q = Math.floor((m - 1) / 3)
      if (q === 0) return `${y - 1}-10-01 ~ ${y - 1}-12-31`
      const qs = (q - 1) * 3 + 1, qe = qs + 2
      return `${y}-${pad(qs)}-01 ~ ${y}-${pad(qe)}-${lastDay(y, qe)}`
    })(),
    range_last_7_days: (() => {
      const d = new Date(now); d.setDate(d.getDate() - 7)
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ~ ${y}-${pad(m)}-${pad(now.getDate())}`
    })(),
    range_last_30_days: (() => {
      const d = new Date(now); d.setDate(d.getDate() - 30)
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ~ ${y}-${pad(m)}-${pad(now.getDate())}`
    })(),
  }
  return previews[expr] || ''
}

function onScriptChange() {
  const activeKeys = new Set()
  for (const sid of form.script_ids) {
    const script = exportScripts.value.find(s => s.id === sid)
    if (!script) continue
    let paramsConfig = []
    if (script.params_config) {
      try {
        paramsConfig = typeof script.params_config === 'string'
          ? JSON.parse(script.params_config)
          : script.params_config
        if (!Array.isArray(paramsConfig)) paramsConfig = []
      } catch {
        paramsConfig = []
      }
    }
    for (const p of paramsConfig) {
      activeKeys.add(getParamKey(sid, p.name))
    }
  }
  for (const key of Object.keys(form.auto_params)) {
    if (!activeKeys.has(key)) {
      delete form.auto_params[key]
    }
  }
  for (const key of Object.keys(paramModes)) {
    if (!activeKeys.has(key)) {
      delete paramModes[key]
    }
  }
  for (const key of Object.keys(allChecked)) {
    if (!activeKeys.has(key)) {
      delete allChecked[key]
    }
  }
}

function buildAutoParamsPayload() {
  const result = {}
  const allCheckedState = {}
  for (const sid of form.script_ids) {
    const script = exportScripts.value.find(s => s.id === sid)
    if (!script) continue
    let paramsConfig = []
    if (script.params_config) {
      try {
        paramsConfig = typeof script.params_config === 'string'
          ? JSON.parse(script.params_config)
          : script.params_config
        if (!Array.isArray(paramsConfig)) paramsConfig = []
      } catch {
        paramsConfig = []
      }
    }
    for (const p of paramsConfig) {
      const key = getParamKey(sid, p.name)
      // 保存 allChecked 状态
      if (allChecked[key]) {
        allCheckedState[key] = true
      }
      // 跳过勾选"全部"的参数
      if (allChecked[key]) continue
      const val = form.auto_params[key]
      if (val !== undefined && val !== null && val !== '') {
        // range类型参数自定义固定值：数组拆分为 _start 和 _end
        if (p.range && Array.isArray(val) && val.length === 2) {
          result[`${p.name}_start`] = val[0]
          result[`${p.name}_end`] = val[1]
        } else {
          result[p.name] = val
        }
      }
    }
  }
  // 将 allChecked 状态存入特殊 key
  if (Object.keys(allCheckedState).length > 0) {
    result.__allChecked__ = allCheckedState
  }
  return result
}

async function fetchList() {
  loading.value = true
  try {
    const res = await api.autoExport.list()
    taskList.value = res.data || res || []
  } catch {
    taskList.value = []
  } finally {
    loading.value = false
  }
}

async function fetchExportScripts() {
  try {
    const res = await api.scripts.list({ type: 'export' })
    exportScripts.value = res.data || res || []
  } catch {
    exportScripts.value = []
  }
}

async function fetchParamOptions() {
  try {
    const res = await api.autoExport.paramOptions()
    const data = res.data || res || {}
    paramOptionsData.value = {
      time: data.time || [],
      range: data.range || [],
      fixed: data.fixed || []
    }
  } catch {
    paramOptionsData.value = { time: [], range: [], fixed: [] }
  }
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    const autoParams = row.auto_params || {}
    // 提取并移除 __allChecked__ 状态
    const savedAllChecked = autoParams.__allChecked__ || {}
    const cleanedAutoParams = { ...autoParams }
    delete cleanedAutoParams.__allChecked__

    const restoredParams = {}
    const restoredModes = {}
    if (row.script_ids && row.script_ids.length > 0) {
      for (const sid of row.script_ids) {
        const script = exportScripts.value.find(s => s.id === sid)
        if (!script) continue
        let paramsConfig = []
        if (script.params_config) {
          try {
            paramsConfig = typeof script.params_config === 'string'
              ? JSON.parse(script.params_config)
              : script.params_config
            if (!Array.isArray(paramsConfig)) paramsConfig = []
          } catch {
            paramsConfig = []
          }
        }
        for (const p of paramsConfig) {
          const key = getParamKey(sid, p.name)
          if (cleanedAutoParams[p.name] !== undefined) {
            restoredParams[key] = cleanedAutoParams[p.name]
            const allDynamicValues = [
              ...paramOptionsData.value.time.map(o => o.value),
              ...paramOptionsData.value.range.map(o => o.value),
              ...paramOptionsData.value.fixed.map(o => o.value)
            ]
            restoredModes[key] = allDynamicValues.includes(cleanedAutoParams[p.name]) ? 'dynamic' : 'custom'
          }
        }
      }
    }
    Object.keys(paramModes).forEach(k => delete paramModes[k])
    Object.keys(allChecked).forEach(k => delete allChecked[k])
    // 恢复 allChecked 状态
    Object.assign(allChecked, savedAllChecked)
    Object.assign(paramModes, restoredModes)
    Object.assign(form, {
      name: row.name || '',
      description: row.description || '',
      cron_expression: row.cron_expression || '',
      output_format: row.output_format || 'sheets',
      is_enabled: row.is_enabled !== false,
      script_ids: row.script_ids || [],
      auto_params: restoredParams,
      notify_enabled: row.notify_enabled || false,
      notify_emails: Array.isArray(row.notify_emails) ? row.notify_emails.join(', ') : (row.notify_emails || ''),
      notify_attach_file: row.notify_attach_file || false
    })
  } else {
    isEdit.value = false
    editId.value = null
    Object.keys(paramModes).forEach(k => delete paramModes[k])
    Object.keys(allChecked).forEach(k => delete allChecked[k])
    Object.assign(form, {
      ...defaultForm,
      script_ids: [],
      auto_params: {}
    })
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description,
      cron_expression: form.cron_expression,
      output_format: form.output_format,
      is_enabled: form.is_enabled,
      script_ids: form.script_ids,
      auto_params: buildAutoParamsPayload(),
      notify_enabled: form.notify_enabled,
      notify_emails: form.notify_emails ? form.notify_emails.split(',').map(e => e.trim()).filter(e => e) : [],
      notify_attach_file: form.notify_attach_file
    }
    if (isEdit.value) {
      await api.autoExport.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.autoExport.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch {
  } finally {
    submitting.value = false
  }
}

async function handleToggle(row) {
  try {
    await api.autoExport.toggle(row.id)
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    fetchList()
  } catch {
  }
}

async function handleRunNow(row) {
  try {
    await ElMessageBox.confirm(
      `确定要立即执行任务「${row.name}」吗？`,
      '确认执行',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.autoExport.runNow(row.id)
    ElMessage.success('任务已触发执行')
    fetchList()
  } catch {
  }
}

async function handleDelete(id) {
  try {
    await api.autoExport.delete(id)
    ElMessage.success('删除成功')
    fetchList()
  } catch {
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个任务吗？`,
      '批量删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.autoExport.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchList()
  } catch {
  }
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除所有自动导出任务吗？此操作不可恢复！',
      '删除全部确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.autoExport.deleteAll()
    ElMessage.success('删除全部成功')
    selectedRows.value = []
    fetchList()
  } catch {
  }
}

onMounted(() => {
  fetchList()
  fetchExportScripts()
  fetchParamOptions()
})
</script>

<style scoped>
.auto-export-manager {
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

.notify-bell-icon {
  color: #e6a23c;
  font-size: 12px;
  margin-left: 4px;
  cursor: default;
}

.dialog-body {
  display: flex;
  gap: 24px;
  min-height: 400px;
}

.dialog-left {
  flex: 1;
  min-width: 0;
}

.dialog-right {
  flex: 1;
  min-width: 0;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin-bottom: 16px;
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

.dialog-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.dialog-form :deep(.el-form-item__label) {
  font-size: 13px;
  color: #606266;
  padding-bottom: 4px;
  font-weight: 500;
}

.cron-helper {
  font-size: 12px;
  color: var(--text-muted, #909399);
  line-height: 1.6;
  margin-top: 4px;
}

.script-checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
  padding-right: 4px;
}

.params-section {
  margin-top: 8px;
}

.params-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.script-params-block {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-left: 3px solid var(--primary-color, #409eff);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
}

.script-params-block:last-child {
  margin-bottom: 0;
}

.script-params-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-color, #409eff);
  margin-bottom: 10px;
}

.no-params-hint {
  font-size: 12px;
  color: #c0c4cc;
}

.param-config-row {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.param-config-row:last-child {
  margin-bottom: 0;
}

.param-config-label {
  display: inline-block;
  font-size: 12px;
  color: var(--primary-color, #409eff);
  background: #ecf5ff;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  font-weight: 500;
}

.param-config-control {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.param-range-preview {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 4px;
  padding: 4px 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.param-range-preview i {
  color: #e6a23c;
  font-size: 11px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
