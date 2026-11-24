<template>
  <div class="query-executor">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-play-circle"></i> 查询执行</span>
        </div>
      </template>

      <el-steps :active="currentStep" finish-status="success" align-center class="steps">
        <el-step title="上传文件与选择查询任务" />
        <el-step :title="isPerFileMode ? '逐文件配置' : '配置选项'" />
        <el-step title="执行查询" />
      </el-steps>

      <div class="step-content">
        <div v-if="currentStep === 0" class="step-panel">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            multiple
            accept=".xlsx,.xls"
            :on-change="onFileChange"
            :show-file-list="false"
            drag
            class="upload-area"
          >
            <i class="fas fa-cloud-upload-alt" style="font-size: 48px; color: #c0c4cc"></i>
            <div style="margin-top: 12px; font-size: 15px">将Excel文件拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持一次选择多个 .xlsx / .xls 文件，逐个解析</div>
            </template>
          </el-upload>

          <div v-if="uploadFiles.length" class="file-info-card">
            <div class="parse-header">
              <span class="parse-title">解析结果（{{ uploadFiles.length }} 个文件）</span>
              <div>
                <el-button size="small" text type="primary" @click="toggleAllParse">{{ allExpanded ? '全部收起' : '全部展开' }}</el-button>
                <el-button size="small" text @click="clearUploadFiles">清空文件</el-button>
              </div>
            </div>
            <div class="parse-list">
              <el-collapse v-model="expandedFileUids">
                <el-collapse-item v-for="f in uploadFiles" :key="f.uid" :name="f.uid">
                  <template #title>
                    <div class="parse-file-title">
                      <i class="fas fa-file-excel parse-file-icon"></i>
                      <span class="parse-file-name">{{ f.name }}</span>
                      <span class="parse-file-size">{{ formatSize(f.size) }}</span>
                      <el-tag v-if="f.parsing" size="small" type="warning">解析中...</el-tag>
                      <el-tag v-else-if="f.error" size="small" type="danger">解析失败</el-tag>
                      <el-tag v-else-if="f.sheets.length" size="small" type="success">
                        {{ f.sheets.length }} 个工作表 · 已选 {{ f.selectedSheets.length }}
                      </el-tag>
                      <el-tag v-else size="small" type="info">未解析到工作表</el-tag>
                      <el-button class="parse-file-remove" size="small" text type="danger" @click.stop="removeUploadFile(f)">
                        <i class="fas fa-times"></i> 移除
                      </el-button>
                    </div>
                  </template>
                  <div v-if="f.error" class="parse-error">{{ f.error }}</div>
                  <template v-else-if="f.sheets.length">
                    <div class="sheet-head">
                      <span>工作表</span>
                      <div>
                        <el-button size="small" text type="primary" @click="selectAllSheets(f)">全选</el-button>
                        <el-button size="small" text @click="deselectAllSheets(f)">取消全选</el-button>
                      </div>
                    </div>
                    <el-checkbox-group v-model="f.selectedSheets" class="sheet-list" @change="onSheetsChange">
                      <div v-for="s in f.sheets" :key="s.sheet_name" class="sheet-row">
                        <el-checkbox :value="s.sheet_name">
                          <span class="sheet-name">{{ s.sheet_name }}</span>
                        </el-checkbox>
                        <span class="sheet-rows">{{ s.data_rows }} 行</span>
                        <div class="sheet-cols">
                          <el-tag v-for="col in (s.column_names || []).slice(0, 6)" :key="col" size="small" type="primary" style="margin: 1px 3px">{{ col }}</el-tag>
                          <el-tag v-if="(s.column_names || []).length > 6" size="small" type="info" style="margin: 1px 3px">+{{ s.column_names.length - 6 }}</el-tag>
                        </div>
                      </div>
                    </el-checkbox-group>
                  </template>
                  <div v-else class="parse-empty">未检测到有数据的工作表，执行时将使用该文件中的全部工作表</div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>

          <!-- 解析完成后直接选择查询任务：列一致的文件共用一次选择，列不一致时按文件分组分别选择 -->
          <div v-if="uploadFiles.length && canProceed" class="query-select-section">
            <div class="parse-header">
              <span class="parse-title">选择查询任务</span>
              <span class="select-hint" v-if="isPerFileMode">
                检测到文件的列不一致，已按列分组，{{ fileGroups.length }} 组分别选择
              </span>
              <span class="select-hint" v-else>文件的列一致，统一选择一次</span>
            </div>

            <!-- 统一模式：所有文件合并执行 -->
            <div v-if="!isPerFileMode" class="per-file-script-list">
              <div class="per-file-script-row">
                <div class="per-file-meta">
                  <i class="fas fa-list-check"></i>
                  <span class="per-file-name">{{ fileGroups.length ? groupFileNames(fileGroups[0]) : '' }}</span>
                  <span class="per-file-cols">{{ fileGroups.length ? groupColumnsSummary(fileGroups[0]) : '' }}</span>
                </div>
                <div class="per-file-select-row">
                  <el-select
                    v-model="selectionTag"
                    placeholder="选择标签"
                    style="width: 180px"
                    @change="onUnifiedTagChange"
                  >
                    <el-option v-for="t in scriptTagOptions" :key="t" :label="t" :value="t" />
                  </el-select>
                  <el-select
                    v-model="selectedScriptIds"
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    :disabled="!selectionTag"
                    placeholder="选择该标签下的查询选项"
                    style="flex: 1; min-width: 220px"
                  >
                    <el-option v-for="s in scriptsUnderTag(selectionTag)" :key="s.id" :label="s.name" :value="s.id" />
                  </el-select>
                  <el-button size="small" :disabled="!selectionTag" @click="selectAllUnified">全选</el-button>
                  <el-button size="small" :disabled="!selectedScriptIds.length" @click="clearUnified">全不选</el-button>
                </div>
              </div>
            </div>

            <!-- 逐文件模式：同列文件归为一组，每组选择一次 -->
            <div v-else class="per-file-script-list">
              <div v-for="g in fileGroups" :key="g.sig" class="per-file-script-row">
                <div class="per-file-meta">
                  <i class="fas fa-file-excel"></i>
                  <span class="per-file-name">{{ groupFileNames(g) }}</span>
                  <span class="per-file-cols">{{ groupColumnsSummary(g) }}</span>
                </div>
                <div class="per-file-select-row">
                  <el-select
                    v-model="g.lead.tag"
                    placeholder="选择标签"
                    style="width: 180px"
                    @change="onGroupTagChange(g)"
                  >
                    <el-option v-for="t in scriptTagOptions" :key="t" :label="t" :value="t" />
                  </el-select>
                  <el-select
                    v-model="g.lead.scriptIds"
                    multiple
                    collapse-tags
                    collapse-tags-tooltip
                    :disabled="!g.lead.tag"
                    placeholder="选择该标签下的查询选项"
                    style="flex: 1; min-width: 220px"
                    @change="syncGroupSelection(g)"
                  >
                    <el-option
                      v-for="s in scriptsUnderTag(g.lead.tag)"
                      :key="s.id"
                      :label="s.name"
                      :value="s.id"
                    />
                  </el-select>
                  <el-button size="small" :disabled="!g.lead.tag" @click="selectAllUnderTag(g.lead); syncGroupSelection(g)">全选</el-button>
                  <el-button size="small" :disabled="!g.lead.scriptIds || !g.lead.scriptIds.length" @click="clearUnderTag(g.lead); syncGroupSelection(g)">全不选</el-button>
                </div>
              </div>
            </div>

            <el-empty v-if="visibleScripts.length === 0" description="暂无查询选项，请先在查询选项管理中创建" />
          </div>

          <div class="step-actions">
            <el-button
              type="primary"
              :disabled="!canProceed || (isPerFileMode ? !perFileScriptReady : selectedScriptIds.length === 0)"
              @click="afterUpload"
            >
              下一步
            </el-button>
          </div>
        </div>

        <div v-if="currentStep === 1" class="step-panel">
          <!-- 统一模式：一份配置应用于所有文件（合并后统一查询） -->
          <template v-if="!isPerFileMode">
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
          </template>

          <!-- 逐文件模式：每个文件分别配置参数列与列映射 -->
          <template v-else>
            <div class="per-file-config-list">
              <div v-for="f in uploadFiles" :key="f.uid" class="per-file-config-card">
                <div class="per-file-config-head">
                  <i class="fas fa-file-excel"></i>
                  <span class="per-file-name">{{ f.name }}</span>
                  <el-tag size="small" type="info">{{ selectedScriptNamesOf(f) || '未选择查询选项' }}</el-tag>
                </div>
                <el-form label-width="130px">
                  <el-form-item label="参数列">
                    <el-select v-model="f.paramColumn" placeholder="请选择参数列" style="width: 100%">
                      <el-option v-for="col in fileDetectedColumns(f)" :key="col" :label="col" :value="col" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="自动新建工作表">
                    <el-switch v-model="f.newSheet" active-text="开" inactive-text="关" />
                  </el-form-item>

                  <template v-if="!f.newSheet">
                    <el-divider content-position="left">列映射配置</el-divider>
                    <div class="column-mapping-config">
                      <div v-for="field in f.sqlFields" :key="field" class="mapping-row">
                        <span class="mapping-sql-field">{{ field }}</span>
                        <span class="mapping-arrow"><i class="fas fa-arrow-right"></i></span>
                        <el-select
                          v-model="f.columnMapping[field]"
                          placeholder="选择Excel列"
                          style="width: 200px"
                          :disabled="f.hiddenFields[field]"
                        >
                          <el-option v-for="col in fileDetectedColumns(f)" :key="col" :label="col" :value="col" />
                        </el-select>
                        <el-checkbox v-model="f.hiddenFields[field]" class="mapping-hidden" @change="onPerFileHiddenChange(f, field)">隐藏</el-checkbox>
                        <el-radio v-model="f.primaryKey" :value="field" class="mapping-pk" :disabled="f.hiddenFields[field]">主键</el-radio>
                      </div>
                    </div>
                  </template>
                </el-form>
              </div>
            </div>
          </template>

          <div class="step-actions">
            <el-button @click="currentStep = 0">上一步</el-button>
            <el-button type="primary" @click="goToExecute">下一步</el-button>
          </div>
        </div>

        <div v-if="currentStep === 2" class="step-panel">
          <!-- 统一模式：所有文件合并执行，产出一个结果文件 -->
          <template v-if="!isPerFileMode">
            <el-descriptions title="执行摘要" :column="2" border>
            <el-descriptions-item label="查询选项">{{ selectedScriptNames || '-' }}</el-descriptions-item>
            <el-descriptions-item label="关联数据库">{{ associatedDbNames || '-' }}</el-descriptions-item>
            <el-descriptions-item label="文件">{{ uploadFileNames || '-' }}</el-descriptions-item>
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
              <i class="fas fa-stop"></i> 终止任务
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

            <div v-if="taskStatus.status === 'completed' && !taskStatus.output_file" class="download-area">
              <el-alert
                type="warning"
                :closable="false"
                show-icon
                title="本次未查询到匹配的数据，未生成结果文件"
                description="可调整查询条件或参数后重新执行。"
              />
            </div>
            <div v-else-if="taskStatus.status === 'completed'" class="download-area">
              <el-button type="primary" size="large" @click="downloadResult">
                <i class="fas fa-download"></i> 下载结果文件
              </el-button>
              <div class="retention-tip">
                <i class="fas fa-exclamation-triangle"></i> 结果文件将保留 {{ fileRetentionHours }} 小时，请及时下载
              </div>
            </div>

            <div v-if="taskStatus.status === 'failed' || taskStatus.status === 'cancelled' || taskStatus.status === 'manual_cancelled'" class="retry-area">
              <el-button type="warning" size="large" :loading="retrying" @click="handleRetry">
                <i class="fas fa-redo"></i> 重新执行
              </el-button>
            </div>
            </div>
          </template>

          <!-- 逐文件模式：每个文件独立执行，分别产出结果文件 -->
          <template v-else>
            <el-descriptions title="执行摘要" :column="2" border>
              <el-descriptions-item label="执行模式">逐文件独立执行（列不一致）</el-descriptions-item>
              <el-descriptions-item label="文件数">{{ uploadFiles.length }}</el-descriptions-item>
            </el-descriptions>

            <el-table :data="perFileSummaryData" border size="small" style="margin-top: 12px">
              <el-table-column prop="name" label="文件" min-width="200" show-overflow-tooltip />
              <el-table-column prop="scriptNames" label="查询选项" min-width="200" show-overflow-tooltip />
              <el-table-column prop="paramColumn" label="参数列" width="150" show-overflow-tooltip />
              <el-table-column prop="newSheet" label="自动新建工作表" width="130" align="center" />
            </el-table>

            <div class="execute-area">
              <el-button
                v-if="!perFileExecuting && perFileResults.length === 0"
                type="success"
                size="large"
                @click="executeQuery"
              >
                <i class="fas fa-play"></i> 开始执行（{{ uploadFiles.length }} 个文件）
              </el-button>
              <el-button v-if="perFileExecuting" type="danger" size="large" @click="cancelPerFileQueries">
                <i class="fas fa-stop"></i> 终止全部任务
              </el-button>
              <el-button
                v-if="!perFileExecuting && perFileResults.length > 0"
                type="primary"
                size="large"
                @click="executeQuery"
              >
                <i class="fas fa-redo"></i> 重新执行
              </el-button>
            </div>

            <div v-if="perFileResults.length > 0" class="progress-area">
              <el-divider content-position="left">
                执行进度（{{ perFileResults.filter(isPerFileResultFinal).length }}/{{ perFileResults.length }} 个文件已完成）
              </el-divider>
              <div v-for="r in perFileResults" :key="r.uid" class="per-file-result">
                <div class="per-file-result-head">
                  <i class="fas fa-file-excel"></i>
                  <span class="per-file-result-name">{{ r.name }}</span>
                  <el-tag size="small" :type="perFileStatusType(r.status)">{{ perFileStatusLabel(r.status) }}</el-tag>
                </div>
                <el-progress
                  :percentage="r.progress"
                  :status="r.status === 'completed' ? 'success' : (r.status === 'failed' ? 'exception' : undefined)"
                  :stroke-width="10"
                />
                <div class="per-file-result-actions">
                  <el-button
                    v-if="r.status === 'completed' && r.outputFile"
                    size="small"
                    type="primary"
                    @click="downloadPerFileResult(r)"
                  >
                    <i class="fas fa-download"></i> 下载结果
                  </el-button>
                  <span v-else-if="r.status === 'completed'" class="per-file-empty">未查询到匹配数据，未生成结果文件</span>
                  <span v-else-if="r.status === 'failed'" class="per-file-error">{{ r.error || '执行失败' }}</span>
                  <span v-else-if="r.status === 'running'" class="per-file-empty">查询执行中...</span>
                </div>
              </div>
              <div class="retention-tip">
                <i class="fas fa-exclamation-triangle"></i> 结果文件将保留 {{ fileRetentionHours }} 小时，请及时下载
              </div>
            </div>
          </template>

          <div class="step-actions" style="margin-top: 20px">
            <el-button @click="currentStep = 1" :disabled="isPerFileMode ? perFileExecuting : !!taskId">上一步</el-button>
            <el-button @click="resetAll" :disabled="isPerFileMode ? perFileExecuting : executing">重新开始</el-button>
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
        <p class="match-tip">根据文件名 <strong>{{ uploadFileNames }}</strong> 匹配到以下查询选项：</p>
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
import { emitPetEvent } from '../utils/petBus'

const store = useAppStore()

const visibleScripts = computed(() => {
  const scriptIds = store.getUserScriptIds()
  const base = store.scripts.filter((s) => s.type === 'query')
  if (scriptIds.length === 0) return base
  return base.filter((s) => scriptIds.includes(s.id))
})
const currentStep = ref(0)
const selectedScriptIds = ref([])
// 统一模式（单文件或列一致）下的查询任务标签
const selectionTag = ref('')
// 多文件上传：每个文件独立解析，可单独移除、勾选参与任务的工作表
const uploadFiles = ref([])
const expandedFileUids = ref([])
const uploadRef = ref(null)
let fileUidSeq = 0
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
// 逐文件模式（多文件且列不一致）：每个文件独立提交，可能生成多个结果文件
const perFileResults = ref([])
const perFileExecuting = ref(false)
const perFileEventSources = {}
let perFileRetryTimers = {}

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

// 所有已选工作表的列名并集，作为参数列/列映射的可选列
const detectedColumns = computed(() => {
  const cols = []
  uploadFiles.value.forEach((f) => {
    f.sheets.forEach((s) => {
      if (f.selectedSheets.includes(s.sheet_name)) {
        ;(s.column_names || []).forEach((c) => {
          if (c && !cols.includes(c)) cols.push(c)
        })
      }
    })
  })
  return cols
})

const uploadFileNames = computed(() => uploadFiles.value.map((f) => f.name).join(', '))

// 单个文件（按已勾选工作表）解析到的列名并集
function fileDetectedColumns(f) {
  const cols = []
  ;(f.sheets || []).forEach((s) => {
    if (f.selectedSheets.includes(s.sheet_name)) {
      ;(s.column_names || []).forEach((c) => {
        if (c && !cols.includes(c)) cols.push(c)
      })
    }
  })
  return cols
}

// 列签名：忽略大小写、空格与顺序，用于判断多文件之间列是否一致
function fileColumnsSignature(f) {
  const normalized = fileDetectedColumns(f).map((c) => String(c).trim().toLowerCase())
  return [...new Set(normalized)].sort().join('|')
}

// 多文件且解析到的列不一致：改为逐文件选择查询选项、分别配置并分别生成结果
const isPerFileMode = computed(() => {
  if (uploadFiles.value.length <= 1) return false
  return new Set(uploadFiles.value.map(fileColumnsSignature)).size > 1
})

// 按列签名对文件分组：列一致的文件共用一次查询任务选择
const fileGroups = computed(() => {
  const map = new Map()
  uploadFiles.value.forEach((f) => {
    const sig = fileColumnsSignature(f)
    if (!map.has(sig)) map.set(sig, { sig, files: [] })
    map.get(sig).files.push(f)
  })
  return [...map.values()].map((g) => ({ ...g, lead: g.files[0] }))
})

function groupFileNames(g) {
  return g.files.map((f) => f.name).join('、')
}

function groupColumnsSummary(g) {
  return fileColumnsSummary(g.lead)
}

const perFileScriptReady = computed(() =>
  uploadFiles.value.length > 0 && uploadFiles.value.every((f) => (f.scriptIds || []).length > 0)
)

const perFileSummaryData = computed(() =>
  uploadFiles.value.map((f) => ({
    name: f.name,
    scriptNames: selectedScriptNamesOf(f) || '-',
    paramColumn: f.paramColumn || '-',
    newSheet: f.newSheet ? '是' : '否'
  }))
)

const canProceed = computed(() =>
  uploadFiles.value.length > 0 && uploadFiles.value.every((f) => !f.parsing && !f.error)
)

const allExpanded = computed(() =>
  uploadFiles.value.length > 0 && uploadFiles.value.every((f) => expandedFileUids.value.includes(f.uid))
)


const selectedScriptNames = computed(() => {
  return visibleScripts.value
    .filter((s) => selectedScriptIds.value.includes(s.id))
    .map((s) => s.name)
    .join(', ')
})

function selectedScriptNamesOf(f) {
  return visibleScripts.value
    .filter((s) => (f.scriptIds || []).includes(s.id))
    .map((s) => s.name)
    .join(', ')
}

// 逐文件模式：按标签二级联动选择查询选项
const NO_TAG_LABEL = '未分类'
function tagOfScript(s) {
  return (s.tag || '').trim() || NO_TAG_LABEL
}
const scriptTagOptions = computed(() => {
  const tags = []
  visibleScripts.value.forEach((s) => {
    const t = tagOfScript(s)
    if (!tags.includes(t)) tags.push(t)
  })
  return tags
})
function scriptsUnderTag(tag) {
  if (!tag) return []
  return visibleScripts.value.filter((s) => tagOfScript(s) === tag)
}
function onPerFileTagChange(f) {
  // 切换标签后只保留新标签下的已选查询选项
  const ids = scriptsUnderTag(f.tag).map((s) => s.id)
  f.scriptIds = (f.scriptIds || []).filter((id) => ids.includes(id))
}
function selectAllUnderTag(f) {
  f.scriptIds = scriptsUnderTag(f.tag).map((s) => s.id)
}
function clearUnderTag(f) {
  f.scriptIds = []
}

// 统一模式：标签联动选择
function onUnifiedTagChange() {
  const ids = scriptsUnderTag(selectionTag.value).map((s) => s.id)
  selectedScriptIds.value = selectedScriptIds.value.filter((id) => ids.includes(id))
}
function selectAllUnified() {
  selectedScriptIds.value = scriptsUnderTag(selectionTag.value).map((s) => s.id)
}
function clearUnified() {
  selectedScriptIds.value = []
}
// 智能匹配后同步标签，使匹配到的选项在联动列表中可见
function syncUnifiedTagFromSelection() {
  if (!selectedScriptIds.value.length) {
    selectionTag.value = ''
    return
  }
  const first = visibleScripts.value.find((s) => s.id === selectedScriptIds.value[0])
  if (first) {
    selectionTag.value = tagOfScript(first)
    onUnifiedTagChange()
  }
}

// 同列分组：组内选择同步到每个文件
function syncGroupSelection(g) {
  const lead = g.lead
  g.files.forEach((f) => {
    if (f === lead) return
    f.tag = lead.tag
    f.scriptIds = [...(lead.scriptIds || [])]
  })
}
function syncAllGroups() {
  fileGroups.value.forEach(syncGroupSelection)
}
function onGroupTagChange(g) {
  onPerFileTagChange(g.lead)
  syncGroupSelection(g)
}

function fileColumnsSummary(f) {
  const cols = fileDetectedColumns(f)
  if (!cols.length) return '未解析到列'
  return `${cols.length} 列：${cols.slice(0, 5).join('、')}${cols.length > 5 ? ' 等' : ''}`
}

function perFileStatusType(status) {
  const map = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info', manual_cancelled: 'info' }
  return map[status] || 'info'
}

function perFileStatusLabel(status) {
  const map = { pending: '等待中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消', manual_cancelled: '手动终止' }
  return map[status] || status
}

function isPerFileResultFinal(r) {
  return ['completed', 'failed', 'cancelled', 'manual_cancelled'].includes(r.status)
}

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
  const map = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', cancelled: 'info', manual_cancelled: 'info' }
  return map[taskStatus.value.status] || 'info'
})

const statusLabel = computed(() => {
  const map = { pending: '等待中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消', manual_cancelled: '手动终止' }
  return map[taskStatus.value.status] || '-'
})

function onHiddenChange(field) {
  if (hiddenFields[field] && primaryKey.value === field) {
    primaryKey.value = ''
  }
}

async function onFileChange(file) {
  if (!file || !file.raw) return
  // 同一文件（文件名 + 大小）只允许上传一次
  const duplicated = uploadFiles.value.some(
    (f) => f.name === file.name && f.size === file.size
  )
  if (duplicated) {
    ElMessage.warning(`文件 ${file.name} 已上传，请勿重复添加`)
    return
  }
  // 使用 reactive 包装，解析过程中的字段变更才能触发视图更新
  const entry = reactive({
    uid: `f_${Date.now()}_${fileUidSeq++}`,
    name: file.name,
    size: file.size,
    raw: file.raw,
    sheets: [],
    selectedSheets: [],
    parsing: true,
    error: ''
  })
  uploadFiles.value.push(entry)
  expandedFileUids.value.push(entry.uid)
  // 多文件时关闭单文件智能匹配弹窗，避免误入统一配置流程
  if (uploadFiles.value.length > 1) {
    matchDialogVisible.value = false
    matchedScripts.value = []
    matchedDefaultParamColumn.value = []
  }
  await parseUploadFile(entry)
  // 仅单个文件时触发智能匹配弹窗；多文件在下方按列分组选择查询任务
  if (uploadFiles.value.length === 1) {
    autoSmartMatch(entry.name)
  } else {
    uploadFiles.value.forEach(ensurePerFileConfig)
    await prefillPerFileScripts()
  }
}

async function parseUploadFile(entry) {
  entry.parsing = true
  entry.error = ''
  try {
    const formData = new FormData()
    formData.append('file', entry.raw)
    const res = await api.query.uploadInfo(formData)
    entry.sheets = Array.isArray(res.sheets) ? res.sheets : []
    entry.selectedSheets = entry.sheets.map((s) => s.sheet_name)
  } catch (e) {
    entry.sheets = []
    entry.selectedSheets = []
    entry.error = e?.response?.data?.message || '文件解析失败'
  } finally {
    entry.parsing = false
  }
}

function removeUploadFile(entry) {
  uploadFiles.value = uploadFiles.value.filter((f) => f.uid !== entry.uid)
  expandedFileUids.value = expandedFileUids.value.filter((uid) => uid !== entry.uid)
  // 回到单文件时，沿用该文件已选的查询任务
  if (uploadFiles.value.length === 1) {
    const f = uploadFiles.value[0]
    selectedScriptIds.value = [...(f.scriptIds || [])]
    selectionTag.value = f.tag || ''
  }
  resetPerFileState()
}

function clearUploadFiles() {
  uploadFiles.value = []
  expandedFileUids.value = []
  selectedScriptIds.value = []
  selectionTag.value = ''
  resetPerFileState()
}

// 勾选工作表可能改变列签名与分组，重新同步组内选择
async function onSheetsChange() {
  if (uploadFiles.value.length <= 1) return
  if (isPerFileMode.value) {
    uploadFiles.value.forEach(ensurePerFileConfig)
    if (fileGroups.value.some((g) => !(g.lead.scriptIds || []).length)) {
      await prefillPerFileScripts()
      return
    }
  } else if (!selectedScriptIds.value.length) {
    const lead = fileGroups.value[0]?.lead
    if (lead && (lead.scriptIds || []).length) {
      selectedScriptIds.value = [...lead.scriptIds]
      selectionTag.value = lead.tag || ''
    }
  }
  syncAllGroups()
}

function resetPerFileState() {
  perFileExecuting.value = false
  perFileResults.value = []
  Object.values(perFileEventSources).forEach((es) => es.close())
  Object.keys(perFileEventSources).forEach((uid) => delete perFileEventSources[uid])
  Object.values(perFileRetryTimers).forEach((timer) => clearTimeout(timer))
  perFileRetryTimers = {}
}

function toggleAllParse() {
  expandedFileUids.value = allExpanded.value ? [] : uploadFiles.value.map((f) => f.uid)
}

function selectAllSheets(entry) {
  entry.selectedSheets = entry.sheets.map((s) => s.sheet_name)
}

function deselectAllSheets(entry) {
  entry.selectedSheets = []
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

async function autoSmartMatch(filename) {
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
  syncUnifiedTagFromSelection()
  matchDialogVisible.value = false
  currentStep.value = 1
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
    currentStep.value = 2
    await nextTick()
    directMode.value = true
    executeQuery()
  }
}

async function afterUpload() {
  if (!uploadFiles.value.length) {
    ElMessage.warning('请先上传Excel文件')
    return
  }
  if (uploadFiles.value.some((f) => f.parsing)) {
    ElMessage.warning('文件正在解析，请稍候')
    return
  }
  if (uploadFiles.value.some((f) => f.error)) {
    ElMessage.warning('存在解析失败的文件，请移除后再继续')
    return
  }

  // 如果已经有智能匹配结果且弹窗已显示，不需要再处理
  if (matchDialogVisible.value) return

  await goToConfig()
}

// 逐文件模式：为每个分组预填智能匹配到的查询选项（默认取最匹配的一个，用户可修改）
async function prefillPerFileScripts() {
  const leaders = fileGroups.value.map((g) => g.lead)
  await Promise.all(
    leaders.map(async (f) => {
      ensurePerFileConfig(f)
      if ((f.scriptIds || []).length > 0) return
      try {
        const res = await api.query.smartMatch(f.name)
        const ids = (res.matched_script_ids || []).filter((id) =>
          visibleScripts.value.some((s) => s.id === id)
        )
        if (ids.length > 0) {
          const matched = visibleScripts.value.find((s) => s.id === ids[0])
          f.tag = tagOfScript(matched)
          f.scriptIds = [matched.id]
        }
      } catch {
        // 匹配失败不阻塞，用户手动选择
      }
    })
  )
  syncAllGroups()
  // 列一致（统一模式）时，把智能匹配结果带入统一下拉
  if (!isPerFileMode.value) {
    const lead = fileGroups.value[0]?.lead
    if (!selectedScriptIds.value.length && lead && (lead.scriptIds || []).length) {
      selectedScriptIds.value = [...lead.scriptIds]
      selectionTag.value = lead.tag || ''
    }
  }
}

function ensurePerFileConfig(f) {
  if (!f.scriptIds) f.scriptIds = []
  if (f.tag === undefined) f.tag = ''
  if (f.paramColumn === undefined) f.paramColumn = ''
  if (f.newSheet === undefined) f.newSheet = true
  if (!f.sqlFields) f.sqlFields = []
  if (!f.columnMapping) f.columnMapping = {}
  if (!f.hiddenFields) f.hiddenFields = {}
  if (f.primaryKey === undefined) f.primaryKey = ''
}

function onPerFileHiddenChange(f, field) {
  if (f.hiddenFields[field] && f.primaryKey === field) f.primaryKey = ''
}

// 逐文件模式：按每个文件选择的查询选项加载字段并自动映射该文件的列
async function loadPerFileConfigs() {
  await Promise.all(
    uploadFiles.value.map(async (f) => {
      ensurePerFileConfig(f)
      const script = visibleScripts.value.find((s) => (f.scriptIds || []).includes(s.id))
      const fields = await fetchScriptFields(script)
      f.sqlFields = fields
      Object.keys(f.columnMapping).forEach((k) => delete f.columnMapping[k])
      Object.keys(f.hiddenFields).forEach((k) => delete f.hiddenFields[k])
      fields.forEach((field) => {
        f.columnMapping[field] = ''
        f.hiddenFields[field] = false
      })
      if (script) {
        f.newSheet = script.new_sheet !== false
        f.primaryKey = script.primary_key || ''
      }
      const cols = fileDetectedColumns(f)
      f.paramColumn = cols[0] || ''
      await autoMapColumnsFor(fields, cols, f.columnMapping)
    })
  )
}

async function confirmMatch() {
  selectedScriptIds.value = matchedScripts.value.map((s) => s.id)
  syncUnifiedTagFromSelection()
  matchDialogVisible.value = false
  currentStep.value = 1
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
    currentStep.value = 2
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
  currentStep.value = 0
}

async function goToConfig() {
  if (isPerFileMode.value) {
    if (!perFileScriptReady.value) {
      ElMessage.warning('请为每个文件分组选择查询选项')
      return
    }
    currentStep.value = 1
    await loadPerFileConfigs()
    return
  }
  if (selectedScriptIds.value.length === 0) {
    ElMessage.warning('请至少选择一个查询选项')
    return
  }
  matchedDefaultParamColumn.value = []
  currentStep.value = 1
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

function goToExecute() {
  if (isPerFileMode.value) {
    const missing = uploadFiles.value.find((f) => !f.paramColumn)
    if (missing) {
      ElMessage.warning(`请为文件「${missing.name}」选择参数列`)
      return
    }
    currentStep.value = 2
    return
  }
  if (!options.param_column) {
    ElMessage.warning('请选择参数列')
    return
  }
  currentStep.value = 2
}

// 提取查询选项的 SQL 字段名（模板选项先渲染再提取）
async function fetchScriptFields(script) {
  if (!script) return []
  let sqlToExtract = script.sql_text
  if (script.is_template && script.sql_template) {
    try {
      const renderRes = await api.scripts.renderTemplate({
        template: script.sql_template,
        template_config: script.template_config || []
      })
      if (renderRes.success && renderRes.rendered_sql) {
        sqlToExtract = renderRes.rendered_sql
      }
    } catch {}
  }
  try {
    const res = await api.scripts.extractColumns({ sql: sqlToExtract })
    return res.columns || []
  } catch {
    return []
  }
}

async function loadSqlFields() {
  const firstScript = visibleScripts.value.find((s) => s.id === selectedScriptIds.value[0])
  if (!firstScript) return

  const fields = await fetchScriptFields(firstScript)
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
}

async function autoMapColumnsFor(fields, columns, mapping) {
  // 先做简单匹配（忽略大小写和空格）
  fields.forEach((field) => {
    const lowerField = field.toLowerCase()
    const match = columns.find(
      (col) => col.toLowerCase() === lowerField || col.toLowerCase().replace(/\s+/g, '') === lowerField.replace(/\s+/g, '')
    )
    if (match) {
      mapping[field] = match
    }
  })

  // 对未匹配的字段调用后端模糊匹配API
  const unmapped = fields.filter((f) => !mapping[f])
  if (unmapped.length > 0 && columns.length > 0) {
    try {
      const res = await api.query.fuzzyMatchColumns({
        sql_fields: unmapped,
        excel_columns: columns
      })
      const fuzzyMapping = res.mapping || {}
      for (const [sqlField, excelCol] of Object.entries(fuzzyMapping)) {
        if (excelCol && !mapping[sqlField]) {
          mapping[sqlField] = excelCol
        }
      }
    } catch {
      // 模糊匹配失败不影响流程
    }
  }
}

function autoMapColumns() {
  return autoMapColumnsFor(sqlFields.value, detectedColumns.value, columnMapping)
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
  if (isPerFileMode.value) {
    await executePerFile()
    return
  }
  submitting.value = true
  try {
    const formData = new FormData()
    formData.append('script_ids', JSON.stringify(selectedScriptIds.value))
    // 多文件按顺序提交，并附带每个文件勾选的工作表
    const selectedSheetsMap = {}
    uploadFiles.value.forEach((f, idx) => {
      formData.append('files', f.raw, f.name)
      if (f.selectedSheets.length) {
        selectedSheetsMap[idx] = [...f.selectedSheets]
      }
    })
    formData.append('file_selected_sheets', JSON.stringify(selectedSheetsMap))
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
    emitPetEvent('operation', { type: 'query', label: '' })
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

// 逐文件模式的列映射（隐藏字段记为“隐藏”）
function buildPerFileMappingPayload(f) {
  const mapping = {}
  ;(f.sqlFields || []).forEach((field) => {
    if (f.hiddenFields[field]) {
      mapping[field] = '隐藏'
    } else if (f.columnMapping[field]) {
      mapping[field] = f.columnMapping[field]
    }
  })
  return mapping
}

// 逐文件模式：每个文件独立提交一个查询任务，各自产出结果文件
async function executePerFile() {
  resetPerFileState()
  perFileResults.value = uploadFiles.value.map((f) => ({
    uid: f.uid,
    name: f.name,
    scriptNames: selectedScriptNamesOf(f),
    taskId: null,
    status: 'pending',
    progress: 0,
    outputFile: '',
    error: ''
  }))
  perFileExecuting.value = true
  emitPetEvent('operation', { type: 'query', label: '' })
  await Promise.all(uploadFiles.value.map((f) => submitPerFileQuery(f)))
  maybeFinishPerFile()
}

async function submitPerFileQuery(f) {
  const result = perFileResults.value.find((r) => r.uid === f.uid)
  if (!result) return
  try {
    const formData = new FormData()
    formData.append('script_ids', JSON.stringify(f.scriptIds))
    formData.append('files', f.raw, f.name)
    if (f.selectedSheets.length) {
      formData.append('selected_sheets', JSON.stringify(f.selectedSheets))
    }
    formData.append('param_column', f.paramColumn)
    formData.append('new_sheet', f.newSheet)
    if (!f.newSheet) {
      formData.append('column_mapping', JSON.stringify(buildPerFileMappingPayload(f)))
      if (f.primaryKey) {
        formData.append('primary_key', f.primaryKey)
      }
    }

    const res = await api.query.execute(formData)
    const data = res.data || res
    result.taskId = data.task_id || data.id
    result.status = 'running'
    startPerFileSSE(result)
  } catch (e) {
    result.status = 'failed'
    result.error = e?.response?.data?.message || '任务提交失败'
  }
}

function startPerFileSSE(result) {
  if (!result.taskId) return
  if (perFileEventSources[result.uid]) {
    perFileEventSources[result.uid].close()
  }
  const es = new EventSource(api.query.streamStatus(result.taskId))
  perFileEventSources[result.uid] = es

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.progress !== undefined) result.progress = Math.round(data.progress)
      if (data.status) result.status = data.status
      if (data.output_file) result.outputFile = data.output_file
      if (['completed', 'failed', 'cancelled', 'manual_cancelled'].includes(data.status)) {
        if (data.status === 'completed') result.progress = 100
        if (data.status === 'failed' && data.error_message) result.error = data.error_message
        es.close()
        delete perFileEventSources[result.uid]
        if (data.status === 'completed') {
          emitPetEvent('file_ready', { type: 'query', label: result.outputFile ? '查询结果' : '' })
        }
        store.notifyTaskChanged()
        maybeFinishPerFile()
      }
    } catch {
      // 忽略非 JSON 心跳
    }
  }

  es.onerror = () => {
    es.close()
    delete perFileEventSources[result.uid]
    fetchPerFileStatus(result)
  }
}

async function fetchPerFileStatus(result) {
  try {
    const res = await api.query.status(result.taskId)
    const data = res.data || res
    if (data.progress !== undefined) result.progress = Math.round(data.progress)
    if (data.output_file) result.outputFile = data.output_file
    if (['completed', 'failed', 'cancelled', 'manual_cancelled'].includes(data.status)) {
      result.status = data.status
      if (data.status === 'completed') result.progress = 100
      if (data.status === 'failed' && data.error_message) result.error = data.error_message
      store.notifyTaskChanged()
      maybeFinishPerFile()
      return
    }
    schedulePerFileResubscribe(result, 3000)
  } catch {
    schedulePerFileResubscribe(result, 5000)
  }
}

function schedulePerFileResubscribe(result, delay) {
  if (perFileRetryTimers[result.uid]) return
  perFileRetryTimers[result.uid] = setTimeout(() => {
    delete perFileRetryTimers[result.uid]
    if (perFileExecuting.value && !isPerFileResultFinal(result)) {
      startPerFileSSE(result)
    }
  }, delay)
}

function maybeFinishPerFile() {
  if (!perFileResults.value.length) return
  if (perFileResults.value.every(isPerFileResultFinal)) {
    perFileExecuting.value = false
  }
}

async function cancelPerFileQueries() {
  const running = perFileResults.value.filter((r) => r.taskId && !isPerFileResultFinal(r))
  if (!running.length) return
  try {
    await ElMessageBox.confirm(`确定要终止 ${running.length} 个正在执行的任务吗？`, '终止任务', {
      confirmButtonText: '确定终止',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await Promise.all(running.map((r) => api.query.cancel(r.taskId).catch(() => {})))
    ElMessage.success('已提交终止请求')
  } catch {
    // 用户取消
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
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled' || data.status === 'manual_cancelled') {
        executing.value = false
        eventSource.close()
        eventSource = null
        if (data.status === 'completed') {
          progress.value = 100
          emitPetEvent('file_ready', { type: 'query', label: taskStatus.value?.output_file ? '查询结果' : '' })
        }
        store.notifyTaskChanged()
        // direct模式执行完成后自动下载（仅在有结果文件时；无数据时给出提示，避免误触发下载）
        if (data.status === 'completed' && directMode.value) {
          directMode.value = false
          if (data.output_file) {
            nextTick(() => {
              downloadResult()
            })
          } else {
            ElMessage.warning('本次未查询到匹配的数据，未生成结果文件')
          }
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
        emitPetEvent('file_ready', { type: 'query', label: data.output_file ? '查询结果' : '' })
      }
    }
  } catch {
  }
}

async function cancelQuery() {
  if (!taskId.value) return
  try {
    await ElMessageBox.confirm('确定要终止当前执行任务吗？终止后将立即杀死任务线程，释放占用的资源。', '终止任务', {
      confirmButtonText: '确定终止',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.query.cancel(taskId.value)
    ElMessage.success('任务已终止')
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
  return downloadTaskResult(taskId.value, `result_${taskId.value}.xlsx`)
}

function downloadPerFileResult(result) {
  if (!result.taskId) return
  const base = result.name.replace(/\.(xlsx|xls|csv)$/i, '')
  return downloadTaskResult(result.taskId, `${base}_查询结果.xlsx`)
}

async function downloadTaskResult(tid, defaultName) {
  const url = api.download.file(tid)
  try {
    const check = await fetch(url, { method: 'HEAD' })
    if (!check.ok) {
      // HEAD 请求无响应体，需改用 GET 读取后端返回的具体失败原因（如「未查询到数据」「文件已被清理」）
      let message = '结果文件不存在或已被清理'
      try {
        const resp = await fetch(url)
        const data = await resp.json()
        if (data && data.message) message = data.message
      } catch (_) { /* 解析失败则回退默认提示 */ }
      ElMessageBox.alert(message, '提示', { type: 'warning' })
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
  selectionTag.value = ''
  uploadFiles.value = []
  expandedFileUids.value = []
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
  resetPerFileState()
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
  resetPerFileState()
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

.template-var-group {
  margin-bottom: 12px;
}

.template-var-group-title {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 8px;
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

.parse-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.query-select-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-color, #e4e7ed);
}

.select-hint {
  font-size: 12px;
  color: var(--text-muted, #909399);
}

.parse-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

/* 文件较多时可滚动查看解析结果 */
.parse-list {
  max-height: 380px;
  overflow-y: auto;
  padding-right: 4px;
}

.parse-list :deep(.el-collapse) {
  border: none;
  background: transparent;
}

.parse-list :deep(.el-collapse-item) {
  margin-bottom: 8px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.parse-list :deep(.el-collapse-item__header) {
  padding: 0 12px;
  border-bottom: none;
  background: #fff;
  height: 44px;
}

.parse-list :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.parse-list :deep(.el-collapse-item__content) {
  padding: 0 12px 12px;
}

.parse-file-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.parse-file-icon {
  color: #67c23a;
}

.parse-file-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.parse-file-size {
  font-size: 12px;
  color: #909399;
}

.parse-file-remove {
  margin-left: auto;
}

.parse-error {
  font-size: 13px;
  color: #f56c6c;
}

.parse-empty {
  font-size: 13px;
  color: #909399;
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.sheet-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sheet-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #f8fafc;
}

.sheet-name {
  font-size: 13px;
  color: #303133;
}

.sheet-rows {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.sheet-cols {
  flex: 1;
  min-width: 0;
  text-align: right;
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

/* 逐文件模式：多文件且列不一致 */
.per-file-script-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.per-file-script-row {
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 12px 14px;
  background: #fff;
}

.per-file-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  min-width: 0;
}

.per-file-meta > i {
  color: #67c23a;
}

.per-file-name {
  font-weight: 600;
  color: var(--text-primary, #303133);
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.per-file-cols {
  color: var(--text-muted, #909399);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.per-file-select-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.per-file-config-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.per-file-config-card {
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 14px 16px 2px;
  background: #fafcff;
}

.per-file-config-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}

.per-file-config-head > i {
  color: #67c23a;
}

.per-file-result {
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fff;
}

.per-file-result-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  min-width: 0;
}

.per-file-result-head > i {
  color: #67c23a;
}

.per-file-result-name {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  color: var(--text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.per-file-result-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.per-file-empty {
  font-size: 12px;
  color: var(--text-muted, #909399);
}

.per-file-error {
  font-size: 12px;
  color: #f56c6c;
}
</style>
