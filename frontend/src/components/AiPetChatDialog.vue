<template>
  <teleport to="body">
    <transition name="pet-chat-pop">
      <div v-if="modelValue" class="pet-chat-mask" @click.self="close">
        <div class="pet-chat-dialog">
          <div class="pet-chat-header">
            <div class="pet-avatar-mini">{{ petMeta.emoji }}</div>
            <div class="pet-chat-title">
              <div class="title-main">AI 宠物助手 · {{ petMeta.name }}</div>
              <div class="title-sub">{{ chatTitleText }}</div>
            </div>
            <button class="header-btn" title="开启新对话" @click="startNewChat">
              <i class="fas fa-comment-medical"></i>
            </button>
            <button class="header-btn" title="收起" @click="close">
              <i class="fas fa-chevron-down"></i>
            </button>
          </div>

          <div ref="listRef" class="pet-chat-body">
            <div v-if="loadingHistory" class="body-loading">
              <i class="fas fa-spinner fa-spin"></i> 正在唤醒记忆…
            </div>
            <template v-else>
              <div v-if="!messages.length" class="body-empty">
                <div class="empty-pet-avatar">{{ petMeta.emoji }}</div>
                <p>你好呀～我是你的{{ petMeta.name }} (◕‿◕)</p>
                <p class="empty-tip">有什么可以帮你的吗？</p>
              </div>
              <div
                v-for="msg in messages"
                :key="msg.id"
                class="chat-row"
                :class="msg.role"
              >
                <div v-if="msg.role === 'assistant'" class="row-avatar">{{ petMeta.emoji }}</div>
                <div class="bubble" :class="msg.role">
                  <div v-if="msg._thinking && !msg._thinking_done" class="thinking-tag">
                    <i class="fas fa-brain"></i> 深度思考中…
                  </div>
                  <div class="bubble-content" v-html="renderMarkdown(msg.content)"></div>
                  <span v-if="msg._streaming" class="stream-cursor"></span>
                </div>
              </div>
            </template>
          </div>

          <div class="pet-chat-footer">
            <div class="input-wrap">
              <textarea
                ref="inputRef"
                v-model="inputText"
                rows="1"
                placeholder="和宠物聊点什么… (Enter 发送，Shift+Enter 换行)"
                @keydown.enter.exact.prevent="handleSend"
              ></textarea>
              <button
                class="send-btn"
                :disabled="!inputText.trim() || sending"
                :title="sending ? '回复中…' : '发送'"
                @click="handleSend"
              >
                <i :class="sending ? 'fas fa-spinner fa-spin' : 'fas fa-paper-plane'"></i>
              </button>
            </div>
            <div class="footer-tip">宠物对话与「AI 助手」页共用会话记录，随时可前往查看完整功能</div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import api from '../api'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 宠物造型标识，与后端 PET_STYLES 白名单一致 */
  petStyle: { type: String, default: 'robot' },
})
const emit = defineEmits(['update:modelValue'])

/** 各造型对应的头像 emoji 与昵称 */
const PET_META = {
  robot: { emoji: '🤖', name: '小机器人' },
  cat: { emoji: '🐱', name: '喵喵' },
  bunny: { emoji: '🐰', name: '兔兔' },
  panda: { emoji: '🐼', name: '团团' },
  bear: { emoji: '🐻', name: '棕熊' },
  fox: { emoji: '🦊', name: '狐狐' },
  pig: { emoji: '🐷', name: '猪猪' },
  frog: { emoji: '🐸', name: '呱呱' },
  koala: { emoji: '🐨', name: '考拉' },
  chick: { emoji: '🐤', name: '小鸡' },
}
const petMeta = computed(() => PET_META[props.petStyle] || PET_META.robot)

const chats = ref([])
const currentChatId = ref(null)
const chatTitle = ref('')
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const loadingHistory = ref(false)
const listRef = ref(null)
const inputRef = ref(null)

const chatTitleText = computed(() => {
  if (loadingHistory.value) return '…'
  if (!currentChatId.value) return '新对话'
  return chatTitle.value || '对话中'
})

function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text
  }
}

function close() {
  emit('update:modelValue', false)
}

async function scrollToBottom(smooth = true) {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTo({ top: listRef.value.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  }
}

async function loadChats() {
  try {
    const res = await api.ai.getChats()
    chats.value = res.data || []
  } catch {
    chats.value = []
  }
}

async function loadMessages(chatId) {
  try {
    const res = await api.ai.getMessages(chatId)
    messages.value = (res.data || []).map(m => ({ ...m }))
  } catch {
    messages.value = []
  }
  await scrollToBottom(false)
}

async function ensureChat() {
  loadingHistory.value = true
  await loadChats()
  const latest = chats.value[0]
  if (latest) {
    currentChatId.value = latest.id
    chatTitle.value = latest.title || ''
    await loadMessages(latest.id)
  } else {
    await createChat()
  }
  loadingHistory.value = false
}

async function createChat() {
  try {
    const res = await api.ai.createChat({ title: '宠物对话' })
    if (res.data) {
      chats.value.unshift(res.data)
      currentChatId.value = res.data.id
      chatTitle.value = res.data.title || '宠物对话'
      messages.value = []
    }
  } catch {
    chatTitle.value = '新对话'
  }
}

async function startNewChat() {
  if (sending.value) return
  await createChat()
  await nextTick()
  inputRef.value?.focus()
}

watch(() => props.modelValue, async (val) => {
  if (val) {
    await ensureChat()
    await nextTick()
    inputRef.value?.focus()
  }
})

async function handleSend() {
  const content = inputText.value.trim()
  if (!content || sending.value || !currentChatId.value) return
  inputText.value = ''
  messages.value.push({
    id: `local_u_${Date.now()}`,
    role: 'user',
    content,
  })
  sending.value = true
  await scrollToBottom()

  const streamMsg = {
    id: `local_a_${Date.now()}`,
    role: 'assistant',
    content: '',
    _streaming: true,
    _thinking: '',
    _thinking_done: false,
  }
  messages.value.push(streamMsg)
  await scrollToBottom()

  const payload = { content }
  const url = api.ai.sendMessageStream(currentChatId.value, payload)
  const token = localStorage.getItem('token')

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(payload),
    })
    if (!response.ok || !response.body) {
      throw new Error('stream unavailable')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        for (const line of block.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue
          try {
            const event = JSON.parse(dataStr)
            if (event.type === 'thinking') {
              streamMsg._thinking += event.content
            } else if (event.type === 'content') {
              streamMsg.content += event.content
            } else if (event.type === 'truncated') {
              streamMsg.content += (streamMsg.content ? '\n\n' : '') + `*${event.content || 'AI输出因token上限被截断'}*`
            } else if (event.type === 'done') {
              streamMsg._streaming = false
              streamMsg._thinking_done = true
              if (event.message_id) streamMsg.id = event.message_id
            } else if (event.type === 'error') {
              streamMsg._streaming = false
              streamMsg._thinking_done = true
              streamMsg.content = event.content || 'AI服务调用失败'
            }
          } catch {
            // 忽略解析失败的事件块
          }
        }
      }
      await scrollToBottom()
    }
    streamMsg._streaming = false
    streamMsg._thinking_done = true
    if (!streamMsg.content.trim()) {
      streamMsg.content = '（本次没有返回内容，可稍后重试）'
    }
  } catch {
    // 流式失败 → 回退非流式发送
    const idx = messages.value.findIndex(m => m.id === streamMsg.id)
    if (idx > -1) messages.value.splice(idx, 1)
    try {
      const res = await api.ai.sendMessage(currentChatId.value, payload)
      if (res.data?.assistant_message) {
        messages.value.push(res.data.assistant_message)
      }
    } catch {
      messages.value.push({
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: '请求失败，请稍后重试',
      })
    }
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}
</script>

<style scoped>
.pet-chat-mask {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: 0 28px 108px 0;
}

.pet-chat-dialog {
  width: 420px;
  height: 580px;
  max-height: calc(100vh - 160px);
  display: flex;
  flex-direction: column;
  background: var(--main-bg, #fff);
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.22), 0 0 0 1px rgba(64, 158, 255, 0.08);
}

/* ── 头部 ── */
.pet-chat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #a8c8f8 0%, #7ea6ee 50%, #b7d5f7 100%);
  position: relative;
}

.pet-chat-header::before,
.pet-chat-header::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
}

.pet-chat-header::before {
  width: 90px;
  height: 90px;
  top: -34px;
  left: -20px;
}

.pet-chat-header::after {
  width: 52px;
  height: 52px;
  bottom: -18px;
  right: 64px;
}

.pet-chat-title {
  flex: 1;
  min-width: 0;
  position: relative;
  z-index: 1;
}

.title-main {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.title-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.header-btn {
  position: relative;
  z-index: 1;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.header-btn:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: translateY(-1px);
}

/* ── 宠物头像（emoji 随造型切换） ── */
.pet-avatar-mini {
  position: relative;
  z-index: 1;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.28);
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.5);
  animation: mini-float 2.8s ease-in-out infinite;
}

@keyframes mini-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

/* ── 消息区 ── */
.pet-chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 12px;
  background: var(--main-bg, #f7f9fc);
  background-image: radial-gradient(circle at 12px 12px, rgba(126, 166, 238, 0.08) 2px, transparent 2.5px);
  background-size: 34px 34px;
}

.body-loading {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 40px 0;
}

.body-empty {
  text-align: center;
  padding: 40px 0 20px;
  color: #606266;
  font-size: 13px;
}

.empty-pet-avatar {
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  line-height: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 32%, #ffffff, #eaf1fd);
  box-shadow: 0 4px 14px rgba(126, 166, 238, 0.28);
  animation: mini-float 2.8s ease-in-out infinite;
}

.empty-tip {
  color: #a0a6b0;
  font-size: 12px;
  margin-top: 6px;
}

.chat-row {
  display: flex;
  margin-bottom: 12px;
  gap: 8px;
}

.chat-row.user {
  justify-content: flex-end;
}

.row-avatar {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  align-self: flex-end;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  line-height: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 32%, #ffffff, #eaf1fd);
  box-shadow: 0 2px 6px rgba(139, 163, 201, 0.2);
}

.bubble {
  max-width: 78%;
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.65;
  border-radius: 14px;
  word-break: break-word;
}

.bubble.user {
  background: linear-gradient(135deg, #6ea3f0, #5288e0);
  color: #fff;
  border-bottom-right-radius: 5px;
}

.bubble.assistant {
  background: #fff;
  color: var(--text-primary, #303133);
  border: 1px solid rgba(126, 166, 238, 0.25);
  border-bottom-left-radius: 5px;
  box-shadow: 0 2px 8px rgba(139, 163, 201, 0.12);
}

.bubble-content :deep(p) {
  margin: 0 0 6px;
}

.bubble-content :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble-content :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
}

.bubble-content :deep(code) {
  font-family: Consolas, Monaco, monospace;
}

.bubble-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.bubble-content :deep(code) {
  background: rgba(126, 166, 238, 0.14);
  padding: 1px 5px;
  border-radius: 4px;
  color: #4a6fb5;
}

.bubble-content :deep(ul),
.bubble-content :deep(ol) {
  padding-left: 18px;
  margin: 4px 0;
}

.bubble-content :deep(table) {
  border-collapse: collapse;
  font-size: 12px;
  margin: 6px 0;
}

.bubble-content :deep(th),
.bubble-content :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
}

.bubble-content :deep(blockquote) {
  margin: 4px 0;
  padding: 2px 10px;
  border-left: 3px solid #a8c8f8;
  color: #909399;
}

.thinking-tag {
  font-size: 11px;
  color: #9b7ee0;
  margin-bottom: 6px;
  animation: thinking-pulse 1.4s ease-in-out infinite;
}

@keyframes thinking-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.stream-cursor {
  display: inline-block;
  width: 7px;
  height: 14px;
  margin-left: 2px;
  vertical-align: -2px;
  background: #7ea6ee;
  border-radius: 2px;
  animation: cursor-blink 0.9s steps(2) infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── 输入区 ── */
.pet-chat-footer {
  padding: 10px 12px 12px;
  background: var(--header-bg, #fff);
  border-top: 1px solid var(--border-color, #e4e7ed);
}

.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--main-bg, #f5f7fa);
  border: 1.5px solid rgba(126, 166, 238, 0.35);
  border-radius: 14px;
  padding: 8px 8px 8px 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-wrap:focus-within {
  border-color: #7ea6ee;
  box-shadow: 0 0 0 3px rgba(126, 166, 238, 0.15);
}

.input-wrap textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-size: 13px;
  line-height: 1.6;
  max-height: 96px;
  color: var(--text-primary, #303133);
  font-family: inherit;
}

.input-wrap textarea::placeholder {
  color: #a8adb8;
}

.send-btn {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 11px;
  background: linear-gradient(135deg, #6ea3f0, #5288e0);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.04);
  box-shadow: 0 4px 10px rgba(82, 136, 224, 0.4);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.footer-tip {
  font-size: 11px;
  color: #a8adb8;
  text-align: center;
  margin-top: 8px;
}

/* ── 弹窗动画 ── */
.pet-chat-pop-enter-active {
  transition: all 0.32s cubic-bezier(0.34, 1.4, 0.64, 1);
}

.pet-chat-pop-leave-active {
  transition: all 0.22s ease;
}

.pet-chat-pop-enter-from,
.pet-chat-pop-leave-to {
  opacity: 0;
}

.pet-chat-pop-enter-from .pet-chat-dialog {
  transform: translateY(28px) scale(0.92);
}

.pet-chat-pop-enter-active .pet-chat-dialog,
.pet-chat-pop-leave-active .pet-chat-dialog {
  transition: transform 0.32s cubic-bezier(0.34, 1.4, 0.64, 1);
}

.pet-chat-pop-leave-to .pet-chat-dialog {
  transform: translateY(20px) scale(0.95);
}
</style>
