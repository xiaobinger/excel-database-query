<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-chart-line"></i>自选股行情</span>
      <button class="widget-refresh" title="刷新行情" @click="load">
        <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
      </button>
    </div>
    <div class="widget-body">
      <div v-if="error" class="widget-error">{{ error }}</div>
      <div v-else-if="!items.length" class="widget-empty">加载中…</div>
      <template v-else>
        <div v-for="item in items" :key="item.symbol" class="stock-row">
          <div class="stock-name">
            <div class="stock-title" :title="item.name">{{ item.name }}</div>
            <div class="stock-code">{{ item.symbol }}</div>
          </div>
          <div class="stock-quote">
            <div class="stock-price" :class="trendClass(item.change_pct)">{{ fmtPrice(item.price) }}</div>
            <div class="stock-change" :class="trendClass(item.change_pct)">
              {{ fmtSigned(item.change) }} / {{ fmtPct(item.change_pct) }}
            </div>
          </div>
        </div>
        <div v-if="updatedAt" class="stock-updated">更新于 {{ updatedAt }}</div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import api from '../../api'

const props = defineProps({
  settings: { type: Object, default: () => ({}) },
})

const items = ref([])
const updatedAt = ref('')
const error = ref('')
const loading = ref(false)
let timer = null

function trendClass(pct) {
  const value = Number(pct) || 0
  if (value > 0) return 'up'
  if (value < 0) return 'down'
  return 'flat'
}

function fmtPrice(value) {
  return value === null || value === undefined ? '-' : Number(value).toFixed(2)
}

function fmtSigned(value) {
  const number = Number(value) || 0
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}`
}

function fmtPct(value) {
  const number = Number(value) || 0
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.widgets.stocks({ symbols: props.settings?.symbols })
    if (res.success === false) {
      error.value = res.message || '行情获取失败'
      items.value = []
      return
    }
    const data = res.data || res
    items.value = data.items || []
    updatedAt.value = (data.updated_at || '').slice(11, 19)
  } catch {
    error.value = '行情获取失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.settings?.symbols, load)

onMounted(() => {
  load()
  timer = setInterval(load, 30 * 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.stock-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px dashed var(--border-color, #e4e7ed);
}

.stock-row:last-of-type {
  border-bottom: none;
}

.stock-name {
  min-width: 0;
}

.stock-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stock-code {
  font-size: 11px;
  color: var(--text-muted, #909399);
  text-transform: uppercase;
}

.stock-quote {
  text-align: right;
  flex-shrink: 0;
}

.stock-price {
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.stock-change {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.up {
  color: #f56c6c;
}

.down {
  color: #67c23a;
}

.flat {
  color: var(--text-muted, #909399);
}

.stock-updated {
  margin-top: 8px;
  text-align: right;
  font-size: 11px;
  color: var(--text-muted, #909399);
}
</style>
