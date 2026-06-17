<template>
  <div class="system-task-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-cogs"></i> 系统任务</span>
          <div class="header-actions">
            <el-button type="info" plain @click="goToScripts">
              <i class="fas fa-code"></i> 管理SQL脚本
            </el-button>
            <el-button v-if="store.hasButtonPermission('system_task:create')" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建任务
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="任务列表" name="tasks">
          <div v-if="store.hasButtonPermission('system_task:delete')" style="margin-bottom: 12px; display: flex; gap: 10px;">
            <el-button type="danger" plain :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除 <span v-if="selectedRows.length > 0">({{ selectedRows.length }})</span>
            </el-button>
            <el-button type="danger" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
          </div>
          <el-table ref="tableRef" :data="taskList" stripe v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="55" align="center" />
            <el-table-column prop="name" label="任务名称" min-width="140" show-overflow-tooltip />
            <el-table-column label="任务类型" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.task_type === 'sql' ? 'primary' : row.task_type === 'api' ? 'success' : 'warning'">
                  {{ row.task_type === 'sql' ? 'SQL' : row.task_type === 'api' ? 'API' : '本地脚本' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="关联对象" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.task_type === 'sql'">
                  脚本: {{ row.script_name || '-' }}
                </span>
                <span v-else-if="row.task_type === 'api'">
                  {{ row.api_method }} {{ row.api_url || '-' }}
                  <div v-if="row.api_body" style="color: #909399; font-size: 12px; margin-top: 2px">
                    Body: {{ row.api_body.length > 50 ? row.api_body.substring(0, 50) + '...' : row.api_body }}
                  </div>
                </span>
                <span v-else-if="row.task_type === 'script'">
                  {{ row.script_type || 'python' }}: {{ row.script_path || '-' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="加签" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.sign_enabled" size="small" type="warning">已启用</el-tag>
                <span v-else style="color: #c0c4cc">-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
                  {{ row.is_enabled ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="300" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-if="store.hasButtonPermission('system_task:execute')" size="small" type="primary" text @click="openExecuteDialog(row)">
                  <i class="fas fa-play"></i> 执行
                </el-button>
                <el-button v-if="store.hasButtonPermission('system_task:edit')" size="small" type="primary" text @click="openDialog(row)">
                  <i class="fas fa-edit"></i> 编辑
                </el-button>
                <el-button v-if="store.hasButtonPermission('system_task:edit')" size="small" :type="row.is_enabled ? 'warning' : 'success'" text @click="handleToggle(row)">
                  {{ row.is_enabled ? '禁用' : '启用' }}
                </el-button>
                <el-popconfirm
                  v-if="store.hasButtonPermission('system_task:delete')"
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
          <el-empty v-if="!loading && taskList.length === 0" description="暂无系统任务" />
        </el-tab-pane>

        <el-tab-pane label="执行记录" name="executions">
          <el-table :data="executionList" stripe v-loading="executionLoading" style="width: 100%">
            <el-table-column prop="execution_id" label="执行ID" min-width="200" show-overflow-tooltip />
            <el-table-column prop="system_task_name" label="任务名称" min-width="140" show-overflow-tooltip />
            <el-table-column label="类型" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.system_task_type === 'sql' ? 'primary' : row.system_task_type === 'api' ? 'success' : 'warning'">
                  {{ row.system_task_type === 'sql' ? 'SQL' : row.system_task_type === 'api' ? 'API' : '本地脚本' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">
                  {{ statusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.progress" :status="row.status === 'failed' ? 'exception' : ''" />
              </template>
            </el-table-column>
            <el-table-column prop="started_at" label="开始时间" width="170" />
            <el-table-column prop="completed_at" label="完成时间" width="170" />
            <el-table-column label="操作" width="180" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-if="store.hasButtonPermission('system_task:view_log')" size="small" type="primary" text @click="openExecutionDetail(row)">
                  <i class="fas fa-eye"></i> 详情
                </el-button>
                <el-popconfirm
                  v-if="store.hasButtonPermission('system_task:delete_log')"
                  title="确定要删除此记录吗？"
                  confirm-button-text="确定"
                  cancel-button-text="取消"
                  @confirm="handleDeleteExecution(row.execution_id)"
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
          <el-empty v-if="!executionLoading && executionList.length === 0" description="暂无执行记录" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Task Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑系统任务' : '新建系统任务'"
      width="800px"
      destroy-on-close
      :close-on-click-modal="false"
      top="5vh"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" label-position="right">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简要描述此任务" />
        </el-form-item>
        <el-form-item label="任务类型" prop="task_type">
          <el-radio-group v-model="form.task_type">
            <el-radio value="sql">SQL脚本</el-radio>
            <el-radio value="api">API接口</el-radio>
            <el-radio value="script">本地脚本</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>

        <!-- SQL Config -->
        <template v-if="form.task_type === 'sql'">
          <el-form-item label="关联脚本" prop="script_id">
            <el-select v-model="form.script_id" placeholder="请选择脚本" style="width: 100%" filterable>
              <el-option
                v-for="s in sqlScripts"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="数据库连接">
            <el-select v-model="form.database_ids" multiple :collapse-tags="true" :collapse-tags-tooltip="true" placeholder="请选择数据库（可选，可多选，不选则使用脚本配置）" style="width: 100%" clearable filterable>
              <el-option
                v-for="d in databases"
                :key="d.id"
                :label="d.name"
                :value="d.id"
              />
            </el-select>
          </el-form-item>
        </template>

        <!-- API Config -->
        <template v-if="form.task_type === 'api'">
          <el-form-item label="请求方式" prop="api_method">
            <el-select v-model="form.api_method" placeholder="请选择请求方式" style="width: 120px">
              <el-option value="GET" label="GET" />
              <el-option value="POST" label="POST" />
              <el-option value="PUT" label="PUT" />
              <el-option value="DELETE" label="DELETE" />
            </el-select>
          </el-form-item>
          <el-form-item label="API地址" prop="api_url">
            <el-input v-model="form.api_url" placeholder="https://api.example.com/endpoint" />
          </el-form-item>
          <el-form-item label="请求头">
            <el-input v-model="apiHeadersText" type="textarea" :rows="3" placeholder='{"Content-Type": "application/json"}' />
          </el-form-item>
          <el-form-item label="请求体模板">
            <el-input v-model="form.api_body" type="textarea" :rows="4" placeholder='请求体模板，可使用 {{param_name}} 作为参数占位符' />
          </el-form-item>
          <el-form-item label="超时时间(秒)">
            <el-input-number v-model="form.api_timeout" :min="1" :max="300" />
          </el-form-item>
        </template>

        <!-- Script Config -->
        <template v-if="form.task_type === 'script'">
          <el-form-item label="脚本类型" prop="script_type">
            <el-select v-model="form.script_type" placeholder="请选择脚本类型" style="width: 200px">
              <el-option value="python" label="Python" />
              <el-option value="shell" label="Shell/Bash" />
              <el-option value="bat" label="Batch (Windows)" />
              <el-option value="powershell" label="PowerShell" />
            </el-select>
          </el-form-item>
          <el-form-item label="脚本路径" prop="script_path">
            <el-input v-model="form.script_path" placeholder="/path/to/script.py" />
          </el-form-item>
          <el-form-item label="超时时间(秒)">
            <el-input-number v-model="form.script_timeout" :min="1" :max="3600" />
          </el-form-item>
          <el-form-item label="环境变量">
            <el-input v-model="scriptEnvText" type="textarea" :rows="3" placeholder='{"KEY": "value"}' />
          </el-form-item>
        </template>

        <!-- Params Config (for API and Script tasks) -->
        <template v-if="form.task_type === 'api' || form.task_type === 'script'">
          <el-form-item label="参数配置">
            <div v-for="(param, idx) in form.params_config" :key="idx" class="param-row">
              <el-input v-model="param.name" placeholder="参数名" style="width: 140px" />
              <el-input v-model="param.label" placeholder="显示名称" style="width: 140px" />
              <el-select v-model="param.type" placeholder="类型" style="width: 100px">
                <el-option value="text" label="文本" />
                <el-option value="number" label="数字" />
                <el-option value="textarea" label="多行文本" />
              </el-select>
              <el-button type="danger" text @click="removeParam(idx)">
                <i class="fas fa-trash"></i>
              </el-button>
            </div>
            <el-button type="primary" text @click="addParam">
              <i class="fas fa-plus"></i> 添加参数
            </el-button>
          </el-form-item>
        </template>

        <!-- Signing Config (only for API tasks) -->
        <template v-if="form.task_type === 'api'">
          <el-divider content-position="left">加签配置</el-divider>
        <el-form-item label="启用加签">
          <el-switch v-model="form.sign_enabled" />
        </el-form-item>
        <template v-if="form.sign_enabled">
          <el-form-item label="加签密钥">
            <el-input v-model="form.sign_key" placeholder="签名密钥" show-password />
          </el-form-item>
          <el-form-item label="加签方法">
            <el-select v-model="form.sign_method" placeholder="选择加签方法" style="width: 200px">
              <el-option value="md5" label="MD5" />
              <el-option value="sha256" label="SHA256" />
              <el-option value="hmac_sha256" label="HMAC-SHA256" />
              <el-option value="md5_upper" label="MD5(大写)" />
            </el-select>
          </el-form-item>
          <el-form-item label="签名字段名">
            <el-input v-model="form.sign_param_name" placeholder="sign" style="width: 200px" />
          </el-form-item>
          <el-form-item label="签名附加方式">
            <el-radio-group v-model="form.sign_append_type">
              <el-radio value="query">URL参数</el-radio>
              <el-radio value="body">请求体</el-radio>
              <el-radio value="header">请求头</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>
        </template>

        <!-- Response Mapping (only for API tasks) -->
        <template v-if="form.task_type === 'api'">
          <el-divider content-position="left">响应字段映射</el-divider>
          <el-form-item label="字段映射">
            <div class="mapping-hint" style="margin-bottom: 8px; color: #909399; font-size: 12px;">
              配置API响应字段的意义枚举映射，执行结果中会自动将原始值替换为可读文本（如 status: 0→失败, 1→成功）
            </div>
            <div v-for="(item, idx) in form.response_mapping" :key="idx" class="mapping-row" style="margin-bottom: 8px;">
              <el-input v-model="item.field" placeholder="字段路径(如status或data.code)" style="width: 180px" />
              <el-input v-model="item.label" placeholder="字段含义(如状态)" style="width: 120px" />
              <div class="mapping-enum" style="flex: 1;">
                <div v-for="(val, key) in item.mappingEntries" :key="key" style="display: flex; gap: 4px; margin-bottom: 4px;">
                  <el-input v-model="item.mappingEntries[key].key" placeholder="原始值" style="width: 100px" />
                  <span style="line-height: 32px; color: #909399;">→</span>
                  <el-input v-model="item.mappingEntries[key].value" placeholder="含义" style="width: 100px" />
                  <el-button type="danger" text @click="item.mappingEntries.splice(key, 1)"><i class="fas fa-times"></i></el-button>
                </div>
                <el-button type="primary" text size="small" @click="item.mappingEntries.push({key: '', value: ''})">
                  <i class="fas fa-plus"></i> 添加枚举
                </el-button>
              </div>
              <el-button type="danger" text @click="form.response_mapping.splice(idx, 1)">
                <i class="fas fa-trash"></i>
              </el-button>
            </div>
            <el-button type="primary" text @click="addResponseMapping">
              <i class="fas fa-plus"></i> 添加字段映射
            </el-button>
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            <i class="fas fa-check"></i> {{ isEdit ? '保存修改' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Execute Dialog -->
    <el-dialog
      v-model="executeDialogVisible"
      title="执行任务"
      width="600px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <div v-if="currentTask">
        <p style="margin-bottom: 16px;">
          <strong>任务:</strong> {{ currentTask.name }}
          <el-tag size="small" style="margin-left: 8px">{{ currentTask.task_type }}</el-tag>
        </p>
        <el-form label-width="100px" label-position="right">
          <el-form-item v-if="currentTaskDatabases.length > 0 && currentTask.task_type === 'sql'" label="数据库连接">
            <el-select v-model="executeDatabaseId" placeholder="全部数据库（默认）" clearable style="width: 100%">
              <el-option
                v-for="db in currentTaskDatabases"
                :key="db.id"
                :label="db.name"
                :value="db.id"
              />
            </el-select>
            <div style="color: #909399; font-size: 12px; margin-top: 4px">不选择则默认在所有关联数据库上执行</div>
          </el-form-item>
          <el-form-item v-for="param in currentTaskParamsConfig" :key="param.name">
            <template #label>
              <span v-if="currentTask.task_type === 'sql' || param.required" style="color: #f56c6c">* </span>{{ param.label || param.name }}
            </template>
            <el-input
              v-if="param.type === 'textarea'"
              v-model="executeParams[param.name]"
              type="textarea"
              :rows="3"
              :placeholder="`请输入 ${param.label || param.name}`"
            />
            <el-input-number
              v-else-if="param.type === 'number'"
              v-model="executeParams[param.name]"
              :placeholder="`请输入 ${param.label || param.name}`"
              style="width: 100%"
            />
            <el-input
              v-else
              v-model="executeParams[param.name]"
              :placeholder="`请输入 ${param.label || param.name}`"
            />
          </el-form-item>
          <el-empty v-if="currentTaskParamsConfig.length === 0" description="此任务无需参数" :image-size="60" />
        </el-form>
        <div v-if="currentTaskParamsConfig.length > 0 && !allParamsFilled" style="color: #e6a23c; font-size: 13px; margin-top: 8px; text-align: center;">
          <i class="fas fa-exclamation-triangle"></i> 请填写所有必填参数后才能执行
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="executeDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="executing"
            :disabled="currentTaskParamsConfig.length > 0 && !allParamsFilled"
            @click="handleExecute"
          >
            <i class="fas fa-play"></i> 立即执行
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Execution Detail Dialog -->
    <el-dialog
      v-model="detailDialogVisible"
      title="执行详情"
      width="800px"
      destroy-on-close
    >
      <div v-if="currentExecution" class="execution-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="执行ID">{{ currentExecution.execution_id }}</el-descriptions-item>
          <el-descriptions-item label="任务名称">{{ currentExecution.system_task_name }}</el-descriptions-item>
          <el-descriptions-item label="任务类型">{{ currentExecution.system_task_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(currentExecution.status)" size="small">
              {{ statusLabel(currentExecution.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ currentExecution.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ currentExecution.completed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <div class="detail-section-title">参数值</div>
          <pre v-if="Object.keys(currentExecution.params_values || {}).length > 0" class="json-pre">{{ JSON.stringify(currentExecution.params_values, null, 2) }}</pre>
          <span v-else style="color: #c0c4cc">无参数</span>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">执行结果</div>
          <pre v-if="currentExecution.result_data && Object.keys(currentExecution.result_data).length > 0" class="json-pre">{{ JSON.stringify(currentExecution.result_data, null, 2) }}</pre>
          <span v-else style="color: #c0c4cc">无结果</span>
        </div>

        <div class="detail-section">
          <div class="detail-section-title">执行日志</div>
          <div v-if="currentExecution.logs && currentExecution.logs.length > 0" class="log-list">
            <div v-for="(log, idx) in currentExecution.logs" :key="idx" class="log-item">
              <span class="log-time">{{ log.time }}</span>
              <el-tag :type="logLevelType(log.level)" size="small" style="margin: 0 8px">{{ log.level }}</el-tag>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
          <span v-else style="color: #c0c4cc">无日志</span>
        </div>

        <div v-if="currentExecution.error_message" class="detail-section">
          <div class="detail-section-title" style="color: #f56c6c">错误信息</div>
          <el-alert :title="currentExecution.error_message" type="error" :closable="false" show-icon />
        </div>
      </div>
    </el-dialog>

    <!-- Execution Progress Dialog -->
    <el-dialog
      v-model="progressDialogVisible"
      title="执行中..."
      width="600px"
      :close-on-click-modal="false"
      :show-close="progressDone"
      :close-on-press-escape="progressDone"
    >
      <div class="progress-content">
        <el-progress :percentage="progressValue" :status="progressStatus" />
        <div class="progress-status">
          <el-tag :type="statusType(progressStatusText)" size="small">{{ statusLabel(progressStatusText) }}</el-tag>
        </div>
        <div class="progress-logs">
          <div v-for="(log, idx) in progressLogs" :key="idx" class="log-item">
            <span class="log-time">{{ log.time }}</span>
            <el-tag :type="logLevelType(log.level)" size="small" style="margin: 0 8px">{{ log.level }}</el-tag>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useAppStore()
const router = useRouter()
const activeTab = ref('tasks')
const loading = ref(false)
const executionLoading = ref(false)
const submitting = ref(false)
const executing = ref(false)
const dialogVisible = ref(false)
const executeDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const progressDialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const tableRef = ref(null)
const selectedRows = ref([])
const taskList = ref([])
const executionList = ref([])
const sqlScripts = ref([])
const databases = ref([])
const currentTask = ref(null)
const currentExecution = ref(null)
const executeParams = reactive({})
const executeDatabaseId = ref(null)

const currentTaskParamsConfig = computed(() => {
  if (!currentTask.value) return []
  return getTaskParamsConfig(currentTask.value)
})

// 所有必填参数是否已填写（SQL类型任务所有参数必填）
const allParamsFilled = computed(() => {
  if (!currentTask.value) return false
  const params = currentTaskParamsConfig.value
  if (params.length === 0) return true
  if (currentTask.value.task_type === 'sql' || currentTask.value.task_type === 'script') {
    return params.every(p => {
      const v = executeParams[p.name]
      return v !== undefined && v !== null && v !== ''
    })
  }
  // API类型按required字段判断
  return params.filter(p => p.required).every(p => {
    const v = executeParams[p.name]
    return v !== undefined && v !== null && v !== ''
  })
})

// 当前任务关联的数据库连接列表
const currentTaskDatabases = computed(() => {
  if (!currentTask.value) return []
  const dbIds = currentTask.value.database_ids || []
  if (dbIds.length <= 1) return []  // 只有一个或没有，不需要选择
  return databases.value.filter(d => dbIds.includes(d.id))
})

const progressValue = ref(0)
const progressStatus = ref('')
const progressStatusText = ref('pending')
const progressLogs = ref([])
const progressDone = ref(false)
let eventSource = null

const defaultForm = {
  name: '',
  description: '',
  task_type: 'sql',
  script_id: null,
  database_ids: [],
  api_method: 'POST',
  api_url: '',
  api_headers: {},
  api_body: '',
  api_timeout: 30,
  params_config: [],
  response_mapping: [],
  sign_enabled: false,
  sign_key: '',
  sign_method: 'md5',
  sign_param_name: 'sign',
  sign_append_type: 'query',
  is_enabled: true,
  script_type: 'python',
  script_path: '',
  script_timeout: 60,
  script_env: {},
}

const form = reactive({ ...defaultForm })

const apiHeadersText = computed({
  get() {
    return form.api_headers ? JSON.stringify(form.api_headers, null, 2) : ''
  },
  set(val) {
    try {
      form.api_headers = val ? JSON.parse(val) : {}
    } catch {
      form.api_headers = {}
    }
  }
})

const scriptEnvText = computed({
  get() {
    return form.script_env ? JSON.stringify(form.script_env, null, 2) : ''
  },
  set(val) {
    try {
      form.script_env = val ? JSON.parse(val) : {}
    } catch {
      form.script_env = {}
    }
  }
})

const rules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
  script_id: [{ required: true, message: '请选择脚本', trigger: 'change', type: 'number' }],
  api_url: [{ required: true, message: '请输入API地址', trigger: 'blur' }],
  script_path: [{ required: true, message: '请输入脚本路径', trigger: 'blur' }],
}

function statusType(status) {
  const map = { completed: 'success', failed: 'danger', running: 'warning', pending: 'info', cancelled: 'info' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { completed: '成功', failed: '失败', running: '执行中', pending: '等待中', cancelled: '已取消' }
  return map[status] || status
}

function logLevelType(level) {
  const map = { info: 'info', warning: 'warning', error: 'danger', success: 'success' }
  return map[level] || 'info'
}

function addParam() {
  if (!form.params_config) form.params_config = []
  form.params_config.push({ name: '', label: '', type: 'text' })
}

function removeParam(idx) {
  form.params_config.splice(idx, 1)
}

function addResponseMapping() {
  if (!form.response_mapping) form.response_mapping = []
  form.response_mapping.push({ field: '', label: '', mapping: {}, mappingEntries: [{ key: '', value: '' }] })
}

// 将mappingEntries转换为mapping对象（提交时调用）
function convertMappingEntriesToMapping(entries) {
  const mapping = {}
  if (entries && Array.isArray(entries)) {
    entries.forEach(e => {
      if (e.key !== '' && e.value !== '') {
        mapping[e.key] = e.value
      }
    })
  }
  return mapping
}

// 将mapping对象转换为mappingEntries数组（编辑时调用）
function convertMappingToEntries(mapping) {
  if (!mapping || typeof mapping !== 'object') return [{ key: '', value: '' }]
  const entries = Object.entries(mapping).map(([key, value]) => ({ key, value }))
  return entries.length > 0 ? entries : [{ key: '', value: '' }]
}

async function fetchList() {
  loading.value = true
  try {
    const res = await api.systemTask.list()
    taskList.value = res.data || []
  } catch {
    taskList.value = []
  } finally {
    loading.value = false
  }
}

async function fetchExecutions() {
  executionLoading.value = true
  try {
    const res = await api.systemTask.executions({ per_page: 50 })
    executionList.value = res.data || []
  } catch {
    executionList.value = []
  } finally {
    executionLoading.value = false
  }
}

async function fetchScripts() {
  try {
    const res = await api.scripts.list({ type: 'system' })
    sqlScripts.value = res.data || []
  } catch {
    sqlScripts.value = []
  }
}

async function fetchDatabases() {
  try {
    const res = await api.databases.list()
    databases.value = res.data || []
  } catch {
    databases.value = []
  }
}

function goToScripts() {
  router.push('/scripts?type=system')
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(form, {
      name: row.name || '',
      description: row.description || '',
      task_type: row.task_type || 'sql',
      script_id: row.script_id || null,
      database_ids: row.database_ids && row.database_ids.length > 0 ? [...row.database_ids] : [],
      api_method: row.api_method || 'POST',
      api_url: row.api_url || '',
      api_headers: row.api_headers || {},
      api_body: row.api_body || '',
      api_timeout: row.api_timeout || 30,
      params_config: row.params_config && row.params_config.length > 0 ? JSON.parse(JSON.stringify(row.params_config)) : [],
      response_mapping: (row.response_mapping && row.response_mapping.length > 0)
        ? row.response_mapping.map(m => ({
            field: m.field || '',
            label: m.label || '',
            mapping: m.mapping || {},
            mappingEntries: convertMappingToEntries(m.mapping),
          }))
        : [],
      sign_enabled: row.sign_enabled || false,
      sign_key: row.sign_key || '',
      sign_method: row.sign_method || 'md5',
      sign_param_name: row.sign_param_name || 'sign',
      sign_append_type: row.sign_append_type || 'query',
      is_enabled: row.is_enabled !== false,
      script_type: row.script_type || 'python',
      script_path: row.script_path || '',
      script_timeout: row.script_timeout || 60,
      script_env: row.script_env || {},
    })
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm, params_config: [], response_mapping: [] })
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
      task_type: form.task_type,
      script_id: form.script_id,
      database_ids: form.database_ids || [],
      api_method: form.api_method,
      api_url: form.api_url,
      api_body: form.api_body,
      api_timeout: form.api_timeout,
      sign_enabled: form.sign_enabled,
      sign_key: form.sign_key,
      sign_method: form.sign_method,
      sign_param_name: form.sign_param_name,
      sign_append_type: form.sign_append_type,
      is_enabled: form.is_enabled,
      script_type: form.script_type,
      script_path: form.script_path,
      script_timeout: form.script_timeout,
    }
    if (form.task_type === 'api' || form.task_type === 'script') {
      payload.params_config = form.params_config || []
    }
    if (form.task_type === 'api') {
      // 转换response_mapping：将mappingEntries转为mapping对象
      payload.response_mapping = (form.response_mapping || [])
        .filter(m => m.field)
        .map(m => ({
          field: m.field,
          label: m.label || m.field,
          mapping: convertMappingEntriesToMapping(m.mappingEntries),
        }))
        .filter(m => Object.keys(m.mapping).length > 0)
    }
    if (form.api_headers && Object.keys(form.api_headers).length > 0) {
      payload.api_headers = form.api_headers
    }
    if (form.task_type === 'script' && form.script_env && Object.keys(form.script_env).length > 0) {
      payload.script_env = form.script_env
    }

    if (isEdit.value) {
      await api.systemTask.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.systemTask.create(payload)
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
    const payload = { ...row, is_enabled: !row.is_enabled }
    await api.systemTask.update(row.id, payload)
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    fetchList()
  } catch {
  }
}

async function handleDelete(id) {
  try {
    await api.systemTask.delete(id)
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
      '批量删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.systemTask.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchList()
  } catch {
  }
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除全部任务吗？此操作不可恢复！',
      '删除全部',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.systemTask.deleteAll()
    ElMessage.success('全部删除成功')
    selectedRows.value = []
    fetchList()
  } catch {
  }
}

function getTaskParamsConfig(row) {
  if (row.task_type === 'sql' && row.script_id) {
    // First try script_params_config (included directly from backend)
    if (row.script_params_config && row.script_params_config.length > 0) {
      return row.script_params_config
    }
    // Fallback: look up from sqlScripts list
    const script = sqlScripts.value.find(s => s.id === row.script_id)
    if (script && script.params_config && script.params_config.length > 0) {
      return script.params_config
    }
  }
  if (row.task_type === 'script') {
    return row.params_config || []
  }
  return row.params_config || []
}

function openExecuteDialog(row) {
  currentTask.value = row
  executeDatabaseId.value = null
  Object.keys(executeParams).forEach(k => delete executeParams[k])
  const paramsConfig = getTaskParamsConfig(row)
  if (paramsConfig && paramsConfig.length > 0) {
    paramsConfig.forEach(p => {
      executeParams[p.name] = ''
    })
  }
  executeDialogVisible.value = true
}

async function handleExecute() {
  if (!currentTask.value) return
  executing.value = true
  try {
    const params = {}
    const paramsConfig = getTaskParamsConfig(currentTask.value)
    if (paramsConfig && paramsConfig.length > 0) {
      paramsConfig.forEach(p => {
        params[p.name] = executeParams[p.name]
      })
    }
    const payload = { params_values: params }
    if (executeDatabaseId.value) {
      payload.database_id = executeDatabaseId.value
    }
    const res = await api.systemTask.execute(currentTask.value.id, payload)
    executeDialogVisible.value = false
    ElMessage.success('任务已提交执行')
    startProgressStream(res.execution_id)
  } catch {
  } finally {
    executing.value = false
  }
}

function startProgressStream(executionId) {
  progressValue.value = 0
  progressStatus.value = ''
  progressStatusText.value = 'pending'
  progressLogs.value = []
  progressDone.value = false
  progressDialogVisible.value = true

  if (eventSource) {
    eventSource.close()
    eventSource = null
  }

  const url = api.systemTask.streamExecution(executionId)
  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.error) {
        ElMessage.error(data.error)
        progressDone.value = true
        eventSource.close()
        return
      }
      if (data.progress !== undefined) {
        progressValue.value = data.progress
      }
      if (data.status) {
        progressStatusText.value = data.status
        if (data.status === 'failed') {
          progressStatus.value = 'exception'
        }
      }
      if (data.new_logs && data.new_logs.length > 0) {
        progressLogs.value.push(...data.new_logs)
      }
      if (data.done) {
        progressDone.value = true
        eventSource.close()
        fetchExecutions()
      }
    } catch {
    }
  }

  eventSource.onerror = () => {
    progressDone.value = true
    eventSource.close()
    fetchExecutions()
  }
}

async function openExecutionDetail(row) {
  try {
    const res = await api.systemTask.getExecution(row.execution_id)
    currentExecution.value = res.data || null
    detailDialogVisible.value = true
  } catch {
  }
}

async function handleDeleteExecution(executionId) {
  try {
    await api.systemTask.deleteExecution(executionId)
    ElMessage.success('删除成功')
    fetchExecutions()
  } catch {
  }
}

watch(activeTab, (val) => {
  if (val === 'executions') {
    fetchExecutions()
  }
})

onMounted(() => {
  fetchList()
  fetchScripts()
  fetchDatabases()
})
</script>

<style scoped>
.system-task-manager {
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.execution-detail {
  max-height: 600px;
  overflow-y: auto;
}

.detail-section {
  margin-top: 16px;
}

.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin-bottom: 8px;
}

.json-pre {
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.log-list {
  max-height: 300px;
  overflow-y: auto;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 12px;
}

.log-item {
  padding: 4px 0;
  font-size: 13px;
  display: flex;
  align-items: center;
}

.log-time {
  color: #909399;
  font-size: 12px;
  min-width: 160px;
}

.log-message {
  color: #303133;
}

.progress-content {
  padding: 8px;
}

.progress-status {
  margin-top: 12px;
  text-align: center;
}

.progress-logs {
  margin-top: 16px;
  max-height: 300px;
  overflow-y: auto;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 12px;
}
</style>
