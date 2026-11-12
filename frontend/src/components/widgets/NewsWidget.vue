<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-newspaper"></i>支付圈新闻</span>
      <button class="widget-refresh" title="刷新资讯" @click="load">
        <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
      </button>
    </div>
    <div class="widget-body">
      <div v-if="error" class="widget-error">{{ error }}</div>
      <div v-else-if="!items.length" class="widget-empty">加载中…</div>
      <ul v-else class="news-list">
        <li v-for="(item, index) in items" :key="index" class="news-item">
          <a v-if="item.link" :href="item.link" target="_blank" rel="noopener noreferrer" class="news-title" :title="item.title">
            {{ item.title }}
          </a>
          <span v-else class="news-title">{{ item.title }}</span>
          <span class="news-meta">
            <span v-if="item.source" class="news-source">{{ item.source }}</span>
            <span v-if="formatTime(item.published)" class="news-time">{{ formatTime(item.published) }}</span>
          </span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import api from '../../api'

const items = ref([])
const error = ref('')
const loading = ref(false)
let timer = null

function formatTime(raw) {
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return String(raw).slice(0, 16)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.widgets.news()
    if (res.success === false) {
      error.value = res.message || '资讯获取失败'
      items.value = []
      return
    }
    items.value = (res.data || res).items || []
  } catch {
    error.value = '资讯获取失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 15 * 60 * 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.news-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.news-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border-color, #e4e7ed);
}

.news-item:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.news-title {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary, #303133);
  text-decoration: none;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

a.news-title:hover {
  color: var(--primary-color, #409eff);
}

.news-time {
  font-size: 11px;
  color: var(--text-muted, #909399);
}

.news-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.news-source {
  font-size: 11px;
  color: var(--primary-color, #409eff);
}
</style>
