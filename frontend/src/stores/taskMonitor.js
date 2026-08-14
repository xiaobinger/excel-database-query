import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

/**
 * 全局任务监控 Store
 *
 * 职责：
 * 1. 轮询 /tasks/active 获取进行中的任务（驱动右上角红点+悬停面板）
 * 2. 轮询 /tasks/recent 检测"刚完成"的任务，推入 notifications 队列（驱动完成弹窗）
 *
 * 完成检测策略：维护 knownActiveIds 集合（上一轮仍 active 的任务 id）。
 * 若某任务上一轮在 active 中，本轮在 recent 中出现且未通知过 → 视为新完成，入队。
 * 同时 active 轮询本身也会发现 active 列表减少，配合 recent 接口补全终态信息。
 */
export const useTaskMonitorStore = defineStore('taskMonitor', () => {
  /** 进行中任务列表 */
  const activeTasks = ref([])
  /** 完成通知队列（待弹窗展示） */
  const notifications = ref([])
  /** 已通知过的任务 id 集合（避免重复通知，会话内有效） */
  const notifiedIds = ref(new Set())
  /** 上一轮 active 任务 id 集合（用于检测刚完成） */
  const lastActiveIds = ref(new Set())

  /** 是否正在拉取（防止并发） */
  const fetchingActive = ref(false)
  const fetchingRecent = ref(false)

  /** 轮询定时器 */
  let activeTimer = null
  let recentTimer = null

  /** 轮询间隔（毫秒） */
  const ACTIVE_INTERVAL = 5000
  const RECENT_INTERVAL = 8000
  /** recent 接口查询最近完成的窗口（分钟） */
  const RECENT_MINUTES = 3

  /** 进行中任务数（红点数字） */
  const activeCount = computed(() => activeTasks.value.length)

  /** 是否有任务在进行 */
  const hasActive = computed(() => activeCount.value > 0)

  /** 状态标签映射 */
  const statusMeta = {
    pending: { label: '等待中', type: 'info', color: '#909399' },
    running: { label: '执行中', type: 'warning', color: '#e6a23c' },
    completed: { label: '已完成', type: 'success', color: '#67c23a' },
    failed: { label: '失败', type: 'danger', color: '#f56c6c' },
    cancelled: { label: '已取消', type: 'info', color: '#909399' },
    manual_cancelled: { label: '已终止', type: 'info', color: '#909399' },
    timeout: { label: '超时', type: 'danger', color: '#f56c6c' },
  }

  function getStatusMeta(status) {
    return statusMeta[status] || { label: status || '未知', type: 'info', color: '#909399' }
  }

  /** 拉取进行中任务 */
  async function fetchActive() {
    if (fetchingActive.value) return
    fetchingActive.value = true
    let currentIds = new Set()
    try {
      const res = await api.tasks.getActive()
      const list = res.data || res || []
      activeTasks.value = list
      currentIds = new Set(list.map(t => t.id))
      // 检测刚完成的任务：上一轮在 active，本轮不在 active → 拉 recent 补全
      const justFinished = []
      lastActiveIds.value.forEach(id => {
        if (!currentIds.has(id) && !notifiedIds.value.has(id)) {
          justFinished.push(id)
        }
      })
      if (justFinished.length > 0) {
        // 触发一次 recent 拉取以补全完成信息
        fetchRecent(justFinished)
      }
      lastActiveIds.value = currentIds
    } catch (e) {
      // 静默失败，不打扰用户（拦截器已处理 401）
    } finally {
      fetchingActive.value = false
    }
  }

  /** 拉取最近完成任务，并筛选出需要通知的 */
  async function fetchRecent(targetIds = null) {
    if (fetchingRecent.value) return
    fetchingRecent.value = true
    try {
      const res = await api.tasks.getRecent({ minutes: RECENT_MINUTES, limit: 20 })
      const list = res.data || res || []
      const newNotifs = []
      list.forEach(task => {
        // 未通知过 且 （上一轮在 active 中 或 调用方指定了该 id）→ 入队
        const wasActive = lastActiveIds.value.has(task.id)
        const isTarget = targetIds && targetIds.includes(task.id)
        if (!notifiedIds.value.has(task.id) && (wasActive || isTarget)) {
          newNotifs.push(task)
          notifiedIds.value.add(task.id)
        }
      })
      if (newNotifs.length > 0) {
        notifications.value.push(...newNotifs)
      }
    } catch (e) {
      // 静默
    } finally {
      fetchingRecent.value = false
    }
  }

  /** 启动轮询 */
  function start() {
    stop()
    // 立即拉一次
    fetchActive()
    activeTimer = setInterval(fetchActive, ACTIVE_INTERVAL)
    recentTimer = setInterval(() => fetchRecent(), RECENT_INTERVAL)
  }

  /** 停止轮询 */
  function stop() {
    if (activeTimer) { clearInterval(activeTimer); activeTimer = null }
    if (recentTimer) { clearInterval(recentTimer); recentTimer = null }
  }

  /** 弹窗已展示某条通知后调用，移除队列首条 */
  function dismissNotification(id) {
    const idx = notifications.value.findIndex(n => n.id === id)
    if (idx >= 0) notifications.value.splice(idx, 1)
  }

  /** 取下一条待通知任务（FIFO） */
  const nextNotification = computed(() => notifications.value[0] || null)

  /** 重置（登出时调用） */
  function reset() {
    stop()
    activeTasks.value = []
    notifications.value = []
    notifiedIds.value = new Set()
    lastActiveIds.value = new Set()
  }

  return {
    activeTasks,
    notifications,
    activeCount,
    hasActive,
    nextNotification,
    fetchActive,
    fetchRecent,
    start,
    stop,
    dismissNotification,
    getStatusMeta,
    reset,
  }
})
