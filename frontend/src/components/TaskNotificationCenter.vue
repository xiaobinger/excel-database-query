<template>
  <transition-group tag="div" name="notify" class="task-notify-container">
    <div
      v-for="task in visibleNotifs"
      :key="task.id"
      class="task-notify"
      :class="['is-' + task.status]"
      @mouseenter="pause(task.id)"
      @mouseleave="resume(task.id)"
    >
      <div class="notify-icon" :style="{ background: statusColor(task.status) }">
        <i class="fas" :class="statusIcon(task.status)"></i>
      </div>
      <div class="notify-body">
        <div class="notify-head">
          <span class="notify-cat">{{ task.category }} · {{ statusLabel(task.status) }}</span>
          <span class="notify-time">{{ formatTime(task.completed_at) }}</span>
        </div>
        <div class="notify-title" :title="task.title">{{ task.title }}</div>
        <div v-if="task.error_message && isFailed(task.status)" class="notify-error">
          {{ task.error_message }}
        </div>
        <div v-if="task.total_rows" class="notify-meta">
          成功 {{ task.success_count || 0 }} · 失败 {{ task.failure_count || 0 }} · 共 {{ task.total_rows }}
        </div>
        <div class="notify-actions">
          <el-button
            v-if="task.url"
            text
            size="small"
            class="notify-link"
            @click="handleView(task)"
          >
            <i class="fas fa-arrow-right"></i> 查看
          </el-button>
          <el-button
            type="primary"
            size="small"
            class="notify-confirm"
            @click="handleConfirm(task)"
          >
            我知道了
          </el-button>
        </div>
        <div class="notify-progress-bar" :style="{ background: statusColor(task.status), animationDuration: '10s', animationPlayState: paused.has(task.id) ? 'paused' : 'running' }"></div>
      </div>
      <button class="notify-close" @click="handleConfirm(task)">
        <i class="fas fa-xmark"></i>
      </button>
    </div>
  </transition-group>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskMonitorStore } from '../stores/taskMonitor'

const router = useRouter()
const monitor = useTaskMonitorStore()

/** 当前可见的通知（最多 3 条，FIFO） */
const visibleNotifs = ref([])
/** 每条通知的自动关闭定时器 */
const timers = new Map()
/** 暂停状态（hover 时暂停倒计时） */
const paused = ref(new Set())

const AUTO_CLOSE_MS = 10000
const MAX_VISIBLE = 3

function statusLabel(s) { return monitor.getStatusMeta(s).label }
function statusColor(s) { return monitor.getStatusMeta(s).color }
function statusIcon(s) {
  const map = {
    completed: 'fa-circle-check',
    failed: 'fa-circle-xmark',
    cancelled: 'fa-ban',
    manual_cancelled: 'fa-hand',
    timeout: 'fa-clock',
  }
  return map[s] || 'fa-circle-info'
}
function isFailed(s) { return s === 'failed' || s === 'timeout' }

function formatTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    const pad = n => String(n).padStart(2, '0')
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch (e) { return '' }
}

/** 监听 store.notifications 队列变化，弹出下一条 */
watch(() => monitor.notifications.length, (len) => {
  if (len > 0 && visibleNotifs.value.length < MAX_VISIBLE) {
    // 取队列中尚未展示的第一条
    const next = monitor.notifications.find(n => !visibleNotifs.value.find(v => v.id === n.id))
    if (next) showNotification(next)
  }
}, { immediate: true })

function showNotification(task) {
  if (visibleNotifs.value.find(v => v.id === task.id)) return
  visibleNotifs.value.push(task)
  startTimer(task.id)
}

function startTimer(id) {
  clearTimer(id)
  const t = setTimeout(() => dismiss(id), AUTO_CLOSE_MS)
  timers.set(id, t)
}

function clearTimer(id) {
  const t = timers.get(id)
  if (t) { clearTimeout(t); timers.delete(id) }
}

function pause(id) {
  // 简化处理：暂停即清空定时器，恢复时重新计时剩余时间（这里直接重置 10s）
  const t = timers.get(id)
  if (t) { clearTimeout(t); timers.delete(id) }
  paused.value.add(id)
  paused.value = new Set(paused.value)
}

function resume(id) {
  if (paused.value.has(id)) {
    paused.value.delete(id)
    paused.value = new Set(paused.value)
    startTimer(id)
  }
}

function dismiss(id) {
  clearTimer(id)
  const idx = visibleNotifs.value.findIndex(v => v.id === id)
  if (idx >= 0) visibleNotifs.value.splice(idx, 1)
  // 从 store 队列中移除
  monitor.dismissNotification(id)
}

function handleConfirm(task) {
  dismiss(task.id)
}

function handleView(task) {
  dismiss(task.id)
  if (task.url) router.push(task.url)
}

onUnmounted(() => {
  timers.forEach(t => clearTimeout(t))
  timers.clear()
})
</script>

<style scoped>
.task-notify-container {
  position: fixed;
  top: 70px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3000;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  pointer-events: none;
}

.task-notify {
  position: relative;
  display: flex;
  align-items: stretch;
  width: 420px;
  max-width: 92vw;
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  pointer-events: auto;
  backdrop-filter: blur(8px);
}

.task-notify.is-completed { border-left: 4px solid #67c23a; }
.task-notify.is-failed,
.task-notify.is-timeout { border-left: 4px solid #f56c6c; }
.task-notify.is-cancelled,
.task-notify.is-manual_cancelled { border-left: 4px solid #909399; }

.notify-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  color: #fff;
  font-size: 22px;
  flex-shrink: 0;
}

.notify-body {
  flex: 1;
  padding: 12px 14px 10px;
  min-width: 0;
}

.notify-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.notify-cat {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.notify-time {
  font-size: 11px;
  color: var(--text-muted);
}

.notify-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.notify-error {
  font-size: 12px;
  color: #f56c6c;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notify-meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.notify-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.notify-progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  width: 100%;
  opacity: 0.7;
  transform-origin: left;
  animation: notify-shrink linear forwards;
}

@keyframes notify-shrink {
  from { transform: scaleX(1); }
  to { transform: scaleX(0); }
}

.notify-close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.2s;
}

.notify-close:hover {
  background: var(--primary-light);
  color: var(--text-primary);
}

.notify-enter-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.notify-leave-active {
  transition: all 0.3s ease;
}
.notify-enter-from {
  opacity: 0;
  transform: translateY(-30px) scale(0.9);
}
.notify-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}
.notify-move {
  transition: transform 0.3s ease;
}
</style>
