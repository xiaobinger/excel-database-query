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
      <component :is="petComponent" :working="hasTasks" :mood="petMood" />
    </div>
    <div class="pet-shadow"></div>
  </div>

  <AiPetChatDialog v-model="chatVisible" :pet-style="petStyle" />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api'
import { onPetEvent } from '../utils/petBus'
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
/** 空闲自动互动：随机间隔范围（毫秒）——稍频繁但不过度打扰 */
const IDLE_MIN_INTERVAL = 10000
const IDLE_MAX_INTERVAL = 24000
/** 单条闲聊气泡展示时长（毫秒） */
const IDLE_SHOW_DURATION = 6000
/** 特殊大动效（滚动横穿/偷袭光标）触发概率 */
const SPECIAL_PROBABILITY = 0.22
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
  'SQL 写得好，下班下得早 ✌️',
  '偷偷问一句……今天要跑分润吗？',
  '小天线收到了想查数据的电波 📡',
  '别看我圆，跑起任务来可快了 ⚡',
  '一键导出，交给我就好！',
  '盯……监测到你在认真工作 👏',
  '咕噜咕噜～肚子饿了，喂我点任务吧',
  '今天也是元气满满的一天！',
  '光标一闪一闪的，好像在叫我 ✨',
  '久坐提醒：起来晃两下再战 💪',
  'Ctrl+S 了吗？我帮你记着呢',
  '监督者说我今天表现很乖 😇',
  '悄悄说：我也能直接执行任务哦',
  '翻了个身，继续待命 🌀',
  '哇，屏幕好大，数据好多 🌏',
  '电量满格，随时开工！🔋',
  '打个哈欠……啊——还是想帮你查数据',
  '发现问题？不，那是特性 😉',
]

/** 空闲小动效 class 池（纯 CSS） */
const IDLE_ANIMS = ['idle-wave', 'idle-hop', 'idle-spin', 'idle-squash', 'idle-shimmy', 'idle-backflip']

/** 特殊大动效池（JS 驱动）：滚动横穿屏幕 / 偷袭鼠标光标 */
const IDLE_SPECIALS = ['idle-roll', 'idle-pounce']

/** 特殊动效专用话术 */
const SPECIAL_CHATS = {
  'idle-roll': [
    '咕噜咕噜——滚过去咯！',
    '冲鸭——！咕噜噜噜～',
    '看我无敌风火轮！🌀',
    '咕噜咕噜，巡回演出开始～',
    '滚一圈回来继续待命！',
  ],
  'idle-pounce': [
    '发现光标！偷袭～',
    '嘿！你的鼠标被我盯上了 😼',
    '光标别跑！噗——',
    '偷袭成功！爪下留情 🐾',
    '突袭鼠标小分队，出动！',
  ],
}

/** 围观话术：用户手动执行查询/导出时，凑近看两眼再跑开 */
const PEEK_CHATS = {
  query: [
    '主人，在干嘛呢，这么简单的活下次直接交给我吧',
    '让我康康……哦～是在查数据呀',
    '这个查询我会！下次喊我就好啦',
    '哇，屏幕上的数据在跳舞诶 👀',
  ],
  export: [
    '又要导报表啦？我可比你手快哦',
    '导出交给人家嘛，你歇会儿～',
    '这份表我来导，保证又快又整齐！',
    '偷偷问一句：要导哪张表呀？',
  ],
  common: [
    '啥机密数据啊，我保证不偷看哦 🙈',
    '嘿嘿，我就看一眼，马上走～',
  ],
}

/** 文件生成提醒话术 */
const READY_CHATS = [
  '叮！文件出炉啦，快来下载 📥',
  '报告主人！您的文件已打包完毕 ✨',
  '热乎乎的结果文件出炉咯，趁热下载～',
  '任务搞定！文件在等你带回家 📦',
]

let pollTimer = null
let rotateTimer = null
let idleTimer = null
let idleHideTimer = null
/** petBus 事件退订函数集合 */
const eventCleanups = []
/** 特殊大动效进行中标记（防止叠加触发） */
let specialRunning = false
/** 最近一次鼠标光标位置（偷袭光标动效使用） */
const lastMouse = { x: null, y: null }
/** 最近一次围观触发时间（冷却用） */
let lastPeekAt = 0
/** 宠物表情状态：normal/happy/curious/sneaky/proud/excited/dizzy/sleepy/alert */
const petMood = ref('normal')
let moodTimer = null

/** 临时切换表情，到期自动回落 normal */
function flashMood(mood, ms = 2600) {
  petMood.value = mood
  if (moodTimer) clearTimeout(moodTimer)
  moodTimer = setTimeout(() => {
    petMood.value = 'normal'
    moodTimer = null
  }, ms)
}

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

function pickRandom(list) {
  return list[Math.floor(Math.random() * list.length)]
}

/** 特殊动效中途是否放弃（打开对话/切后台/开始拖动时终止） */
function specialBailed() {
  return chatVisible.value || document.hidden || isDragging.value
}

/** 光标目标位置（无移动记录时回退屏幕中心） */
function mouseTarget() {
  const w = window.innerWidth
  const h = window.innerHeight
  if (lastMouse.x == null || lastMouse.y == null) {
    return { x: w * 0.5, y: h * 0.5 }
  }
  return { x: lastMouse.x, y: lastMouse.y }
}

function triggerIdle() {
  idleTimer = null
  if (hasTasks.value || chatVisible.value || isDragging.value || document.hidden || specialRunning) {
    scheduleIdle()
    return
  }
  // 小概率触发特殊大动效：滚动横穿屏幕 / 偷袭鼠标光标
  if (Math.random() < SPECIAL_PROBABILITY) {
    runSpecial(pickRandom(IDLE_SPECIALS))
    return
  }
  idleChat.value = pickRandom(IDLE_CHATS)
  idleAnim.value = pickRandom(IDLE_ANIMS)
  flashMood(pickRandom(['happy', 'happy', 'curious', 'sleepy']), 3200)
  idleHideTimer = setTimeout(() => {
    idleChat.value = ''
    idleAnim.value = ''
    idleHideTimer = null
    scheduleIdle()
  }, IDLE_SHOW_DURATION)
}

/** 特殊大动效：专用话术 + JS 驱动动画，结束后自动恢复排程 */
async function runSpecial(kind) {
  specialRunning = true
  clearIdleChat()
  idleChat.value = pickRandom(SPECIAL_CHATS[kind] || ['～'])
  try {
    if (kind === 'idle-roll') {
      flashMood('dizzy', 5600)
      await playRoll()
    } else if (kind === 'idle-pounce') {
      flashMood('sneaky', 2000)
      await playPounce()
      flashMood('proud', 2200)
    }
  } catch {
    // 动画中断（WAAPI缺失/中途打开对话等）直接复位
  } finally {
    resetSpecialPose()
    idleChat.value = ''
    idleAnim.value = ''
    specialRunning = false
    scheduleIdle()
  }
}

/** 清理 WAAPI 残留，让 CSS 悬浮动画自然接管 */
function resetSpecialPose() {
  const el = petRef.value
  if (!el) return
  el.getAnimations().forEach(a => a.cancel())
  const robot = el.querySelector('.pet-robot')
  if (robot) robot.getAnimations().forEach(a => a.cancel())
}

/** 滚动横穿屏幕：贴地滚到屏幕另一侧，停顿一下后滚回原位 */
async function playRoll() {
  const el = petRef.value
  if (!el || !el.animate) throw new Error('no waapi')
  const rect = el.getBoundingClientRect()
  const w = window.innerWidth
  const goingLeft = rect.left + rect.width / 2 > w / 2
  const margin = 12
  const targetX = goingLeft ? (margin - rect.left) : (w - margin - rect.right)
  const dist = Math.abs(targetX)
  if (dist < 40) throw new Error('too close')
  const dur = Math.min(2400, Math.max(800, dist * 1.2))
  const spinDeg = (goingLeft ? -1 : 1) * 360 * Math.max(1, Math.round(dist / 500))
  const robot = el.querySelector('.pet-robot')
  const easing = 'cubic-bezier(0.5, 0, 0.5, 1)'
  // 滚出去（本体平移 + 造型本体翻滚，气泡保持水平可读）
  const rollOut = el.animate(
    [{ transform: 'translateX(0)' }, { transform: `translateX(${targetX}px)` }],
    { duration: dur, easing, fill: 'forwards' }
  )
  const spinOut = robot
    ? robot.animate(
        [{ transform: 'translateX(-50%) rotate(0deg)' }, { transform: `translateX(-50%) rotate(${spinDeg}deg)` }],
        { duration: dur, easing, fill: 'forwards' }
      )
    : null
  await rollOut.finished
  if (specialBailed()) throw new Error('bail')
  await sleep(320)
  // 滚回来（反向翻滚）
  const rollBack = el.animate(
    [{ transform: `translateX(${targetX}px)` }, { transform: 'translateX(0)' }],
    { duration: dur, easing, fill: 'forwards' }
  )
  const spinBack = robot
    ? robot.animate(
        [{ transform: `translateX(-50%) rotate(${spinDeg}deg)` }, { transform: 'translateX(-50%) rotate(0deg)' }],
        { duration: dur, easing, fill: 'forwards' }
      )
    : null
  await rollBack.finished
}

/** 偷袭鼠标光标：蓄力下蹲 → 弧线猛扑到光标旁 → 得意停留 → 蹦回原位 */
async function playPounce() {
  const el = petRef.value
  if (!el || !el.animate) throw new Error('no waapi')
  const rect = el.getBoundingClientRect()
  const w = window.innerWidth
  const h = window.innerHeight
  const cur = mouseTarget()
  // 落点在光标右上方一点，不遮挡光标本体
  const targetLeft = Math.min(Math.max(cur.x - rect.width / 2 + 34, 4), w - rect.width - 4)
  const targetTop = Math.min(Math.max(cur.y - rect.height - 8, 4), h - rect.height - 4)
  const dx = targetLeft - rect.left
  const dy = targetTop - rect.top
  if (Math.hypot(dx, dy) < 30) throw new Error('too close')
  // 蓄力下蹲
  await el.animate(
    [{ transform: 'translate(0, 0) scale(1, 1)' }, { transform: 'translate(0, 7px) scale(1.14, 0.8)' }],
    { duration: 240, easing: 'ease-in', fill: 'forwards' }
  ).finished
  // 猛扑（小弧线跳跃）
  await el.animate(
    [
      { transform: 'translate(0, 7px) scale(1.14, 0.8)' },
      { transform: `translate(${dx * 0.5}px, ${dy * 0.5 - 30}px) scale(0.92, 1.12)`, offset: 0.55 },
      { transform: `translate(${dx}px, ${dy}px) scale(1.1, 0.88)`, offset: 0.85 },
      { transform: `translate(${dx}px, ${dy}px) scale(1, 1)` },
    ],
    { duration: 520, easing: 'ease-out', fill: 'forwards' }
  ).finished
  if (specialBailed()) throw new Error('bail')
  await sleep(620)
  // 蹦回原地
  await el.animate(
    [
      { transform: `translate(${dx}px, ${dy}px)` },
      { transform: `translate(${dx * 0.45}px, ${dy * 0.45 - 44}px) scale(0.95, 1.08)`, offset: 0.5 },
      { transform: 'translate(0, 0)' },
    ],
    { duration: 560, easing: 'ease-in-out', fill: 'forwards' }
  ).finished
}

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/** 围观用户操作：慢慢凑近 → 俏皮话 → 跑开（查询/导出执行时由页面事件触发） */
async function runPeek(op) {
  const now = Date.now()
  if (specialRunning || chatVisible.value || isDragging.value || document.hidden) return
  if (now - lastPeekAt < 30000) return
  const el = petRef.value
  if (!el || !el.animate) return
  lastPeekAt = now
  specialRunning = true
  clearIdleChat()
  const rect = el.getBoundingClientRect()
  const w = window.innerWidth
  const h = window.innerHeight
  const cur = mouseTarget()
  // 目标：朝光标方向凑近 35%，稍微抬高视线
  let dx = (cur.x - (rect.left + rect.width / 2)) * 0.35
  let dy = (cur.y - (rect.top + rect.height / 2)) * 0.35 - 26
  dx = Math.min(Math.max(dx, 8 - rect.left), w - 8 - rect.left - rect.width)
  dy = Math.min(Math.max(dy, 8 - rect.top), h - 8 - rect.top - rect.height)
  try {
    // 慢慢凑近（两段探头探脑）
    flashMood(op?.type === 'export' ? 'sneaky' : 'curious', 5400)
    await el.animate(
      [{ transform: 'translate(0, 0)' }, { transform: `translate(${dx * 0.7}px, ${dy * 0.7}px)` }],
      { duration: 520, easing: 'ease-in-out', fill: 'forwards' }
    ).finished
    if (specialBailed()) throw new Error('bail')
    await el.animate(
      [{ transform: `translate(${dx * 0.7}px, ${dy * 0.7}px)` }, { transform: `translate(${dx}px, ${dy}px)` }],
      { duration: 420, easing: 'ease-in-out', fill: 'forwards' }
    ).finished
    if (specialBailed()) throw new Error('bail')
    // 俏皮话（本类型话术 + 通用话术混合）
    idleChat.value = pickRandom([...(PEEK_CHATS[op?.type] || []), ...PEEK_CHATS.common])
    idleAnim.value = 'idle-shimmy'
    await sleep(3000)
    idleChat.value = ''
    idleAnim.value = ''
    // 跑开（快速弹回 + 小跳）
    await el.animate(
      [
        { transform: `translate(${dx}px, ${dy}px)` },
        { transform: `translate(${dx * 0.4}px, ${dy * 0.4 - 30}px)`, offset: 0.45 },
        { transform: 'translate(0, 0)' },
      ],
      { duration: 560, easing: 'ease-in', fill: 'forwards' }
    ).finished
  } catch {
    // 中断即复位
  } finally {
    resetSpecialPose()
    idleChat.value = ''
    idleAnim.value = ''
    specialRunning = false
  }
}

/** 文件生成提醒：气泡 + 弹跳庆祝 + 惊喜表情 */
function notifyFileReady(op) {
  if (chatVisible.value || document.hidden) return
  clearIdleChat()
  flashMood('alert', 3400)
  const label = op?.label && op.label.length <= 14 ? `（${op.label}）` : ''
  idleChat.value = pickRandom(READY_CHATS) + label
  idleAnim.value = 'idle-hop'
  if (idleHideTimer) clearTimeout(idleHideTimer)
  idleHideTimer = setTimeout(() => {
    idleChat.value = ''
    idleAnim.value = ''
    idleHideTimer = null
  }, 5200)
  const el = petRef.value
  if (el && el.animate) {
    el.animate(
      [
        { transform: 'translateY(0)' },
        { transform: 'translateY(-16px)', offset: 0.3 },
        { transform: 'translateY(0)', offset: 0.55 },
        { transform: 'translateY(-10px)', offset: 0.75 },
        { transform: 'translateY(0)' },
      ],
      { duration: 760, easing: 'ease-out' }
    )
  }
}

function onMouseMove(e) {
  lastMouse.x = e.clientX
  lastMouse.y = e.clientY
}

onMounted(() => {
  loadPos()
  fetchTasks()
  pollTimer = setInterval(fetchTasks, POLL_INTERVAL)
  rotateTimer = setInterval(() => {
    if (!chatVisible.value) rotateBubble()
  }, ROTATE_INTERVAL)
  window.addEventListener('mousemove', onMouseMove, { passive: true })
  const offOp = onPetEvent('operation', runPeek)
  const offReady = onPetEvent('file_ready', notifyFileReady)
  eventCleanups.push(offOp, offReady)
  scheduleIdle()
})

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (rotateTimer) { clearInterval(rotateTimer); rotateTimer = null }
  if (idleTimer) { clearTimeout(idleTimer); idleTimer = null }
  if (idleHideTimer) { clearTimeout(idleHideTimer); idleHideTimer = null }
  if (moodTimer) { clearTimeout(moodTimer); moodTimer = null }
  window.removeEventListener('mousemove', onMouseMove)
  eventCleanups.forEach(off => { try { off() } catch {} })
  eventCleanups.length = 0
  resetSpecialPose()
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

/* 扭屁股小舞步 */
.ai-pet.idle-shimmy .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-idle-shimmy 0.9s ease-in-out 3;
}

@keyframes pet-idle-shimmy {
  0%, 100% { rotate: 0deg; translate: 0 0; }
  20% { rotate: 9deg; translate: 5px 0; }
  40% { rotate: -9deg; translate: -5px 0; }
  60% { rotate: 9deg; translate: 5px 0; }
  80% { rotate: -9deg; translate: -5px 0; }
}

/* 后空翻 */
.ai-pet.idle-backflip .pet-robot {
  animation: pet-float 3s ease-in-out infinite, pet-idle-backflip 0.95s ease-in-out 1;
}

@keyframes pet-idle-backflip {
  0% { rotate: 0deg; translate: 0 0; }
  35% { rotate: -130deg; translate: 0 -22px; }
  70% { rotate: -300deg; translate: 0 -6px; }
  100% { rotate: -360deg; translate: 0 0; }
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
