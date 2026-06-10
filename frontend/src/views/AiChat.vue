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
          <el-dropdown v-if="isAdmin" trigger="click" class="chat-item-del" @command="(cmd) => handleDeleteCommand(cmd, chat.id)">
            <el-button type="danger" text size="small" @click.stop>
              <i class="fas fa-trash"></i>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="soft">删除对话</el-dropdown-item>
                <el-dropdown-item command="hard">永久删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button v-else type="danger" text size="small" class="chat-item-del" @click.stop="deleteChat(chat.id)">
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
          <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role" @mouseenter="msg._showActions = true" @mouseleave="msg._showActions = false">
            <div class="message-avatar">
              <i :class="msg.role === 'user' ? 'fas fa-user' : 'fas fa-robot'"></i>
            </div>
            <div class="message-content" :class="{ 'full-width': msg._type === 'tool' || msg._type === 'file' }">
              <!-- 删除按钮（悬浮显示，执行中的任务不显示删除按钮） -->
              <div class="message-actions" v-show="msg._showActions && !msg._executing">
                <el-dropdown v-if="isAdmin" trigger="click" @command="(cmd) => handleMsgDelete(cmd, msg)">
                  <el-button text size="small" class="msg-action-btn" @click.stop>
                    <i class="fas fa-trash"></i>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="soft">删除消息</el-dropdown-item>
                      <el-dropdown-item command="hard" divided>
                        <span style="color: #f56c6c">永久删除</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-button v-else text size="small" class="msg-action-btn" @click="softDeleteMessage(msg)">
                  <i class="fas fa-trash"></i>
                </el-button>
              </div>
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
              <!-- 选项选择卡片 -->
              <template v-else-if="msg._type === 'select_options'">
                <div class="tool-card select-card" :class="{ ignored: msg._ignored, done: msg._done, executing: msg._executing }">
                  <div class="tool-card-header">
                    <i v-if="msg._ignored" class="fas fa-ban tool-icon tool-icon-error"></i>
                    <i v-else-if="msg._executing" class="fas fa-spinner fa-spin tool-icon"></i>
                    <i v-else-if="msg._done" class="fas fa-check-circle tool-icon tool-icon-success"></i>
                    <i v-else-if="msg._failed" class="fas fa-times-circle tool-icon tool-icon-error"></i>
                    <i v-else class="fas fa-list-check tool-icon"></i>
                    <span class="tool-title">
                      <template v-if="msg._ignored">已忽略</template>
                      <template v-else-if="msg._executing">正在执行...</template>
                      <template v-else-if="msg._done">执行成功</template>
                      <template v-else-if="msg._failed">执行失败</template>
                      <template v-else-if="msg._action_type === 'export'">可选导出任务</template>
                      <template v-else>可选查询任务</template>
                    </span>
                  </div>
                  <div class="tool-card-body">
                    <p class="tool-confirm-msg">{{ msg.content }}</p>

                    <!-- 执行进度条 -->
                    <div v-if="msg._executing" class="tool-progress-info">
                      <el-progress :percentage="msg._progress || 0" :stroke-width="6" />
                      <span class="tool-progress-text">{{ msg._status_text || '正在初始化...' }}</span>
                    </div>

                    <!-- 执行完成下载链接 -->
                    <div v-if="msg._done && msg._download_url" class="tool-download-link">
                      <el-button type="success" size="small" @click="downloadFile(msg._download_url)">
                        <i class="fas fa-download"></i> 下载文件
                      </el-button>
                    </div>

                    <!-- 执行失败错误 -->
                    <div v-if="msg._failed && msg._error_msg" class="tool-error-msg">
                      <i class="fas fa-exclamation-circle"></i>
                      <span class="error-msg-content">
                        <span class="error-msg-text">{{ msg._error_msg }}</span>
                        <span v-if="msg._ai_suggestion" class="error-ai-suggestion">
                          <i class="fas fa-lightbulb"></i> {{ msg._ai_suggestion }}
                        </span>
                      </span>
                    </div>

                    <div v-if="!msg._executing && !msg._done" class="select-options-list">
                      <label v-for="s in msg._scripts" :key="s.id" class="select-option-item">
                        <input type="checkbox" :value="s.id" v-model="msg._selected" :disabled="msg._ignored || msg._executing" @change="onSelectionChange(msg)" />
                        <div class="select-option-detail">
                          <span class="select-option-name">{{ s.name }}</span>
                          <span v-if="s.description" class="select-option-desc">{{ s.description }}</span>
                          <!-- 显示参数信息 -->
                          <div v-if="s.params && s.params.length > 0" class="select-option-params">
                            <el-tag v-for="p in s.params" :key="p.name" size="small" :type="p.required ? 'danger' : 'info'" effect="plain" style="margin: 2px 4px 2px 0">
                              {{ p.label || p.name }}{{ p.required ? '*' : '' }}
                            </el-tag>
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>
                  <div class="tool-card-actions">
                    <el-button
                      type="primary" size="small"
                      @click="executeSelectedOptions(msg)"
                      :disabled="msg._ignored || msg._selected.length === 0 || msg._executing || !canExecute(msg)"
                      :loading="msg._executing"
                    >
                      <template v-if="msg._ignored">已忽略</template>
                      <template v-else-if="msg._executing">正在执行...</template>
                      <template v-else-if="msg._failed">重新执行 ({{ msg._selected.length }})</template>
                      <template v-else>确认执行所选 ({{ msg._selected.length }})</template>
                    </el-button>
                    <el-button
                      v-if="msg._done && msg._download_url"
                      type="success" size="small"
                      @click="downloadFile(msg._download_url)"
                    >
                      <i class="fas fa-download"></i> 下载文件
                    </el-button>
                    <el-button size="small" text @click="dismissTool(msg)" :disabled="msg._ignored || msg._executing" v-if="!msg._executing">{{ msg._ignored ? '已忽略' : '忽略' }}</el-button>
                  </div>
                </div>
              </template>
              <!-- 参数确认消息（带操作按钮） -->
              <template v-else-if="msg._type === 'param_confirm'">
                <div class="param-confirm-card">
                  <div class="param-confirm-body">
                    <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
                  </div>
                  <div class="param-confirm-actions">
                    <el-button type="primary" size="small" @click="confirmParamAll(msg)">
                      <i class="fas fa-check"></i> 确认全部不筛选
                    </el-button>
                    <el-button size="small" @click="cancelParamConfirm(msg)">
                      取消
                    </el-button>
                  </div>
                </div>
              </template>
              <!-- 普通文本消息 -->
              <template v-else-if="msg._type !== 'tool'">
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </template>
              <!-- 工具调用确认卡片 -->
              <template v-else-if="!msg._dismissed">
                <div class="tool-card" :class="msg._executing ? 'executing' : (msg._done ? 'done' : (msg._failed ? 'failed' : ''))">
                  <div class="tool-card-header">
                    <i v-if="msg._executing" class="fas fa-spinner fa-spin tool-icon"></i>
                    <i v-else-if="msg._done" class="fas fa-check-circle tool-icon tool-icon-success"></i>
                    <i v-else-if="msg._failed" class="fas fa-times-circle tool-icon tool-icon-error"></i>
                    <i v-else class="fas fa-magic tool-icon"></i>
                    <span class="tool-title">
                      <template v-if="msg._executing">任务执行中...</template>
                      <template v-else-if="msg._done">执行成功</template>
                      <template v-else-if="msg._failed">执行失败</template>
                      <template v-else>{{ msg.tool_data.action_type === 'export' ? '导出任务确认' : '查询任务确认' }}</template>
                    </span>
                  </div>
                  <div class="tool-card-body">
                    <p class="tool-confirm-msg">{{ msg.tool_data.confirm_message }}</p>
                    <p v-if="msg._executing" class="tool-progress-info">
                      <el-progress :percentage="msg._progress || 0" :stroke-width="6" />
                      <span class="tool-progress-text">{{ msg._status_text || '正在初始化...' }}</span>
                    </p>
                    <p v-if="msg._done && msg._download_url" class="tool-download-link">
                      <a :href="msg._download_url" target="_blank" download>
                        <i class="fas fa-download"></i> 点击下载文件
                      </a>
                    </p>
                    <p v-if="msg._failed && msg._error_msg" class="tool-error-msg">
                      <i class="fas fa-exclamation-circle"></i>
                      <span class="error-msg-content">
                        <span class="error-msg-text">{{ msg._error_msg }}</span>
                        <span v-if="msg._ai_suggestion" class="error-ai-suggestion">
                          <i class="fas fa-lightbulb"></i> {{ msg._ai_suggestion }}
                        </span>
                      </span>
                    </p>
                    <p v-if="msg.tool_data.required_missing && msg.tool_data.required_missing.length && !msg._executing && !msg._done" class="tool-warning">
                      <i class="fas fa-exclamation-triangle"></i> 缺少必填参数：{{ msg.tool_data.required_missing.join(', ') }}
                    </p>
                  </div>
                  <div class="tool-card-actions">
                    <el-button
                      v-if="msg.tool_data.action_type === 'export' && !msg._executing && !msg._done && !msg._failed"
                      type="primary"
                      size="small"
                      @click="confirmExport(msg)"
                      :disabled="msg._ignored || (msg.tool_data.required_missing && msg.tool_data.required_missing.length > 0)"
                    >
                      <i class="fas fa-play"></i> <template v-if="msg._ignored">已忽略</template><template v-else>确认执行导出</template>
                    </el-button>
                    <el-button
                      v-if="msg._done && msg._download_url"
                      type="success"
                      size="small"
                      @click="downloadFile(msg._download_url)"
                    >
                      <i class="fas fa-download"></i> 下载文件
                    </el-button>
                    <el-button
                      v-if="msg.tool_data.action_type === 'query' && !msg._executing && !msg._done && !msg._failed && !msg._ignored"
                      type="primary"
                      size="small"
                      @click="confirmQuery(msg)"
                    >
                      <i class="fas fa-play"></i> 确认执行查询
                    </el-button>
                    <el-button
                      v-if="!msg._ignored && !msg._executing"
                      size="small" text @click="dismissTool(msg)">
                      {{ msg._done || msg._failed ? '关闭' : '忽略' }}
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
import { ref, onMounted, nextTick, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAppStore } from '../stores'
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
const store = useAppStore()
const isAdmin = computed(() => store.isAdmin)

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
    messages.value = msgs.map(m => {
      const base = { ...m, _dismissed: false }
      // 恢复工具卡片状态
      if (m._metadata) {
        const meta = m._metadata
        if (meta._type === 'tool') {
          base._type = 'tool'
          base.tool_data = meta.tool_data
        } else if (meta._type === 'select_options') {
        base._type = 'select_options'
        base._select_mode = meta._select_mode
        base._scripts = meta.scripts || []
        base._selected = []
        base._action_type = meta.action_type || ''
        base._params_checked = false
        base._param_values = {}
        base._all_checked = {}
        base._selectedScripts = []
        base._missing_required_params = []
      }
        // 恢复执行状态
        if (meta._executing) base._executing = true
        if (meta._done) base._done = true
        if (meta._failed) base._failed = true
        if (meta._ignored) base._ignored = true
        if (meta._progress != null) base._progress = meta._progress
        if (meta._status_text) base._status_text = meta._status_text
        if (meta._download_url) base._download_url = meta._download_url
        if (meta._error_msg) base._error_msg = meta._error_msg
        if (meta._ai_suggestion) base._ai_suggestion = meta._ai_suggestion
      }
      return base
    })
    await nextTick()
    scrollToBottom()
  } catch {}
}

async function deleteChat(chatId) {
  try {
    await ElMessageBox.confirm(
      '删除对话后，消息记录将不再显示，但管理员可在后台恢复。确定要删除吗？',
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.ai.deleteChat(chatId)
    chats.value = chats.value.filter(c => c.id !== chatId)
    if (currentChatId.value === chatId) {
      currentChatId.value = null
      messages.value = []
    }
  } catch {}
}

async function softDeleteMessage(msg) {
  try {
    await ElMessageBox.confirm(
      '确定要删除此消息吗？',
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.ai.deleteMessage(currentChatId.value, msg.id)
    messages.value = messages.value.filter(m => m.id !== msg.id)
    ElMessage.success('已删除')
  } catch {}
}

async function hardDeleteMessage(msg) {
  try {
    await ElMessageBox.confirm(
      '永久删除后将无法恢复，确定要永久删除此消息吗？',
      '永久删除确认',
      { confirmButtonText: '永久删除', cancelButtonText: '取消', type: 'error' }
    )
    await api.ai.hardDeleteMessage(currentChatId.value, msg.id)
    messages.value = messages.value.filter(m => m.id !== msg.id)
    ElMessage.success('已永久删除')
  } catch {}
}

function handleMsgDelete(cmd, msg) {
  if (cmd === 'soft') {
    softDeleteMessage(msg)
  } else if (cmd === 'hard') {
    hardDeleteMessage(msg)
  }
}

function handleDeleteCommand(cmd, chatId) {
  if (cmd === 'soft') {
    deleteChat(chatId)
  } else if (cmd === 'hard') {
    hardDeleteChat(chatId)
  }
}

async function hardDeleteChat(chatId) {
  try {
    await ElMessageBox.confirm(
      '此操作将永久删除该对话及其所有消息记录，不可恢复！确定要永久删除吗？',
      '永久删除确认',
      { confirmButtonText: '永久删除', cancelButtonText: '取消', type: 'error' }
    )
    await api.ai.hardDeleteChat(chatId)
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

  // 检查是否有等待参数的select_options卡片，尝试将用户输入解析为参数值
  const pendingCard = messages.value.find(m =>
    m._type === 'select_options' && !m._executing && !m._done && !m._ignored
    && m._selectedScripts && m._selectedScripts.length > 0
    && hasMissingRequiredNoAllParams(m)
  )
  if (pendingCard && !uploadedFile.value) {
    const parsed = tryParseParamValues(text, pendingCard)
    if (parsed) {
      // 成功解析参数，填充到卡片中并执行
      Object.assign(pendingCard._param_values, parsed)
      // 检查是否还有缺失的必填参数
      const stillMissing = getMissingRequiredNoAllParams(pendingCard)
      if (stillMissing.length === 0) {
        // 所有必填参数已填写，添加用户消息后自动执行
        const userMsg = { id: Date.now(), role: 'user', content: text }
        messages.value.push(userMsg)
        inputText.value = ''
        await nextTick()
        scrollToBottom()

        // 检查是否还有allow_all参数需要确认
        const hasAllowAllParams = getAllowAllParamsNeedConfirm(pendingCard)
        if (hasAllowAllParams.length > 0 && !pendingCard._params_checked) {
          const paramList = hasAllowAllParams.map(p => p.label).join('、')
          const confirmContent = `📋 已收到必填参数。当前以下参数将使用 **全部不筛选**：\n\n${hasAllowAllParams.map(p => `- ${p.label}`).join('\n')}\n\n请确认是否继续？`
          let msgId = Date.now() + 1
          try {
            const res = await api.ai.createMessage(currentChatId.value, { content: confirmContent })
            msgId = res.data?.id || msgId
          } catch {}
          messages.value.push({
            id: msgId,
            role: 'assistant',
            content: confirmContent,
            _type: 'param_confirm',
            _pending_card_id: pendingCard.id,
            _confirm_action: 'all_checked',
          })
          await nextTick()
          scrollToBottom()
          return
        }

        // 直接执行
        doExecuteExport(pendingCard)
        return
      } else {
        // 还有缺失参数，提示用户继续补充
        const userMsg = { id: Date.now(), role: 'user', content: text }
        messages.value.push(userMsg)
        inputText.value = ''

        const stillMissingList = stillMissing.map(p => `**${p.label}**`).join('、')
        const replyContent = `已收到部分参数，还需要以下必填参数：\n\n${stillMissing.map(p => `- ${p.label}（必填）`).join('\n')}\n\n请继续提供。`
        let replyId = Date.now() + 1
        try {
          const res = await api.ai.createMessage(currentChatId.value, { content: replyContent })
          replyId = res.data?.id || replyId
        } catch {}
        messages.value.push({
          id: replyId,
          role: 'assistant',
          content: replyContent,
        })
        await nextTick()
        scrollToBottom()
        return
      }
    }
    // 解析失败，走正常的AI对话流程
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
            id: tr.message_id || Date.now() + Math.random(),
            role: 'assistant',
            content: '',
            _type: 'tool',
            _dismissed: false,
            tool_data: result,
          })
        } else if (result && result._select_mode) {
          // 选项选择卡片：列出多个/全部选项供用户勾选
          messages.value.push({
            id: tr.message_id || Date.now() + Math.random(),
            role: 'assistant',
            content: result.message || '',
            _type: 'select_options',
            _select_mode: result._select_mode,
            _scripts: result.scripts || [],
            _action_type: result.scripts && result.scripts.length > 0 ? (tr.name === 'list_export_options' ? 'export' : 'query') : '',
            _selected: [],
            _params_checked: false,
            _param_values: {},
            _all_checked: {},
            _selectedScripts: [],
            _missing_required_params: [],
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
  msg._ignored = true
  saveMessageState(msg)
}

// 保存工具卡片状态到数据库
async function saveMessageState(msg) {
  if (!msg.id || !currentChatId.value) return
  const metadata = {}
  if (msg._executing) metadata._executing = true
  if (msg._done) metadata._done = true
  if (msg._failed) metadata._failed = true
  if (msg._ignored) metadata._ignored = true
  if (msg._progress != null) metadata._progress = msg._progress
  if (msg._status_text) metadata._status_text = msg._status_text
  if (msg._download_url) metadata._download_url = msg._download_url
  if (msg._error_msg) metadata._error_msg = msg._error_msg
  if (msg._ai_suggestion) metadata._ai_suggestion = msg._ai_suggestion
  if (Object.keys(metadata).length > 0) {
    try {
      await api.ai.updateMessage(currentChatId.value, msg.id, { metadata })
    } catch {}
  }
}

async function executeSelectedOptions(msg) {
  const selectedIds = msg._selected
  if (!selectedIds || selectedIds.length === 0) {
    ElMessage.warning('请至少选择一个选项')
    return
  }

  // 更新选中脚本
  msg._selectedScripts = msg._scripts.filter(s => selectedIds.includes(s.id)) || []

  // 检查是否有未允许全部且必填的参数未填写 → 不能执行，发送消息提示
  const missingRequiredNoAll = getMissingRequiredNoAllParams(msg)
  if (missingRequiredNoAll.length > 0) {
    // 发送AI消息提示用户补充必填参数
    const paramList = missingRequiredNoAll.map(p => `**${p.label}**`).join('、')
    const content = `⚠️ 执行导出任务需要以下必填参数，请在对话中提供参数值：\n\n${missingRequiredNoAll.map(p => `- ${p.label}（必填）`).join('\n')}\n\n例如回复："${missingRequiredNoAll.map(p => p.label + ': xxx').join('，')}"`

    let msgId = Date.now()
    try {
      const res = await api.ai.createMessage(currentChatId.value, { content })
      msgId = res.data?.id || msgId
    } catch {}
    messages.value.push({
      id: msgId,
      role: 'assistant',
      content,
    })
    await nextTick()
    scrollToBottom()
    return
  }

  // 检查是否有允许全部的参数未确认 → 发送确认消息
  const hasAllowAllParams = getAllowAllParamsNeedConfirm(msg)
  if (hasAllowAllParams.length > 0 && !msg._params_checked) {
    const paramList = hasAllowAllParams.map(p => p.label).join('、')
    const content = `📋 当前以下参数将使用 **全部不筛选**：\n\n${hasAllowAllParams.map(p => `- ${p.label}`).join('\n')}\n\n请确认是否继续？`

    let msgId = Date.now()
    try {
      const res = await api.ai.createMessage(currentChatId.value, { content })
      msgId = res.data?.id || msgId
    } catch {}
    messages.value.push({
      id: msgId,
      role: 'assistant',
      content,
      _type: 'param_confirm',
      _pending_card_id: msg.id,
      _confirm_action: 'all_checked',
    })
    await nextTick()
    scrollToBottom()
    return
  }

  // 所有参数已确认，执行任务
  doExecuteExport(msg)
}

// 获取需要确认的"允许全部"参数列表
function getAllowAllParamsNeedConfirm(msg) {
  const params = []
  const selectedScripts = msg._selectedScripts || []
  const paramValues = msg._param_values || {}
  const allChecked = msg._all_checked || {}

  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (!p.allow_all) continue
      const key = script.id + '_' + p.name
      const val = paramValues[key]
      // 已有值或已勾选全部的不需要确认
      if ((val && val.trim() !== '') || allChecked[key]) continue
      params.push({
        key,
        label: (script.name ? script.name + ' - ' : '') + (p.label || p.name),
        scriptId: script.id,
        paramName: p.name
      })
    }
  }
  return params
}

// 实际执行导出任务
async function doExecuteExport(msg) {
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在初始化任务...'
  msg._done = false
  msg._failed = false
  msg._error_msg = ''
  msg._download_url = ''
  msg._missing_required_params = []

  try {
    // 构建参数
    const paramsValues = msg._param_values || {}
    const allChecked = msg._all_checked || {}

    const res = await api.export.execute({
      script_ids: msg._selected,
      params_values: paramsValues,
      all_checked: allChecked,
      output_format: 'sheets',
    })
    if (!res.task_id) {
      throw new Error('未获取到任务ID')
    }
    const taskId = res.task_id
    await pollTaskStatus(taskId, msg)
  } catch (e) {
    msg._executing = false
    msg._failed = true
    msg._error_msg = e.message || '未知错误'
    saveMessageState(msg)
    await nextTick()
    scrollToBottom()
  }
}

// 检查选中的脚本是否有必填参数未填写
function checkMissingRequiredParams(msg) {
  const missing = []
  const selectedScripts = msg._selectedScripts || []
  const paramValues = msg._param_values || {}
  const allChecked = msg._all_checked || {}

  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (!p.required) continue
      if (p.allow_all && allChecked[script.id + '_' + p.name]) continue
      const val = paramValues[script.id + '_' + p.name]
      if (!val || val.trim() === '') {
        const label = (script.name ? script.name + ' - ' : '') + (p.label || p.name)
        missing.push(label)
      }
    }
  }
  return missing
}

// 检查是否有未允许全部且必填的参数未填写（阻止执行的核心检查）
function hasMissingRequiredNoAllParams(msg) {
  const selectedScripts = msg._selectedScripts || []
  const paramValues = msg._param_values || {}
  const allChecked = msg._all_checked || {}

  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (!p.required) continue
      if (p.allow_all) continue // 允许全部的跳过（可以勾选全部不筛选）
      const val = paramValues[script.id + '_' + p.name]
      if (!val || val.trim() === '') {
        return true
      }
    }
  }
  return false
}

// 获取未允许全部且必填的参数列表（用于显示输入框）
function getMissingRequiredNoAllParams(msg) {
  const missing = []
  const selectedScripts = msg._selectedScripts || []
  const paramValues = msg._param_values || {}

  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (!p.required) continue
      if (p.allow_all) continue // 允许全部的跳过
      const key = script.id + '_' + p.name
      const val = paramValues[key]
      if (!val || val.trim() === '') {
        missing.push({
          key,
          label: (script.name ? script.name + ' - ' : '') + (p.label || p.name)
        })
      }
    }
  }
  return missing
}

// 判断是否有任何必填参数（只检查已勾选的脚本）
function hasAnyRequiredParams(msg) {
  const selectedIds = msg._selected || []
  for (const s of msg._scripts) {
    if (!selectedIds.includes(s.id)) continue
    if (!s.params) continue
    for (const p of s.params) {
      if (p.required) return true
    }
  }
  return false
}

// 判断是否可以执行（点击执行按钮后由消息互动引导参数，按钮本身只需检查是否有选中）
function canExecute(msg) {
  if (msg._executing || msg._done || msg._ignored) return false
  if (msg._selected.length === 0) return false
  return true
}

// 参数输入框值变化时的处理（已废弃，保留兼容）
function onParamInputChange(msg) {
  msg._missing_required_params = []
}

// 确认参数全部不筛选
async function confirmParamAll(msg) {
  const cardId = msg._pending_card_id
  if (!cardId) return

  // 找到对应的卡片消息
  const card = messages.value.find(m => m.id === cardId)
  if (!card) {
    ElMessage.warning('关联的任务卡片已不存在')
    return
  }

  // 将所有允许全部的参数标记为全部不筛选
  const selectedScripts = card._selectedScripts || []
  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (p.allow_all) {
        card._all_checked[script.id + '_' + p.name] = true
      }
    }
  }
  card._params_checked = true

  // 移除确认消息
  messages.value = messages.value.filter(m => m.id !== msg.id)

  // 执行任务
  await nextTick()
  doExecuteExport(card)
}

// 取消参数确认
function cancelParamConfirm(msg) {
  // 移除确认消息
  messages.value = messages.value.filter(m => m.id !== msg.id)
  ElMessage.info('已取消执行')
}

// 尝试将用户输入的文本解析为参数值
function tryParseParamValues(text, msg) {
  const selectedScripts = msg._selectedScripts || []
  const paramValues = msg._param_values || {}
  const allChecked = msg._all_checked || {}
  const parsed = {}
  let matched = false

  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      const key = script.id + '_' + p.name
      // 跳过已有值的参数
      if (paramValues[key] && paramValues[key].trim() !== '') continue
      if (allChecked[key]) continue

      const label = p.label || p.name
      const paramName = p.name

      // 尝试多种格式匹配：
      // 1. "参数名: 值" 或 "参数名：值"
      // 2. "标签: 值" 或 "标签：值"
      // 3. "参数名=值"
      const patterns = [
        new RegExp(`${paramName}\\s*[:：=]\\s*(.+?)(?:[,，;；\\n]|$)`, 'i'),
        new RegExp(`${label}\\s*[:：=]\\s*(.+?)(?:[,，;；\\n]|$)`, 'i'),
      ]

      for (const pattern of patterns) {
        const match = text.match(pattern)
        if (match && match[1] && match[1].trim()) {
          parsed[key] = match[1].trim()
          matched = true
          break
        }
      }
    }
  }

  return matched ? parsed : null
}

// 选择变化时更新选中的脚本详情
function onSelectionChange(msg) {
  const selectedIds = msg._selected || []
  msg._selectedScripts = msg._scripts.filter(s => selectedIds.includes(s.id)) || []
  // 清除之前的必填参数缺失提示
  msg._missing_required_params = []
  // 重置参数确认状态：有必填参数时不显示"全部不筛选"确认提醒
  msg._params_checked = false
}

async function confirmExport(msg) {
  const td = msg.tool_data
  const params = { ...td.params }
  const allChecked = td.all_checked || {}

  // Set executing state
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在初始化任务...'
  msg._done = false
  msg._failed = false

  try {
    const res = await api.export.execute({
      script_ids: [td.script_id],
      params_values: params,
      all_checked: allChecked,
      output_format: td.output_format || 'sheets',
    })
    if (!res.task_id) {
      throw new Error('未获取到任务ID')
    }

    const taskId = res.task_id
    msg._status_text = '任务已提交，正在执行...'

    // Poll task status
    await pollTaskStatus(taskId, msg)
  } catch (e) {
    msg._executing = false
    msg._failed = true
    msg._error_msg = e.message || '未知错误'
    ElMessage.error('导出执行失败: ' + msg._error_msg)
  }
}

function pollTaskStatus(taskId, msg) {
  const statusTextMap = {
    pending: '任务等待中...',
    running: '正在执行导出...',
    completed: '执行完成',
    failed: '执行失败',
    cancelled: '已取消',
  }

  return new Promise((resolve) => {
    let pollCount = 0
    const maxPolls = 300 // max 5 minutes at 1s interval
    const poll = async () => {
      try {
        pollCount++
        if (pollCount > maxPolls) {
          msg._executing = false
          msg._failed = true
          msg._error_msg = '任务执行超时'
          msg._status_text = '执行超时'
          resolve()
          return
        }

        const res = await api.export.status(taskId)
        const task = res.data
        if (!task) {
          // Task not found yet (still initializing), wait and retry
          setTimeout(poll, 2000)
          return
        }

        msg._progress = task.progress || 0
        msg._status_text = statusTextMap[task.status] || '执行中...'

        if (task.status === 'completed') {
          msg._executing = false
          msg._done = true
          msg._progress = 100

          // 检查是否有输出文件（未查询到数据时 output_file 为 null）
          if (task.output_file) {
            msg._download_url = `/api/download/${taskId}`
            msg._status_text = '执行完成'

            // 持久化状态
            saveMessageState(msg)

            // 弹出下载确认
            ElMessageBox.confirm(
              '导出任务已完成，是否立即下载文件？',
              '下载确认',
              { confirmButtonText: '立即下载', cancelButtonText: '稍后下载', type: 'success' }
            ).then(() => {
              downloadFile(msg._download_url)
            }).catch(() => {})

            // 保存反馈消息到数据库
            const scriptNames = msg._selectedScripts
              ? msg._selectedScripts.map(s => s.name).join('、')
              : (msg.tool_data?.script_name || '未知任务')
            const feedbackContent = `✅ 导出任务 **${scriptNames}** 已完成！\n\n- 任务ID：\`${taskId}\`\n- 输出格式：${msg.tool_data?.output_format || 'sheets'}\n\n你可以点击上方卡片中的按钮下载文件，或前往导出任务列表查看历史记录。`
            let feedbackId = Date.now()
            try {
              const fbRes = await api.ai.createMessage(currentChatId.value, { content: feedbackContent })
              feedbackId = fbRes.data?.id || feedbackId
            } catch {}
            messages.value.push({
              id: feedbackId,
              role: 'assistant',
              content: feedbackContent,
            })
          } else {
            // 未查询到数据，任务完成但无输出文件
            msg._status_text = '执行完成（无数据）'
            saveMessageState(msg)

            const scriptNames = msg._selectedScripts
              ? msg._selectedScripts.map(s => s.name).join('、')
              : (msg.tool_data?.script_name || '未知任务')
            const noDataContent = `⚠️ 导出任务 **${scriptNames}** 已执行完成，但 **未查询到任何数据**，未生成结果文件。

请检查筛选参数是否正确，或前往执行历史查看详细日志。`
            let noDataId = Date.now()
            try {
              const fbRes = await api.ai.createMessage(currentChatId.value, { content: noDataContent })
              noDataId = fbRes.data?.id || noDataId
            } catch {}
            messages.value.push({
              id: noDataId,
              role: 'assistant',
              content: noDataContent,
            })
          }
          await nextTick()
          scrollToBottom()
          resolve()
          return
        }

        if (task.status === 'failed') {
          msg._executing = false
          msg._failed = true
          msg._error_msg = task.error_message || '执行失败'
          msg._ai_suggestion = task.ai_suggestion || null
          msg._status_text = '执行失败'

          // 持久化状态
          saveMessageState(msg)

          // 保存反馈消息到数据库
          const scriptNames = msg._selectedScripts
            ? msg._selectedScripts.map(s => s.name).join('、')
            : (msg.tool_data?.script_name || '未知任务')
          let failContent = `❌ 导出任务执行失败：**${scriptNames}**`
          failContent += `\n\n**错误信息：** ${msg._error_msg}`
          if (msg._ai_suggestion) {
            failContent += `\n\n**AI修正建议：**\n${msg._ai_suggestion}`
          }
          let failId = Date.now()
          try {
            const fbRes = await api.ai.createMessage(currentChatId.value, { content: failContent })
            failId = fbRes.data?.id || failId
          } catch {}
          messages.value.push({
            id: failId,
            role: 'assistant',
            content: failContent,
          })
          await nextTick()
          scrollToBottom()
          resolve()
          return
        }

        // Still running, poll again
        setTimeout(poll, 1500)
      } catch (e) {
        msg._executing = false
        msg._failed = true
        msg._error_msg = '轮询任务状态失败: ' + (e.message || '未知错误')
        msg._status_text = '轮询失败'
        saveMessageState(msg)
        await nextTick()
        scrollToBottom()
        resolve()
      }
    }
    poll()
  })
}

function downloadFile(url) {
  window.open(url, '_blank')
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
  position: relative;
}

.message-content.full-width {
  max-width: 100%;
}

/* 消息操作按钮（悬浮显示） */
.message-actions {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 10;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.message-actions:hover {
  opacity: 1;
}

.msg-action-btn {
  color: #909399;
  padding: 2px 4px;
  font-size: 12px;
  min-height: auto;
}

.msg-action-btn:hover {
  color: #f56c6c;
}

.message.user .message-actions {
  right: 8px;
  top: 8px;
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

/* Tool Card States */
.tool-card.executing {
  border-color: #e6a23c;
  box-shadow: 0 2px 12px rgba(230, 162, 60, 0.2);
}

.tool-card.executing .tool-card-header {
  background: linear-gradient(135deg, #fdf6ec, #fcf5e0);
  border-bottom-color: #f0d9a6;
}

.tool-card.executing .tool-icon {
  color: #e6a23c;
}

.tool-card.done {
  border-color: #67c23a;
  box-shadow: 0 2px 12px rgba(103, 194, 58, 0.2);
}

.tool-card.done .tool-card-header {
  background: linear-gradient(135deg, #f0f9eb, #e5f7d5);
  border-bottom-color: #c2e09a;
}

.tool-card.done .tool-icon {
  color: #67c23a;
}

.tool-icon-success {
  color: #67c23a !important;
}

.tool-icon-error {
  color: #f56c6c !important;
}

.tool-card.failed {
  border-color: #f56c6c;
  box-shadow: 0 2px 12px rgba(245, 108, 108, 0.2);
}

.tool-card.failed .tool-card-header {
  background: linear-gradient(135deg, #fef0f0, #fde8e8);
  border-bottom-color: #f5c6c6;
}

.tool-card.failed .tool-icon {
  color: #f56c6c;
}

.tool-progress-info {
  margin: 0;
}

.tool-progress-text {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  display: block;
}

.tool-download-link {
  margin: 8px 0 0;
  display: flex;
  align-items: center;
}

.tool-download-link a {
  color: #409eff;
  text-decoration: none;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tool-download-link a:hover {
  text-decoration: underline;
}

.tool-error-msg {
  font-size: 12px;
  color: #f56c6c;
  margin: 0;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  background: #fef0f0;
  padding: 8px 12px;
  border-radius: 6px;
  flex-direction: column;
}

.error-msg-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.error-msg-text {
  line-height: 1.5;
}

.error-ai-suggestion {
  color: #409eff;
  background: #ecf5ff;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.error-ai-suggestion i {
  margin-top: 2px;
  flex-shrink: 0;
}

/* ===== Select Card Styles ===== */
.tool-card.select-card {
  border-color: #e6a23c;
  box-shadow: 0 2px 12px rgba(230, 162, 60, 0.15);
  max-width: 600px;
}

.tool-card.select-card .tool-card-header {
  background: linear-gradient(135deg, #fdf6ec, #fcf5e0);
  border-bottom-color: #f0d9a6;
}

.tool-card.select-card .tool-icon {
  color: #e6a23c;
}

/* 已忽略状态 */
.tool-card.select-card.ignored {
  border-color: #c0c4cc;
  box-shadow: none;
  opacity: 0.65;
}

.tool-card.select-card.ignored .tool-card-header {
  background: linear-gradient(135deg, #f5f7fa, #edf0f5);
  border-bottom-color: #dcdfe6;
}

.tool-card.select-card.ignored .tool-icon {
  color: #c0c4cc !important;
}

.tool-card.select-card.ignored .select-option-item {
  cursor: not-allowed;
  opacity: 0.5;
  pointer-events: none;
}

.select-options-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0;
  max-height: 400px;
  overflow-y: auto;
}

.select-option-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.select-option-item:hover {
  background: #ecf5ff;
  border-color: #b3d8ff;
}

.select-option-item input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--primary-color, #409eff);
  flex-shrink: 0;
  margin-top: 2px;
}

.select-option-name {
  font-weight: 500;
  font-size: 13px;
  color: #303133;
  flex: 1;
}

.select-option-desc {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select-option-detail {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  gap: 4px;
}

.select-option-params {
  display: flex;
  flex-wrap: wrap;
  margin-top: 4px;
}

/* 执行中状态 */
.tool-card.select-card.executing {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
}

.tool-card.select-card.executing .tool-card-header {
  background: linear-gradient(135deg, #ecf5ff, #e1eeff);
  border-bottom-color: #b3d8ff;
}

.tool-card.select-card.executing .select-options-list {
  pointer-events: none;
  opacity: 0.5;
}

/* 执行完成状态 */
.tool-card.select-card.done {
  border-color: #67c23a;
  box-shadow: 0 2px 12px rgba(103, 194, 58, 0.15);
}

.tool-card.select-card.done .tool-card-header {
  background: linear-gradient(135deg, #f0f9eb, #e7f8dc);
  border-bottom-color: #c2e7b0;
}

.tool-card.select-card.done .tool-icon {
  color: #67c23a !important;
}

.tool-card.select-card.done .select-options-list {
  pointer-events: none;
  opacity: 0.4;
}

/* 执行失败状态 */
.tool-card.select-card.failed {
  border-color: #f56c6c;
  box-shadow: 0 2px 12px rgba(245, 108, 108, 0.15);
}

.tool-card.select-card.failed .tool-card-header {
  background: linear-gradient(135deg, #fef0f0, #fde2e2);
  border-bottom-color: #fbc4c4;
}

.tool-card.select-card.failed .tool-icon {
  color: #f56c6c !important;
}

.tool-card.select-card.failed .select-options-list {
  pointer-events: none;
  opacity: 0.4;
}

/* 必填参数输入区域（已移除，保留样式兼容） */
.param-input-section,
.param-required-block,
.param-reminder,
.param-input-group,
.param-input-script-name,
.param-input-item,
.param-input-controls,
.param-missing-warning {
  display: none;
}

/* 参数确认卡片样式 */
.param-confirm-card {
  background: #fff;
  border: 2px solid #409eff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  max-width: 480px;
}

.param-confirm-body {
  padding: 14px 16px;
}

.param-confirm-body .message-text {
  background: none;
  padding: 0;
  border-radius: 0;
}

.param-confirm-actions {
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
