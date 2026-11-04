<template>
  <div class="token-stats-page">
    <!-- 概览卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :xs="12" :sm="6">
        <div class="stat-card total">
          <div class="stat-icon"><i class="fas fa-coins"></i></div>
          <div class="stat-info">
            <div class="stat-label">总Token消耗</div>
            <div class="stat-value">{{ fmtNum(overview.total_tokens) }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card chat">
          <div class="stat-icon"><i class="fas fa-robot"></i></div>
          <div class="stat-info">
            <div class="stat-label">AI对话消耗</div>
            <div class="stat-value">{{ fmtNum(overview.ai_chat_tokens) }}</div>
            <div class="stat-sub">{{ fmtNum(overview.chat_message_count) }} 条对话消息</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card ticket">
          <div class="stat-icon"><i class="fas fa-tasks"></i></div>
          <div class="stat-info">
            <div class="stat-label">工单消耗</div>
            <div class="stat-value">{{ fmtNum(overview.ticket_tokens) }}</div>
            <div class="stat-sub">{{ fmtNum(overview.ticket_count) }} 个AI工单</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card breakdown">
          <div class="stat-icon"><i class="fas fa-arrow-right-arrow-left"></i></div>
          <div class="stat-info">
            <div class="stat-label">输入 / 输出</div>
            <div class="stat-value">{{ fmtNum(overview.prompt_tokens) }}</div>
            <div class="stat-sub">输出 {{ fmtNum(overview.completion_tokens) }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 维度切换 -->
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label"><i class="fas fa-clock"></i> 时间范围</span>
        <el-radio-group v-model="filters.days" size="small" @change="reload">
          <el-radio-button :value="7">近7天</el-radio-button>
          <el-radio-button :value="30">近30天</el-radio-button>
          <el-radio-button :value="90">近90天</el-radio-button>
          <el-radio-button :value="0">全部</el-radio-button>
        </el-radio-group>
      </div>
      <div class="filter-group">
        <span class="filter-label"><i class="fas fa-layer-group"></i> 使用场景</span>
        <el-radio-group v-model="filters.scene" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="ai_chat">AI对话</el-radio-button>
          <el-radio-button value="ticket">工单</el-radio-button>
        </el-radio-group>
      </div>
      <div class="filter-group">
        <span class="filter-label"><i class="fas fa-chart-line"></i> 趋势粒度</span>
        <el-radio-group v-model="filters.granularity" size="small">
          <el-radio-button value="day">按日</el-radio-button>
          <el-radio-button value="week">按周</el-radio-button>
          <el-radio-button value="month">按月</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title"><i class="fas fa-chart-pie"></i> 场景占比</span></template>
          <div v-show="hasUsage" ref="pieChartRef" class="chart-body"></div>
          <el-empty v-if="!hasUsage" description="暂无Token消耗数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="16">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title"><i class="fas fa-chart-area"></i> 消耗趋势</span></template>
          <div ref="trendChartRef" class="chart-body"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 模型使用 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="card-title"><i class="fas fa-microchip"></i> 模型占比（AI对话Token）</span></template>
          <div v-show="hasModelUsage" ref="modelChartRef" class="chart-body"></div>
          <el-empty v-if="!hasModelUsage" description="暂无模型使用数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="16">
        <el-card shadow="never" class="ranking-card">
          <template #header>
            <div class="ranking-header">
              <span class="card-title"><i class="fas fa-trophy"></i> 模型使用排名</span>
              <span class="ranking-tip">
                <template v-if="topModel">
                  <i class="fas fa-crown crown"></i> 最受欢迎：<b>{{ topModel }}</b>
                </template>
                <template v-else>按AI对话Token降序</template>
              </span>
            </div>
          </template>
          <el-table :data="models" v-loading="loading" size="default" max-height="320">
            <el-table-column label="排名" width="70" align="center">
              <template #default="{ row }">
                <span class="rank-badge" :class="'rank-' + row.rank">{{ row.rank }}</span>
              </template>
            </el-table-column>
            <el-table-column label="模型" min-width="200">
              <template #default="{ row }">
                <span class="model-name">{{ row.model }}</span>
                <el-tag v-if="row.model === topModel" size="small" type="warning" effect="light" class="top-tag">
                  <i class="fas fa-crown"></i> 最受欢迎
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="tokens" label="对话Token" min-width="120" sortable align="right">
              <template #default="{ row }">{{ fmtNum(row.tokens) }}</template>
            </el-table-column>
            <el-table-column prop="message_count" label="消息数" width="100" sortable align="right">
              <template #default="{ row }">{{ fmtNum(row.message_count) }}</template>
            </el-table-column>
            <el-table-column prop="ticket_count" label="工单次数" width="100" sortable align="right">
              <template #default="{ row }">{{ fmtNum(row.ticket_count) }}</template>
            </el-table-column>
            <el-table-column label="占比" width="90" align="right">
              <template #default="{ row }">{{ row.share }}%</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 用户排名 -->
    <el-card shadow="never" class="ranking-card">
      <template #header>
        <div class="ranking-header">
          <span class="card-title"><i class="fas fa-ranking-star"></i> 用户使用量排名</span>
          <span class="ranking-tip">当前时间范围内，Token总消耗降序（前100名）</span>
        </div>
      </template>
      <el-table :data="ranking" v-loading="loading" size="default" :default-sort="{ prop: 'total_tokens', order: 'descending' }">
        <el-table-column label="排名" width="70" align="center">
          <template #default="{ row }">
            <span class="rank-badge" :class="'rank-' + row.rank">{{ row.rank }}</span>
          </template>
        </el-table-column>
        <el-table-column label="用户" min-width="140">
          <template #default="{ row }">
            <span class="rank-user">{{ row.display_name || row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ai_chat_tokens" label="AI对话消耗" min-width="120" sortable align="right">
          <template #default="{ row }">{{ fmtNum(row.ai_chat_tokens) }}</template>
        </el-table-column>
        <el-table-column prop="ticket_tokens" label="工单消耗" min-width="120" sortable align="right">
          <template #default="{ row }">{{ fmtNum(row.ticket_tokens) }}</template>
        </el-table-column>
        <el-table-column prop="message_count" label="对话消息" min-width="100" sortable align="right">
          <template #default="{ row }">{{ fmtNum(row.message_count) }}</template>
        </el-table-column>
        <el-table-column prop="ticket_count" label="AI工单数" min-width="100" sortable align="right">
          <template #default="{ row }">{{ fmtNum(row.ticket_count) }}</template>
        </el-table-column>
        <el-table-column prop="total_tokens" label="总消耗" min-width="130" sortable align="right" sort-by="total_tokens">
          <template #default="{ row }">
            <div class="total-cell">
              <span class="total-num">{{ fmtNum(row.total_tokens) }}</span>
              <el-progress
                :percentage="row.share"
                :stroke-width="6"
                :show-text="false"
                class="share-bar"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="占比" width="80" align="right">
          <template #default="{ row }">{{ row.share }}%</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const filters = reactive({ days: 30, scene: 'all', granularity: 'day' })
const loading = ref(false)
const overview = ref({ total_tokens: 0, ai_chat_tokens: 0, ticket_tokens: 0, prompt_tokens: 0, completion_tokens: 0, chat_message_count: 0, ticket_count: 0 })
const ranking = ref([])
const trend = ref([])
const models = ref([])
const topModel = ref('')

const hasUsage = computed(() => overview.value.total_tokens > 0)
const hasModelUsage = computed(() => models.value.some(m => m.tokens > 0))

const fmtNum = (n) => (n ?? 0).toLocaleString('zh-CN')

// ── 图表 ──────────────────────────────────────────────
const pieChartRef = ref(null)
const trendChartRef = ref(null)
const modelChartRef = ref(null)
let pieChart = null
let trendChart = null
let modelChart = null

const SCENE_COLORS = { ai_chat: '#409eff', ticket: '#67c23a', total: '#e6a23c' }
const SCENE_NAMES = { ai_chat: 'AI对话', ticket: '工单', total: '总量' }

const MODEL_COLORS = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#9b59b6',
  '#00b8a9', '#ff8c42', '#5470c6', '#91cc75', '#909399']

function renderPieChart() {
  if (!pieChartRef.value) return
  if (!pieChart) pieChart = echarts.init(pieChartRef.value)
  const o = overview.value
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, itemWidth: 12, itemHeight: 12 },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '46%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: 'rgba(255,255,255,0.6)', borderWidth: 2 },
      label: { formatter: '{b}\n{d}%' },
      data: [
        { value: o.ai_chat_tokens, name: 'AI对话', itemStyle: { color: SCENE_COLORS.ai_chat } },
        { value: o.ticket_tokens, name: '工单', itemStyle: { color: SCENE_COLORS.ticket } },
      ],
    }],
    graphic: [{
      type: 'text', left: 'center', top: '44%',
      style: {
        text: fmtNum(o.total_tokens), textAlign: 'center', fill: 'var(--text-primary, #303133)',
        fontSize: 16, fontWeight: 600,
      },
    }],
  }, true)
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)
  const rows = trend.value
  const dates = rows.map(r => r.date)
  const showChat = filters.scene === 'all' || filters.scene === 'ai_chat'
  const showTicket = filters.scene === 'all' || filters.scene === 'ticket'
  const stacked = filters.scene === 'all'

  const series = []
  if (showChat) {
    series.push({
      name: SCENE_NAMES.ai_chat, type: 'line', smooth: true, stack: stacked ? 'total' : null,
      areaStyle: { opacity: 0.25 }, itemStyle: { color: SCENE_COLORS.ai_chat },
      data: rows.map(r => r.ai_chat_tokens),
    })
  }
  if (showTicket) {
    series.push({
      name: SCENE_NAMES.ticket, type: 'line', smooth: true, stack: stacked ? 'total' : null,
      areaStyle: { opacity: 0.25 }, itemStyle: { color: SCENE_COLORS.ticket },
      data: rows.map(r => r.ticket_tokens),
    })
  }
  if (stacked) {
    series.push({
      name: SCENE_NAMES.total, type: 'line', smooth: true,
      symbol: 'none', lineStyle: { type: 'dashed', width: 1.5 }, itemStyle: { color: SCENE_COLORS.total },
      data: rows.map(r => r.total_tokens),
    })
  }

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0, itemWidth: 12, itemHeight: 12 },
    grid: { left: 12, right: 20, top: 32, bottom: 8, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: dates, axisLabel: { rotate: dates.length > 20 ? 45 : 0 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
    series,
  }, true)
}

function renderModelChart() {
  if (!modelChartRef.value) return
  if (!modelChart) modelChart = echarts.init(modelChartRef.value)
  const rows = models.value.filter(m => m.tokens > 0)
  const top = rows.slice(0, 8)
  const rest = rows.slice(8)
  const data = top.map((r, i) => ({
    name: r.model, value: r.tokens,
    itemStyle: { color: r.model === topModel.value ? '#f7ba2a' : MODEL_COLORS[i % MODEL_COLORS.length] },
  }))
  if (rest.length) {
    data.push({
      name: '其他', value: rest.reduce((s, r) => s + r.tokens, 0),
      itemStyle: { color: '#c0c4cc' },
    })
  }
  const topName = topModel.value && topModel.value.length > 16
    ? topModel.value.slice(0, 16) + '…'
    : (topModel.value || '-')
  modelChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll', itemWidth: 12, itemHeight: 12 },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 6, borderColor: 'rgba(255,255,255,0.6)', borderWidth: 2 },
      label: { show: false },
      data,
    }],
    graphic: [
      {
        type: 'text', left: 'center', top: '39%',
        style: { text: topName, textAlign: 'center', fill: '#303133', fontSize: 13, fontWeight: 600 },
      },
      {
        type: 'text', left: 'center', top: '46%',
        style: { text: '最受欢迎模型', textAlign: 'center', fill: '#909399', fontSize: 11 },
      },
    ],
  }, true)
}

function resizeCharts() {
  pieChart?.resize()
  trendChart?.resize()
  modelChart?.resize()
}

// ── 数据加载 ──────────────────────────────────────────
async function loadOverview() {
  const res = await api.tokenStats.overview({ days: filters.days })
  overview.value = res.data || res
}

async function loadRanking() {
  const res = await api.tokenStats.ranking({ days: filters.days })
  ranking.value = res.data?.ranking || []
}

async function loadTrend() {
  const res = await api.tokenStats.trend({ days: filters.days, granularity: filters.granularity })
  trend.value = res.data?.trend || []
}

async function loadModels() {
  const res = await api.tokenStats.models({ days: filters.days })
  models.value = res.data?.models || []
  topModel.value = res.data?.top_model || ''
}

async function reload() {
  loading.value = true
  try {
    await Promise.all([loadOverview(), loadRanking(), loadTrend(), loadModels()])
    await nextTick()
    renderPieChart()
    renderTrendChart()
    renderModelChart()
    resizeCharts()
  } finally {
    loading.value = false
  }
}

watch(() => filters.scene, () => renderTrendChart())
watch(() => filters.granularity, async () => {
  await loadTrend()
  await nextTick()
  renderTrendChart()
})

onMounted(() => {
  reload()
  window.addEventListener('resize', resizeCharts)
})

onActivated(() => nextTick(resizeCharts))
onDeactivated(() => window.removeEventListener('resize', resizeCharts))
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  pieChart?.dispose()
  trendChart?.dispose()
  modelChart?.dispose()
  pieChart = null
  trendChart = null
  modelChart = null
})
</script>

<style scoped>
.token-stats-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-cards {
  margin: 0 !important;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e4e7ed);
  background: var(--card-bg, #fff);
  height: 100%;
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
  color: #fff;
}

.stat-card.total .stat-icon { background: linear-gradient(135deg, #e6a23c, #f5c78e); }
.stat-card.chat .stat-icon { background: linear-gradient(135deg, #409eff, #7ea6ee); }
.stat-card.ticket .stat-icon { background: linear-gradient(135deg, #67c23a, #95d475); }
.stat-card.breakdown .stat-icon { background: linear-gradient(135deg, #909399, #b1b3b8); }

.stat-label {
  font-size: 13px;
  color: var(--text-secondary, #909399);
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary, #303133);
  line-height: 1.3;
  word-break: break-all;
}

.stat-sub {
  font-size: 12px;
  color: var(--text-muted, #c0c4cc);
  margin-top: 2px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid var(--border-color, #e4e7ed);
  background: var(--card-bg, #fff);
  align-items: center;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-label {
  font-size: 13px;
  color: var(--text-secondary, #909399);
  white-space: nowrap;
}

.chart-row {
  margin: 0 !important;
}

.chart-card :deep(.el-card__body) {
  padding: 12px;
}

.card-title {
  font-weight: 600;
  font-size: 14px;
}

.card-title i {
  margin-right: 6px;
  color: var(--primary-color, #409eff);
}

.chart-body {
  height: 320px;
  width: 100%;
}

.ranking-card :deep(.el-card__body) {
  padding: 0;
}

.ranking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.ranking-tip {
  font-size: 12px;
  color: var(--text-muted, #c0c4cc);
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 700;
  background: var(--main-bg, #f5f7fa);
  color: var(--text-secondary, #909399);
}

.rank-badge.rank-1 { background: #f7ba2a; color: #fff; }
.rank-badge.rank-2 { background: #b1b3b8; color: #fff; }
.rank-badge.rank-3 { background: #d4a574; color: #fff; }

.rank-user {
  font-weight: 500;
}

.model-name {
  font-weight: 500;
  margin-right: 8px;
  word-break: break-all;
}

.top-tag {
  flex-shrink: 0;
}

.top-tag i {
  margin-right: 3px;
}

.crown {
  color: #f7ba2a;
  margin-right: 2px;
}

.total-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 110px;
}

.total-num {
  font-weight: 700;
  color: var(--text-primary, #303133);
}

.share-bar {
  width: 90px;
}
</style>
