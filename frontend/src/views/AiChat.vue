<template>
  <div class="ai-chat">
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <el-button type="primary" style="width: 100%" @click="createNewChat">
          <i class="fas fa-plus"></i> 新对话
        </el-button>
      </div>
      <div class="chat-list">
        <div
          v-for="chat in chats"
          :key="chat.id"
          class="chat-item"
          :class="{ active: currentChatId === chat.id }"
          @click="selectChat(chat.id)"
        >
          <div class="chat-item-title">{{ chat.title || '新对话' }}</div>
          <el-button type="danger" text size="small" class="chat-item-del" @click.stop="deleteChat(chat.id)">
            <i class="fas fa-trash"></i>
          </el-button>
        </div>
        <el-empty v-if="chats.length === 0" description="暂无对话" :image-size="60" />
      </div>
    </div>

    <div class="chat-main">
      <div v-if="!currentChatId" class="chat-welcome">
        <div class="welcome-icon"><i class="fas fa-robot"></i></div>
        <h2>AI 智能助手</h2>
        <p>我可以帮你生成SQL查询、创建查询选项、优化语句等</p>
        <div class="quick-actions">
          <el-button @click="quickAsk('帮我生成一个查询商户信息的SQL')">生成SQL查询</el-button>
          <el-button @click="quickAsk('帮我优化这个SQL语句')">优化SQL</el-button>
          <el-button @click="quickAsk('如何配置自动导出任务？')">使用帮助</el-button>
        </div>
      </div>

      <template v-else>
        <div class="messages-area" ref="messagesRef">
          <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
            <div class="message-avatar">
              <i :class="msg.role === 'user' ? 'fas fa-user' : 'fas fa-robot'"></i>
            </div>
            <div class="message-content">
              <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <div v-if="loading" class="message assistant">
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">
              <div class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>

        <div class="input-area">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入消息，按 Enter 发送，Shift+Enter 换行..."
            resize="none"
            @keydown="handleKeydown"
          />
          <el-button type="primary" :loading="loading" :disabled="!inputText.trim()" @click="sendMessage">
            <i class="fas fa-paper-plane"></i>
          </el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import hljs from 'highlight.js'

// 配置 marked
marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang }).value
      } catch {}
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true,
})

const chats = ref([])
const currentChatId = ref(null)
const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messagesRef = ref(null)

async function fetchChats() {
  try {
    const res = await api.ai.getChats()
    chats.value = res.data || []
  } catch {}
}

async function createNewChat() {
  try {
    const res = await api.ai.createChat({ title: '新对话' })
    if (res.data) {
      chats.value.unshift(res.data)
      selectChat(res.data.id)
    }
  } catch {}
}

async function selectChat(chatId) {
  currentChatId.value = chatId
  try {
    const res = await api.ai.getMessages(chatId)
    messages.value = res.data || []
    await nextTick()
    scrollToBottom()
  } catch {}
}

async function deleteChat(chatId) {
  try {
    await api.ai.deleteChat(chatId)
    chats.value = chats.value.filter(c => c.id !== chatId)
    if (currentChatId.value === chatId) {
      currentChatId.value = null
      messages.value = []
    }
  } catch {}
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  if (!currentChatId.value) {
    await createNewChat()
    if (!currentChatId.value) return
  }

  inputText.value = ''
  loading.value = true

  // Optimistic add user message
  messages.value.push({ id: Date.now(), role: 'user', content: text })
  await nextTick()
  scrollToBottom()

  try {
    const res = await api.ai.sendMessage(currentChatId.value, { content: text })
    if (res.data?.assistant_message) {
      messages.value.push(res.data.assistant_message)
    }
    await nextTick()
    scrollToBottom()

    // Track behavior
    api.ai.trackBehavior({ action: 'chat', target_type: 'ai_chat', target_id: currentChatId.value }).catch(() => {})
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    loading.value = false
  }
}

function quickAsk(text) {
  inputText.value = text
  sendMessage()
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text.replace(/\n/g, '<br>')
  }
}

onMounted(() => {
  fetchChats()
})
</script>

<style scoped>
.ai-chat {
  display: flex;
  height: calc(100vh - 120px);
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #eef2f7;
}

.chat-sidebar {
  width: 260px;
  border-right: 1px solid #eef2f7;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #eef2f7;
}

.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.chat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.chat-item:hover {
  background: #f0f2f5;
}

.chat-item.active {
  background: var(--primary-color, #409eff);
  color: #fff;
}

.chat-item.active .chat-item-del {
  color: rgba(255,255,255,0.7);
}

.chat-item-title {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-item-del {
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-item:hover .chat-item-del {
  opacity: 1;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
}

.welcome-icon {
  font-size: 48px;
  color: var(--primary-color, #409eff);
  margin-bottom: 16px;
}

.chat-welcome h2 {
  color: #303133;
  margin: 0 0 8px;
}

.chat-welcome p {
  margin: 0 0 24px;
}

.quick-actions {
  display: flex;
  gap: 12px;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
}

.message.user .message-avatar {
  background: var(--primary-color, #409eff);
  color: #fff;
}

.message.assistant .message-avatar {
  background: #f0f2f5;
  color: #606266;
}

.message-content {
  max-width: 70%;
}

.message-text {
  padding: 10px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message.user .message-text {
  background: var(--primary-color, #409eff);
  color: #fff;
  border-top-right-radius: 4px;
}

.message.assistant .message-text {
  background: #f4f6f8;
  color: #303133;
  border-top-left-radius: 4px;
}

/* Markdown 渲染样式 */
.message.assistant .message-text :deep(h1),
.message.assistant .message-text :deep(h2),
.message.assistant .message-text :deep(h3),
.message.assistant .message-text :deep(h4) {
  margin: 12px 0 8px;
  font-weight: 600;
  color: #1a1a2e;
}

.message.assistant .message-text :deep(h1) { font-size: 1.4em; }
.message.assistant .message-text :deep(h2) { font-size: 1.25em; }
.message.assistant .message-text :deep(h3) { font-size: 1.1em; }

.message.assistant .message-text :deep(p) {
  margin: 6px 0;
  line-height: 1.7;
}

.message.assistant .message-text :deep(ul),
.message.assistant .message-text :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}

.message.assistant .message-text :deep(li) {
  margin: 3px 0;
  line-height: 1.6;
}

.message.assistant .message-text :deep(blockquote) {
  border-left: 4px solid var(--primary-color, #409eff);
  padding: 8px 12px;
  margin: 8px 0;
  background: rgba(64, 158, 255, 0.06);
  border-radius: 0 6px 6px 0;
  color: #606266;
}

.message.assistant .message-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 13px;
}

.message.assistant .message-text :deep(th),
.message.assistant .message-text :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
  text-align: left;
}

.message.assistant .message-text :deep(th) {
  background: #f0f2f5;
  font-weight: 600;
}

.message.assistant .message-text :deep(hr) {
  border: none;
  border-top: 1px solid #dcdfe6;
  margin: 12px 0;
}

.message.assistant .message-text :deep(a) {
  color: var(--primary-color, #409eff);
  text-decoration: none;
}

.message.assistant .message-text :deep(a:hover) {
  text-decoration: underline;
}

.message.assistant .message-text :deep(pre) {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  font-size: 13px;
  line-height: 1.5;
  position: relative;
}

.message.assistant .message-text :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
  font-size: inherit;
  line-height: inherit;
}

.message.assistant .message-text :deep(code) {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

.message.assistant .message-text :deep(strong) {
  color: #1a1a2e;
  font-weight: 600;
}

.message.assistant .message-text :deep(em) {
  color: #606266;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

.input-area {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #eef2f7;
  align-items: flex-end;
}

.input-area :deep(.el-textarea__inner) {
  border-radius: 8px;
}
</style>
