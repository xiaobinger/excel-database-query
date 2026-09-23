<template>
  <div class="operation-logs">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-clipboard-list"></i> 操作日志</span>
          <div class="header-actions">
            <el-select v-model="actionFilter" placeholder="操作类型" clearable filterable style="width: 140px" @change="fetchData">
              <el-option v-for="opt in actionOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-input
              v-model="keywordFilter"
              placeholder="搜索用户名/IP/详情"
              clearable
              style="width: 220px"
              @keyup.enter="fetchData"
              @clear="fetchData"
            >
              <template #prefix><i class="fas fa-search"></i></template>
            </el-input>
            <el-date-picker
              v-model="dateFilter"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 280px"
              @change="fetchData"
            />
            <el-button @click="resetFilters">重置</el-button>
            <el-button type="danger" size="small" plain @click="handleClearAll">
              <i class="fas fa-trash"></i> 清空日志
            </el-button>
            <el-button type="primary" @click="fetchData" style="margin-left: 12px">
              <i class="fas fa-sync-alt"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="logList" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="操作人" min-width="110" show-overflow-tooltip />
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.target_type" type="info" size="small" effect="plain">{{ targetLabel(row.target_type) }}</el-tag>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="目标ID" width="80" align="center">
          <template #default="{ row }">
            {{ row.target_id != null ? row.target_id : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作详情" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="detail-text">{{ row.detail || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="IP地址" width="150">
          <template #default="{ row }">
            <span class="ip-text">{{ row.ip_address || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="操作时间" width="180" show-overflow-tooltip />
      </el-table>

      <div class="pagination-area">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>

      <el-empty v-if="!loading && logList.length === 0" description="暂无操作日志" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const logList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const actionFilter = ref('')
const keywordFilter = ref('')
const dateFilter = ref(null)

const ACTION_LABELS = {
  create: '创建',
  update: '更新',
  delete: '删除',
  batch_delete: '批量删除',
  delete_all: '删除全部',
  login: '登录',
  logout: '登出',
  execute: '执行',
  export: '导出',
  chat: 'AI对话',
  submit: '提交',
  status_change: '状态流转',
  test: '测试',
  toggle: '启停',
  cancel: '取消',
  retry: '重试',
  abort: '中止',
  interrupt: '打断',
  comment: '评论',
  upload: '上传',
  clear: '清空',
  compress: '压缩',
  refresh: '刷新',
  confirm_action: '确认执行',
  send_email: '发送邮件',
}

const TARGET_LABELS = {
  user: '用户',
  role: '角色',
  script: '查询选项',
  database: '数据库',
  query: '查询',
  export: '导出',
  home_export: '首页导出',
  auto_export: '自动导出',
  task: '任务',
  ai_chat: 'AI对话',
  ai_strategy: 'AI策略',
  ticket: '工单',
  system_task: '系统任务',
  agent: 'AI Agent',
  mcp_server: 'MCP服务',
  business_system: '业务系统',
  pay: '付款',
  payment: '付款',
  pay_flow: '付款流程',
  profit_share: '分润',
  api_key: 'API密钥',
  ssh_config: 'SSH配置',
  lookup: '查询',
  dashboard: '仪表盘',
  log: '日志',
  auth: '认证',
  scheduler: '调度',
  strategy: '策略',
}

const actionOptions = Object.entries(ACTION_LABELS).map(([value, label]) => ({ value, label }))

function actionLabel(action) {
  return ACTION_LABELS[action] || action
}

const DANGER_ACTIONS = ['delete', 'batch_delete', 'delete_all', 'abort', 'cancel']
const SUCCESS_ACTIONS = ['create', 'login', 'submit']
const PRIMARY_ACTIONS = ['update', 'execute', 'export', 'chat', 'status_change', 'confirm_action']
const WARNING_ACTIONS = ['toggle', 'interrupt', 'retry']

function actionTagType(action) {
  if (DANGER_ACTIONS.includes(action)) return 'danger'
  if (SUCCESS_ACTIONS.includes(action)) return 'success'
  if (PRIMARY_ACTIONS.includes(action)) return 'primary'
  if (WARNING_ACTIONS.includes(action)) return 'warning'
  return 'info'
}

function targetLabel(type) {
  return TARGET_LABELS[type] || type
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: pageSize.value,
    }
    if (actionFilter.value) params.action = actionFilter.value
    if (keywordFilter.value) params.keyword = keywordFilter.value
    if (dateFilter.value && dateFilter.value.length === 2) {
      params.start_date = dateFilter.value[0]
      params.end_date = dateFilter.value[1]
    }
    const res = await api.logs.operation(params)
    logList.value = res.data || []
    total.value = res.total || 0
  } catch {
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  actionFilter.value = ''
  keywordFilter.value = ''
  dateFilter.value = null
  currentPage.value = 1
  fetchData()
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有操作日志吗？此操作不可恢复！',
      '清空确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.logs.clearOperation()
    ElMessage.success('操作日志已清空')
    currentPage.value = 1
    fetchData()
  } catch {
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.operation-logs {
  max-width: 1400px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  flex-wrap: wrap;
  gap: 10px;
}

.card-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.ip-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
}

.detail-text {
  font-size: 13px;
}

.pagination-area {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
