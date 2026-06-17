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
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
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

const defaultForm = {
  name: '',
  description: '',
  system_prompt: '',
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
      is_default: row.is_default,
      is_active: row.is_active,
    })
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm })
  }
  dialogVisible.value = true
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
    if (isEdit.value) {
      await api.agent.update(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await api.agent.create(form)
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