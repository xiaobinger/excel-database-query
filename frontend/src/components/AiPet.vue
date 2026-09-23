<template>
  <div
    ref="petRef"
    class="ai-pet"
    :class="{ working: hasTasks, dragging: isDragging }"
    :style="petPosStyle"
    title="点击和我聊天 · 拖动调整位置"
    @pointerdown="onPointerDown"
  >
    <transition name="bubble-fade">
      <div v-if="bubbleText && !chatVisible" class="pet-bubble">{{ bubbleText }}</div>
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
/** 位移小于该阈值视为点击而非拖动 */
const DRAG_THRESHOLD = 6
const PET_SIZE = { w: 84, h: 104 }

let pollTimer = null
let rotateTimer = null

const hasTasks = computed(() => tasks.value.length > 0)

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
  } catch {
    // 静默失败
  }
}

onMounted(() => {
  loadPos()
  fetchTasks()
  pollTimer = setInterval(fetchTasks, POLL_INTERVAL)
  rotateTimer = setInterval(() => {
    if (!chatVisible.value) rotateBubble()
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
