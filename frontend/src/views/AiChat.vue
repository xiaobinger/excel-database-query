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
        <p>我可以帮你生成SQL查询、创建查询选项、优化语句、执行导出任务、解析Excel文件等</p>
        <div class="quick-actions">
          <el-button @click="quickAsk('帮我导出商户123456的信息')">执行导出任务</el-button>
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
            <div class="message-content" :class="{ 'full-width': msg._type === 'tool' || msg._type === 'file' }">
              <!-- 文件附件显示 -->
              <template v-if="msg._type === 'file'">
                <div class="file-card">
                  <div class="file-card-header">
                    <i class="fas fa-file-excel file-icon"></i>
                    <span class="file-title">{{ msg._file_data.filename }}</span>
                  </div>
                  <div class="file-card-body">
                    <div class="file-info-row">
                      <span><i class="fas fa-table"></i> {{ msg._file_data.row_count }} 行</span>
                      <span><i class="fas fa-columns"></i> {{ msg._file_data.columns.length }} 列</span>
                    </div>
                    <div class="file-columns">
                      <el-tag v-for="col in msg._file_data.columns.slice(0, 10)" :key="col" size="small" effect="plain" style="margin: 2px 4px 2px 0">
                        {{ col }}
                      </el-tag>
                      <el-tag v-if="msg._file_data.columns.length > 10" size="small" type="info" effect="plain">
                        +{{ msg._file_data.columns.length - 10 }}
                      </el-tag>
                    </div>
                  </div>
                </div>
              </template>
              <!-- 普通文本消息 -->
              <template v-else-if="msg._type !== 'tool'">
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </template>
              <!-- 工具调用确认卡片 -->
              <template v-else-if="!msg._dismissed">
                <div class="tool-card">
                  <div class="tool-card-header">
                    <i class="fas fa-magic tool-icon"></i>
                    <span class="tool-title">{{ msg.tool_data.action_type === 'export' ? '导出任务确认' : '查询任务确认' }}</span>
                  </div>
                  <div class="tool-card-body">
                    <p class="tool-confirm-msg">{{ msg.tool_data.confirm_message }}</p>
                    <p v-if="msg.tool_data.required_missing && msg.tool_data.required_missing.length" class="tool-warning">
                      <i class="fas fa-exclamation-triangle"></i> 缺少必填参数：{{ msg.tool_data.required_missing.join(', ') }}
                    </p>
                  </div>
                  <div class="tool-card-actions">
                    <el-button
                      v-if="msg.tool_data.action_type === 'export'"
                      type="primary"
                      size="small"
                      @click="confirmExport(msg)"
                      :disabled="msg.tool_data.required_missing && msg.tool_data.required_missing.length > 0"
                    >
                      <i class="fas fa-play"></i> 确认执行导出
                    </el-button>
                    <el-button
                      v-else-if="msg.tool_data.action_type === 'query'"
                      type="primary"
                      size="small"
                      @click="confirmQuery(msg)"
                    >
                      <i class="fas fa-play"></i> 确认执行查询
                    </el-button>
                    <el-button size="small" text @click="dismissTool(msg)">
                      忽略
                    </el-button>
                  </div>
                </div>
              </template>
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
          <div class="input-wrapper">
            <div v-if="uploadedFile" class="file-attachment">
              <i class="fas fa-file-excel"></i>
              <span class="file-name">{{ uploadedFile.filename }}</span>
              <span class="file-info">{{ uploadedFile.row_count }} 行 · {{ uploadedFile.columns.length }} 列</span>
              <i class="fas fa-times file-remove" @click="uploadedFile = null"></i>
            </div>
            <div class="input-row">
              <el-input
                v-model="inputText"
                type="textarea"
                :rows="2"
                placeholder="输入消息，按 Enter 发送，Shift+Enter 换行..."
                resize="none"
                @keydown="handleKeydown"
              />
              <div class="input-buttons">
                <el-upload
                  :show-file-list="false"
                  :before-upload="handleFileUpload"
                  accept=".xlsx,.xls,.csv"
                >
                  <el-button type="info" size="small" :disabled="loading" title="上传Excel文件">
                    <i class="fas fa-file-upload"></i>
                  </el-button>
                </el-upload>
                <el-button type="primary" :loading="loading" :disabled="!canSend" @click="sendMessage">
                  <i class="fas fa-paper-plane"></i>
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
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
const uploadedFile = ref(null)

const canSend = computed(() => {
  return (inputText.value.trim() || uploadedFile.value) && !loading.value
})

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
    const msgs = res.data || []
    messages.value = msgs.map(m => ({ ...m, _dismissed: false }))
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

async function handleFileUpload(file) {
  if (!currentChatId.value) {
    await createNewChat()
    if (!currentChatId.value) return false
  }
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.ai.uploadFile(formData)
    if (res.data) {
      uploadedFile.value = res.data
      ElMessage.success(`文件解析成功：${res.data.row_count} 行，${res.data.columns.length} 列`)
    }
  } catch (e) {
    ElMessage.error('文件上传失败: ' + (e.message || '未知错误'))
  }
  return false // prevent default upload
}

async function sendMessage() {
  const text = inputText.value.trim()
  if ((!text && !uploadedFile.value) || loading.value) return

  if (!currentChatId.value) {
    await createNewChat()
    if (!currentChatId.value) return
  }

  // Build message content with file info if uploaded
  let content = text
  if (uploadedFile.value) {
    const fileInfo = uploadedFile.value
    const fileDesc = `用户上传了文件 "${fileInfo.filename}"（${fileInfo.row_count} 行，${fileInfo.columns.length} 列），列名：${fileInfo.columns.join(', ')}`
    content = text ? `${content}\n\n[${fileDesc}]` : fileDesc
  }

  inputText.value = ''
  loading.value = true

  // Optimistic add user message
  const userMsg = { id: Date.now(), role: 'user', content: content }
  messages.value.push(userMsg)

  // Show file as separate bubble
  if (uploadedFile.value) {
    messages.value.push({
      id: Date.now() + 1,
      role: 'user',
      content: '',
      _type: 'file',
      _dismissed: false,
      _file_data: { ...uploadedFile.value },
    })
  }

  await nextTick()
  scrollToBottom()

  try {
    const res = await api.ai.sendMessage(currentChatId.value, { content: content })

    // Add AI text reply
    if (res.data?.assistant_message) {
      messages.value.push(res.data.assistant_message)
    }

    // Handle tool call results
    if (res.data?.tool_results && res.data.tool_results.length > 0) {
      for (const tr of res.data.tool_results) {
        const result = tr.result
        if (result && !result.error && (result.action_type === 'export' || result.action_type === 'query')) {
          messages.value.push({
            id: Date.now() + Math.random(),
            role: 'assistant',
            content: '',
            _type: 'tool',
            _dismissed: false,
            tool_data: result,
          })
        } else if (result && result.error) {
          messages.value.push({
            id: Date.now() + Math.random(),
            role: 'assistant',
            content: `⚠️ ${result.error}`,
          })
        }
      }
    }

    await nextTick()
    scrollToBottom()

    api.ai.trackBehavior({ action: 'chat', target_type: 'ai_chat', target_id: currentChatId.value }).catch(() => {})
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    loading.value = false
    uploadedFile.value = null
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

function dismissTool(msg) {
  msg._dismissed = true
}

async function confirmExport(msg) {
  const td = msg.tool_data
  const params = { ...td.params }
  // 添加 all_checked 状态（未提供的 allow_all 参数自动勾选全部）
  const allChecked = td.all_checked || {}

  try {
    ElMessage.info('正在执行导出...')
    const res = await api.export.execute({
      script_ids: [td.script_id],
      params_values: params,
      all_checked: allChecked,
      output_format: td.output_format || 'sheets',
    })
    if (res.data) {
      const taskId = res.data.task_id
      ElMessage.success('导出任务已提交')
      messages.value.push({
        id: Date.now(),
        role: 'assistant',
        content: `✅ 导出任务已提交！任务ID: ${taskId}\n\n你可以在导出任务列表中查看进度和下载文件。`,
      })
      dismissTool(msg)
      await nextTick()
      scrollToBottom()
    }
  } catch (e) {
    ElMessage.error('导出执行失败: ' + (e.message || '未知错误'))
  }
}

async function confirmQuery(msg) {
  const td = msg.tool_data
  try {
    ElMessage.info('正在执行查询...')
    window.dispatchEvent(new CustomEvent('navigate-to-query', { detail: { script_id: td.script_id } }))
    dismissTool(msg)
  } catch (e) {
    ElMessage.error('查询执行失败: ' + (e.message || '未知错误'))
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
  flex-wrap: wrap;
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

.message-content.full-width {
  max-width: 100%;
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

/* ===== File Card Styles ===== */
.file-card {
  background: #fff;
  border: 2px solid #67c23a;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(103, 194, 58, 0.15);
  max-width: 480px;
}

.file-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #f0f9eb, #f5fcf0);
  border-bottom: 1px solid #d9f0be;
}

.file-icon {
  font-size: 16px;
  color: #67c23a;
}

.file-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.file-card-body {
  padding: 10px 14px;
}

.file-info-row {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
  margin-bottom: 8px;
}

.file-info-row i {
  margin-right: 4px;
  color: #909399;
}

.file-columns {
  display: flex;
  flex-wrap: wrap;
}

/* ===== Tool Card Styles ===== */
.tool-card {
  background: #fff;
  border: 2px solid #409eff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  max-width: 500px;
}

.tool-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #ecf5ff, #f0f7ff);
  border-bottom: 1px solid #d9ecff;
}

.tool-icon {
  font-size: 16px;
  color: #409eff;
}

.tool-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.tool-card-body {
  padding: 14px 16px;
}

.tool-confirm-msg {
  font-size: 13px;
  color: #606266;
  margin: 0 0 8px;
  line-height: 1.6;
}

.tool-warning {
  font-size: 12px;
  color: #e6a23c;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  background: #fdf6ec;
  padding: 6px 10px;
  border-radius: 6px;
}

.tool-card-actions {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  background: #fafbfc;
  border-top: 1px solid #eef2f7;
}

/* ===== Input Area ===== */
.input-area {
  padding: 12px 24px 16px;
  border-top: 1px solid #eef2f7;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-attachment {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f9eb;
  border: 1px solid #d9f0be;
  border-radius: 8px;
  font-size: 12px;
  color: #606266;
  align-self: flex-start;
}

.file-attachment > i:first-child {
  color: #67c23a;
  font-size: 14px;
}

.file-name {
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-info {
  color: #909399;
}

.file-remove {
  cursor: pointer;
  color: #c0c4cc;
  transition: color 0.2s;
}

.file-remove:hover {
  color: #f56c6c;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-row :deep(.el-textarea__inner) {
  border-radius: 8px;
  flex: 1;
}

.input-buttons {
  display: flex;
  gap: 6px;
  align-items: center;
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
</style>
