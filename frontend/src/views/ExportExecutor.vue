<template>
  <div class="export-executor">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-file-export"></i> 导出执行</span>
        </div>
      </template>

      <el-steps :active="currentStep" finish-status="success" align-center class="steps">
        <el-step title="导出选项" />
        <el-step title="参数设置" />
        <el-step title="执行导出" />
      </el-steps>

      <div class="step-content">
        <div v-if="currentStep === 0" class="step-panel">
          <div class="select-all-bar">
            <el-button size="small" @click="selectAllScripts">全选</el-button>
            <el-button size="small" @click="deselectAllScripts">取消全选</el-button>
            <span class="selected-count">已选择 {{ selectedScriptIds.length }} 个导出选项</span>
          </div>
          <div class="script-card-grid">
            <div
              v-for="s in visibleScripts"
              :key="s.id"
              class="script-card"
              :class="{ selected: selectedScriptIds.includes(s.id) }"
              @click="toggleScript(s.id)"
            >
              <div class="script-card-header">
                <span class="check-box"><i class="fas fa-check"></i></span>
                <span class="script-card-name">{{ s.name }}</span>
              </div>
              <div class="script-card-body">
                <el-tag v-if="s.tag" size="small" type="info" style="margin-right: 6px">{{ s.tag }}</el-tag>
                <el-tag size="small" type="primary">{{ (s.params_config || []).length }} 个参数</el-tag>
              </div>
              <div class="script-card-dbs">
                <el-tag
                  v-for="dbId in (s.database_ids || [])"
                  :key="dbId"
                  size="small"
                  type="success"
                  effect="plain"
                  style="margin: 2px 4px 2px 0"
                >
                  <i class="fas fa-database" style="margin-right: 2px"></i> {{ getDbName(dbId) }}
                </el-tag>
              </div>
            </div>
          </div>
          <el-empty v-if="visibleScripts.length === 0" description="暂无导出选项，请先在查询选项管理中创建" />
          <div class="step-actions">
            <el-button type="primary" :disabled="selectedScriptIds.length === 0" @click="goToStep1">下一步</el-button>
          </div>
        </div>

        <div v-if="currentStep === 1" class="step-panel">
          <div v-if="sharedParams.length > 0" class="shared-params-section">
            <div class="params-section-title">
              <i class="fas fa-layer-group"></i>
              <span>公共参数</span>
              <el-tag size="small" type="info" effect="plain" style="margin-left: 8px">多个导出选项共用</el-tag>
            </div>
            <div class="params-card shared-params-card">
              <div class="param-item" v-for="p in sharedParams" :key="p.name">
                <div class="param-item-label">
                  <span class="param-name-tag">{{ p.label || p.name }}</span>
                  <el-tag v-if="p.multi" size="small" type="warning" effect="plain">IN</el-tag>
                  <el-tag v-if="p.range" size="small" type="warning" effect="plain">范围</el-tag>
                  <el-tag size="small" type="info" effect="plain">{{ p.scriptIds.length }}个选项共用</el-tag>
                  <el-tag v-if="p.required" size="small" type="danger" effect="plain">必填</el-tag>
                </div>
                <div class="param-item-control">
                  <template v-if="p.enum_enabled && p.enum_mode === 'neq' && p.neq_value">
                    <div class="neq-param-control">
                      <span class="neq-param-label">{{ p.label || p.name }}</span>
                      <el-switch
                        v-model="sharedParamValues[p.name]"
                        active-text="是"
                        inactive-text="否"
                        active-color="#67c23a"
                        inactive-color="#f56c6c"
                        :disabled="p.allow_all && neqAllChecked[p.name]"
                      />
                      <el-checkbox
                        v-if="p.allow_all"
                        v-model="neqAllChecked[p.name]"
                        size="small"
                      >全部</el-checkbox>
                    </div>
                  </template>
                  <el-select
                    v-else-if="p.enum_enabled && p.enum_values && p.enum_values.length > 0"
                    v-model="sharedParamValues[p.name]"
                    :multiple="p.multi"
                    :collapse-tags="p.multi"
                    :collapse-tags-tooltip="p.multi"
                    placeholder="请选择"
                    style="width: 100%"
                  >
                    <el-option
                      v-if="p.allow_all"
                      value=""
                      label="全部（不筛选）"
                    />
                    <el-option
                      v-for="item in p.enum_values"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                  <el-input
                    v-else-if="p.type === 'text'"
                    v-model="sharedParamValues[p.name]"
                    :placeholder="p.multi ? '请输入多个值，以逗号分隔' : '请输入' + (p.label || p.name)"
                  />
                  <template v-else-if="p.type === 'date' || p.type === 'datetime'">
                    <el-date-picker
                      v-if="p.range && p.date_format === 'year'"
                      v-model="sharedParamValues[p.name]"
                      type="yearrange"
                      :start-placeholder="'开始' + (p.label || p.name)"
                      :end-placeholder="'结束' + (p.label || p.name)"
                      value-format="YYYY"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="p.range && p.date_format === 'month'"
                      v-model="sharedParamValues[p.name]"
                      type="monthrange"
                      :start-placeholder="'开始' + (p.label || p.name)"
                      :end-placeholder="'结束' + (p.label || p.name)"
                      value-format="YYYY-MM"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="p.range && (p.date_format === 'day' || !p.date_format)"
                      v-model="sharedParamValues[p.name]"
                      type="daterange"
                      :start-placeholder="'开始' + (p.label || p.name)"
                      :end-placeholder="'结束' + (p.label || p.name)"
                      value-format="YYYY-MM-DD"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="p.range && p.date_format === 'datetime'"
                      v-model="sharedParamValues[p.name]"
                      type="datetimerange"
                      :start-placeholder="'开始' + (p.label || p.name)"
                      :end-placeholder="'结束' + (p.label || p.name)"
                      value-format="YYYY-MM-DD HH:mm:ss"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="!p.range && p.date_format === 'year'"
                      v-model="sharedParamValues[p.name]"
                      type="year"
                      :placeholder="'请选择' + (p.label || p.name)"
                      value-format="YYYY"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="!p.range && p.date_format === 'month'"
                      v-model="sharedParamValues[p.name]"
                      type="month"
                      :placeholder="'请选择' + (p.label || p.name)"
                      value-format="YYYY-MM"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="!p.range && (p.date_format === 'day' || !p.date_format)"
                      v-model="sharedParamValues[p.name]"
                      type="date"
                      :placeholder="'请选择' + (p.label || p.name)"
                      value-format="YYYY-MM-DD"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="!p.range && p.date_format === 'datetime'"
                      v-model="sharedParamValues[p.name]"
                      type="datetime"
                      :placeholder="'请选择' + (p.label || p.name)"
                      value-format="YYYY-MM-DD HH:mm:ss"
                      style="width: 100%"
                    />
                    <el-date-picker
                      v-else-if="p.type === 'datetime'"
                      v-model="sharedParamValues[p.name]"
                      type="datetime"
                      :placeholder="'请选择' + (p.label || p.name)"
                      value-format="YYYY-MM-DD HH:mm:ss"
                      style="width: 100%"
                    />
                  </template>
                </div>
              </div>
            </div>
          </div>

          <div v-if="Object.keys(uniqueParamsByScript).length > 0" class="unique-params-section">
            <div class="params-section-title">
              <i class="fas fa-cubes"></i>
              <span>独立参数</span>
              <el-tag size="small" type="info" effect="plain" style="margin-left: 8px">各导出选项独有</el-tag>
            </div>
            <div class="unique-params-list">
              <div
                v-for="(params, scriptId) in uniqueParamsByScript"
                :key="scriptId"
                class="script-params-block"
              >
                <div class="script-params-header">
                  <span class="script-params-name">{{ getScriptNameById(scriptId) }}</span>
                  <el-tag size="small" type="primary">{{ params.length }} 个参数</el-tag>
                </div>
                <div class="params-card">
                  <div class="param-item" v-for="p in params" :key="p.name">
                    <div class="param-item-label">
                      <span class="param-name-tag">{{ p.label || p.name }}</span>
                      <el-tag v-if="p.multi" size="small" type="warning" effect="plain">IN</el-tag>
                      <el-tag v-if="p.range" size="small" type="warning" effect="plain">范围</el-tag>
                      <el-tag v-if="p.required" size="small" type="danger" effect="plain">必填</el-tag>
                    </div>
                    <div class="param-item-control">
                      <template v-if="p.enum_enabled && p.enum_mode === 'neq' && p.neq_value">
                        <div class="neq-param-control">
                          <span class="neq-param-label">{{ p.label || p.name }}</span>
                          <el-switch
                            v-model="paramValues[scriptId][p.name]"
                            active-text="是"
                            inactive-text="否"
                            active-color="#67c23a"
                            inactive-color="#f56c6c"
                            :disabled="p.allow_all && neqAllChecked[scriptId + '_' + p.name]"
                          />
                          <el-checkbox
                            v-if="p.allow_all"
                            v-model="neqAllChecked[scriptId + '_' + p.name]"
                            size="small"
                          >全部</el-checkbox>
                        </div>
                      </template>
                      <el-select
                        v-else-if="p.enum_enabled && p.enum_values && p.enum_values.length > 0"
                        v-model="paramValues[scriptId][p.name]"
                        :multiple="p.multi"
                        :collapse-tags="p.multi"
                        :collapse-tags-tooltip="p.multi"
                        placeholder="请选择"
                        style="width: 100%"
                      >
                        <el-option
                          v-if="p.allow_all"
                          value=""
                          label="全部（不筛选）"
                        />
                        <el-option
                          v-for="item in p.enum_values"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                      <el-input
                        v-else-if="p.type === 'text'"
                        v-model="paramValues[scriptId][p.name]"
                        :placeholder="p.multi ? '请输入多个值，以逗号分隔' : '请输入' + (p.label || p.name)"
                      />
                      <template v-else-if="p.type === 'date' || p.type === 'datetime'">
                        <el-date-picker
                          v-if="p.range && p.date_format === 'year'"
                          v-model="paramValues[scriptId][p.name]"
                          type="yearrange"
                          :start-placeholder="'开始' + (p.label || p.name)"
                          :end-placeholder="'结束' + (p.label || p.name)"
                          value-format="YYYY"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="p.range && p.date_format === 'month'"
                          v-model="paramValues[scriptId][p.name]"
                          type="monthrange"
                          :start-placeholder="'开始' + (p.label || p.name)"
                          :end-placeholder="'结束' + (p.label || p.name)"
                          value-format="YYYY-MM"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="p.range && (p.date_format === 'day' || !p.date_format)"
                          v-model="paramValues[scriptId][p.name]"
                          type="daterange"
                          :start-placeholder="'开始' + (p.label || p.name)"
                          :end-placeholder="'结束' + (p.label || p.name)"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="p.range && p.date_format === 'datetime'"
                          v-model="paramValues[scriptId][p.name]"
                          type="datetimerange"
                          :start-placeholder="'开始' + (p.label || p.name)"
                          :end-placeholder="'结束' + (p.label || p.name)"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="!p.range && p.date_format === 'year'"
                          v-model="paramValues[scriptId][p.name]"
                          type="year"
                          :placeholder="'请选择' + (p.label || p.name)"
                          value-format="YYYY"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="!p.range && p.date_format === 'month'"
                          v-model="paramValues[scriptId][p.name]"
                          type="month"
                          :placeholder="'请选择' + (p.label || p.name)"
                          value-format="YYYY-MM"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="!p.range && (p.date_format === 'day' || !p.date_format)"
                          v-model="paramValues[scriptId][p.name]"
                          type="date"
                          :placeholder="'请选择' + (p.label || p.name)"
                          value-format="YYYY-MM-DD"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else-if="!p.range && p.date_format === 'datetime'"
                          v-model="paramValues[scriptId][p.name]"
                          type="datetime"
                          :placeholder="'请选择' + (p.label || p.name)"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          style="width: 100%"
                        />
                        <el-date-picker
                          v-else
                          v-model="paramValues[scriptId][p.name]"
                          type="datetime"
                          :placeholder="'请选择' + (p.label || p.name)"
                          value-format="YYYY-MM-DD HH:mm:ss"
                          style="width: 100%"
                        />
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="sharedParams.length === 0 && Object.keys(uniqueParamsByScript).length === 0" class="no-params">
            所有导出选项均无参数，可直接执行
          </div>
          <div class="step-actions">
            <el-button @click="currentStep = 0">上一步</el-button>
            <el-button type="primary" @click="goToStep2">下一步</el-button>
          </div>
        </div>

        <div v-if="currentStep === 2" class="step-panel">
          <el-form label-width="120px">
            <el-form-item label="输出格式">
              <el-radio-group v-model="outputFormat">
                <el-radio value="sheets">多工作表（所有结果在一个Excel文件中，每个导出选项结果单独一个工作表）</el-radio>
                <el-radio value="zip">多文件压缩（每个导出选项结果为单独Excel文件，打包为ZIP）</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <el-divider content-position="left">执行摘要</el-divider>
          <div class="summary-list">
            <div v-for="s in selectedScripts" :key="s.id" class="summary-item">
              <div class="summary-item-header">
                <span class="summary-item-name">{{ s.name }}</span>
                <el-tag v-if="s.tag" size="small" type="info" style="margin-left: 8px">{{ s.tag }}</el-tag>
              </div>
              <div class="summary-item-body">
                <div class="summary-row">
                  <span class="summary-label">关联数据库:</span>
                  <div class="summary-value">
                    <el-tag
                      v-for="dbId in (s.database_ids || [])"
                      :key="dbId"
                      size="small"
                      type="success"
                      effect="plain"
                      style="margin: 2px 4px 2px 0"
                    >
                      <i class="fas fa-database" style="margin-right: 2px"></i> {{ getDbName(dbId) }}
                    </el-tag>
                    <span v-if="!s.database_ids || s.database_ids.length === 0" style="color: #c0c4cc">未关联</span>
                  </div>
                </div>
                <div v-if="s.params_config && s.params_config.length > 0" class="summary-row">
                  <span class="summary-label">参数设置:</span>
                  <div class="summary-value">
                    <el-tag
                      v-for="p in s.params_config"
                      :key="p.name"
                      size="small"
                      effect="plain"
                      style="margin: 2px 4px 2px 0"
                    >
                      {{ p.label || p.name }} = {{ getParamDisplayValue(s.id, p.name) }}
                    </el-tag>
                  </div>
                </div>
                <div v-else class="summary-row">
                  <span class="summary-label">参数设置:</span>
                  <span class="summary-value" style="color: #909399">无参数</span>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-if="selectedScripts.length === 0" description="未选择导出选项" />

          <div class="execute-area">
            <el-button
              v-if="!executing && !taskId && store.hasButtonPermission('export:execute')"
              type="success"
              size="large"
              @click="executeExport"
              :loading="submitting"
            >
              <i class="fas fa-play"></i> 开始执行
            </el-button>
            <el-button v-if="executing && store.hasButtonPermission('export:cancel')" type="danger" size="large" @click="cancelExport">
              <i class="fas fa-stop"></i> 取消执行
            </el-button>
          </div>

          <div v-if="taskId" class="progress-area">
            <div v-if="executing" class="executing-indicator">
              <div class="spinner-ring"></div>
              <span class="spinner-text">导出执行中...</span>
            </div>
            <el-divider content-position="left">执行进度</el-divider>
            <el-progress :percentage="progress" :status="progressStatus" :stroke-width="20" :text-inside="true" />
            <div class="status-info">
              <el-tag :type="statusType" size="large">{{ statusLabel }}</el-tag>
              <span v-if="taskStatus.total_rows" class="status-detail">总行数: {{ taskStatus.total_rows }}</span>
              <span v-if="taskStatus.success_count" class="status-detail success">成功: {{ taskStatus.success_count }}</span>
              <span v-if="taskStatus.failure_count" class="status-detail danger">失败: {{ taskStatus.failure_count }}</span>
            </div>

            <div v-if="logLines.length > 0" class="log-area">
              <div class="log-header">
                <span>实时日志</span>
                <el-button size="small" text @click="logLines = []">清空</el-button>
              </div>
              <div class="log-content" ref="logContentRef">
                <div v-for="(line, idx) in logLines" :key="idx" class="log-line" :class="line.type">{{ line.text }}</div>
              </div>
            </div>

            <div v-if="taskStatus.status === 'completed' && store.hasButtonPermission('export:download')" class="download-area">
              <el-button type="primary" size="large" @click="downloadResult">
                <i class="fas fa-download"></i> 下载结果文件
              </el-button>
              <div class="retention-tip">
                <i class="fas fa-exclamation-triangle"></i> 结果文件将保留 {{ fileRetentionHours }} 小时，请及时下载
              </div>
            </div>

            <div v-if="(taskStatus.status === 'failed' || taskStatus.status === 'cancelled') && store.hasButtonPermission('export:retry')" class="retry-area">
              <el-button type="warning" size="large" :loading="retrying" @click="handleRetry">
                <i class="fas fa-redo"></i> 重新执行
              </el-button>
            </div>
          </div>

          <div class="step-actions" style="margin-top: 20px">
            <el-button @click="currentStep = 1" :disabled="!!taskId">上一步</el-button>
            <el-button @click="resetAll" :disabled="executing">重新开始</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useAppStore()

const currentStep = ref(0)
const selectedScriptIds = ref([])
const exportScripts = ref([])
const activeCollapse = ref('')
const paramValues = reactive({})
const sharedParamValues = reactive({})
const neqAllChecked = reactive({})
const formRefs = reactive({})
const outputFormat = ref('sheets')
const submitting = ref(false)
const executing = ref(false)
const taskId = ref(null)
const progress = ref(0)
const taskStatus = ref({})
const logLines = ref([])
const logContentRef = ref(null)
const retrying = ref(false)
const fileRetentionHours = ref(24)
let eventSource = null

const visibleScripts = computed(() => {
  const scriptIds = store.getUserScriptIds()
  if (scriptIds.length === 0) return exportScripts.value
  return exportScripts.value.filter((s) => scriptIds.includes(s.id))
})

const selectedScripts = computed(() => {
  return visibleScripts.value.filter((s) => selectedScriptIds.value.includes(s.id))
})

const selectedScriptNames = computed(() => {
  return selectedScripts.value.map((s) => s.name).join(', ')
})

const associatedDbIds = computed(() => {
  const ids = new Set()
  selectedScripts.value.forEach((s) => {
    ;(s.database_ids || []).forEach((id) => ids.add(id))
  })
  return [...ids]
})

const associatedDbNames = computed(() => {
  return store.databases
    .filter((db) => associatedDbIds.value.includes(db.id))
    .map((db) => db.name)
    .join(', ')
})

const hasParams = computed(() => {
  return selectedScripts.value.some((s) => s.params_config && s.params_config.length > 0)
})

const mergedParams = computed(() => {
  const paramMap = new Map()
  selectedScripts.value.forEach((s) => {
    const params = s.params_config || []
    params.forEach((p) => {
      const key = `${p.name}|${p.type}|${p.date_format || ''}`
      if (!paramMap.has(key)) {
        paramMap.set(key, { ...p, scriptIds: [s.id] })
      } else {
        const existing = paramMap.get(key)
        if (!existing.scriptIds.includes(s.id)) {
          existing.scriptIds.push(s.id)
        }
      }
    })
  })
  return [...paramMap.values()]
})

const sharedParams = computed(() => {
  return mergedParams.value.filter((p) => p.scriptIds.length > 1)
})

const uniqueParamsByScript = computed(() => {
  const result = {}
  selectedScripts.value.forEach((s) => {
    const params = (s.params_config || []).filter((p) => {
      const key = `${p.name}|${p.type}|${p.date_format || ''}`
      const merged = mergedParams.value.find((m) => `${m.name}|${m.type}|${m.date_format || ''}` === key)
      return merged && merged.scriptIds.length <= 1
    })
    if (params.length > 0) {
      result[s.id] = params
    }
  })
  return result
})

const paramsSummaryData = computed(() => {
  const rows = []
  selectedScripts.value.forEach((s) => {
    const params = s.params_config || []
    if (params.length === 0) {
      rows.push({ scriptName: s.name, paramName: '-', paramValue: '无参数' })
    } else {
      params.forEach((p) => {
        const val = paramValues[s.id]?.[p.name]
        rows.push({
          scriptName: s.name,
          paramName: p.label || p.name,
          paramValue: val || '-'
        })
      })
    }
  })
  return rows
})

const progressStatus = computed(() => {
  const s = taskStatus.value.status
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'exception'
  return undefined
})

const statusType = computed(() => {
  const map = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' }
  return map[taskStatus.value.status] || 'info'
})

const statusLabel = computed(() => {
  const map = { pending: '等待中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
  return map[taskStatus.value.status] || '-'
})

function getDbName(dbId) {
  const db = store.databases.find((d) => d.id === dbId)
  return db ? db.name : `ID:${dbId}`
}

function getScriptNameById(scriptId) {
  const s = exportScripts.value.find((s) => s.id === Number(scriptId))
  return s ? s.name : `选项${scriptId}`
}

function getParamDisplayValue(scriptId, paramName) {
  const uniqueVal = paramValues[scriptId]?.[paramName]
  if (uniqueVal !== undefined && uniqueVal !== '' && uniqueVal !== null) {
    if (Array.isArray(uniqueVal)) return uniqueVal.join(' ~ ')
    return uniqueVal
  }
  const sharedVal = sharedParamValues[paramName]
  if (sharedVal !== undefined && sharedVal !== '' && sharedVal !== null) {
    if (Array.isArray(sharedVal)) return sharedVal.join(' ~ ')
    return sharedVal
  }
  return '-'
}

function toggleScript(id) {
  const idx = selectedScriptIds.value.indexOf(id)
  if (idx === -1) {
    selectedScriptIds.value.push(id)
  } else {
    selectedScriptIds.value.splice(idx, 1)
  }
}

function selectAllScripts() {
  selectedScriptIds.value = visibleScripts.value.map(s => s.id)
}

function deselectAllScripts() {
  selectedScriptIds.value = []
}

function setFormRef(scriptId, el) {
  if (el) {
    formRefs[scriptId] = el
  }
}

function initParamValues() {
  selectedScripts.value.forEach((s) => {
    if (!paramValues[s.id]) {
      paramValues[s.id] = {}
    }
    const params = s.params_config || []
    params.forEach((p) => {
      if (p.enum_enabled && p.enum_mode === 'neq') {
        if (paramValues[s.id][p.name] === undefined) {
          paramValues[s.id][p.name] = p.default_checked ? true : false
        }
        const allKey = `${s.id}_${p.name}`
        if (neqAllChecked[allKey] === undefined) {
          neqAllChecked[allKey] = false
        }
      } else if (paramValues[s.id][p.name] === undefined) {
        if (p.range && (p.type === 'date' || p.type === 'datetime')) {
          paramValues[s.id][p.name] = null
        } else {
          paramValues[s.id][p.name] = p.default_value || ''
        }
      }
    })
  })
  sharedParams.value.forEach((p) => {
    if (p.enum_enabled && p.enum_mode === 'neq') {
      if (sharedParamValues[p.name] === undefined) {
        sharedParamValues[p.name] = p.default_checked ? true : false
      }
      if (neqAllChecked[p.name] === undefined) {
        neqAllChecked[p.name] = false
      }
    } else if (sharedParamValues[p.name] === undefined) {
      if (p.range && (p.type === 'date' || p.type === 'datetime')) {
        sharedParamValues[p.name] = null
      } else {
        sharedParamValues[p.name] = p.default_value || ''
      }
    }
  })
}

function goToStep1() {
  if (selectedScriptIds.value.length === 0) {
    ElMessage.warning('请至少选择一个导出选项')
    return
  }
  initParamValues()
  if (selectedScripts.value.length > 0) {
    activeCollapse.value = selectedScripts.value[0].id
  }
  currentStep.value = 1
}

async function goToStep2() {
  for (const p of sharedParams.value) {
    if (p.required && !sharedParamValues[p.name] && !isNeqParam(p)) {
      ElMessage.warning(`请填写公共参数"${p.label || p.name}"`)
      return
    }
  }
  for (const s of selectedScripts.value) {
    const params = (s.params_config || []).filter((p) => {
      const key = `${p.name}|${p.type}|${p.date_format || ''}`
      const merged = mergedParams.value.find((m) => `${m.name}|${m.type}|${m.date_format || ''}` === key)
      return !merged || merged.scriptIds.length <= 1
    })
    for (const p of params) {
      if (p.required && !paramValues[s.id]?.[p.name] && !isNeqParam(p)) {
        ElMessage.warning(`请填写导出选项"${s.name}"的参数"${p.label || p.name}"`)
        activeCollapse.value = s.id
        return
      }
    }
  }
  currentStep.value = 2
}

function isNeqParam(p) {
  return p.enum_enabled && p.enum_mode === 'neq'
}

async function executeExport() {
  submitting.value = true
  try {
    const params_values = {}
    // 从公共参数构建，跳过选中"全部"的非即不等于参数
    Object.keys(sharedParamValues).forEach((k) => {
      if (neqAllChecked[k]) return
      params_values[k] = sharedParamValues[k]
    })
    selectedScripts.value.forEach((s) => {
      const scriptParams = s.params_config || []
      scriptParams.forEach((p) => {
        // 跳过选中"全部"的非即不等于参数
        if (p.enum_enabled && p.enum_mode === 'neq' && neqAllChecked[`${s.id}_${p.name}`]) {
          return
        }
        const val = paramValues[s.id]?.[p.name]
        if (val !== undefined && val !== '') {
          params_values[p.name] = val
        }
      })
    })

    const allParamsConfig = []
    selectedScripts.value.forEach((s) => {
      const pc = s.params_config || []
      pc.forEach((p) => {
        if (!allParamsConfig.find((ap) => ap.name === p.name)) {
          allParamsConfig.push(p)
        }
      })
    })

    Object.keys(params_values).forEach((k) => {
      const val = params_values[k]
      if (val === undefined || val === '' || val === null) {
        delete params_values[k]
        return
      }
      const paramConfig = allParamsConfig.find((p) => p.name === k)
      if (paramConfig && paramConfig.range && Array.isArray(val) && val.length === 2) {
        params_values[`${k}_start`] = val[0]
        params_values[`${k}_end`] = val[1]
        delete params_values[k]
      }
    })

    const data = {
      script_ids: selectedScriptIds.value,
      output_format: outputFormat.value,
      params_values
    }

    const res = await api.export.execute(data)
    const result = res.data || res
    taskId.value = result.task_id || result.id
    executing.value = true
    progress.value = 0
    logLines.value = []
    startSSE(taskId.value)
    ElMessage.success('任务已提交')
  } catch {
  } finally {
    submitting.value = false
  }
}

function startSSE(tid) {
  if (eventSource) {
    eventSource.close()
  }
  const url = api.export.streamStatus(tid)
  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      taskStatus.value = data
      if (data.progress !== undefined) {
        progress.value = Math.round(data.progress)
      }
      if (data.new_logs && data.new_logs.length > 0) {
        data.new_logs.forEach((log) => {
          logLines.value.push({ text: `[${log.time}] ${log.message}`, type: log.level || 'info' })
        })
        nextTick(() => {
          if (logContentRef.value) {
            logContentRef.value.scrollTop = logContentRef.value.scrollHeight
          }
        })
      }
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
        executing.value = false
        eventSource.close()
        eventSource = null
        if (data.status === 'completed') {
          progress.value = 100
        }
        store.notifyTaskChanged()
      }
    } catch {
      logLines.value.push({ text: event.data, type: 'info' })
    }
  }

  eventSource.onerror = () => {
    eventSource.close()
    eventSource = null
    if (executing.value) {
      fetchStatus(tid)
    }
  }
}

async function fetchStatus(tid) {
  try {
    const res = await api.export.status(tid)
    const data = res.data || res
    taskStatus.value = data
    if (data.progress !== undefined) {
      progress.value = Math.round(data.progress)
    }
    if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
      executing.value = false
      if (data.status === 'completed') {
        progress.value = 100
      }
    }
  } catch {
  }
}

async function cancelExport() {
  if (!taskId.value) return
  try {
    await ElMessageBox.confirm('确定要取消当前导出任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.export.cancel(taskId.value)
    ElMessage.success('已发送取消请求')
  } catch {
  }
}

async function handleRetry() {
  if (!taskId.value) return
  retrying.value = true
  try {
    const res = await api.export.retry(taskId.value)
    if (res.success) {
      ElMessage.success('任务已重新提交执行')
      executing.value = true
      progress.value = 0
      logLines.value = []
      startSSE(taskId.value)
    } else {
      ElMessageBox.alert(res.message || '重新执行失败', '提示', { type: 'warning' })
    }
  } catch (e) {
    const msg = e?.response?.data?.message || '重新执行失败'
    ElMessageBox.alert(msg, '提示', { type: 'warning' })
  } finally {
    retrying.value = false
  }
}

async function downloadResult() {
  if (!taskId.value) return
  const url = api.download.file(taskId.value)
  const isZip = outputFormat.value === 'zip'
  const defaultName = isZip ? `export_${taskId.value}.zip` : `export_${taskId.value}.xlsx`
  try {
    const check = await fetch(url, { method: 'HEAD' })
    if (!check.ok) {
      const data = await check.json().catch(() => ({}))
      ElMessageBox.alert(data.message || '结果文件不存在或已被清理', '提示', { type: 'warning' })
      return
    }
    if (window.showSaveFilePicker) {
      const types = isZip
        ? [{ description: 'ZIP压缩包', accept: { 'application/zip': ['.zip'] } }]
        : [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }]
      const handle = await window.showSaveFilePicker({
        suggestedName: defaultName,
        types
      })
      const resp = await fetch(url)
      const blob = await resp.blob()
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
    } else {
      const { value: customName } = await ElMessageBox.prompt(
        '请输入保存的文件名',
        '下载文件',
        {
          confirmButtonText: '下载',
          cancelButtonText: '取消',
          inputValue: defaultName,
          inputPattern: /\S+/,
          inputErrorMessage: '文件名不能为空'
        }
      ).catch(() => ({ value: null }))
      if (!customName) return
      const resp = await fetch(url)
      const blob = await resp.blob()
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = customName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(blobUrl)
    }
  } catch (e) {
    if (e.name === 'AbortError') return
    ElMessageBox.alert('文件下载失败，请稍后重试', '提示', { type: 'warning' })
  }
}

function resetAll() {
  currentStep.value = 0
  selectedScriptIds.value = []
  outputFormat.value = 'sheets'
  taskId.value = null
  executing.value = false
  progress.value = 0
  taskStatus.value = {}
  logLines.value = []
  Object.keys(paramValues).forEach((k) => delete paramValues[k])
  Object.keys(sharedParamValues).forEach((k) => delete sharedParamValues[k])
  Object.keys(neqAllChecked).forEach((k) => delete neqAllChecked[k])
  Object.keys(formRefs).forEach((k) => delete formRefs[k])
  activeCollapse.value = ''
  if (eventSource) {
    eventSource.close()
    eventSource = null
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

onMounted(() => {
  store.fetchDatabases()
  fetchExportScripts()
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})
</script>

<style scoped>
.export-executor {
  max-width: 1000px;
  margin: 0 auto;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.card-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.steps {
  margin-bottom: 30px;
}

.step-panel {
  padding: 20px 40px;
}

.step-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
}

.select-all-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.selected-count {
  font-size: 13px;
  color: var(--text-muted, #909399);
  margin-left: 8px;
}

.script-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.script-card {
  border: 2px solid #eef2f7;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}

.script-card:hover {
  border-color: #c6e2ff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.08);
}

.script-card.selected {
  border-color: var(--primary-color, #409eff);
  background: #f0f7ff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.12);
}

.script-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.check-box {
  width: 18px;
  height: 18px;
  border: 2px solid #c0c4cc;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
  font-size: 11px;
  color: #fff;
}

.script-card.selected .check-box {
  background: var(--primary-color, #409eff);
  border-color: var(--primary-color, #409eff);
}

.script-card:not(.selected) .check-box i {
  display: none;
}

.script-card-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #303133);
}

.script-card-body {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.script-card-dbs {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.collapse-title {
  display: flex;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
}

.no-params {
  text-align: center;
  padding: 20px 0;
  color: var(--text-muted, #909399);
  font-size: 14px;
}

.neq-param-control {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
}

.neq-param-label {
  font-size: 13px;
  color: var(--text-regular, #606266);
  font-weight: 500;
}

.neq-param-value {
  font-size: 14px;
  color: var(--text-primary, #303133);
  font-weight: 600;
  font-family: monospace;
}

.shared-params-section {
  margin-bottom: 24px;
}

.unique-params-section {
  margin-top: 10px;
}

.params-section-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 2px solid #eef2f7;
}

.params-section-title i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
  font-size: 16px;
}

.params-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.shared-params-card {
  border-left: 3px solid #67c23a;
}

.param-item {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 12px 14px;
  transition: box-shadow 0.2s;
}

.param-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.param-item-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.param-name-tag {
  display: inline-block;
  background: #ecf5ff;
  color: var(--primary-color, #409eff);
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
}

.param-item-control {
  width: 100%;
}

.unique-params-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.script-params-block {
  border-left: 3px solid var(--primary-color, #409eff);
  border-radius: 0 8px 8px 0;
  overflow: hidden;
}

.script-params-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f0f7ff;
  border-bottom: 1px solid #e4edf8;
}

.script-params-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #303133);
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-item {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 16px 18px;
  transition: box-shadow 0.2s;
}

.summary-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.summary-item-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.summary-item-name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary, #303133);
}

.summary-item-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.summary-label {
  font-size: 13px;
  color: var(--text-muted, #909399);
  white-space: nowrap;
  min-width: 80px;
  line-height: 24px;
}

.summary-value {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  font-size: 13px;
  line-height: 24px;
}

.params-summary {
  margin-top: 16px;
}

.execute-area {
  display: flex;
  justify-content: center;
  margin-top: 30px;
}

.progress-area {
  margin-top: 20px;
}

.executing-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 0;
}

.spinner-ring {
  width: 28px;
  height: 28px;
  border: 3px solid #e4e7ed;
  border-top-color: var(--primary-color, #409eff);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner-text {
  font-size: 15px;
  color: var(--primary-color, #409eff);
  font-weight: 600;
  letter-spacing: 1px;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}

.status-detail {
  font-size: 14px;
  color: #606266;
}

.status-detail.success {
  color: #67c23a;
}

.status-detail.danger {
  color: #f56c6c;
}

.log-area {
  margin-top: 20px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--table-header-bg, #f5f7fa);
  border-bottom: 1px solid #dcdfe6;
  font-size: 14px;
  font-weight: 600;
}

.log-content {
  height: 200px;
  overflow-y: auto;
  padding: 8px 12px;
  background: #1e1e1e;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

.log-line {
  color: #d4d4d4;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-line.error { color: #f56c6c; }
.log-line.warning { color: #e6a23c; }
.log-line.success { color: #67c23a; }

.download-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 20px;
  gap: 10px;
}

.retry-area {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.retention-tip {
  font-size: 13px;
  color: #e6a23c;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
