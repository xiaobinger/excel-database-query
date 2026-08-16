<template>
  <div class="ticket-analytics">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-chart-bar"></i> 工单统计</span>
          <div class="header-actions">
            <el-radio-group v-model="filters.dimension" size="small" @change="fetchData">
              <el-radio-button label="day">按天</el-radio-button>
              <el-radio-button label="month">按月</el-radio-button>
              <el-radio-button label="year">按年</el-radio-button>
            </el-radio-group>
            <el-select v-model="filters.date_field" placeholder="时间字段" size="small" style="width: 130px" @change="fetchData">
              <el-option label="按提交时间" value="submitted" />
              <el-option label="按处理完成时间" value="processed" />
            </el-select>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              value-format="YYYY-MM-DD"
              :shortcuts="dateShortcuts"
              style="width: 260px"
              @change="handleDateChange"
            />
            <el-button type="primary" size="small" @click="fetchData">
              <i class="fas fa-sync-alt"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 总览卡片 -->
      <el-row :gutter="16" class="summary-row" v-loading="loading">
        <el-col :xs="12" :sm="8" :md="4">
          <div class="summary-card summary-submitted">
            <div class="summary-icon"><i class="fas fa-file-alt"></i></div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.total_submitted || 0 }}</div>
              <div class="summary-label">提交总数</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="4">
          <div class="summary-card summary-assigned">
            <div class="summary-icon"><i class="fas fa-user-check"></i></div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.total_assigned || 0 }}</div>
              <div class="summary-label">指派总数</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="4">
          <div class="summary-card summary-completed">
            <div class="summary-icon"><i class="fas fa-check-double"></i></div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.total_completed || 0 }}</div>
              <div class="summary-label">完成总数</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="4">
          <div class="summary-card summary-rate">
            <div class="summary-icon"><i class="fas fa-percentage"></i></div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.overall_completion_rate || 0 }}%</div>
              <div class="summary-label">完成占比</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="4">
          <div class="summary-card summary-duration">
            <div class="summary-icon"><i class="fas fa-stopwatch"></i></div>
            <div class="summary-info">
              <div class="summary-value">{{ formatDuration(summary.overall_avg_duration_seconds || 0) }}</div>
              <div class="summary-label">平均处理时长</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="8" :md="4">
          <div class="summary-card summary-users">
            <div class="summary-icon"><i class="fas fa-users"></i></div>
            <div class="summary-info">
              <div class="summary-value">{{ summary.user_count || 0 }}</div>
              <div class="summary-label">参与人数</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 趋势图（CSS条形图） -->
      <el-card shadow="never" class="trend-card" v-if="periods.length > 0">
        <template #header>
          <span><i class="fas fa-chart-line"></i> {{ dataLabel }}趋势</span>
        </template>
        <div class="trend-chart">
          <div v-for="p in periods" :key="p.period" class="trend-bar-item">
            <div class="trend-bar-wrapper">
              <div class="trend-bar" :style="{ height: getBarHeight(p.count) + '%' }" :title="`${p.period}: ${p.count}个`">
                <span class="trend-bar-value" v-if="getBarHeight(p.count) > 15">{{ p.count }}</span>
              </div>
            </div>
            <div class="trend-bar-label">{{ p.period }}</div>
          </div>
        </div>
      </el-card>

      <!-- AI 统计模块 -->
      <el-card shadow="never" class="ai-stats-card" v-if="aiStats.length > 0 || summary.ai_total_assigned > 0">
        <template #header>
          <div class="table-header">
            <span><i class="fas fa-robot"></i> AI Agent 处理统计</span>
            <div class="ai-summary-inline">
              <span class="ai-summary-item">指派 <b>{{ summary.ai_total_assigned || 0 }}</b></span>
              <span class="ai-summary-item">完成 <b style="color: #67c23a">{{ summary.ai_total_completed || 0 }}</b></span>
              <span class="ai-summary-item">待确认 <b style="color: #e6a23c">{{ summary.ai_total_pending || 0 }}</b></span>
              <span class="ai-summary-item">失败 <b style="color: #f56c6c">{{ summary.ai_total_failed || 0 }}</b></span>
              <span class="ai-summary-item">完成率 <b>{{ summary.ai_completion_rate || 0 }}%</b></span>
              <span class="ai-summary-item">平均耗时 <b>{{ formatDuration(summary.ai_avg_duration_seconds || 0) }}</b></span>
            </div>
          </div>
        </template>
        <el-table :data="aiStats" stripe style="width: 100%">
          <el-table-column type="index" label="#" width="55" align="center" />
          <el-table-column prop="agent_name" label="AI Agent" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <i class="fas fa-robot" style="color: #722ed1; margin-right: 6px"></i>
              {{ row.agent_name }}
              <el-tag v-if="row.is_default" type="success" size="small" effect="plain" style="margin-left: 6px">默认</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_count" label="指派数" width="90" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="primary" size="small">{{ row.assigned_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="completed_count" label="完成数" width="90" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="success" size="small">{{ row.completed_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="pending_count" label="待确认" width="90" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="warning" size="small">{{ row.pending_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="failed_count" label="失败数" width="90" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="danger" size="small" v-if="row.failed_count > 0">{{ row.failed_count }}</el-tag>
              <span v-else style="color: #c0c4cc">0</span>
            </template>
          </el-table-column>
          <el-table-column prop="completion_rate" label="完成占比" width="180" align="center" sortable>
            <template #default="{ row }">
              <div class="rate-progress">
                <el-progress
                  :percentage="Math.min(row.completion_rate, 100)"
                  :color="getRateColor(row.completion_rate)"
                  :stroke-width="14"
                  :text-inside="true"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="avg_duration_seconds" label="平均处理时长" width="130" align="center" sortable>
            <template #default="{ row }">
              <span v-if="row.avg_duration_seconds > 0" :style="{ color: getDurationColor(row.avg_duration_seconds) }">
                <i class="fas fa-clock"></i> {{ formatDuration(row.avg_duration_seconds) }}
              </span>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 用户统计表格 -->
      <el-card shadow="never" class="table-card">
        <template #header>
          <div class="table-header">
            <span><i class="fas fa-table"></i> 用户工单统计明细</span>
            <span class="table-tip" v-if="!isAdmin">仅显示您自己的统计数据</span>
          </div>
        </template>
        <el-table :data="userStats" stripe v-loading="loading" style="width: 100%">
          <el-table-column type="index" label="#" width="55" align="center" />
          <el-table-column prop="display_name" label="用户" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <i class="fas fa-user-circle" style="color: #409eff; margin-right: 6px"></i>
              {{ row.display_name }}
            </template>
          </el-table-column>
          <el-table-column prop="submitted_count" label="提交数" width="100" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="primary" size="small">{{ row.submitted_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_count" label="被指派数" width="110" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="info" size="small">{{ row.assigned_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="completed_count" label="完成数" width="100" align="center" sortable>
            <template #default="{ row }">
              <el-tag type="success" size="small">{{ row.completed_count }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="completion_rate" label="完成占比" width="200" align="center" sortable>
            <template #default="{ row }">
              <div class="rate-progress">
                <el-progress
                  :percentage="Math.min(row.completion_rate, 100)"
                  :color="getRateColor(row.completion_rate)"
                  :stroke-width="14"
                  :text-inside="true"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="avg_duration_seconds" label="平均处理时长" width="140" align="center" sortable>
            <template #default="{ row }">
              <span v-if="row.avg_duration_seconds > 0" :style="{ color: getDurationColor(row.avg_duration_seconds) }">
                <i class="fas fa-clock"></i> {{ formatDuration(row.avg_duration_seconds) }}
              </span>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && userStats.length === 0" description="暂无统计数据" />
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage } from 'element-plus'

const store = useAppStore()
const isAdmin = computed(() => store.isAdmin)

const loading = ref(false)
const filters = reactive({
  dimension: 'month',
  date_field: 'submitted',
  start_date: '',
  end_date: '',
})
const dateRange = ref([])

const summary = ref({})
const periods = ref([])
const userStats = ref([])
const aiStats = ref([])
const dataLabel = ref('月份')

const dateShortcuts = [
  {
    text: '近7天',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 6)
      return [start, end]
    }
  },
  {
    text: '近30天',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 29)
      return [start, end]
    }
  },
  {
    text: '本月',
    value: () => {
      const now = new Date()
      const start = new Date(now.getFullYear(), now.getMonth(), 1)
      return [start, now]
    }
  },
  {
    text: '本季度',
    value: () => {
      const now = new Date()
      const quarter = Math.floor(now.getMonth() / 3)
      const start = new Date(now.getFullYear(), quarter * 3, 1)
      return [start, now]
    }
  },
  {
    text: '本年',
    value: () => {
      const now = new Date()
      const start = new Date(now.getFullYear(), 0, 1)
      return [start, now]
    }
  },
]

function handleDateChange(val) {
  if (val && val.length === 2) {
    filters.start_date = val[0]
    filters.end_date = val[1]
  } else {
    filters.start_date = ''
    filters.end_date = ''
  }
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      dimension: filters.dimension,
      date_field: filters.date_field,
    }
    if (filters.start_date) params.start_date = filters.start_date
    if (filters.end_date) params.end_date = filters.end_date

    const res = await api.tickets.analytics(params)
    const data = res.data || res
    summary.value = data.summary || {}
    periods.value = data.periods || []
    userStats.value = data.user_stats || []
    aiStats.value = data.ai_stats || []
    dataLabel.value = data.date_label || '月份'
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '获取统计数据失败')
  } finally {
    loading.value = false
  }
}

function getBarHeight(count) {
  const max = Math.max(...periods.value.map(p => p.count), 1)
  return Math.max((count / max) * 100, 4)
}

function getRateColor(rate) {
  if (rate >= 80) return '#67c23a'
  if (rate >= 50) return '#e6a23c'
  return '#f56c6c'
}

function getDurationColor(seconds) {
  if (seconds <= 300) return '#67c23a'       // 5分钟内 绿色
  if (seconds <= 3600) return '#e6a23c'       // 1小时内 黄色
  return '#f56c6c'                             // 超过1小时 红色
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '-'
  if (seconds < 60) {
    return Math.round(seconds) + '秒'
  }
  if (seconds < 3600) {
    return Math.round(seconds / 60) + '分钟'
  }
  if (seconds < 86400) {
    return (seconds / 3600).toFixed(1) + '小时'
  }
  const days = Math.floor(seconds / 86400)
  const remainHours = Math.round((seconds % 86400) / 3600)
  return remainHours > 0 ? `${days}天${remainHours}小时` : `${days}天`
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.ticket-analytics {
  max-width: 1400px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  flex-wrap: wrap;
  gap: 8px;
}

.card-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-row {
  margin-bottom: 16px;
}

.summary-card {
  display: flex;
  align-items: center;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  color: #fff;
  transition: transform 0.2s;
}

.summary-card:hover {
  transform: translateY(-2px);
}

.summary-icon {
  font-size: 32px;
  margin-right: 14px;
  opacity: 0.9;
}

.summary-info {
  flex: 1;
  min-width: 0;
}

.summary-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.summary-label {
  font-size: 13px;
  opacity: 0.9;
  margin-top: 4px;
}

.summary-submitted { background: linear-gradient(135deg, #409eff, #66b1ff); }
.summary-assigned { background: linear-gradient(135deg, #909399, #b1b3b8); }
.summary-completed { background: linear-gradient(135deg, #67c23a, #85ce61); }
.summary-rate { background: linear-gradient(135deg, #e6a23c, #ebb563); }
.summary-duration { background: linear-gradient(135deg, #f56c6c, #f78989); }
.summary-users { background: linear-gradient(135deg, #722ed1, #9254de); }

.trend-card {
  margin-bottom: 16px;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 220px;
  padding: 12px 8px;
  overflow-x: auto;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}

.trend-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 50px;
  flex: 1;
  height: 100%;
}

.trend-bar-wrapper {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.trend-bar {
  width: 70%;
  max-width: 40px;
  background: linear-gradient(180deg, #409eff, #66b1ff);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 4px;
}

.trend-bar:hover {
  background: linear-gradient(180deg, #66b1ff, #79bbff);
}

.trend-bar-value {
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.trend-bar-label {
  font-size: 11px;
  color: #606266;
  margin-top: 6px;
  white-space: nowrap;
  transform: rotate(-45deg);
  transform-origin: center top;
}

.table-card {
  margin-bottom: 0;
}

.ai-stats-card {
  margin-bottom: 16px;
  border-left: 3px solid #722ed1;
}

.ai-summary-inline {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #606266;
}

.ai-summary-item b {
  margin-left: 4px;
  font-weight: 600;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.table-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.rate-progress {
  width: 100%;
}

:deep(.el-progress-bar__innerText) {
  font-size: 12px;
}
</style>
