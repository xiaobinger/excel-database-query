<template>
  <div class="profit-share">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-hand-holding-usd"></i> 分润导出</span>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      >
        <template #title>
          根据一级代理商编号及交易时间范围，逐笔订单计算各级代理分润金额，按月聚合后导出 Excel。
          <br />数据库连接默认使用"融聚商户通(海科)"，也可手动指定。
        </template>
      </el-alert>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" class="params-form">
        <el-form-item label="代理商编号" prop="org_no">
          <el-input
            v-model="form.org_no"
            placeholder="请输入一级代理商编号，例如 AG10000557"
            clearable
            style="max-width: 360px"
          />
        </el-form-item>

        <el-form-item label="交易时间范围" prop="time_range">
          <el-date-picker
            v-model="form.time_range"
            type="datetimerange"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%; max-width: 480px"
          />
          <div class="month-shortcut">
            <span class="shortcut-label">按月份快捷选择:</span>
            <el-date-picker
              v-model="monthRange.start"
              type="month"
              placeholder="起始月"
              value-format="YYYY-MM"
              style="width: 140px"
              :clearable="false"
            />
            <span class="range-sep">至</span>
            <el-date-picker
              v-model="monthRange.end"
              type="month"
              placeholder="结束月"
              value-format="YYYY-MM"
              style="width: 140px"
              :clearable="false"
            />
            <el-button type="primary" plain size="small" @click="applyMonthRange">应用</el-button>
            <span v-if="monthShortcutTip" class="shortcut-tip">{{ monthShortcutTip }}</span>
          </div>
        </el-form-item>

        <el-form-item label="数据库连接">
          <el-select
            v-model="form.database_connection_id"
            placeholder="不选则自动查找 融聚商户通(海科)"
            clearable
            filterable
            style="max-width: 480px"
          >
            <el-option
              v-for="db in databases"
              :key="db.id"
              :label="db.name"
              :value="db.id"
            >
              <span style="float: left">{{ db.name }}</span>
              <span style="float: right; color: #8492a6; font-size: 12px">{{ db.db_type }}</span>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>

      <div class="execute-area">
        <el-button
          v-if="!executing"
          type="success"
          size="large"
          @click="executeExport"
          :loading="submitting"
        >
          <i class="fas fa-play"></i> 开始执行
        </el-button>
        <el-button v-if="executing" type="danger" size="large" @click="cancelExport">
          <i class="fas fa-stop"></i> 终止任务
        </el-button>
      </div>

      <div v-if="taskId" class="progress-area">
        <div v-if="executing" class="executing-indicator">
          <div class="spinner-ring"></div>
          <span class="spinner-text">分润计算中...</span>
        </div>
        <el-divider content-position="left">执行进度</el-divider>
        <el-progress :percentage="progress" :status="progressStatus" :stroke-width="20" :text-inside="true" />
        <div class="status-info">
          <el-tag :type="statusType" size="large">{{ statusLabel }}</el-tag>
          <span v-if="taskStatus.total_rows" class="status-detail">分润记录: {{ taskStatus.total_rows }}</span>
          <span v-if="taskStatus.success_count" class="status-detail success">成功: {{ taskStatus.success_count }}</span>
        </div>

        <div v-if="taskStatus.error_message" class="error-message">
          <el-alert
            :title="taskStatus.error_message"
            type="error"
            :closable="false"
            show-icon
          />
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
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const formRef = ref(null)
const databases = ref([])
const submitting = ref(false)
const executing = ref(false)
const taskId = ref(null)
const progress = ref(0)
const taskStatus = ref({})
const logLines = ref([])
const logContentRef = ref(null)
let eventSource = null

const form = reactive({
  org_no: '',
  time_range: [],
  database_connection_id: null,
})

// 按月份快捷选择
const monthRange = reactive({
  start: '',
  end: '',
})
const monthShortcutTip = ref('')

// 将 YYYY-MM 转为 月初 00:00:00
function monthToStart(monthStr) {
  if (!monthStr) return ''
  return `${monthStr}-01 00:00:00`
}

// 将 YYYY-MM 转为 月末 23:59:59（下个月1号减1秒，自动处理闰年/大小月）
function monthToEnd(monthStr) {
  if (!monthStr) return ''
  const [year, month] = monthStr.split('-').map(Number)
  const nextMonth = new Date(year, month, 1) // month 是 1-12，传 month 即下个月1号
  nextMonth.setSeconds(nextMonth.getSeconds() - 1)
  const y = nextMonth.getFullYear()
  const m = String(nextMonth.getMonth() + 1).padStart(2, '0')
  const d = String(nextMonth.getDate()).padStart(2, '0')
  const h = String(nextMonth.getHours()).padStart(2, '0')
  const mi = String(nextMonth.getMinutes()).padStart(2, '0')
  const s = String(nextMonth.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${h}:${mi}:${s}`
}

function applyMonthRange() {
  if (!monthRange.start || !monthRange.end) {
    ElMessage.warning('请选择起始月份和结束月份')
    return
  }
  if (monthRange.start > monthRange.end) {
    ElMessage.warning('起始月份不能晚于结束月份')
    return
  }
  const startTime = monthToStart(monthRange.start)
  const endTime = monthToEnd(monthRange.end)
  form.time_range = [startTime, endTime]
  monthShortcutTip.value = `已应用: ${startTime} ~ ${endTime}`
  ElMessage.success('时间范围已设置')
}

const rules = {
  org_no: [{ required: true, message: '请输入代理商编号', trigger: 'blur' }],
  time_range: [{ required: true, message: '请选择交易时间范围', trigger: 'change' }],
}

const progressStatus = computed(() => {
  const s = taskStatus.value.status
  if (s === 'completed') return 'success'
  if (s === 'failed' || s === 'cancelled' || s === 'manual_cancelled') return 'exception'
  return ''
})

const statusType = computed(() => {
  const s = taskStatus.value.status
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'cancelled' || s === 'manual_cancelled') return 'warning'
  return 'primary'
})

const statusLabel = computed(() => {
  const map = {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
    manual_cancelled: '已终止',
  }
  return map[taskStatus.value.status] || '未知'
})

async function loadDatabases() {
  try {
    const res = await api.profitShare.databases()
    databases.value = res.data || res || []
  } catch {
    databases.value = []
  }
}

async function executeExport() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const data = {
      org_no: form.org_no.trim(),
      start_time: form.time_range[0],
      end_time: form.time_range[1],
    }
    if (form.database_connection_id) {
      data.database_connection_id = form.database_connection_id
    }

    const res = await api.profitShare.execute(data)
    const result = res.data || res
    taskId.value = result.task_id
    executing.value = true
    progress.value = 0
    logLines.value = []
    taskStatus.value = {}
    startSSE(taskId.value)
    ElMessage.success(result.message || '任务已提交')
  } catch (e) {
    const msg = e?.response?.data?.message || '提交失败'
    ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

function startSSE(tid) {
  if (eventSource) {
    eventSource.close()
  }
  const url = api.profitShare.streamStatus(tid)
  eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      taskStatus.value = { ...taskStatus.value, ...data }
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
      if (['completed', 'failed', 'cancelled', 'manual_cancelled', 'timeout'].includes(data.status)) {
        executing.value = false
        if (data.status === 'completed') {
          progress.value = 100
        }
        if (data.status === 'timeout') {
          ElMessage.warning('状态推送超时，请稍后刷新查看')
        }
        eventSource.close()
        eventSource = null
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
    const res = await api.profitShare.status(tid)
    const data = res.data || res
    taskStatus.value = data
    if (data.progress !== undefined) {
      progress.value = Math.round(data.progress)
    }
    if (['completed', 'failed', 'cancelled', 'manual_cancelled'].includes(data.status)) {
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
    await ElMessageBox.confirm('确定要终止当前分润导出任务吗？', '终止任务', {
      confirmButtonText: '确定终止',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await api.profitShare.cancel(taskId.value)
    ElMessage.success('任务已终止')
  } catch {
  }
}

async function downloadResult() {
  if (!taskId.value) return
  const url = api.download.file(taskId.value)
  const defaultName = `profit_share_${taskId.value.slice(0, 8)}.xlsx`
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
      const resp = await fetch(url)
      const blob = await resp.blob()
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = defaultName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(blobUrl)
    }
  } catch (e) {
    if (e.name === 'AbortError') return
    ElMessage.error('下载失败')
  }
}

onMounted(() => {
  loadDatabases()
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})
</script>

<style scoped>
.profit-share {
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

.params-form {
  margin-top: 10px;
}

.month-shortcut {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.shortcut-label {
  font-size: 13px;
  color: #606266;
}

.range-sep {
  color: #909399;
  font-size: 13px;
}

.shortcut-tip {
  font-size: 12px;
  color: #67c23a;
  margin-left: 4px;
}

.execute-area {
  display: flex;
  justify-content: center;
  margin-top: 24px;
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

.error-message {
  margin-top: 16px;
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
  height: 240px;
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
  justify-content: center;
  margin-top: 20px;
}
</style>
