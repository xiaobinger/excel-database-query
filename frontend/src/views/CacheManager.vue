<template>
  <div class="cache-manager">
    <div class="page-header">
      <h2><i class="fas fa-bolt"></i> AI缓存统计</h2>
    </div>

    <!-- Overview Cards -->
    <el-row :gutter="16" class="stats-cards">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-prompt">
          <div class="stat-icon"><i class="fas fa-arrow-right"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ formatNumber(overview.prompt_tokens) }}</div>
            <div class="stat-label">Prompt Tokens</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-completion">
          <div class="stat-icon"><i class="fas fa-arrow-left"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ formatNumber(overview.completion_tokens) }}</div>
            <div class="stat-label">Completion Tokens</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-cache-create">
          <div class="stat-icon"><i class="fas fa-plus-circle"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ formatNumber(overview.cache_creation_tokens) }}</div>
            <div class="stat-label">缓存写入Tokens</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-cache-read">
          <div class="stat-icon"><i class="fas fa-check-circle"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ formatNumber(overview.cache_read_tokens) }}</div>
            <div class="stat-label">缓存命中Tokens</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-hit-rate">
          <div class="stat-icon"><i class="fas fa-percentage"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ hitRate }}</div>
            <div class="stat-label">缓存命中率</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card stat-messages">
          <div class="stat-icon"><i class="fas fa-comments"></i></div>
          <div class="stat-info">
            <div class="stat-value">{{ formatNumber(overview.message_count) }}</div>
            <div class="stat-label">消息总数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Agent Stats Table -->
    <el-card class="section-card">
      <template #header>
        <span><i class="fas fa-robot"></i> 按Agent统计</span>
      </template>
      <el-table :data="agentStats" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="agent_name" label="Agent名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="prompt_tokens" label="Prompt Tokens" width="140" align="right">
          <template #default="{ row }">
            <span class="token-prompt">{{ formatNumber(row.prompt_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="completion_tokens" label="Completion Tokens" width="160" align="right">
          <template #default="{ row }">
            <span class="token-completion">{{ formatNumber(row.completion_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cache_creation_tokens" label="缓存写入Tokens" width="150" align="right">
          <template #default="{ row }">
            <span class="token-cache-create">{{ formatNumber(row.cache_creation_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cache_read_tokens" label="缓存命中Tokens" width="150" align="right">
          <template #default="{ row }">
            <span class="token-cache-read">{{ formatNumber(row.cache_read_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="消息数" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.message_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="缓存命中率" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getHitRateType(row)" size="small">{{ calcHitRate(row) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && agentStats.length === 0" description="暂无Agent统计数据" />
    </el-card>

    <!-- Daily Stats Table -->
    <el-card class="section-card">
      <template #header>
        <span><i class="fas fa-calendar-alt"></i> 最近30天趋势</span>
      </template>
      <el-table :data="dailyStats" stripe style="width: 100%">
        <el-table-column prop="date" label="日期" width="120" align="center" />
        <el-table-column prop="prompt_tokens" label="Prompt Tokens" width="140" align="right">
          <template #default="{ row }">
            <span class="token-prompt">{{ formatNumber(row.prompt_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="completion_tokens" label="Completion Tokens" width="160" align="right">
          <template #default="{ row }">
            <span class="token-completion">{{ formatNumber(row.completion_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cache_creation_tokens" label="缓存写入Tokens" width="150" align="right">
          <template #default="{ row }">
            <span class="token-cache-create">{{ formatNumber(row.cache_creation_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cache_read_tokens" label="缓存命中Tokens" width="150" align="right">
          <template #default="{ row }">
            <span class="token-cache-read">{{ formatNumber(row.cache_read_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="消息数" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.message_count || 0 }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="dailyStats.length === 0" description="暂无每日统计数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const overview = ref({
  prompt_tokens: 0,
  completion_tokens: 0,
  cache_creation_tokens: 0,
  cache_read_tokens: 0,
  message_count: 0,
})
const agentStats = ref([])
const dailyStats = ref([])

const hitRate = computed(() => {
  const prompt = overview.value.prompt_tokens || 0
  const cacheRead = overview.value.cache_read_tokens || 0
  if (prompt === 0) return '0%'
  return (cacheRead / prompt * 100).toFixed(1) + '%'
})

function calcHitRate(row) {
  const prompt = row.prompt_tokens || 0
  const cacheRead = row.cache_read_tokens || 0
  if (prompt === 0) return '0%'
  return (cacheRead / prompt * 100).toFixed(1) + '%'
}

function getHitRateType(row) {
  const prompt = row.prompt_tokens || 0
  const cacheRead = row.cache_read_tokens || 0
  if (prompt === 0) return 'info'
  const rate = cacheRead / prompt
  if (rate >= 0.5) return 'success'
  if (rate >= 0.2) return 'warning'
  return 'danger'
}

function formatNumber(num) {
  if (num === null || num === undefined) return '0'
  return Number(num).toLocaleString()
}

async function fetchStats() {
  loading.value = true
  try {
    const res = await api.ai.getCacheStats()
    const data = res.data || res || {}
    const raw = data.overview || {}
    overview.value = {
      prompt_tokens: raw.total_prompt_tokens || 0,
      completion_tokens: raw.total_completion_tokens || 0,
      cache_creation_tokens: raw.total_cache_creation_tokens || 0,
      cache_read_tokens: raw.total_cache_read_tokens || 0,
      message_count: raw.total_messages || 0,
    }
    agentStats.value = data.by_agent || []
    dailyStats.value = data.daily || []
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '获取缓存统计数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchStats)
</script>

<style scoped>
.cache-manager {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin: 0;
}

.page-header h2 i {
  margin-right: 8px;
  color: #e6a23c;
}

.stats-cards {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 16px;
  border-radius: 8px;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-right: 12px;
  flex-shrink: 0;
}

.stat-prompt .stat-icon {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.stat-completion .stat-icon {
  background: rgba(144, 147, 153, 0.1);
  color: #909399;
}

.stat-cache-create .stat-icon {
  background: rgba(230, 162, 60, 0.1);
  color: #e6a23c;
}

.stat-cache-read .stat-icon {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
}

.stat-hit-rate .stat-icon {
  background: rgba(103, 194, 58, 0.1);
  color: #67c23a;
}

.stat-messages .stat-icon {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary, #303133);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted, #909399);
  margin-top: 4px;
}

.section-card {
  margin-bottom: 20px;
  border-radius: 8px;
}

.section-card :deep(.el-card__header) {
  font-size: 16px;
  font-weight: 600;
}

.section-card :deep(.el-card__header i) {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.token-prompt {
  color: #409eff;
  font-weight: 500;
}

.token-completion {
  color: #909399;
  font-weight: 500;
}

.token-cache-create {
  color: #e6a23c;
  font-weight: 500;
}

.token-cache-read {
  color: #67c23a;
  font-weight: 500;
}
</style>
