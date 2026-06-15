<template>
  <div class="skill-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-brain"></i> Skills 管理</span>
          <div class="header-actions">
            <el-select v-model="filterCategory" placeholder="分类筛选" clearable style="width: 140px; margin-right: 12px" @change="fetchSkills">
              <el-option label="查询" value="query" />
              <el-option label="导出" value="export" />
              <el-option label="界面" value="ui" />
              <el-option label="行为" value="behavior" />
              <el-option label="工作流" value="workflow" />
            </el-select>
            <el-select v-model="filterType" placeholder="类型筛选" clearable style="width: 140px; margin-right: 12px" @change="fetchSkills">
              <el-option label="系统" value="system" />
              <el-option label="用户" value="user" />
              <el-option label="自动" value="auto" />
            </el-select>
            <el-button v-hasPermi="['skill:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
            </el-button>
            <el-button v-hasPermi="['skill:delete']" type="danger" size="small" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
            <el-button v-if="store.hasButtonPermission('skill:create')" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建 Skill
            </el-button>
          </div>
        </div>
      </template>

      <el-table ref="tableRef" :data="skills" stripe v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="skill_type" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ skillTypeLabel(row.skill_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ sourceLabel(row.source) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" width="80" align="center" />
        <el-table-column prop="usage_count" label="使用次数" width="100" align="center" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-popconfirm title="确定删除此Skill？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" text>
                  <i class="fas fa-trash"></i> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && skills.length === 0" description="暂无Skills" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑 Skill' : '新建 Skill'" width="600px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="技能名称" />
        </el-form-item>
        <div style="display: flex; gap: 12px">
          <el-form-item label="分类" prop="category" style="flex: 1">
            <el-select v-model="form.category" style="width: 100%">
              <el-option label="查询" value="query" />
              <el-option label="导出" value="export" />
              <el-option label="界面" value="ui" />
              <el-option label="行为" value="behavior" />
              <el-option label="工作流" value="workflow" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型" prop="skill_type" style="flex: 1">
            <el-select v-model="form.skill_type" style="width: 100%">
              <el-option label="系统" value="system" />
              <el-option label="用户" value="user" />
              <el-option label="自动" value="auto" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="描述此技能" />
        </el-form-item>
        <el-form-item label="技能内容">
          <el-input v-model="form.content" type="textarea" :rows="6" placeholder="JSON格式的技能内容" />
        </el-form-item>
        <el-form-item label="触发条件">
          <el-input v-model="form.trigger_conditions" type="textarea" :rows="3" placeholder="JSON格式的触发条件（可选）" />
        </el-form-item>
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
const skills = ref([])
const filterCategory = ref('')
const filterType = ref('')
const selectedRows = ref([])
const tableRef = ref(null)

const defaultForm = {
  name: '',
  skill_type: 'user',
  category: 'workflow',
  description: '',
  content: '',
  trigger_conditions: '',
}

const form = reactive({ ...defaultForm })
const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  skill_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
}

function categoryLabel(c) {
  return { query: '查询', export: '导出', ui: '界面', behavior: '行为', workflow: '工作流' }[c] || c
}
function categoryTagType(c) {
  return { query: '', export: 'success', ui: 'warning', behavior: 'info', workflow: 'danger' }[c] || ''
}
function skillTypeLabel(t) {
  return { system: '系统', user: '用户', auto: '自动' }[t] || t
}
function sourceLabel(s) {
  return { manual: '手动', auto_learn: '自学习', ai_generated: 'AI生成' }[s] || s
}

async function fetchSkills() {
  loading.value = true
  try {
    const params = {}
    if (filterCategory.value) params.category = filterCategory.value
    if (filterType.value) params.skill_type = filterType.value
    const res = await api.ai.getSkills(params)
    skills.value = res.data || []
  } catch {
    skills.value = []
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
      skill_type: row.skill_type,
      category: row.category,
      description: row.description || '',
      content: typeof row.content === 'object' ? JSON.stringify(row.content, null, 2) : (row.content || ''),
      trigger_conditions: typeof row.trigger_conditions === 'object' ? JSON.stringify(row.trigger_conditions, null, 2) : (row.trigger_conditions || ''),
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
  await formRef.value.validate()
  submitting.value = true
  try {
    let contentVal = form.content
    try { contentVal = JSON.parse(contentVal) } catch {}
    let triggerVal = form.trigger_conditions
    try { triggerVal = JSON.parse(triggerVal) } catch {}

    const payload = { ...form, content: contentVal, trigger_conditions: triggerVal }
    if (isEdit.value) {
      await api.ai.updateSkill(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.ai.createSkill(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchSkills()
  } catch {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await api.ai.deleteSkill(id)
    ElMessage.success('删除成功')
    fetchSkills()
  } catch {}
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个Skill吗？`,
      '批量删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.ai.batchDeleteSkills(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchSkills()
  } catch {}
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除所有Skill吗？此操作不可恢复！',
      '删除全部确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.ai.deleteAllSkills()
    ElMessage.success('删除全部成功')
    selectedRows.value = []
    fetchSkills()
  } catch {}
}

onMounted(() => {
  fetchSkills()
})
</script>

<style scoped>
.skill-manager {
  max-width: 1400px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
}

.card-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.header-actions {
  display: flex;
  align-items: center;
}
</style>
