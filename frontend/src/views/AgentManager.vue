<template>
  <div class="agent-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-robot"></i> Agent 管理</span>
          <div class="header-actions">
            <el-button v-hasPermi="['agent:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
            </el-button>
            <el-button v-hasPermi="['agent:delete']" type="danger" size="small" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
            <el-button v-if="store.hasButtonPermission('agent:create')" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建 Agent
            </el-button>
          </div>
        </div>
      </template>

      <el-table ref="tableRef" :data="agents" stripe v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="启用工具" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="!row.enabled_tools" type="info" size="small">全部</el-tag>
            <el-tag v-else size="small">{{ row.enabled_tools.length }}个</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_default" label="默认" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" size="small">默认</el-tag>
            <el-button v-else size="small" type="primary" text @click="setDefault(row.id)">
              设为默认
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" align="center" />
        <el-table-column label="操作" width="260" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-button size="small" type="warning" text @click="openMemoryDialog(row)">
              <i class="fas fa-brain"></i> 记忆
            </el-button>
            <el-popconfirm v-if="!row.is_default" title="确定删除此Agent？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" text>
                  <i class="fas fa-trash"></i> 删除
                </el-button>
              </template>
            </el-popconfirm>
            <span v-else style="color: #999; font-size: 12px">（默认）</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && agents.length === 0" description="暂无Agent" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑 Agent' : '新建 Agent'" width="700px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="Agent名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="描述此Agent的功能和用途" />
        </el-form-item>
        <el-form-item label="系统提示词" prop="system_prompt">
          <el-input v-model="form.system_prompt" type="textarea" :rows="12" placeholder="Agent的系统提示词，定义Agent的行为规则和能力范围" />
        </el-form-item>
        <el-form-item label="启用工具">
          <div style="width: 100%">
            <div style="margin-bottom: 8px">
              <el-checkbox v-model="useAllTools" @change="onUseAllToolsChange">全部启用（不限制）</el-checkbox>
            </div>
            <el-checkbox-group v-model="form.enabled_tools" :disabled="useAllTools" style="display: flex; flex-wrap: wrap; gap: 8px">
              <el-checkbox v-for="t in toolOptions" :key="t.name" :label="t.name">{{ t.label }}</el-checkbox>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <div style="display: flex; gap: 12px">
          <el-form-item label="是否默认" style="flex: 1">
            <el-switch v-model="form.is_default" />
          </el-form-item>
          <el-form-item label="是否启用" style="flex: 1">
            <el-switch v-model="form.is_active" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 记忆管理对话框 -->
    <el-dialog v-model="memoryDialogVisible" :title="`记忆管理 - ${memoryAgentName}`" width="750px" destroy-on-close>
      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <el-tag type="info" size="small">记忆会在AI对话中自动注入，让Agent记住你的特别要求</el-tag>
        </div>
        <el-button type="primary" size="small" @click="openMemoryForm()">
          <i class="fas fa-plus"></i> 添加记忆
        </el-button>
      </div>

      <!-- 添加/编辑记忆表单 -->
      <el-card v-if="memoryFormVisible" shadow="never" style="margin-bottom: 12px; background: #f5f7fa;">
        <el-form :model="memoryForm" label-width="80px" size="small">
          <el-form-item label="类型">
            <el-select v-model="memoryForm.memory_type" style="width: 150px;">
              <el-option label="规则" value="rule" />
              <el-option label="偏好" value="preference" />
              <el-option label="事实" value="fact" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容">
            <el-input v-model="memoryForm.content" type="textarea" :rows="3" placeholder="输入记忆内容，例如：回答时不要加多余的解释" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSaveMemory">保存</el-button>
            <el-button @click="memoryFormVisible = false">取消</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-table :data="memories" stripe v-loading="memoriesLoading" size="small" style="width: 100%">
        <el-table-column prop="memory_type" label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="memoryTypeTag[row.memory_type] || 'info'" size="small">{{ memoryTypeLabel[row.memory_type] || row.memory_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="source" label="来源" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.source === 'auto' ? 'info' : 'success'" size="small">{{ row.source === 'auto' ? '自动' : '手动' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="150" align="center" />
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openMemoryForm(row)">
              <i class="fas fa-edit"></i>
            </el-button>
            <el-popconfirm title="确定删除此记忆？" @confirm="handleDeleteMemory(row.id)">
              <template #reference>
                <el-button size="small" type="danger" text>
                  <i class="fas fa-trash"></i>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!memoriesLoading && memories.length === 0" description="暂无记忆，Agent会在对话中自动学习你的偏好" :image-size="60" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'

const store = useAppStore()
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const agents = ref([])
const selectedRows = ref([])
const tableRef = ref(null)
const useAllTools = ref(true)

// 记忆管理相关
const memoryDialogVisible = ref(false)
const memoryAgentId = ref(null)
const memoryAgentName = ref('')
const memories = ref([])
const memoriesLoading = ref(false)
const memoryFormVisible = ref(false)
const memoryEditId = ref(null)
const memoryForm = reactive({ memory_type: 'rule', content: '' })
const memoryTypeLabel = { rule: '规则', preference: '偏好', fact: '事实' }
const memoryTypeTag = { rule: 'danger', preference: 'warning', fact: 'info' }

// 可选工具列表（名称与后端AI_TOOLS定义一致）
const toolOptions = [
  { name: 'list_export_options', label: '列出导出选项' },
  { name: 'request_export', label: '执行导出' },
  { name: 'parse_uploaded_file', label: '解析上传文件' },
  { name: 'list_query_options', label: '列出查询选项' },
  { name: 'request_query', label: '执行查询' },
  { name: 'list_system_tasks', label: '列出系统任务' },
  { name: 'request_system_task', label: '执行系统任务' },
  { name: 'list_lookup_options', label: '列出信息查询' },
  { name: 'request_lookup', label: '执行信息查询' },
  { name: 'fetch_url', label: '请求外部URL' },
]

const defaultForm = {
  name: '',
  description: '',
  system_prompt: '',
  enabled_tools: null,
  is_default: false,
  is_active: true,
}

const form = reactive({ ...defaultForm })
const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }],
}

async function fetchAgents() {
  loading.value = true
  try {
    const res = await api.agent.getAll()
    agents.value = res.data || []
  } catch {
    agents.value = []
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(form, {
      name: row.name,
      description: row.description || '',
      system_prompt: row.system_prompt || '',
      enabled_tools: row.enabled_tools ? [...row.enabled_tools] : null,
      is_default: row.is_default,
      is_active: row.is_active,
    })
    useAllTools.value = !row.enabled_tools
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm })
    useAllTools.value = true
  }
  dialogVisible.value = true
}

function onUseAllToolsChange(val) {
  if (val) {
    form.enabled_tools = null
  } else if (!form.enabled_tools) {
    // 默认不勾选任何工具，让用户自己选
    form.enabled_tools = []
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    // 全部启用时传null
    const payload = { ...form }
    if (useAllTools.value) {
      payload.enabled_tools = null
    }
    if (isEdit.value) {
      await api.agent.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.agent.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchAgents()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await api.agent.delete(id)
    ElMessage.success('删除成功')
    fetchAgents()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '删除失败')
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  // 过滤掉默认Agent
  const ids = selectedRows.value.filter(r => !r.is_default).map(r => r.id)
  if (ids.length === 0) {
    ElMessage.warning('选中的Agent中包含默认Agent，无法删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 个Agent？`, '批量删除', { type: 'warning' })
    await api.agent.batchDelete(ids)
    ElMessage.success('批量删除成功')
    tableRef.value?.clearSelection()
    fetchAgents()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '批量删除失败')
    }
  }
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm('确定删除所有非默认Agent？此操作不可恢复！', '删除全部', { type: 'warning' })
    await api.agent.deleteAll()
    ElMessage.success('删除成功')
    fetchAgents()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error(err.response?.data?.message || '删除失败')
    }
  }
}

async function setDefault(id) {
  try {
    await api.agent.setDefault(id)
    ElMessage.success('已设为默认Agent')
    fetchAgents()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '设置失败')
  }
}

// ============ 记忆管理 ============

async function openMemoryDialog(row) {
  memoryAgentId.value = row.id
  memoryAgentName.value = row.name
  memoryDialogVisible.value = true
  memoryFormVisible.value = false
  await fetchMemories()
}

async function fetchMemories() {
  if (!memoryAgentId.value) return
  memoriesLoading.value = true
  try {
    const res = await api.agent.getMemories(memoryAgentId.value)
    memories.value = res.data || []
  } catch {
    memories.value = []
  } finally {
    memoriesLoading.value = false
  }
}

function openMemoryForm(row) {
  if (row) {
    memoryEditId.value = row.id
    memoryForm.memory_type = row.memory_type
    memoryForm.content = row.content
  } else {
    memoryEditId.value = null
    memoryForm.memory_type = 'rule'
    memoryForm.content = ''
  }
  memoryFormVisible.value = true
}

async function handleSaveMemory() {
  if (!memoryForm.content.trim()) {
    ElMessage.warning('请输入记忆内容')
    return
  }
  try {
    if (memoryEditId.value) {
      await api.agent.updateMemory(memoryAgentId.value, memoryEditId.value, {
        memory_type: memoryForm.memory_type,
        content: memoryForm.content.trim(),
      })
      ElMessage.success('更新成功')
    } else {
      await api.agent.addMemory(memoryAgentId.value, {
        memory_type: memoryForm.memory_type,
        content: memoryForm.content.trim(),
      })
      ElMessage.success('添加成功')
    }
    memoryFormVisible.value = false
    await fetchMemories()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '操作失败')
  }
}

async function handleDeleteMemory(memoryId) {
  try {
    await api.agent.deleteMemory(memoryAgentId.value, memoryId)
    ElMessage.success('删除成功')
    await fetchMemories()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '删除失败')
  }
}

onMounted(fetchAgents)
</script>

<style scoped>
.agent-manager {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 8px;
}
</style>