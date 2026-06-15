<template>
  <div class="user-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-users"></i> 用户管理</span>
          <div style="display: flex; gap: 10px; align-items: center;">
            <el-button v-hasPermi="['user:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
            </el-button>
            <el-button v-hasPermi="['user:delete']" type="danger" size="small" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
            <el-button type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建用户
            </el-button>
          </div>
        </div>
      </template>

      <el-table ref="tableRef" :data="userList" stripe v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="display_name" label="显示名" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.display_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="性别" width="80" align="center">
          <template #default="{ row }">
            <i v-if="row.gender === 'female'" class="fas fa-venus" style="color: #f472b6; font-size: 16px" title="女"></i>
            <i v-else class="fas fa-mars" style="color: #409eff; font-size: 16px" title="男"></i>
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.role" size="small" :type="row.role.is_admin ? 'danger' : 'primary'">
              {{ row.role.name }}
            </el-tag>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active !== false ? 'success' : 'info'" size="small">
              {{ row.is_active !== false ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-popconfirm
              title="确定要删除此用户吗？"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" text>
                  <i class="fas fa-trash"></i> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && userList.length === 0" description="暂无用户" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新建用户'"
      width="680px"
      destroy-on-close
      :close-on-click-modal="false"
      class="user-dialog"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        label-position="right"
        class="user-form"
      >
        <div class="form-section">
          <div class="section-title">
            <i class="fas fa-user-circle"></i>
            <span>基本信息</span>
          </div>
          <div class="section-body">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="用户名" prop="username">
                  <el-input v-model="form.username" placeholder="请输入用户名" :disabled="isEdit" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="显示名" prop="display_name">
                  <el-input v-model="form.display_name" placeholder="请输入显示名" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="性别">
                  <el-radio-group v-model="form.gender">
                    <el-radio value="male">
                      <i class="fas fa-mars" style="color: #409eff; margin-right: 4px"></i>男
                    </el-radio>
                    <el-radio value="female">
                      <i class="fas fa-venus" style="color: #f472b6; margin-right: 4px"></i>女
                    </el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="手机号">
                  <el-input v-model="form.phone" placeholder="用于SSO单点登录" />
                </el-form-item>
              </el-col>
            </el-row>
            <template v-if="!isEdit">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="密码" prop="password">
                    <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="确认密码" prop="confirmPassword">
                    <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入密码" />
                  </el-form-item>
                </el-col>
              </el-row>
            </template>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">
            <i class="fas fa-shield-alt"></i>
            <span>角色与权限</span>
          </div>
          <div class="section-body">
            <el-form-item label="角色" prop="role_id">
              <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%">
                <el-option
                  v-for="role in roleList"
                  :key="role.id"
                  :label="role.name"
                  :value="role.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="查询选项">
              <el-select
                v-model="form.script_ids"
                multiple
                collapse-tags
                collapse-tags-tooltip
                placeholder="选择可用查询选项（空为全部）"
                style="width: 100%"
              >
                <el-option
                  v-for="s in store.scripts"
                  :key="s.id"
                  :label="s.name"
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="自动任务">
              <el-select
                v-model="form.auto_task_ids"
                multiple
                collapse-tags
                collapse-tags-tooltip
                placeholder="选择可用自动导出任务（空为全部）"
                style="width: 100%"
              >
                <el-option
                  v-for="t in autoTaskList"
                  :key="t.id"
                  :label="t.name"
                  :value="t.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="系统任务">
              <el-select
                v-model="form.system_task_ids"
                multiple
                collapse-tags
                collapse-tags-tooltip
                placeholder="选择可用系统任务（空为全部）"
                style="width: 100%"
              >
                <el-option
                  v-for="t in systemTaskList"
                  :key="t.id"
                  :label="t.name"
                  :value="t.id"
                />
              </el-select>
            </el-form-item>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
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
const tableRef = ref(null)
const selectedRows = ref([])
const userList = ref([])
const roleList = ref([])
const autoTaskList = ref([])
const systemTaskList = ref([])

const defaultForm = {
  username: '',
  password: '',
  confirmPassword: '',
  display_name: '',
  gender: 'male',
  phone: '',
  role_id: null,
  script_ids: [],
  auto_task_ids: [],
  system_task_ids: []
}

const form = reactive({ ...defaultForm })

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  role_id: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

async function fetchData() {
  loading.value = true
  try {
    const [usersRes, rolesRes, autoRes, sysRes] = await Promise.all([
      api.users.list(),
      api.roles.list(),
      api.autoExport.list(),
      api.systemTask.list()
    ])
    userList.value = usersRes.data || []
    roleList.value = rolesRes.data || []
    autoTaskList.value = autoRes.data || []
    systemTaskList.value = sysRes.data || []
  } catch {
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(form, {
      username: row.username,
      password: '',
      confirmPassword: '',
      display_name: row.display_name || '',
      gender: row.gender || 'male',
      phone: row.phone || '',
      role_id: row.role_id,
      script_ids: row.script_ids || [],
      auto_task_ids: row.auto_task_ids || [],
      system_task_ids: row.system_task_ids || []
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
    const payload = {
        username: form.username,
        display_name: form.display_name,
        gender: form.gender,
        phone: form.phone,
        role_id: form.role_id,
        script_ids: form.script_ids,
        auto_task_ids: form.auto_task_ids,
        system_task_ids: form.system_task_ids
      }
    if (!isEdit.value) {
      payload.password = form.password
    }
    if (isEdit.value) {
      await api.users.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.users.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await api.users.delete(id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个用户吗？`,
      '批量删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.users.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchData()
  } catch {
  }
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除所有用户吗？此操作不可恢复！',
      '删除全部确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.users.deleteAll()
    ElMessage.success('删除全部成功')
    selectedRows.value = []
    fetchData()
  } catch {
  }
}

onMounted(() => {
  fetchData()
  store.fetchScripts()
})
</script>

<style scoped>
.user-manager {
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

.form-section {
  margin-bottom: 20px;
  border: 1px solid var(--border-color, #e6e6e6);
  border-radius: 8px;
  overflow: hidden;
}

.form-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--table-header-bg, #f5f7fa);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  border-bottom: 1px solid var(--border-color, #e6e6e6);
}

.section-title i {
  color: var(--primary-color, #409eff);
  font-size: 15px;
}

.section-body {
  padding: 20px 16px 4px;
}
</style>
