<template>
  <div class="role-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-user-shield"></i> 角色管理</span>
          <el-button type="primary" @click="openDialog()">
            <i class="fas fa-plus"></i> 新建角色
          </el-button>
        </div>
      </template>

      <el-table :data="roleList" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="管理员" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_admin ? 'danger' : 'info'" size="small">
              {{ row.is_admin ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="菜单权限" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.menu_permissions && row.menu_permissions.length > 0">
              <el-tag
                v-for="perm in row.menu_permissions"
                :key="perm"
                size="small"
                effect="plain"
                style="margin: 2px 4px 2px 0"
              >
                {{ menuPermLabels[perm] || perm }}
              </el-tag>
            </template>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="按钮权限" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.button_permissions && row.button_permissions.length > 0">
              <el-tag
                v-for="perm in row.button_permissions"
                :key="perm"
                size="small"
                type="warning"
                effect="plain"
                style="margin: 2px 4px 2px 0"
              >
                {{ buttonPermLabels[perm] || perm }}
              </el-tag>
            </template>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-popconfirm
              title="确定要删除此角色吗？"
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
      <el-empty v-if="!loading && roleList.length === 0" description="暂无角色" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑角色' : '新建角色'"
      width="680px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="110px"
        label-position="right"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入角色描述" />
        </el-form-item>
        <el-form-item label="管理员">
          <el-switch v-model="form.is_admin" active-text="是" inactive-text="否" />
        </el-form-item>
        <template v-if="!form.is_admin">
          <el-form-item label="菜单权限">
            <el-checkbox-group v-model="form.menu_permissions">
              <el-checkbox
                v-for="menu in menuOptions"
                :key="menu.value"
                :label="menu.value"
              >
                {{ menu.label }}
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="按钮权限">
            <div class="button-perm-groups">
              <div v-for="group in buttonPermGroups" :key="group.label" class="perm-group">
                <div class="perm-group-label">{{ group.label }}</div>
                <el-checkbox-group v-model="form.button_permissions">
                  <el-checkbox
                    v-for="perm in group.items"
                    :key="perm.value"
                    :label="perm.value"
                  >
                    {{ perm.label }}
                  </el-checkbox>
                </el-checkbox-group>
              </div>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const roleList = ref([])

const menuPermLabels = {
  dashboard: '仪表盘',
  databases: '数据库管理',
  scripts: '脚本管理',
  query: '查询执行',
  export_exec: '导出任务',
  auto_export: '自动导出',
  system: '系统配置',
  history: '执行历史',
  users: '用户管理',
  roles: '角色管理',
  ai_chat: 'AI助手',
  ai_sessions: 'AI会话管理',
  skills: 'Skills',
  business_systems: '业务系统',
  system_tasks: '系统任务'
}

const buttonPermLabels = {
  all: '所有权限',
  'script:create': '新建脚本',
  'script:edit': '编辑脚本',
  'script:delete': '删除脚本',
  'database:create': '新建数据库连接',
  'database:edit': '编辑数据库连接',
  'database:delete': '删除数据库连接',
  'database:test': '测试连接',
  'query:execute': '执行查询',
  'query:cancel': '取消查询',
  'query:download': '下载结果',
  'query:retry': '重新执行查询',
  'export:execute': '执行导出',
  'export:cancel': '取消导出',
  'export:download': '下载导出结果',
  'export:retry': '重新执行导出',
  'auto_export:create': '新建自动导出',
  'auto_export:edit': '编辑自动导出',
  'auto_export:delete': '删除自动导出',
  'auto_export:execute': '执行自动导出',
  'system:config': '系统配置管理',
  'task:delete': '删除任务',
  'business:create': '新建业务系统',
  'business:edit': '编辑业务系统',
  'business:delete': '删除业务系统',
  'business:sso': 'SSO单点登录',
  'ai:config': 'AI模型配置',
  'ai:chat': 'AI对话',
  'ai:skill': 'AI技能管理',
  'system_task:create': '新建系统任务',
  'system_task:edit': '编辑系统任务',
  'system_task:delete': '删除系统任务',
  'system_task:execute': '执行系统任务',
  'system_task:view_log': '查看执行记录',
  'system_task:delete_log': '删除执行记录'
}

const menuOptions = [
  { value: 'dashboard', label: '仪表盘' },
  { value: 'databases', label: '数据库管理' },
  { value: 'scripts', label: '脚本管理' },
  { value: 'query', label: '查询执行' },
  { value: 'export_exec', label: '导出任务' },
  { value: 'auto_export', label: '自动导出' },
  { value: 'system', label: '系统配置' },
  { value: 'system_tasks', label: '系统任务' },
  { value: 'history', label: '执行历史' },
  { value: 'users', label: '用户管理' },
  { value: 'roles', label: '角色管理' },
  { value: 'ai_chat', label: 'AI助手' },
  { value: 'ai_sessions', label: 'AI会话管理' },
  { value: 'skills', label: 'Skills' },
  { value: 'business_systems', label: '业务系统' }
]

const buttonPermGroups = [
  {
    label: '脚本管理',
    items: [
      { value: 'script:create', label: '新建' },
      { value: 'script:edit', label: '编辑' },
      { value: 'script:delete', label: '删除' }
    ]
  },
  {
    label: '数据库连接',
    items: [
      { value: 'database:create', label: '新建' },
      { value: 'database:edit', label: '编辑' },
      { value: 'database:delete', label: '删除' },
      { value: 'database:test', label: '测试连接' }
    ]
  },
  {
    label: '查询执行',
    items: [
      { value: 'query:execute', label: '执行查询' },
      { value: 'query:cancel', label: '取消查询' },
      { value: 'query:download', label: '下载结果' },
      { value: 'query:retry', label: '重新执行' }
    ]
  },
  {
    label: '导出任务',
    items: [
      { value: 'export:execute', label: '执行导出' },
      { value: 'export:cancel', label: '取消导出' },
      { value: 'export:download', label: '下载结果' },
      { value: 'export:retry', label: '重新执行' }
    ]
  },
  {
    label: '自动导出',
    items: [
      { value: 'auto_export:create', label: '新建' },
      { value: 'auto_export:edit', label: '编辑' },
      { value: 'auto_export:delete', label: '删除' },
      { value: 'auto_export:execute', label: '执行/启停' }
    ]
  },
  {
    label: '系统配置',
    items: [
      { value: 'system:config', label: '配置管理' }
    ]
  },
  {
    label: '任务管理',
    items: [
      { value: 'task:delete', label: '删除任务' }
    ]
  },
  {
    label: '业务系统',
    items: [
      { value: 'business:create', label: '新建' },
      { value: 'business:edit', label: '编辑' },
      { value: 'business:delete', label: '删除' },
      { value: 'business:sso', label: 'SSO登录' }
    ]
  },
  {
    label: '系统任务',
    items: [
      { value: 'system_task:create', label: '新建' },
      { value: 'system_task:edit', label: '编辑' },
      { value: 'system_task:delete', label: '删除' },
      { value: 'system_task:execute', label: '执行' },
      { value: 'system_task:view_log', label: '查看记录' },
      { value: 'system_task:delete_log', label: '删除记录' }
    ]
  },
  {
    label: 'AI功能',
    items: [
      { value: 'ai:config', label: 'AI模型配置' },
      { value: 'ai:chat', label: 'AI对话' },
      { value: 'ai:skill', label: 'AI技能管理' }
    ]
  }
]

const defaultForm = {
  name: '',
  description: '',
  is_admin: false,
  menu_permissions: [],
  button_permissions: []
}

const form = reactive({ ...defaultForm })

watch(() => form.is_admin, (val) => {
  if (val) {
    form.menu_permissions = []
    form.button_permissions = []
  }
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

async function fetchRoles() {
  loading.value = true
  try {
    const res = await api.roles.list()
    roleList.value = res.data || res || []
  } catch {
    roleList.value = []
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
      is_admin: row.is_admin || false,
      menu_permissions: row.menu_permissions || [],
      button_permissions: row.button_permissions || []
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
    const payload = { ...form }
    if (isEdit.value) {
      await api.roles.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.roles.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchRoles()
  } catch {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await api.roles.delete(id)
    ElMessage.success('删除成功')
    fetchRoles()
  } catch {
  }
}

onMounted(fetchRoles)
</script>

<style scoped>
.role-manager {
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

.button-perm-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.perm-group {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px 16px;
}

.perm-group-label {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}
</style>
