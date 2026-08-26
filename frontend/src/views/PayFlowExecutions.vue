<template>
  <div class="page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span><i class="fa fa-stream"></i> 代付流程执行记录</span>
          <el-button @click="loadExecutions"><i class="fa fa-refresh"></i> 刷新</el-button>
        </div>
      </template>

      <!-- 筛选 -->
      <el-form :inline="true" class="filter-bar">
        <el-form-item label="批次">
          <el-input v-model="filters.batch_id" placeholder="批次ID" clearable style="width:220px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width:120px">
            <el-option label="待执行" value="pending" />
            <el-option label="执行中" value="running" />
            <el-option label="等待中" value="waiting" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadExecutions">查询</el-button>
        </el-form-item>
      </el-form>

      <!-- 执行记录表格 -->
      <el-table :data="executions" stripe border style="width:100%" empty-text="暂无执行记录">
        <el-table-column prop="execution_id" label="执行ID" width="220" show-overflow-tooltip />
        <el-table-column prop="template_name" label="模板" width="140" />
        <el-table-column label="行号" width="60" align="center">
          <template #default="{ row }">{{ row.row_index }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前节点" width="100" align="center">
          <template #default="{ row }">{{ row.current_node_index + 1 }}</template>
        </el-table-column>
        <el-table-column label="循环" width="80" align="center">
          <template #default="{ row }">
            <span v-if="row.loop_count > 0" class="loop-badge">{{ row.loop_count }}次</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">详情</el-button>
            <el-button v-if="row.status === 'running' || row.status === 'waiting'" size="small" type="warning" @click="cancelExecution(row)">取消</el-button>
            <el-button v-if="row.status === 'failed' || row.status === 'cancelled'" size="small" type="success" @click="retryExecution(row)">重试</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
        class="pagination"
      />
    </el-card>

    <!-- 详情 Dialog -->
    <el-dialog v-model="detailVisible" title="流程执行详情" width="1000px" :close-on-click-modal="false">
      <div v-if="detailData" class="detail-container">
        <!-- 概要信息 -->
        <el-descriptions :column="4" border size="small" class="summary-box">
          <el-descriptions-item label="执行ID">{{ detailData.execution_id }}</el-descriptions-item>
          <el-descriptions-item label="模板">{{ detailData.template_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detailData.status)" size="small">{{ statusLabel(detailData.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="当前节点">{{ detailData.current_node_index + 1 }}</el-descriptions-item>
        </el-descriptions>

        <!-- 流程走势图 -->
        <div class="flow-chart">
          <div class="chart-title"><i class="fa fa-project-diagram"></i> 流程走势</div>
          <div class="chart-nodes">
            <div
              v-for="(node, idx) in detailData.template_nodes"
              :key="node.id"
              class="chart-node"
              :class="getNodeStatusClass(detailData, idx)"
            >
              <div class="chart-node-icon">
                <i :class="node.type === 'pay' ? 'fa fa-credit-card' : 'fa fa-bell'"></i>
              </div>
              <div class="chart-node-name">{{ node.name }}</div>
              <div class="chart-node-status">{{ getNodeStatusLabel(detailData, idx) }}</div>
              <div v-if="node.loop?.enabled" class="chart-node-loop"><i class="fa fa-repeat"></i> 循环</div>
            </div>
            <div v-for="i in (detailData.template_nodes.length - 1)" :key="'arrow-' + i" class="chart-arrow">
              <i class="fa fa-arrow-down"></i>
            </div>
          </div>
        </div>

        <!-- 节点执行日志 -->
        <div class="node-logs">
          <div class="chart-title"><i class="fa fa-list"></i> 节点执行日志</div>
          <el-collapse v-model="activeLogIdx">
            <el-collapse-item v-for="(ne, nIdx) in detailData.node_executions" :key="nIdx" :name="String(nIdx)">
              <template #title>
                <span class="log-node-title">
                  <el-tag :type="ne.status === 'completed' ? 'success' : ne.status === 'failed' ? 'danger' : 'warning'" size="small" style="margin-right:8px">
                    {{ ne.status === 'completed' ? '成功' : ne.status === 'failed' ? '失败' : ne.status === 'running' ? '执行中' : ne.status }}
                  </el-tag>
                  {{ ne.node_name }}
                  <span v-if="ne.attempt > 1" class="loop-count">第 {{ ne.attempt }} 次执行</span>
                </span>
              </template>
              <div class="log-detail">
                <div v-if="ne.error_message" class="log-error"><strong>失败原因:</strong> {{ ne.error_message }}</div>
                <div v-if="ne.result_fields && Object.keys(ne.result_fields).length" class="log-fields">
                  <strong>返回字段:</strong>
                  <el-table :data="fieldsToRows(ne.result_fields)" size="small" border>
                    <el-table-column prop="key" label="字段" width="180" />
                    <el-table-column prop="value" label="值" />
                  </el-table>
                </div>
                <div v-if="ne.logs?.length" class="log-entries">
                  <strong>执行日志:</strong>
                  <pre class="log-pre">{{ formatLogs(ne.logs) }}</pre>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-if="!detailData.node_executions?.length" description="暂无节点执行记录" :image-size="60" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import dayjs from 'dayjs'

const executions = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const detailVisible = ref(false)
const detailData = ref(null)
const activeLogIdx = ref([])
let pollTimer = null

const filters = reactive({ batch_id: '', status: '' })

function formatTime(ts) {
  return ts ? dayjs(ts).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function statusTagType(status) {
  return { pending: 'info', running: 'warning', waiting: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' }[status] || 'info'
}

function statusLabel(status) {
  return { pending: '待执行', running: '执行中', waiting: '等待中', completed: '已完成', failed: '失败', cancelled: '已取消' }[status] || status
}

function fieldsToRows(fields) {
  return Object.entries(fields).map(([key, value]) => ({ key, value: typeof value === 'object' ? JSON.stringify(value) : String(value ?? '') }))
}

function formatLogs(logs) {
  if (!logs) return ''
  if (Array.isArray(logs)) return logs.map(l => typeof l === 'string' ? l : JSON.stringify(l)).join('\n')
  return String(logs)
}

function getNodeStatusClass(detail, idx) {
  const nodeExecs = detail.node_executions || []
  const templateNodes = detail.template_nodes || []
  const nodeId = templateNodes[idx]?.id
  const matched = nodeExecs.filter(n => n.node_id === nodeId)
  if (matched.some(n => n.status === 'failed')) return 'node-failed'
  if (matched.some(n => n.status === 'running')) return 'node-running'
  if (matched.every(n => n.status === 'completed') && matched.length > 0) return 'node-completed'
  if (detail.current_node_index === idx && detail.status === 'running') return 'node-running'
  return 'node-pending'
}

function getNodeStatusLabel(detail, idx) {
  const cls = getNodeStatusClass(detail, idx)
  return { 'node-completed': '已完成', 'node-running': '执行中', 'node-failed': '失败', 'node-pending': '待执行' }[cls] || '待执行'
}

async function loadExecutions() {
  try {
    const params = { page: page.value, per_page: pageSize.value }
    if (filters.batch_id) params.batch_id = filters.batch_id
    if (filters.status) params.status = filters.status
    const res = await api.payFlow.executions(params)
    executions.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) { /* ignore */ }
}

function onPageChange(p) {
  page.value = p
  loadExecutions()
}

async function viewDetail(row) {
  try {
    const res = await api.payFlow.getExecution(row.execution_id)
    detailData.value = res.data
    activeLogIdx.value = []
    detailVisible.value = true
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '加载详情失败')
  }
}

async function cancelExecution(row) {
  try {
    await api.payFlow.cancelExecution(row.execution_id)
    ElMessage.success('已取消')
    loadExecutions()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '取消失败')
  }
}

async function retryExecution(row) {
  try {
    await api.payFlow.retryExecution(row.execution_id)
    ElMessage.success('已重试')
    loadExecutions()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '重试失败')
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(() => {
    if (detailVisible.value && detailData.value) {
      api.payFlow.getExecution(detailData.value.execution_id).then(res => {
        detailData.value = res.data
      }).catch(() => {})
    }
    loadExecutions()
  }, 5000)
}

onMounted(() => {
  loadExecutions()
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.page { padding: 0; }
.page-card { border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-header > span:first-child { font-size: 15px; font-weight: 600; }
.filter-bar { margin-bottom: 12px; }
.pagination { margin-top: 16px; justify-content: center; }
.loop-badge { color: #e6a23c; font-weight: 600; }
.detail-container { max-height: 70vh; overflow-y: auto; }
.summary-box { margin-bottom: 16px; }
.chart-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; }
.flow-chart { margin-bottom: 20px; }
.chart-nodes { display: flex; flex-direction: column; align-items: center; gap: 0; }
.chart-node { width: 200px; padding: 12px; border-radius: 8px; border: 2px solid #dcdfe6; background: #fff; text-align: center; transition: all 0.3s; position: relative; }
.chart-node.node-pending { border-color: #dcdfe6; background: #fafafa; }
.chart-node.node-running { border-color: #409eff; background: #ecf5ff; animation: pulse 1.5s infinite; }
.chart-node.node-completed { border-color: #67c23a; background: #f0f9eb; }
.chart-node.node-failed { border-color: #f56c6c; background: #fef0f0; }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(64,158,255,0.3); } 50% { box-shadow: 0 0 0 8px rgba(64,158,255,0); } }
.chart-node-icon { font-size: 20px; margin-bottom: 4px; }
.chart-node-name { font-weight: 600; font-size: 13px; }
.chart-node-status { font-size: 12px; color: #909399; margin-top: 2px; }
.chart-node-loop { font-size: 11px; color: #e6a23c; margin-top: 2px; }
.chart-arrow { color: #c0c4cc; font-size: 16px; padding: 4px 0; }
.log-node-title { display: flex; align-items: center; }
.loop-count { color: #e6a23c; font-size: 12px; margin-left: 8px; }
.log-detail { padding: 8px 0; }
.log-error { color: #f56c6c; margin-bottom: 8px; }
.log-fields { margin-bottom: 8px; }
.log-entries { margin-top: 4px; }
.log-pre { max-height: 200px; overflow: auto; background: #f5f7fa; border-radius: 4px; padding: 8px; font-size: 12px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; margin: 4px 0 0; }
.node-logs { margin-top: 16px; }
</style>
