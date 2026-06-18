<template>
  <div class="query-executor">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-play-circle"></i> 查询执行</span>
        </div>
      </template>

      <el-steps :active="currentStep" finish-status="success" align-center class="steps">
        <el-step title="上传文件" />
        <el-step title="选择查询选项" />
        <el-step title="配置选项" />
        <el-step title="执行查询" />
      </el-steps>

      <div class="step-content">
        <div v-if="currentStep === 0" class="step-panel">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.xls"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :file-list="fileList"
            drag
            class="upload-area"
          >
            <i class="fas fa-cloud-upload-alt" style="font-size: 48px; color: #c0c4cc"></i>
            <div style="margin-top: 12px; font-size: 15px">将Excel文件拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">仅支持 .xlsx / .xls 文件</div>
            </template>
          </el-upload>

          <div v-if="uploadedFileInfo" class="file-info-card">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="文件名">{{ uploadedFileInfo.name }}</el-descriptions-item>
              <el-descriptions-item label="大小">{{ formatSize(uploadedFileInfo.size) }}</el-descriptions-item>
            </el-descriptions>
            <div v-if="detectedColumns.length > 0" style="margin-top: 12px">
              <span style="font-size: 13px; color: #909399; margin-right: 8px">检测到的列:</span>
              <el-tag v-for="col in detectedColumns" :key="col" size="small" type="primary" style="margin: 2px 4px">{{ col }}</el-tag>
            </div>
          </div>

          <div class="step-actions">
            <el-button type="primary" :disabled="!uploadedFile" @click="afterUpload">下一步</el-button>
          </div>
        </div>

        <div v-if="currentStep === 1" class="step-panel">
          <div class="select-all-bar">
            <el-button size="small" @click="selectAllScripts">全选</el-button>
            <el-button size="small" @click="deselectAllScripts">取消全选</el-button>
            <span class="selected-count">已选择 {{ selectedScriptIds.length }} 个查询选项</span>
          </div>
          <div class="script-card-grid">
            <el-tooltip
              v-for="s in visibleScripts"
              :key="s.id"
              :content="s.description || '暂无描述'"
              placement="top"
              :show-after="300"
            >
              <div
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
                  <el-tag :type="s.query_mode === 'in' ? 'primary' : 'success'" size="small">
                    {{ s.query_mode === 'in' ? '批量' : '逐行' }}
                  </el-tag>
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
                <div v-if="s.description" class="script-card-desc">{{ s.description }}</div>
              </div>
            </el-tooltip>
          </div>
          <el-empty v-if="visibleScripts.length === 0" description="暂无查询选项，请先在查询选项管理中创建" />
          <div class="step-actions">
            <el-button @click="currentStep = 0">上一步</el-button>
            <el-button type="primary" :disabled="selectedScriptIds.length === 0" @click="goToStep2">下一步</el-button>
          </div>
        </div>

        <div v-if="currentStep === 2" class="step-panel">
          <el-form label-width="130px">
            <el-form-item label="参数列">
              <el-select v-model="options.param_column" placeholder="请选择参数列" style="width: 100%">
                <el-option v-for="col in detectedColumns" :key="col" :label="col" :value="col" />
              </el-select>
            </el-form-item>
            <el-form-item label="自动新建工作表">
              <el-switch v-model="options.new_sheet" active-text="开" inactive-text="关" />
            </el-form-item>

            <template v-if="!options.new_sheet">
              <el-divider content-position="left">列映射配置</el-divider>
              <div class="column-mapping-config">
                <div v-for="field in sqlFields" :key="field" class="mapping-row">
                  <span class="mapping-sql-field">{{ field }}</span>
                  <span class="mapping-arrow"><i class="fas fa-arrow-right"></i></span>
                  <el-select
                    v-model="columnMapping[field]"
                    placeholder="选择Excel列"
                    style="width: 200px"
                    :disabled="hiddenFields[field]"
                  >
                    <el-option v-for="col in detectedColumns" :key="col" :label="col" :value="col" />
                  </el-select>
                  <el-checkbox v-model="hiddenFields[field]" class="mapping-hidden" @change="onHiddenChange(field)">隐藏</el-checkbox>
                  <el-radio v-model="primaryKey" :value="field" class="mapping-pk" :disabled="hiddenFields[field]">主键</el-radio>
                </div>
              </div>
            </template>
          </el-form>
          <div class="step-actions">
            <el-button @click="currentStep = 1">上一步</el-button>
            <el-button type="primary" @click="goToStep3">下一步</el-button>
          </div>
        </div>

        <div v-if="currentStep === 3" class="step-panel">
          <el-descriptions title="执行摘要" :column="2" border>
            <el-descriptions-item label="查询选项">{{ selectedScriptNames || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联数据库">{{ associatedDbNames || '-' }}</el-descriptions-item>
            <el-descriptions-item label="文件">{{ uploadedFile?.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="参数列">{{ options.param_column || '-' }}</el-descriptions-item>
            <el-descriptions-item label="自动新建工作表">{{ options.new_sheet ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item v-if="!options.new_sheet && primaryKey" label="主键字段">{{ primaryKey }}</el-descriptions-item>
          </el-descriptions>

          <div v-if="!options.new_sheet && Object.keys(columnMapping).length > 0" class="mapping-summary">
            <el-divider content-position="left">列映射概览</el-divider>
            <el-table :data="mappingSummaryData" border size="small" style="max-width: 500px">
              <el-table-column prop="sqlField" label="SQL字段" width="180" />
              <el-table-column prop="excelCol" label="Excel列" width="180" />
              <el-table-column prop="isHidden" label="隐藏" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.isHidden ? 'danger' : 'success'" size="small">{{ row.isHidden ? '是' : '否' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="isPk" label="主键" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.isPk" type="warning" size="small">是</el-tag>
                  <span v-else>-</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="execute-area">
            <el-button
              v-if="!executing && !taskId"
              type="success"
              size="large"
              @click="executeQuery"
              :loading="submitting"
            >
              <i class="fas fa-play"></i> 开始执行
            </el-button>
            <el-button v-if="executing" type="danger" size="large" @click="cancelQuery">
              <i class="fas fa-stop"></i> 取消执行
            </el-button>
          </div>

          <div v-if="taskId" class="progress-area">
            <div v-if="executing" class="executing-indicator">
              <div class="spinner-ring"></div>
              <span class="spinner-text">查询执行中...</span>
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

            <div v-if="taskStatus.status === 'completed'" class="download-area">
              <el-button type="primary" size="large" @click="downloadResult">
                <i class="fas fa-download"></i> 下载结果文件
              </el-button>
              <div class="retention-tip">
                <i class="fas fa-exclamation-triangle"></i> 结果文件将保留 {{ fileRetentionHours }} 小时，请及时下载
              </div>
            </div>

            <div v-if="taskStatus.status === 'failed' || taskStatus.status === 'cancelled'" class="retry-area">
              <el-button type="warning" size="large" :loading="retrying" @click="handleRetry">
                <i class="fas fa-redo"></i> 重新执行
              </el-button>
            </div>
          </div>

          <div class="step-actions" style="margin-top: 20px">
            <el-button @click="currentStep = 2" :disabled="!!taskId">上一步</el-button>
            <el-button @click="resetAll" :disabled="executing">重新开始</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="matchDialogVisible"
      title="智能匹配"
      width="520px"
      :close-on-click-modal="false"
    >
      <div class="match-dialog-content">
        <div class="match-icon"><i class="fas fa-magic"></i></div>
        <p class="match-tip">根据文件名 <strong>{{ uploadedFileInfo?.name }}</strong> 匹配到以下查询选项：</p>
        <div class="match-list">
          <div v-for="s in matchedScripts" :key="s.id" class="match-item">
            <el-tag size="small" type="info" style="margin-right: 6px">{{ s.tag }}</el-tag>
            <span>{{ s.name }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="cancelMatch">取消，手动选择</el-button>
        <el-button type="primary" @click="confirmMatch">确认使用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useAppStore()

const visibleScripts = computed(() => {
  const scriptIds = store.getUserScriptIds()
  const base = store.scripts.filter((s) => s.type === 'query')
  if (scriptIds.length === 0) return base
  return base.filter((s) => scriptIds.includes(s.id))
})
const currentStep = ref(0)
const selectedScriptIds = ref([])
const uploadedFile = ref(null)
const uploadedFileInfo = ref(null)
const detectedColumns = ref([])
const uploadRef = ref(null)
const fileList = ref([])
const submitting = ref(false)
const executing = ref(false)
const taskId = ref(null)
const progress = ref(0)
const taskStatus = ref({})
const directMode = ref(false)
const logLines = ref([])
const logContentRef = ref(null)
const retrying = ref(false)
let eventSource = null

const matchDialogVisible = ref(false)
const matchedScripts = ref([])
const matchedDefaultParamColumn = ref([])
const fileRetentionHours = ref(24)

const options = reactive({
  param_column: '',
  new_sheet: true
})

const sqlFields = ref([])
const columnMapping = reactive({})
const hiddenFields = reactive({})
const primaryKey = ref('')


const selectedScriptNames = computed(() => {
  return visibleScripts.value
    .filter((s) => selectedScriptIds.value.includes(s.id))
    .map((s) => s.name)
    .join(', ')
})

const associatedDbIds = computed(() => {
  const ids = new Set()
  visibleScripts.value
    .filter((s) => selectedScriptIds.value.includes(s.id))
    .forEach((s) => {
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

const mappingSummaryData = computed(() => {
  return sqlFields.value.map((field) => ({
    sqlField: field,
    excelCol: hiddenFields[field] ? '隐藏' : (columnMapping[field] || '-'),
    isHidden: !!hiddenFields[field],
    isPk: primaryKey.value === field
  }))
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

function onHiddenChange(field) {
  if (hiddenFields[field] && primaryKey.value === field) {
    primaryKey.value = ''
  }
}

function onFileChange(file) {
  uploadedFile.value = file.raw
  uploadedFileInfo.value = { name: file.name, size: file.size }
  fileList.value = [file]
  detectedColumns.value = []
  // 文件上传完成后自动触发智能匹配
  autoSmartMatch(file.name)
}

function onFileRemove() {
  uploadedFile.value = null
  uploadedFileInfo.value = null
  fileList.value = []
  detectedColumns.value = []
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

async function autoSmartMatch(filename) {
  // 先解析上传文件信息
  await fetchUploadInfo()

  try {
    const res = await api.query.smartMatch(filename)
    const ids = res.matched_script_ids || []
    const scripts = res.matched_scripts || []

    if (ids.length > 0) {
      matchedScripts.value = scripts
      matchedDefaultParamColumn.value = res.default_param_column || []
      const isDirect = res.direct === true

      if (isDirect) {
        // direct模式：不弹窗，直接自动确认并执行
        await directConfirmAndExecute()
      } else {
        // 非direct模式：弹窗让用户确认
        matchDialogVisible.value = true
      }
    }
    // 未匹配到不弹窗，用户点"下一步"正常进入手动选择
  } catch {
    // 匹配失败不影响流程
  }
}

async function directConfirmAndExecute() {
  // 自动确认匹配结果，设置选中项
  selectedScriptIds.value = matchedScripts.value.map((s) => s.id)
  matchDialogVisible.value = false
  currentStep.value = 2
  await loadSqlFields()

  const scripts = selectedScriptIds.value.map(id => visibleScripts.value.find(s => s.id === id)).filter(Boolean)
  if (scripts.length === 0) return

  const firstNewSheet = scripts[0].new_sheet
  const firstPrimaryKey = scripts[0].primary_key || ''
  const allSameConfig = scripts.every(s => s.new_sheet === firstNewSheet && (s.primary_key || '') === firstPrimaryKey)

  if (allSameConfig) {
    options.new_sheet = firstNewSheet
    if (!firstNewSheet && firstPrimaryKey) {
      primaryKey.value = firstPrimaryKey
    }
  } else {
    options.new_sheet = firstNewSheet
    if (!firstNewSheet && firstPrimaryKey) {
      primaryKey.value = firstPrimaryKey
    }
  }

  // 设置默认参数列
  if (matchedDefaultParamColumn.value.length > 0 && !options.param_column) {
    for (const kw of matchedDefaultParamColumn.value) {
      const found = detectedColumns.value.find(c => c.includes(kw))
      if (found) {
        options.param_column = found
        break
      }
    }
  }

  // 跳到最后一步并触发执行
  if (options.param_column) {
    currentStep.value = 3
    await nextTick()
    directMode.value = true
    executeQuery()
  }
}

async function afterUpload() {
  if (!uploadedFile.value) {
    ElMessage.warning('请先上传Excel文件')
    return
  }

  // 如果已经有智能匹配结果且弹窗已显示，不需要再处理
  if (matchDialogVisible.value) return

  // 如果还没解析文件信息，先解析
  if (detectedColumns.value.length === 0) {
    await fetchUploadInfo()
  }

  // 直接进入手动选择步骤
  currentStep.value = 1
}

async function confirmMatch() {
  selectedScriptIds.value = matchedScripts.value.map((s) => s.id)
  matchDialogVisible.value = false
  currentStep.value = 2
  await loadSqlFields()

  const scripts = selectedScriptIds.value.map(id => visibleScripts.value.find(s => s.id === id)).filter(Boolean)
  if (scripts.length === 0) return

  const firstNewSheet = scripts[0].new_sheet
  const firstPrimaryKey = scripts[0].primary_key || ''
  const allSameConfig = scripts.every(s => s.new_sheet === firstNewSheet && (s.primary_key || '') === firstPrimaryKey)

  if (allSameConfig && options.param_column) {
    options.new_sheet = firstNewSheet
    if (!firstNewSheet && firstPrimaryKey) {
      primaryKey.value = firstPrimaryKey
    }
    currentStep.value = 3
    await nextTick()
    executeQuery()
  } else if (!allSameConfig) {
    // 多个查询选项配置不一致时，也尝试应用第一个的主键配置
    options.new_sheet = firstNewSheet
    if (!firstNewSheet && firstPrimaryKey) {
      primaryKey.value = firstPrimaryKey
    }
  }
}

function cancelMatch() {
  matchDialogVisible.value = false
  currentStep.value = 1
}

async function goToStep2() {
  if (selectedScriptIds.value.length === 0) {
    ElMessage.warning('请至少选择一个查询选项')
    return
  }
  matchedDefaultParamColumn.value = []
  currentStep.value = 2
  await loadSqlFields()

  const scripts = selectedScriptIds.value.map(id => visibleScripts.value.find(s => s.id === id)).filter(Boolean)
  if (scripts.length === 0) return

  const firstNewSheet = scripts[0].new_sheet
  const firstPrimaryKey = scripts[0].primary_key || ''
  const allSameConfig = scripts.every(s => s.new_sheet === firstNewSheet && (s.primary_key || '') === firstPrimaryKey)

  // 手动选择查询选项时，自动填充配置值但不自动触发执行
  if (allSameConfig) {
    options.new_sheet = firstNewSheet
    if (!firstNewSheet && firstPrimaryKey) {
      primaryKey.value = firstPrimaryKey
    }
  } else {
    options.new_sheet = firstNewSheet
    if (!firstNewSheet && firstPrimaryKey) {
      primaryKey.value = firstPrimaryKey
    }
  }
}

function goToStep3() {
  if (!options.param_column) {
    ElMessage.warning('请选择参数列')
    return
  }
  currentStep.value = 3
}

async function fetchUploadInfo() {
  try {
    const formData = new FormData()
    formData.append('file', uploadedFile.value)
    const res = await api.query.uploadInfo(formData)
    if (res.columns && Array.isArray(res.columns)) {
      detectedColumns.value = res.columns
    } else if (res.data && res.data.column_names && Array.isArray(res.data.column_names)) {
      detectedColumns.value = res.data.column_names
    } else if (res.data && res.data.columns && Array.isArray(res.data.columns)) {
      detectedColumns.value = res.data.columns
    }
  } catch {
    detectedColumns.value = []
  }
}

async function loadSqlFields() {
  const firstScript = visibleScripts.value.find((s) => s.id === selectedScriptIds.value[0])
  if (!firstScript) return

  try {
    // 如果是模板模式，先渲染模板再提取字段
    let sqlToExtract = firstScript.sql_text
    if (firstScript.is_template && firstScript.sql_template) {
      try {
        const renderRes = await api.scripts.renderTemplate({
          template: firstScript.sql_template,
          template_config: firstScript.template_config || []
        })
        if (renderRes.success && renderRes.rendered_sql) {
          sqlToExtract = renderRes.rendered_sql
        }
      } catch {}
    }
    const res = await api.scripts.extractColumns({ sql: sqlToExtract })
    const fields = res.columns || []
    sqlFields.value = fields

    Object.keys(columnMapping).forEach((k) => delete columnMapping[k])
    Object.keys(hiddenFields).forEach((k) => delete hiddenFields[k])
    primaryKey.value = ''

    fields.forEach((f) => {
      columnMapping[f] = ''
      hiddenFields[f] = false
    })

    if (matchedDefaultParamColumn.value.length > 0) {
      const matched = matchedDefaultParamColumn.value.find(kw =>
        detectedColumns.value.some(col => col.includes(kw))
      )
      if (matched) {
        options.param_column = detectedColumns.value.find(col => col.includes(matched))
      } else if (detectedColumns.value.length > 0) {
        options.param_column = detectedColumns.value[0]
      }
    } else if (detectedColumns.value.length > 0) {
      options.param_column = detectedColumns.value[0]
    }

    autoMapColumns()
  } catch {
    sqlFields.value = []
  }
}

async function autoMapColumns() {
  // 先做简单匹配（忽略大小写和空格）
  sqlFields.value.forEach((field) => {
    const lowerField = field.toLowerCase()
    const match = detectedColumns.value.find(
      (col) => col.toLowerCase() === lowerField || col.toLowerCase().replace(/\s+/g, '') === lowerField.replace(/\s+/g, '')
    )
    if (match) {
      columnMapping[field] = match
    }
  })

  // 对未匹配的字段调用后端模糊匹配API
  const unmapped = sqlFields.value.filter(f => !columnMapping[f])
  if (unmapped.length > 0 && detectedColumns.value.length > 0) {
    try {
      const res = await api.query.fuzzyMatchColumns({
        sql_fields: unmapped,
        excel_columns: detectedColumns.value
      })
      const fuzzyMapping = res.mapping || {}
      for (const [sqlField, excelCol] of Object.entries(fuzzyMapping)) {
        if (excelCol && !columnMapping[sqlField]) {
          columnMapping[sqlField] = excelCol
        }
      }
    } catch {
      // 模糊匹配失败不影响流程
    }
  }
}

function buildColumnMappingPayload() {
  const mapping = {}
  sqlFields.value.forEach((field) => {
    if (hiddenFields[field]) {
      mapping[field] = '隐藏'
    } else if (columnMapping[field]) {
      mapping[field] = columnMapping[field]
    }
  })
  return mapping
}

async function executeQuery() {
  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('script_ids', JSON.stringify(selectedScriptIds.value))
    formData.append('file', uploadedFile.value)
    formData.append('param_column', options.param_column)
    formData.append('new_sheet', options.new_sheet)

    if (!options.new_sheet) {
      const mapping = buildColumnMappingPayload()
      formData.append('column_mapping', JSON.stringify(mapping))
      if (primaryKey.value) {
        formData.append('primary_key', primaryKey.value)
      }
    }

    const res = await api.query.execute(formData)
    const data = res.data || res
    taskId.value = data.task_id || data.id
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
  const url = api.query.streamStatus(tid)
  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      taskStatus.value = data
      if (data.progress !== undefined) {
        progress.value = Math.round(data.progress)
      }
      if (data.new_logs && data.new_logs.length > 0) {
        data.new_logs.forEach(log => {
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
        // direct模式执行完成后自动下载
        if (data.status === 'completed' && directMode.value) {
          directMode.value = false
          nextTick(() => {
            downloadResult()
          })
        }
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
    const res = await api.query.status(tid)
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

async function cancelQuery() {
  if (!taskId.value) return
  try {
    await ElMessageBox.confirm('确定要取消当前执行任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.query.cancel(taskId.value)
    ElMessage.success('已发送取消请求')
  } catch {
  }
}

async function handleRetry() {
  if (!taskId.value) return
  retrying.value = true
  try {
    const res = await api.query.retry(taskId.value)
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
  const defaultName = `result_${taskId.value}.xlsx`
  try {
    const check = await fetch(url, { method: 'HEAD' })
    if (!check.ok) {
      const data = await check.json().catch(() => ({}))
      ElMessageBox.alert(data.message || '结果文件不存在或已被清理', '提示', { type: 'warning' })
      return
    }
    if (window.showSaveFilePicker) {
      const handle = await window.showSaveFilePicker({
        suggestedName: defaultName,
        types: [{ description: 'Excel文件', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }]
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
  uploadedFile.value = null
  uploadedFileInfo.value = null
  detectedColumns.value = []
  fileList.value = []
  taskId.value = null
  executing.value = false
  progress.value = 0
  taskStatus.value = {}
  directMode.value = false
  logLines.value = []
  options.param_column = ''
  options.new_sheet = true
  sqlFields.value = []
  Object.keys(columnMapping).forEach((k) => delete columnMapping[k])
  Object.keys(hiddenFields).forEach((k) => delete hiddenFields[k])
  primaryKey.value = ''
  matchedScripts.value = []
  matchedDefaultParamColumn.value = []
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

async function fetchClientConfig() {
  try {
    const res = await api.query.config()
    const data = res.data || res || {}
    fileRetentionHours.value = data.file_retention_hours || 24
  } catch {
  }
}

onMounted(() => {
  store.fetchScripts()
  store.fetchDatabases()
  fetchClientConfig()
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})
</script>

<style scoped>
.query-executor {
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

.upload-area {
  margin-bottom: 16px;
}

.upload-area :deep(.el-upload-dragger) {
  padding: 40px 20px;
  border-radius: 12px;
}

.file-info-card {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 16px;
  margin-top: 16px;
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

.script-card-desc {
  font-size: 12px;
  color: var(--text-muted, #909399);
  margin-top: 6px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.column-mapping-config {
  padding: 0 0 0 130px;
}

.mapping-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.mapping-sql-field {
  min-width: 140px;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #303133);
  text-align: right;
}

.mapping-arrow {
  color: var(--text-muted, #909399);
  font-size: 14px;
}

.mapping-hidden {
  margin-left: 8px;
}

.mapping-pk {
  margin-left: 4px;
}

.mapping-summary {
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

.match-dialog-content {
  text-align: center;
  padding: 10px 0;
}

.match-icon {
  font-size: 40px;
  color: var(--primary-color, #409eff);
  margin-bottom: 16px;
}

.match-tip {
  font-size: 15px;
  color: #606266;
  margin-bottom: 20px;
  line-height: 1.6;
}

.match-list {
  text-align: left;
  background: #f0f7ff;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  padding: 12px 16px;
}

.match-item {
  padding: 6px 0;
  font-size: 14px;
  color: var(--text-primary, #303133);
}
</style>
