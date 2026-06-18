<template>
  <div class="history">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-history"></i> 执行历史</span>
          <div class="header-actions">
            <el-button v-hasPermi="['history:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
            </el-button>
            <el-button v-hasPermi="['history:delete']" type="danger" size="small" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
            <el-select
              v-model="statusFilter"
              placeholder="状态筛选"
              clearable
              style="width: 140px"
              @change="fetchTasks"
            >
              <el-option label="等待中" value="pending" />
              <el-option label="执行中" value="running" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
              <el-option label="已取消" value="cancelled" />
              <el-option label="手动终止" value="manual_cancelled" />
            </el-select>
            <el-button type="primary" @click="fetchTasks" style="margin-left: 12px">
              <i class="fas fa-sync-alt"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="tasks" stripe v-loading="loading" style="width: 100%" @row-click="openDetail" @selection-change="handleSelectionChange" ref="tableRef">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="task_id" label="任务ID" width="130" show-overflow-tooltip />
        <el-table-column prop="script_name" label="查询选项" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.type === 'export' && row.script_names && row.script_names.length > 0">
              {{ row.script_names.join(', ') }}
            </template>
            <template v-else>{{ row.script_name || '-' }}</template>
          </template>
        </el-table-column>
        <el-table-column prop="script_tag" label="标签" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.type === 'export' && row.script_tags && row.script_tags.length > 0">
              <el-tag v-for="tag in row.script_tags" :key="tag" size="small" effect="plain" style="margin: 2px 4px 2px 0">{{ tag }}</el-tag>
            </template>
            <template v-else>
              <el-tag v-if="row.script_tag" size="small" effect="plain">{{ row.script_tag }}</el-tag>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.type === 'export' ? 'warning' : 'primary'" size="small">{{ row.type === 'export' ? '导出' : '查询' }}</el-tag>
            <el-tag v-if="row.is_auto" type="info" size="small" style="margin-left: 4px">自动</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="database_names" label="目标数据库" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="Array.isArray(row.database_names) && row.database_names.length > 0">
              <el-tag v-for="name in row.database_names" :key="name" size="small" type="success" style="margin: 2px 4px 2px 0">
                {{ name }}
              </el-tag>
            </template>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="140">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress || 0"
              :status="progressStatus(row.status)"
              :stroke-width="14"
              :text-inside="true"
            />
          </template>
        </el-table-column>
        <el-table-column prop="total_rows" label="总行数" width="90" align="center" />
        <el-table-column prop="success_count" label="成功数" width="90" align="center">
          <template #default="{ row }">
            <span style="color: #67c23a">{{ row.success_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failure_count" label="失败数" width="90" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.failure_count ? '#f56c6c' : '#909399' }">{{ row.failure_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="280" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click.stop="openDetail(row)">
              <i class="fas fa-eye"></i> 详情
            </el-button>
            <el-popconfirm
              v-if="(row.status === 'pending' || row.status === 'running') && store.hasButtonPermission('task:terminate')"
              title="确定要终止此任务吗？终止后将立即杀死任务线程，释放占用的资源。"
              confirm-button-text="确定终止"
              cancel-button-text="取消"
              @confirm="handleTerminate(row)"
            >
              <template #reference>
                <el-button size="small" type="danger" text @click.stop>
                  <i class="fas fa-stop"></i> 终止
                </el-button>
              </template>
            </el-popconfirm>
            <el-button
              v-if="row.status === 'completed' && (row.type === 'export' ? store.hasButtonPermission('export:download') : store.hasButtonPermission('query:download'))"
              size="small"
              type="success"
              text
              @click.stop="downloadResult(row)"
            >
              <i class="fas fa-download"></i> 下载
            </el-button>
            <el-popconfirm
              v-if="store.hasButtonPermission('task:delete')"
              title="确定要删除此任务记录吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button size="small" type="danger" text @click.stop>
                  <i class="fas fa-trash"></i> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-area">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchTasks"
          @current-change="fetchTasks"
        />
      </div>

      <el-empty v-if="!loading && tasks.length === 0" description="暂无执行历史" />
    </el-card>

    <el-dialog
      v-model="detailVisible"
      :title="`执行详情 - ${detailData.task_id || ''}`"
      width="800px"
      destroy-on-close
      top="5vh"
    >
      <div class="detail-content">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="任务ID">{{ detailData.task_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="任务类型">
            <el-tag :type="detailData.type === 'export' ? 'warning' : 'primary'" size="small">{{ detailData.type === 'export' ? '导出任务' : '查询任务' }}</el-tag>
            <el-tag v-if="detailData.is_auto" type="info" size="small" style="margin-left: 4px">自动执行</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="查询选项">
            <template v-if="detailData.type === 'export' && detailData.script_names && detailData.script_names.length > 0">
              {{ detailData.script_names.join(', ') }}
            </template>
            <template v-else-if="detailData.script_tag">
              <el-tag size="small" effect="plain">{{ detailData.script_tag }}</el-tag>
            </template>
            <span v-else>{{ detailData.script_name || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(detailData.status)" size="small">{{ statusLabel(detailData.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="进度">
            <el-progress
              :percentage="detailData.progress || 0"
              :status="progressStatus(detailData.status)"
              :stroke-width="16"
              :text-inside="true"
              style="width: 100%"
            />
          </el-descriptions-item>
          <el-descriptions-item label="总行数">{{ detailData.total_rows || 0 }}</el-descriptions-item>
          <el-descriptions-item label="成功/失败">
            <span style="color: #67c23a">{{ detailData.success_count || 0 }}</span>
            <span style="margin: 0 4px">/</span>
            <span :style="{ color: detailData.failure_count ? '#f56c6c' : '#909399' }">{{ detailData.failure_count || 0 }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="合并策略">{{ detailData.merge_strategy === 'concat' ? '合并' : '分列' }}</el-descriptions-item>
          <el-descriptions-item label="目标数据库">
            <template v-if="Array.isArray(detailData.database_names) && detailData.database_names.length > 0">
              <el-tag v-for="name in detailData.database_names" :key="name" size="small" type="success" style="margin: 2px 4px 2px 0">
                {{ name }}
              </el-tag>
            </template>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="输入文件">{{ detailData.input_file ? detailData.input_file.split(/[\\/]/).pop() : '-' }}</el-descriptions-item>
          <el-descriptions-item label="输出文件">
            <template v-if="detailData.output_file">{{ detailData.output_file.split(/[\\/]/).pop() }}</template>
            <span v-else-if="detailData.status === 'completed'" style="color: #e6a23c">
              <i class="fas fa-exclamation-triangle"></i> 未查询到数据，未生成文件
            </span>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ detailData.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detailData.completed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detailData.error_message" class="error-section">
          <el-divider content-position="left">错误信息</el-divider>
          <el-alert :title="detailData.error_message" type="error" show-icon :closable="false" />
          <div v-if="detailData.ai_suggestion" class="ai-suggestion">
            <div class="suggestion-header">
              <i class="fas fa-lightbulb"></i> AI 分析与修正建议
            </div>
            <div class="suggestion-content">{{ detailData.ai_suggestion }}</div>
          </div>
          <div v-if="detailData.is_admin" class="admin-error-detail">
            <el-divider content-position="left">详细错误日志（仅管理员可见）</el-divider>
            <pre class="error-stack">{{ detailData.raw_error_message || detailData.error_message }}</pre>
          </div>
        </div>

        <div v-if="detailData.is_admin" class="log-section">
          <div class="log-header">
            <span>执行日志（仅管理员可见）</span>
            <el-button size="small" text @click="refreshDetail">
              <i class="fas fa-sync-alt"></i> 刷新
            </el-button>
          </div>
          <div class="log-content" ref="logContentRef">
            <div v-if="detailLogs.length === 0" class="log-empty">暂无日志</div>
            <div v-for="(log, idx) in detailLogs" :key="idx" class="log-line" :class="log.level || 'info'">
              <span class="log-time">{{ log.time }}</span>
              <span class="log-level" :class="log.level || 'info'">{{ levelLabel(log.level) }}</span>
              <span class="log-msg">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%">
          <span v-if="detailData.status === 'completed'" class="retention-tip">
            <i class="fas fa-exclamation-triangle"></i> 结果文件将保留 {{ fileRetentionHours }} 小时，请及时下载
          </span>
          <span v-else></span>
          <div>
            <el-button
              v-if="(detailData.status === 'pending' || detailData.status === 'running') && store.hasButtonPermission('task:terminate')"
              type="danger"
              @click="handleTerminateFromDetail"
            >
              <i class="fas fa-stop"></i> 终止任务
            </el-button>
            <el-button
              v-if="(detailData.status === 'failed' || detailData.status === 'cancelled' || detailData.status === 'manual_cancelled') && (detailData.type === 'export' ? store.hasButtonPermission('export:retry') : store.hasButtonPermission('query:retry'))"
              type="warning"
              :loading="retrying"
              @click="handleRetry(detailData)"
            >
              <i class="fas fa-redo"></i> 重新执行
            </el-button>
            <el-button
              v-if="detailData.status === 'completed' && (detailData.type === 'export' ? store.hasButtonPermission('export:download') : store.hasButtonPermission('query:download'))"
              type="primary"
              @click="downloadResult(detailData)"
            >
              <i class="fas fa-download"></i> 下载结果
            </el-button>
            <el-button @click="detailVisible = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useAppStore()

const loading = ref(false)
const tasks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const detailVisible = ref(false)
const detailData = ref({})
const detailLogs = ref([])
const logContentRef = ref(null)
const fileRetentionHours = ref(24)
const retrying = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)

const statusMap = {
  pending: { label: '等待中', type: 'info' },
  running: { label: '执行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' },
  manual_cancelled: { label: '手动终止', type: 'info' }
}

function statusType(status) {
  return statusMap[status]?.type || 'info'
}

function statusLabel(status) {
  return statusMap[status]?.label || status || '-'
}

function progressStatus(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  if (status === 'manual_cancelled') return 'exception'
  return undefined
}

function levelLabel(level) {
  const map = { info: 'INFO', warning: 'WARN', error: 'ERROR', success: 'OK' }
  return map[level] || 'INFO'
}

async function fetchTasks() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: pageSize.value
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await api.query.tasks(params)
    const data = res.data || res || {}
    tasks.value = Array.isArray(data) ? data : (data.data || data.items || data.tasks || data.list || [])
    total.value = data.total || tasks.value.length
  } catch {
    tasks.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  const taskId = row.task_id
  if (!taskId) return

  try {
    // 根据任务类型选择正确的状态接口
    const isExport = row.type === 'export'
    const res = isExport ? await api.export.status(taskId) : await api.query.status(taskId)
    const data = res.data || res || {}
    detailData.value = data
    detailLogs.value = data.logs || []
    detailVisible.value = true
    // 上报行为：查看任务详情
    api.ai.trackBehavior({ action: 'view', target_type: 'task', target_id: row.id }).catch(() => {})
    nextTick(() => {
      if (logContentRef.value) {
        logContentRef.value.scrollTop = logContentRef.value.scrollHeight
      }
    })
  } catch {
    detailData.value = row
    detailLogs.value = row.logs || []
    detailVisible.value = true
  }
}

async function refreshDetail() {
  const taskId = detailData.value.task_id
  if (!taskId) return
  try {
    const isExport = detailData.value.type === 'export'
    const res = isExport ? await api.export.status(taskId) : await api.query.status(taskId)
    const data = res.data || res || {}
    detailData.value = data
    detailLogs.value = data.logs || []
    nextTick(() => {
      if (logContentRef.value) {
        logContentRef.value.scrollTop = logContentRef.value.scrollHeight
      }
    })
  } catch {
    // error handled by interceptor
  }
}

async function handleDelete(row) {
  try {
    const id = row.task_id || row.id
    const isExport = row.type === 'export'
    if (isExport) {
      await api.export.deleteTask(id)
    } else {
      await api.query.deleteTask(id)
    }
    ElMessage.success('删除成功')
    fetchTasks()
  } catch {
  }
}

async function handleTerminate(row) {
  try {
    const id = row.task_id || row.id
    const isExport = row.type === 'export'
    if (isExport) {
      await api.export.cancel(id)
    } else {
      await api.query.cancel(id)
    }
    ElMessage.success('任务已终止')
    fetchTasks()
  } catch {
  }
}

async function handleTerminateFromDetail() {
  try {
    await ElMessageBox.confirm('确定要终止此任务吗？终止后将立即杀死任务线程，释放占用的资源。', '终止任务', {
      confirmButtonText: '确定终止',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    const id = detailData.value.task_id || detailData.value.id
    const isExport = detailData.value.type === 'export'
    if (isExport) {
      await api.export.cancel(id)
    } else {
      await api.query.cancel(id)
    }
    ElMessage.success('任务已终止')
    detailVisible.value = false
    fetchTasks()
  } catch {
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedRows.value.length} 条记录吗？`, '批量删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await api.query.batchDeleteTasks(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchTasks()
  } catch {
  }
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm('确定要删除全部历史记录吗？此操作不可恢复！', '删除全部', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await api.query.deleteAllTasks()
    ElMessage.success('全部删除成功')
    selectedRows.value = []
    fetchTasks()
  } catch {
  }
}

async function handleRetry(row) {
  const id = row.task_id || row.id
  if (!id) return
  try {
    await ElMessageBox.confirm('确定要重新执行此任务吗？', '重新执行', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  retrying.value = true
  try {
    const isExport = row.type === 'export'
    const res = isExport ? await api.export.retry(id) : await api.query.retry(id)
    if (res.success) {
      ElMessage.success('任务已重新提交执行')
      detailVisible.value = false
      fetchTasks()
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

async function downloadResult(row) {
  const id = row.task_id || row.id
  const url = api.download.file(id)
  const defaultName = `result_${id}.xlsx`
  // 上报行为：下载文件
  api.ai.trackBehavior({ action: 'download', target_type: 'task', target_id: row.id }).catch(() => {})
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

async function fetchClientConfig() {
  try {
    const res = await api.query.config()
    const data = res.data || res || {}
    fileRetentionHours.value = data.file_retention_hours || 24
  } catch {
    // use default value
  }
}

onMounted(() => {
  fetchTasks()
  fetchClientConfig()
})

watch(() => store.taskVersion, () => {
  fetchTasks()
})
</script>

<style scoped>
.history {
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

.pagination-area {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

.detail-content {
  max-height: 70vh;
  overflow-y: auto;
}

.error-section {
  margin-top: 16px;
}

.ai-suggestion {
  margin-top: 12px;
  padding: 12px 16px;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
  border-radius: 6px;
}

.suggestion-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 8px;
}

.suggestion-header i {
  font-size: 16px;
}

.suggestion-content {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
}

.admin-error-detail {
  margin-top: 12px;
}

.error-stack {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
}

.log-section {
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
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  font-size: 14px;
  font-weight: 600;
}

.log-content {
  height: 300px;
  overflow-y: auto;
  padding: 8px 12px;
  background: #1e1e1e;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

.log-empty {
  color: #6a6a6a;
  text-align: center;
  padding: 40px 0;
}

.log-line {
  display: flex;
  gap: 8px;
  line-height: 1.8;
  color: #d4d4d4;
  white-space: nowrap;
}

.log-time {
  color: #6a9955;
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  min-width: 40px;
  text-align: center;
  font-weight: 600;
}

.log-level.info {
  color: #569cd6;
}

.log-level.warning {
  color: #e6a23c;
}

.log-level.error {
  color: #f56c6c;
}

.log-level.success {
  color: #67c23a;
}

.log-msg {
  color: #d4d4d4;
  word-break: break-all;
  white-space: pre-wrap;
}

.log-content::-webkit-scrollbar {
  width: 8px;
}

.log-content::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.log-content::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

.retention-tip {
  font-size: 13px;
  color: #e6a23c;
}

.retention-tip i {
  margin-right: 4px;
}
</style>
