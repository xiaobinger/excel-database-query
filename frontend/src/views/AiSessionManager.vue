<template>
  <div class="ai-session-manager">
    <div class="toolbar">
      <el-form :inline="true">
        <el-form-item label="用户">
          <el-select v-model="selectedUserId" placeholder="全部用户" clearable style="width: 200px" @change="fetchSessions">
            <el-option v-for="u in users" :key="u.id" :label="u.display_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="includeDeleted" label="包含已删除" @change="fetchSessions" />
        </el-form-item>
      </el-form>
      <el-button type="primary" @click="fetchSessions">
        <i class="fas fa-sync-alt"></i> 刷新
      </el-button>
    </div>

    <el-table :data="sessions" stripe v-loading="loading" style="width: 100%">
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
      <el-table-column label="操作" width="180" align="center">
        <template #default="{ row }">
          <el-button v-if="row.is_deleted" type="success" size="small" text @click="restoreChat(row.id)">
            <i class="fas fa-undo"></i> 恢复
          </el-button>
          <el-button type="danger" size="small" text @click="hardDeleteChat(row.id)">
            <i class="fas fa-trash"></i> 永久删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAppStore } from '../stores'

const store = useAppStore()
const sessions = ref([])
const users = ref([])
const userMap = ref({})
const selectedUserId = ref(null)
const includeDeleted = ref(false)
const loading = ref(false)

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
    const params = { include_deleted: includeDeleted.value }
    if (selectedUserId.value) params.user_id = selectedUserId.value
    const res = await api.ai.adminListChats(params)
    sessions.value = res.data || []
  } catch {} finally {
    loading.value = false
  }
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
  margin-bottom: 16px;
}
</style>
