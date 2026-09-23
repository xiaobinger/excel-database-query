<template>
  <div
    ref="petRef"
    class="ai-pet"
    :class="[{ working: hasTasks, dragging: isDragging }, idleAnim]"
    :style="petPosStyle"
    title="点击和我聊天 · 拖动调整位置"
    @pointerdown="onPointerDown"
  >
    <transition name="bubble-fade">
      <div v-if="displayBubble && !chatVisible" class="pet-bubble" :class="{ 'is-idle': !bubbleText }">{{ displayBubble }}</div>
    </transition>

    <div class="pet-robot">
      <transition name="star-fade">
        <span v-if="hasTasks" class="pet-star">
          <span class="star-core">★</span>
        </span>
      </transition>
      <component :is="petComponent" :working="hasTasks" />
    </div>
    <div class="pet-shadow"></div>
  </div>

  <AiPetChatDialog v-model="chatVisible" :pet-style="petStyle" />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api'
import AiPetChatDialog from './AiPetChatDialog.vue'
import RobotPet from './pets/RobotPet.vue'
import CatPet from './pets/CatPet.vue'
import BunnyPet from './pets/BunnyPet.vue'
import PandaPet from './pets/PandaPet.vue'
import BearPet from './pets/BearPet.vue'
import FoxPet from './pets/FoxPet.vue'
import PigPet from './pets/PigPet.vue'
import FrogPet from './pets/FrogPet.vue'
import KoalaPet from './pets/KoalaPet.vue'
import ChickPet from './pets/ChickPet.vue'

const props = defineProps({
  /** 宠物造型标识，与后端 PET_STYLES 白名单一致 */
  petStyle: { type: String, default: 'robot' },
})

const PET_COMPONENTS = {
  robot: RobotPet,
  cat: CatPet,
  bunny: BunnyPet,
  panda: PandaPet,
  bear: BearPet,
  fox: FoxPet,
  pig: PigPet,
  frog: FrogPet,
  koala: KoalaPet,
  chick: ChickPet,
}

const petComponent = computed(() => PET_COMPONENTS[props.petStyle] || RobotPet)

const tasks = ref([])
const bubbleText = ref('')
const bubbleIndex = ref(0)
const chatVisible = ref(false)

const POLL_INTERVAL = 15000
const ROTATE_INTERVAL = 6000
/** 空闲自动互动：随机间隔范围（毫秒） */
const IDLE_MIN_INTERVAL = 18000
const IDLE_MAX_INTERVAL = 42000
/** 单条闲聊气泡展示时长（毫秒） */
const IDLE_SHOW_DURATION = 6000
/** 位移小于该阈值视为点击而非拖动 */
const DRAG_THRESHOLD = 6
const PET_SIZE = { w: 84, h: 104 }

/** 空闲闲聊文案库（无任务时随机播报） */
const IDLE_CHATS = [
  '在的哦，需要我帮你查点什么吗？',
  '今天的数据都还好吗？😊',
  '要不要让我帮你跑个查询？',
  '忙里偷闲，喝口水吧 💧',
  '我一直在这儿守着呢～',
  '有工单就交给我，我盯着进度 👀',
  '需要导出一份报表吗？',
  '嘿嘿，被你发现我在发呆啦',
  '任务有进展我会第一时间提醒你 🔔',
  '忙完了记得来看看我呀 🌟',
  '点我一下就能开始聊天咯',
  '数据海洋里，我是你的小导航 🧭',
]

/** 空闲小动效 class 池 */
const IDLE_ANIMS = ['idle-wave', 'idle-hop', 'idle-spin', 'idle-squash']

let pollTimer = null
let rotateTimer = null
let idleTimer = null
let idleHideTimer = null

const idleChat = ref('')
const idleAnim = ref('')

const hasTasks = computed(() => tasks.value.length > 0)

/** 气泡展示内容：任务播报优先，其次空闲闲聊 */
const displayBubble = computed(() => bubbleText.value || idleChat.value)

/* ── 拖动定位（默认右下角，拖动后以 left/top 持久化） ── */
const petRef = ref(null)
const petPos = ref(null) // { left, top }，null 时用默认右下角
const isDragging = ref(false)

function clampPos(left, top) {
  const w = window.innerWidth || 1280
  const h = window.innerHeight || 800
  return {
    left: Math.min(Math.max(left, 4), w - PET_SIZE.w - 4),
    top: Math.min(Math.max(top, 4), h - PET_SIZE.h - 4),
  }
}

function loadPos() {
  try {
    const raw = localStorage.getItem('ai_pet_pos')
    if (!raw) return
    const pos = JSON.parse(raw)
    if (typeof pos.left === 'number' && typeof pos.top === 'number') {
      petPos.value = clampPos(pos.left, pos.top)
    }
  } catch {
    // 位置数据损坏则忽略，回到默认右下角
  }
}

const petPosStyle = computed(() => {
  if (petPos.value) {
    return { left: `${petPos.value.left}px`, top: `${petPos.value.top}px` }
  }
  return { right: '28px', bottom: '50px' }
})

function onPointerDown(e) {
  // 弹窗内/鼠标右键不触发拖动
  if (e.button !== 0) return
  const startX = e.clientX
  const startY = e.clientY
  const rect = petRef.value.getBoundingClientRect()
  const originLeft = rect.left
  const originTop = rect.top
  let moved = false

  const onMove = (ev) => {
    const dx = ev.clientX - startX
    const dy = ev.clientY - startY
    if (!moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return
    moved = true
    isDragging.value = true
    petPos.value = clampPos(originLeft + dx, originTop + dy)
  }

  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    if (moved) {
      isDragging.value = false
      if (petPos.value) {
        localStorage.setItem('ai_pet_pos', JSON.stringify(petPos.value))
      }
    } else {
      // 位移极小 → 视为点击，打开宠物对话
      chatVisible.value = true
    }
  }

  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

/* ── 任务播报 ── */
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
    if (prevActive !== currActive) {
      bubbleIndex.value = 0
      rotateBubble()
    }
    if (list.length) clearIdleChat()
  } catch {
    // 静默失败
  }
}

/* ── 空闲自动互动（无任务且未聊天时，随机播报闲聊 + 小动效） ── */
function clearIdleChat() {
  if (idleHideTimer) { clearTimeout(idleHideTimer); idleHideTimer = null }
  idleChat.value = ''
  idleAnim.value = ''
}

function scheduleIdle() {
  if (idleTimer) clearTimeout(idleTimer)
  const delay = IDLE_MIN_INTERVAL + Math.random() * (IDLE_MAX_INTERVAL - IDLE_MIN_INTERVAL)
  idleTimer = setTimeout(triggerIdle, delay)
}

function triggerIdle() {
  idleTimer = null
  if (hasTasks.value || chatVisible.value || isDragging.value || document.hidden) {
    scheduleIdle()
    return
  }
  idleChat.value = IDLE_CHATS[Math.floor(Math.random() * IDLE_CHATS.length)]
  idleAnim.value = IDLE_ANIMS[Math.floor(Math.random() * IDLE_ANIMS.length)]
  idleHideTimer = setTimeout(() => {
    idleChat.value = ''
    idleAnim.value = ''
    idleHideTimer = null
    scheduleIdle()
  }, IDLE_SHOW_DURATION)
}

onMounted(() => {
  loadPos()
  fetchTasks()
  pollTimer = setInterval(fetchTasks, POLL_INTERVAL)
  rotateTimer = setInterval(() => {
    if (!chatVisible.value) rotateBubble()
  }, ROTATE_INTERVAL)
  scheduleIdle()
})

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (rotateTimer) { clearInterval(rotateTimer); rotateTimer = null }
  if (idleTimer) { clearTimeout(idleTimer); idleTimer = null }
  if (idleHideTimer) { clearTimeout(idleHideTimer); idleHideTimer = null }
})
</script>

<style scoped>
.ai-pet {
  position: fixed;
  z-index: 2300;
  width: 84px;
  height: 104px;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
}

.ai-pet.dragging {
  cursor: grabbing;
}

/* ── 语音气泡 ── */
.pet-bubble {
  position: absolute;
  bottom: 100px;
  right: 0;
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
  right: 26px;
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
  transform: translateY(6px);
}

/* 空闲闲聊气泡：柔和底色，与任务播报区分 */
.pet-bubble.is-idle {
  background: linear-gradient(135deg, #f0f7ff, #eefbf3);
  border-color: #d5e6ff;
}

.pet-bubble.is-idle::after {
  background: #f0f7ff;
  border-right-color: #d5e6ff;
  border-bottom-color: #d5e6ff;
}

/* ── 宠物本体容器（具体造型由 pets/ 组件渲染） ── */
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

/* ── 工作星光标识（有 AI 任务在处理时出现） ── */
.pet-star {
  position: absolute;
  top: -6px;
  right: -6px;
  z-index: 5;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #fff7cf, #ffd24a 62%, #f6a623);
  box-shadow: 0 0 8px rgba(255, 199, 63, 0.9);
  animation: star-pop 1.6s ease-in-out infinite;
}

.pet-star .star-core {
  font-size: 11px;
  line-height: 1;
  color: #fff;
  text-shadow: 0 0 4px rgba(255, 255, 255, 0.95);
  animation: star-spin 3.2s linear infinite;
}

.star-fade-enter-active,
.star-fade-leave-active {
  transition: all 0.3s ease;
}

.star-fade-enter-from,
.star-fade-leave-to {
  opacity: 0;
  transform: scale(0.3);
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

@keyframes shadow-breathe {
  0%, 100% { transform: translateX(-50%) scale(1); opacity: 1; }
  50% { transform: translateX(-50%) scale(0.82); opacity: 0.6; }
}

@keyframes star-pop {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.18); }
}

@keyframes star-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* working 状态：身体轻微摇摆 */
.ai-pet.working .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-wiggle 2.2s ease-in-out infinite;
}

@keyframes pet-wiggle {
  0%, 100% { rotate: 0deg; }
  25% { rotate: 2.5deg; }
  75% { rotate: -2.5deg; }
}

/* ── 空闲小动效（叠加在悬浮动画上，短促播放后自然停止） ── */
.ai-pet.idle-wave .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-idle-wave 0.7s ease-in-out 3;
}

.ai-pet.idle-hop .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-idle-hop 0.5s ease-in-out 4;
}

.ai-pet.idle-spin .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-idle-spin 1.1s ease-in-out 1;
}

.ai-pet.idle-squash .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-idle-squash 0.6s ease-in-out 3;
}

@keyframes pet-idle-wave {
  0%, 100% { rotate: 0deg; }
  25% { rotate: -12deg; }
  75% { rotate: 12deg; }
}

@keyframes pet-idle-hop {
  0%, 100% { translate: 0 0; }
  50% { translate: 0 -14px; }
}

@keyframes pet-idle-spin {
  from { rotate: 0deg; }
  to { rotate: 360deg; }
}

@keyframes pet-idle-squash {
  0%, 100% { scale: 1; }
  40% { scale: 0.88 1.12; }
  70% { scale: 1.1 0.9; }
}

/* 空闲互动时脚下阴影同步律动 */
.ai-pet.idle-hop .pet-shadow {
  animation: shadow-breathe 0.5s ease-in-out 4;
}

/* 拖动中禁用悬浮动画，跟手更稳 */
.ai-pet.dragging .pet-robot {
  animation: none;
  transform: translateX(-50%) scale(1.05);
}

.ai-pet.dragging .pet-shadow {
  animation: none;
  opacity: 0.5;
}
</style>
