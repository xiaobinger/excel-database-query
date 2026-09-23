<template>
  <div
    class="ai-pet"
    :class="{ working: hasTasks, hovering: isHovering }"
    :style="{ left: sidebarCollapsed ? '76px' : '232px' }"
    title="点击开启 AI 新对话"
    @click="goNewChat"
    @mouseenter="onHover(true)"
    @mouseleave="onHover(false)"
  >
    <transition name="bubble-fade">
      <div v-if="bubbleText" class="pet-bubble">{{ bubbleText }}</div>
    </transition>

    <div class="pet-robot">
      <div class="antenna">
        <span class="antenna-line"></span>
        <span class="antenna-dot"></span>
      </div>
      <div class="pet-head">
        <span class="ear ear-left"></span>
        <div class="face">
          <span class="eye eye-left"></span>
          <span class="eye eye-right"></span>
          <span class="blush blush-left"></span>
          <span class="blush blush-right"></span>
          <span class="mouth"></span>
        </div>
        <span class="ear ear-right"></span>
      </div>
      <div class="pet-torso">
        <span class="hand hand-left"></span>
        <span class="chest"></span>
        <span class="hand hand-right"></span>
      </div>
    </div>
    <div class="pet-shadow"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const props = defineProps({
  sidebarCollapsed: { type: Boolean, default: false },
})

const router = useRouter()
const tasks = ref([])
const bubbleText = ref('')
const isHovering = ref(false)
const bubbleIndex = ref(0)

const POLL_INTERVAL = 15000
const ROTATE_INTERVAL = 6000

let pollTimer = null
let rotateTimer = null

const hasTasks = computed(() => tasks.value.length > 0)

function shortTitle(t) {
  return t.title && t.title.length > 12 ? t.title.slice(0, 12) + '…' : (t.title || '')
}

function bubbleFor(t) {
  const title = shortTitle(t)
  switch (t.status) {
    case 'processing':
      return `⚙️ ${t.agent_name} 正在处理「${title}」${t.progress}%`
    case 'submitted':
      return `📋 「${title}」等待 ${t.agent_name} 接单中…`
    case 'received':
      return `📨 ${t.agent_name} 已接单「${title}」，马上开工`
    case 'pending_confirmation':
      return `🔔 「${title}」待你确认后 AI 才能继续哦`
    default:
      return `${t.status_label || ''}「${title}」`
  }
}

function rotateBubble() {
  if (!tasks.value.length) {
    bubbleText.value = ''
    return
  }
  bubbleText.value = bubbleFor(tasks.value[bubbleIndex.value % tasks.value.length])
  bubbleIndex.value++
}

async function fetchTasks() {
  if (document.hidden) return
  try {
    const res = await api.tasks.getAiPetTasks()
    const list = res.data || []
    const prevActive = tasks.value.map(t => t.ticket_no + ':' + t.status).join('|')
    tasks.value = list
    const currActive = list.map(t => t.ticket_no + ':' + t.status).join('|')
    // 任务集合或状态发生变化时立即播报最新一条
    if (prevActive !== currActive) {
      bubbleIndex.value = 0
      rotateBubble()
    }
  } catch {
    // 静默失败
  }
}

function goNewChat() {
  router.push({ path: '/ai-chat', query: { pet_new: String(Date.now()) } }).catch(() => {})
}

function onHover(enter) {
  isHovering.value = enter
  if (enter && !hasTasks.value) {
    bubbleText.value = '点我开启新对话吧～ (◕‿◕)'
  } else if (!enter) {
    rotateBubble()
  }
}

onMounted(() => {
  fetchTasks()
  pollTimer = setInterval(fetchTasks, POLL_INTERVAL)
  rotateTimer = setInterval(() => {
    if (!isHovering.value) rotateBubble()
  }, ROTATE_INTERVAL)
})

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (rotateTimer) { clearInterval(rotateTimer); rotateTimer = null }
})
</script>

<style scoped>
.ai-pet {
  position: fixed;
  bottom: 50px;
  z-index: 1500;
  width: 84px;
  height: 104px;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}

/* ── 语音气泡 ── */
.pet-bubble {
  position: absolute;
  bottom: 100px;
  left: 50%;
  transform: translateX(-58%);
  max-width: 250px;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary, #303133);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pet-bubble::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 26px;
  width: 10px;
  height: 10px;
  background: #fff;
  border-right: 1px solid var(--border-color, #e4e7ed);
  border-bottom: 1px solid var(--border-color, #e4e7ed);
  transform: rotate(45deg);
}

.bubble-fade-enter-active,
.bubble-fade-leave-active {
  transition: all 0.35s ease;
}

.bubble-fade-enter-from,
.bubble-fade-leave-to {
  opacity: 0;
  transform: translateX(-58%) translateY(6px);
}

/* ── 机器人本体 ── */
.pet-robot {
  position: absolute;
  left: 50%;
  bottom: 10px;
  transform: translateX(-50%);
  width: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  animation: pet-float 3s ease-in-out infinite;
  transition: transform 0.2s;
}

.ai-pet:hover .pet-robot {
  transform: translateX(-50%) scale(1.08);
}

.ai-pet:active .pet-robot {
  transform: translateX(-50%) scale(0.95);
}

/* 天线 */
.antenna {
  position: relative;
  width: 14px;
  height: 14px;
  margin-bottom: -2px;
}

.antenna-line {
  position: absolute;
  left: 50%;
  bottom: 4px;
  transform: translateX(-50%);
  width: 3px;
  height: 10px;
  border-radius: 2px;
  background: linear-gradient(#b3c6e6, #8ba3c9);
}

.antenna-dot {
  position: absolute;
  left: 50%;
  top: -2px;
  transform: translateX(-50%);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #67c23a;
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.8);
}

/* 头 */
.pet-head {
  position: relative;
  width: 64px;
  height: 50px;
  background: linear-gradient(160deg, #ffffff 0%, #eef3fb 100%);
  border: 2px solid #c3d2e8;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 -3px 0 rgba(139, 163, 201, 0.25), 0 3px 8px rgba(139, 163, 201, 0.3);
  z-index: 2;
}

/* 耳朵 */
.ear {
  position: absolute;
  top: 14px;
  width: 7px;
  height: 18px;
  background: linear-gradient(#a9c0e2, #8ba3c9);
  border-radius: 4px;
}

.ear-left { left: -8px; }
.ear-right { right: -8px; }

/* 脸 */
.face {
  position: relative;
  width: 46px;
  height: 34px;
}

.eye {
  position: absolute;
  top: 9px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #2c3e50;
  animation: pet-blink 4.2s infinite;
}

.eye-left { left: 7px; }
.eye-right { right: 7px; }

/* working 状态：眼睛变成开心弧线 */
.ai-pet.working .eye {
  width: 10px;
  height: 5px;
  background: transparent;
  border: 2px solid #2c3e50;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 11px;
}

.blush {
  position: absolute;
  top: 18px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.55);
}

.blush-left { left: 1px; }
.blush-right { right: 1px; }

.mouth {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 3px;
  border-radius: 0 0 6px 6px;
  background: #2c3e50;
}

/* 身体 */
.pet-torso {
  position: relative;
  margin-top: -6px;
  width: 44px;
  height: 32px;
  background: linear-gradient(165deg, #dcebff 0%, #bcd4f5 100%);
  border: 2px solid #a9c0e2;
  border-radius: 12px 12px 10px 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  box-shadow: 0 3px 8px rgba(139, 163, 201, 0.35);
}

.hand {
  position: absolute;
  top: 8px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #a9c0e2;
  border: 2px solid #93aecd;
}

.hand-left { left: -9px; }
.hand-right { right: -9px; }

/* 胸前显示屏 */
.chest {
  width: 18px;
  height: 14px;
  border-radius: 5px;
  background: #2c3e50;
  position: relative;
  overflow: hidden;
  box-shadow: inset 0 0 3px rgba(0, 0, 0, 0.6);
}

.chest::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  right: 3px;
  height: 2px;
  border-radius: 1px;
  background: #56e39f;
  animation: chest-scan 1.6s ease-in-out infinite;
}

/* 脚下阴影 */
.pet-shadow {
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
  width: 46px;
  height: 8px;
  border-radius: 50%;
  background: rgba(100, 116, 139, 0.18);
  filter: blur(2px);
  animation: shadow-breathe 3s ease-in-out infinite;
}

/* ── 动画 ── */
@keyframes pet-float {
  0%, 100% { transform: translateX(-50%) translateY(0); }
  50% { transform: translateX(-50%) translateY(-6px); }
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

@keyframes shadow-breathe {
  0%, 100% { transform: translateX(-50%) scale(1); opacity: 1; }
  50% { transform: translateX(-50%) scale(0.82); opacity: 0.6; }
}

@keyframes chest-scan {
  0% { top: 3px; opacity: 0.4; }
  50% { top: 8px; opacity: 1; }
  100% { top: 3px; opacity: 0.4; }
}

@keyframes antenna-busy {
  0%, 100% { box-shadow: 0 0 4px rgba(230, 162, 60, 0.7); background: #e6a23c; }
  50% { box-shadow: 0 0 10px rgba(245, 108, 108, 0.9); background: #f56c6c; }
}

/* working 状态：天线变橙色快闪 + 身体轻微摇摆 */
.ai-pet.working .antenna-dot {
  background: #e6a23c;
  animation: antenna-busy 0.8s ease-in-out infinite;
}

.ai-pet.working .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-wiggle 2.2s ease-in-out infinite;
}

@keyframes pet-wiggle {
  0%, 100% { rotate: 0deg; }
  25% { rotate: 2.5deg; }
  75% { rotate: -2.5deg; }
}
</style>
