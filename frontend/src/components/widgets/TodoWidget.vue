<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-list-check"></i>系统待办</span>
      <button class="widget-refresh" title="刷新待办" @click="load">
        <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
      </button>
    </div>
    <div class="widget-body">
      <div v-if="error" class="widget-error">{{ error }}</div>
      <div v-else-if="!items.length" class="widget-empty">暂无待办，真棒 🎉</div>
      <ul v-else class="todo-list">
        <li v-for="item in items" :key="item.id" class="todo-item" @click="goTickets">
          <div class="todo-top">
            <span class="todo-action">{{ item.action }}</span>
            <span class="todo-no">{{ item.ticket_no }}</span>
          </div>
          <div class="todo-title" :title="item.title">{{ item.title }}</div>
          <div class="todo-meta">
            <el-tag size="small" effect="plain" :type="statusType(item.status)">{{ item.status_label }}</el-tag>
            <span>{{ item.updated_at }}</span>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../../api'

const props = defineProps({
  settings: { type: Object, default: () => ({}) },
})

const router = useRouter()
const items = ref([])
const error = ref('')
const loading = ref(false)
let timer = null

const STATUS_TYPES = {
  submitted: 'info',
  received: 'primary',
  processing: 'warning',
  pending_assignment: 'warning',
  pending_confirmation: 'warning',
  processed: 'success',
}

function statusType(status) {
  return STATUS_TYPES[status] || 'info'
}

function goTickets() {
  router.push('/tickets')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.widgets.todos({ limit: props.settings?.limit || 5 })
    if (res.success === false) {
      error.value = res.message || '待办获取失败'
      items.value = []
      return
    }
    items.value = (res.data || res).items || []
  } catch {
    error.value = '待办获取失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 2 * 60 * 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.todo-item {
  padding: 8px 9px;
  border-radius: 8px;
  background: var(--main-bg, #f5f7fa);
  cursor: pointer;
  transition: all 0.2s;
}

.todo-item:hover {
  background: var(--primary-light, rgba(64, 158, 255, 0.1));
  transform: translateY(-1px);
}

.todo-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.todo-action {
  font-size: 11px;
  font-weight: 600;
  color: var(--primary-color, #409eff);
}

.todo-no {
  font-size: 11px;
  color: var(--text-muted, #909399);
}

.todo-title {
  margin-top: 3px;
  font-size: 12px;
  color: var(--text-primary, #303133);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-meta {
  margin-top: 5px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted, #909399);
}
</style>
