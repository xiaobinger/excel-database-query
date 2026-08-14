<template>
  <el-popover
    placement="bottom-end"
    :width="380"
    trigger="hover"
    :show-after="150"
    :hide-after="200"
    popper-class="task-badge-popover"
  >
    <template #reference>
      <div class="task-badge-wrap" :class="{ 'has-active': monitor.hasActive }">
        <i class="fas fa-tasks task-icon"></i>
        <transition name="badge-pop">
          <span v-if="monitor.hasActive" class="badge-count">{{ displayCount }}</span>
        </transition>
      </div>
    </template>

    <div class="task-panel">
      <div class="panel-header">
        <span class="panel-title">
          <i class="fas fa-tasks"></i>
          进行中的任务
          <el-tag v-if="monitor.hasActive" size="small" type="warning" effect="dark" round>{{ monitor.activeCount }}</el-tag>
        </span>
        <el-button text size="small" @click="refresh" :loading="loading">
          <i class="fas fa-rotate"></i>
        </el-button>
      </div>

      <div v-if="!monitor.hasActive" class="panel-empty">
        <i class="fas fa-mug-hot empty-icon"></i>
        <p>当前没有正在执行的任务</p>
      </div>

      <div v-else class="panel-list">
        <div
          v-for="task in monitor.activeTasks"
          :key="task.id"
          class="task-item"
          @click="goToTask(task)"
        >
          <div class="task-item-head">
            <span class="task-cat">{{ task.category }}</span>
            <span class="task-status" :style="{ color: statusColor(task.status) }">
              <i class="fas" :class="statusIcon(task.status)"></i>
              {{ statusLabel(task.status) }}
            </span>
          </div>
          <div class="task-title" :title="task.title">{{ task.title }}</div>
          <div class="task-progress-row">
            <el-progress
              :percentage="task.progress || 0"
              :stroke-width="8"
              :color="progressColor(task.status)"
              :show-text="false"
              class="task-progress"
            />
            <span class="task-percent">{{ task.progress || 0 }}%</span>
          </div>
          <div v-if="task.total_rows" class="task-meta">
            成功 {{ task.success_count || 0 }} / 失败 {{ task.failure_count || 0 }} / 共 {{ task.total_rows }}
          </div>
          <div class="task-foot">
            <span class="task-time">{{ formatTime(task.started_at || task.created_at) }}</span>
            <span class="task-goto">查看 <i class="fas fa-arrow-right"></i></span>
          </div>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskMonitorStore } from '../stores/taskMonitor'

const router = useRouter()
const monitor = useTaskMonitorStore()
const loading = ref(false)

const displayCount = computed(() => {
  const n = monitor.activeCount
  return n > 99 ? '99+' : String(n)
})

function statusLabel(s) { return monitor.getStatusMeta(s).label }
function statusColor(s) { return monitor.getStatusMeta(s).color }
function statusIcon(s) {
  const map = {
    pending: 'fa-hourglass-half',
    running: 'fa-spinner fa-spin',
    completed: 'fa-circle-check',
    failed: 'fa-circle-xmark',
    cancelled: 'fa-ban',
    manual_cancelled: 'fa-hand',
    timeout: 'fa-clock',
  }
  return map[s] || 'fa-circle'
}
function progressColor(s) {
  if (s === 'failed' || s === 'cancelled' || s === 'timeout') return '#f56c6c'
  if (s === 'completed') return '#67c23a'
  return 'var(--primary-color, #409eff)'
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const now = new Date()
    const diff = (now - d) / 1000
    if (diff < 60) return '刚刚开始'
    if (diff < 3600) return `已运行 ${Math.floor(diff / 60)} 分钟`
    return `已运行 ${Math.floor(diff / 3600)} 小时`
  } catch (e) { return '' }
}

async function refresh() {
  loading.value = true
  try { await monitor.fetchActive() } finally { loading.value = false }
}

function goToTask(task) {
  if (task.url) router.push(task.url)
}
</script>

<style scoped>
.task-badge-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.task-badge-wrap:hover {
  background: var(--primary-light);
  color: var(--primary-color);
}

.task-badge-wrap.has-active .task-icon {
  animation: task-pulse 1.8s ease-in-out infinite;
}

.task-icon {
  font-size: 16px;
}

.badge-count {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: #f56c6c;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
  border-radius: 9px;
  box-shadow: 0 0 0 2px var(--header-bg, #fff);
}

.badge-pop-enter-active,
.badge-pop-leave-active {
  transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.badge-pop-enter-from,
.badge-pop-leave-to {
  opacity: 0;
  transform: scale(0.3);
}

@keyframes task-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.12); }
}

.task-panel {
  margin: -12px;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--primary-light, #ecf5ff);
  border-bottom: 1px solid var(--border-color);
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-title i {
  color: var(--primary-color);
}

.panel-empty {
  padding: 36px 16px;
  text-align: center;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 36px;
  margin-bottom: 10px;
  opacity: 0.5;
}

.panel-empty p {
  margin: 0;
  font-size: 13px;
}

.panel-list {
  max-height: 420px;
  overflow-y: auto;
  padding: 8px;
}

.task-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  border: 1px solid transparent;
}

.task-item:hover {
  background: var(--primary-light, #ecf5ff);
  border-color: var(--border-color);
}

.task-item + .task-item {
  margin-top: 6px;
}

.task-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.task-cat {
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 6px;
  background: var(--table-header-bg, #f5f7fa);
  border-radius: 4px;
}

.task-status {
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.task-title {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 8px;
}

.task-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-progress {
  flex: 1;
}

.task-percent {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
  min-width: 36px;
  text-align: right;
}

.task-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
}

.task-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.task-goto {
  color: var(--primary-color);
}
</style>
