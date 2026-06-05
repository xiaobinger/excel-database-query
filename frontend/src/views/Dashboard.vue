<template>
  <div class="dashboard">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-database">
          <div class="stat-icon"><i class="fas fa-database"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.database_count || 0 }}</div>
            <div class="stat-label">数据库连接数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-script">
          <div class="stat-icon"><i class="fas fa-clipboard-list"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.script_count || 0 }}</div>
            <div class="stat-label">查询选项数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-task">
          <div class="stat-icon"><i class="fas fa-tasks"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.task_count || 0 }}</div>
            <div class="stat-label">执行任务数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-success">
          <div class="stat-icon"><i class="fas fa-check-circle"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.success_count || 0 }}</div>
            <div class="stat-label">成功任务数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="recent-card">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-clock"></i> 最近执行任务</span>
          <el-button type="primary" text @click="$router.push('/history')">
            查看全部 <i class="fas fa-arrow-right"></i>
          </el-button>
        </div>
      </template>
      <el-table :data="recentTasks" stripe style="width: 100%" v-loading="loading" @row-click="goToDetail">
        <el-table-column prop="script_tag" label="查询选项" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.script_tag" size="small" effect="plain">{{ row.script_tag }}</el-tag>
            <span v-else>{{ row.script_name || '-' }}</span>
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
        <el-table-column prop="progress" label="进度" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress || 0"
              :status="progressStatus(row.status)"
              :stroke-width="14"
              :text-inside="true"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" show-overflow-tooltip />
        <el-table-column label="" width="80" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click.stop="goToDetail(row)">
              <i class="fas fa-eye"></i> 详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && recentTasks.length === 0" description="暂无执行记录" />
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
          <el-descriptions-item label="查询选项">
            <el-tag v-if="detailData.script_tag" size="small" effect="plain">{{ detailData.script_tag }}</el-tag>
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
          <el-descriptions-item label="目标数据库">
            <template v-if="Array.isArray(detailData.database_names) && detailData.database_names.length > 0">
              <el-tag v-for="name in detailData.database_names" :key="name" size="small" type="success" style="margin: 2px 4px 2px 0">
                {{ name }}
              </el-tag>
            </template>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="输入文件">{{ detailData.input_file ? detailData.input_file.split(/[\\/]/).pop() : '-' }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ detailData.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ detailData.completed_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detailData.error_message" class="error-section">
          <el-divider content-position="left">错误信息</el-divider>
          <el-alert :title="detailData.error_message" type="error" show-icon :closable="false" />
        </div>

        <div class="log-section">
          <div class="log-header">
            <span>执行日志</span>
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
        <el-button
          v-if="(detailData.status === 'failed' || detailData.status === 'cancelled') && store.hasButtonPermission('query:retry')"
          type="warning"
          :loading="retrying"
          @click="handleRetry(detailData)"
        >
          <i class="fas fa-redo"></i> 重新执行
        </el-button>
        <el-button
          v-if="detailData.status === 'completed' && store.hasButtonPermission('query:download')"
          type="primary"
          @click="downloadResult(detailData)"
        >
          <i class="fas fa-download"></i> 下载结果
        </el-button>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const store = useAppStore()
const stats = ref({})
const recentTasks = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detailData = ref({})
const detailLogs = ref([])
const logContentRef = ref(null)
const retrying = ref(false)

const statusMap = {
  pending: { label: '等待中', type: 'info' },
  running: { label: '执行中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  cancelled: { label: '已取消', type: 'info' }
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
  return undefined
}

function levelLabel(level) {
  const map = { info: 'INFO', warning: 'WARN', error: 'ERROR', success: 'OK' }
  return map[level] || 'INFO'
}

async function goToDetail(row) {
  const taskId = row.task_id
  if (!taskId) return
  try {
    const res = await api.query.status(taskId)
    const data = res.data || res || {}
    detailData.value = data
    detailLogs.value = data.logs || []
    detailVisible.value = true
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
    const res = await api.query.status(taskId)
    const data = res.data || res || {}
    detailData.value = data
    detailLogs.value = data.logs || []
    nextTick(() => {
      if (logContentRef.value) {
        logContentRef.value.scrollTop = logContentRef.value.scrollHeight
      }
    })
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
    const res = await api.query.retry(id)
    if (res.success) {
      ElMessage.success('任务已重新提交执行')
      detailVisible.value = false
      fetchDashboard()
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

async function fetchDashboard() {
  loading.value = true
  try {
    const res = await api.query.dashboard()
    const data = res.data || res || {}
    stats.value = {
      database_count: data.total_databases || 0,
      script_count: data.total_scripts || 0,
      task_count: data.total_tasks || 0,
      success_count: data.success_tasks || 0
    }
    recentTasks.value = data.recent_tasks || []
  } catch {
    stats.value = {}
    recentTasks.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchDashboard)

watch(() => store.taskVersion, () => {
  fetchDashboard()
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  border-radius: 8px;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin-right: 16px;
  flex-shrink: 0;
}

.stat-database .stat-icon {
  background: rgba(64, 158, 255, 0.1);
  color: var(--primary-color, #409eff);
}

.stat-script .stat-icon {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
}

.stat-task .stat-icon {
  background: rgba(230, 162, 60, 0.1);
  color: #e6a23c;
}

.stat-success .stat-icon {
  background: rgba(19, 206, 102, 0.1);
  color: #13ce66;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary, #303133);
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: var(--text-muted, #909399);
  margin-top: 4px;
}

.recent-card {
  border-radius: 8px;
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
  background: var(--table-header-bg, #f5f7fa);
  border-bottom: 1px solid #dcdfe6;
  font-size: 14px;
  font-weight: 600;
}

.log-content {
  height: 250px;
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

.log-level.info { color: #569cd6; }
.log-level.warning { color: #e6a23c; }
.log-level.error { color: #f56c6c; }
.log-level.success { color: #67c23a; }

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
</style>
