<template>
  <div class="ai-session-manager">
    <div class="toolbar">
      <el-form :inline="true">
        <el-form-item label="用户">
          <el-select v-model="selectedUserId" placeholder="全部用户" clearable style="width: 200px" @change="fetchSessions">
            <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 130px" @change="handleStatusFilterChange">
            <el-option label="活跃" value="active" />
            <el-option label="已删除" value="deleted" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="fetchSessions">
        <i class="fas fa-sync-alt"></i> 刷新
      </el-button>
    </div>
    <div class="toolbar-actions" v-if="store.user?.role?.is_admin">
      <el-button type="success" :disabled="!selectedRows.length" @click="handleBatchRestore">
        <i class="fas fa-undo"></i> 批量恢复<template v-if="selectedRows.length"> ({{ selectedRows.length }})</template>
      </el-button>
      <el-button type="success" plain @click="handleRestoreAll">
        <i class="fas fa-undo-alt"></i> 全部恢复
      </el-button>
      <el-button type="danger" :disabled="!selectedRows.length" @click="handleBatchHardDelete">
        <i class="fas fa-trash"></i> 批量永久删除<template v-if="selectedRows.length"> ({{ selectedRows.length }})</template>
      </el-button>
      <el-button type="danger" plain @click="handleHardDeleteAll">
        <i class="fas fa-trash-alt"></i> 全部永久删除
      </el-button>
    </div>

    <el-table :data="filteredSessions" stripe v-loading="loading" ref="tableRef" @selection-change="handleSelectionChange" style="width: 100%">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="用户" width="120">
        <template #default="{ row }">
          {{ userMap[row.user_id] || row.user_id }}
        </template>
      </el-table-column>
      <el-table-column prop="title" label="对话标题" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_deleted" type="danger" size="small">已删除</el-tag>
          <el-tag v-else type="success" size="small">活跃</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column prop="updated_at" label="更新时间" width="180" />
      <el-table-column label="操作" width="260" align="center">
        <template #default="{ row }">
          <el-button type="primary" size="small" text @click="viewDetail(row.id)">
            <i class="fas fa-eye"></i> 查看
          </el-button>
          <el-button v-if="row.is_deleted" type="success" size="small" text @click="restoreChat(row.id)">
            <i class="fas fa-undo"></i> 恢复
          </el-button>
          <el-button type="danger" size="small" text @click="hardDeleteChat(row.id)">
            <i class="fas fa-trash"></i> 永久删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 对话详情 -->
    <el-dialog v-model="detailVisible" :title="`对话详情 (ID: ${detailChatId})`" width="750px" destroy-on-close>
      <div class="dialog-messages" v-loading="detailLoading" style="max-height: 60vh; overflow-y: auto; padding: 16px">
        <div
          v-for="msg in detailMessages"
          :key="msg.id"
          class="dialog-msg"
          :class="msg.role"
          @mouseenter="msg._showDelete = true"
          @mouseleave="msg._showDelete = false"
        >
          <div class="dialog-msg-avatar">
            <i :class="msg.role === 'user' ? 'fas fa-user' : 'fas fa-robot'"></i>
          </div>
          <div class="dialog-msg-content">
            <!-- 删除按钮（悬浮显示） -->
            <div class="dialog-msg-actions" v-show="msg._showDelete">
              <el-dropdown trigger="click" @command="(cmd) => handleDetailMsgDelete(cmd, msg)">
                <el-button text size="small" class="detail-msg-delete-btn" @click.stop>
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
            </div>
            <template v-if="msg._type === 'tool' && msg._metadata?.tool_data">
              <div class="tool-badge">
                <i class="fas fa-magic"></i>
                <span>{{ msg._metadata.tool_data.action_type === 'export' ? '导出任务' : '查询任务' }}: {{ msg._metadata.tool_data.script_name }}</span>
              </div>
              <pre class="tool-meta">{{ JSON.stringify(msg._metadata.tool_data, null, 2) }}</pre>
            </template>
            <template v-else>
              <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
            </template>
          </div>
        </div>
        <el-empty v-if="!detailLoading && detailMessages.length === 0" description="暂无消息" :image-size="60" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAppStore } from '../stores'
import { marked } from 'marked'

const store = useAppStore()
const sessions = ref([])
const users = ref([])
const userMap = ref({})
const selectedUserId = ref(null)
const statusFilter = ref(null)
const loading = ref(false)
const selectedRows = ref([])
const tableRef = ref(null)

const detailVisible = ref(false)
const detailChatId = ref(null)
const detailMessages = ref([])
const detailLoading = ref(false)

const filteredSessions = computed(() => {
  if (!statusFilter.value) return sessions.value
  if (statusFilter.value === 'active') return sessions.value.filter(s => !s.is_deleted)
  if (statusFilter.value === 'deleted') return sessions.value.filter(s => s.is_deleted)
  return sessions.value
})

function handleStatusFilterChange() {
  // 纯前端筛选，无需重新请求
}

async function fetchUsers() {
  try {
    const res = await api.users.list()
    users.value = res.data || []
    userMap.value = {}
    for (const u of users.value) {
      userMap.value[u.id] = u.display_name || u.username
    }
  } catch {}
}

async function fetchSessions() {
  loading.value = true
  try {
    const params = { include_deleted: true }
    if (selectedUserId.value) params.user_id = selectedUserId.value
    const res = await api.ai.adminListChats(params)
    sessions.value = res.data || []
  } catch {} finally {
    loading.value = false
  }
}

async function viewDetail(chatId) {
  detailChatId.value = chatId
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await api.ai.getMessages(chatId)
    const msgs = res.data || []
    detailMessages.value = msgs.map(m => {
      const base = { ...m }
      if (m._metadata) {
        const meta = m._metadata
        if (meta._type === 'tool') {
          base._type = 'tool'
        }
      }
      return base
    })
  } catch {} finally {
    detailLoading.value = false
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  try { return marked.parse(text) } catch { return text.replace(/\n/g, '<br>') }
}

async function restoreChat(chatId) {
  try {
    await ElMessageBox.confirm('确定要恢复该对话吗？', '恢复确认', { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'info' })
    await api.ai.adminRestoreChat(chatId)
    ElMessage.success('恢复成功')
    fetchSessions()
  } catch {}
}

async function hardDeleteChat(chatId) {
  try {
    await ElMessageBox.confirm('此操作将永久删除该对话及其所有消息记录，不可恢复！确定要永久删除吗？', '永久删除确认', { confirmButtonText: '永久删除', cancelButtonText: '取消', type: 'error' })
    await api.ai.hardDeleteChat(chatId)
    ElMessage.success('永久删除成功')
    fetchSessions()
  } catch {}
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchHardDelete() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(`此操作将永久删除选中的 ${selectedRows.value.length} 个对话及其所有消息记录，不可恢复！确定要永久删除吗？`, '批量永久删除确认', { confirmButtonText: '永久删除', cancelButtonText: '取消', type: 'error' })
    const ids = selectedRows.value.map(r => r.id)
    await api.ai.batchHardDeleteChats(ids)
    ElMessage.success('批量永久删除成功')
    selectedRows.value = []
    fetchSessions()
  } catch {}
}

async function handleHardDeleteAll() {
  try {
    await ElMessageBox.confirm('此操作将永久删除全部对话及其所有消息记录，不可恢复！确定要永久删除全部对话吗？', '全部永久删除确认', { confirmButtonText: '全部永久删除', cancelButtonText: '取消', type: 'error' })
    await api.ai.hardDeleteAllChats()
    ElMessage.success('全部永久删除成功')
    selectedRows.value = []
    fetchSessions()
  } catch {}
}

async function handleBatchRestore() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(`确定要恢复选中的 ${selectedRows.value.length} 个对话吗？`, '批量恢复确认', { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'info' })
    const ids = selectedRows.value.map(r => r.id)
    await api.ai.batchRestoreChats(ids)
    ElMessage.success('批量恢复成功')
    selectedRows.value = []
    fetchSessions()
  } catch {}
}

async function handleRestoreAll() {
  try {
    await ElMessageBox.confirm('确定要恢复全部已删除的对话吗？', '全部恢复确认', { confirmButtonText: '全部恢复', cancelButtonText: '取消', type: 'info' })
    await api.ai.restoreAllChats()
    ElMessage.success('全部恢复成功')
    selectedRows.value = []
    fetchSessions()
  } catch {}
}

async function softDeleteDetailMessage(msg) {
  try {
    await ElMessageBox.confirm('确定要删除此消息吗？', '删除确认', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await api.ai.deleteMessage(detailChatId.value, msg.id)
    detailMessages.value = detailMessages.value.filter(m => m.id !== msg.id)
    ElMessage.success('已删除')
  } catch {}
}

async function hardDeleteDetailMessage(msg) {
  try {
    await ElMessageBox.confirm('永久删除后将无法恢复，确定要永久删除此消息吗？', '永久删除确认', { confirmButtonText: '永久删除', cancelButtonText: '取消', type: 'error' })
    await api.ai.hardDeleteMessage(detailChatId.value, msg.id)
    detailMessages.value = detailMessages.value.filter(m => m.id !== msg.id)
    ElMessage.success('已永久删除')
  } catch {}
}

function handleDetailMsgDelete(cmd, msg) {
  if (cmd === 'soft') {
    softDeleteDetailMessage(msg)
  } else if (cmd === 'hard') {
    hardDeleteDetailMessage(msg)
  }
}

onMounted(() => {
  fetchUsers()
  fetchSessions()
})
</script>

<style scoped>
.ai-session-manager {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.dialog-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dialog-msg {
  display: flex;
  gap: 10px;
}
.dialog-msg.user {
  flex-direction: row-reverse;
}
.dialog-msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
}
.dialog-msg.assistant .dialog-msg-avatar {
  background: #f0f2f5;
  color: #606266;
}
.dialog-msg.user .dialog-msg-avatar {
  background: #409eff;
  color: #fff;
}
.dialog-msg-content {
  max-width: 80%;
  padding: 8px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  position: relative;
}
.dialog-msg.assistant .dialog-msg-content {
  background: #f4f6f8;
  color: #303133;
}
.dialog-msg.user .dialog-msg-content {
  background: #409eff;
  color: #fff;
}

/* 详情对话框消息删除按钮 */
.dialog-msg-actions {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 10;
  opacity: 0.8;
  transition: opacity 0.2s;
}

.dialog-msg-actions:hover {
  opacity: 1;
}

.detail-msg-delete-btn {
  color: #909399;
  padding: 2px 4px;
  font-size: 11px;
  min-height: auto;
}

.detail-msg-delete-btn:hover {
  color: #f56c6c;
}
.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #ecf5ff;
  color: #409eff;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 6px;
}
.tool-meta {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 10px;
  border-radius: 6px;
  font-size: 11px;
  overflow-x: auto;
  margin: 0;
}
.msg-text :deep(p) { margin: 4px 0; }
.msg-text :deep(pre) {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 8px;
  border-radius: 6px;
  font-size: 12px;
  overflow-x: auto;
}
.msg-text :deep(code) {
  background: rgba(64,158,255,0.1);
  color: #409eff;
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}
</style>
