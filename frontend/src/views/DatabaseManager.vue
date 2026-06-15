<template>
  <div class="database-manager">
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="数据库连接" name="databases">
        <div class="tab-header">
          <span><i class="fas fa-database"></i> 数据库连接管理</span>
          <div class="tab-header-actions">
            <el-button v-hasPermi="['database:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
            </el-button>
            <el-button v-hasPermi="['database:delete']" type="danger" size="small" plain @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
            <el-button v-if="store.hasButtonPermission('database:create')" type="primary" size="small" @click="openDbDialog()">
              <i class="fas fa-plus"></i> 新建连接
            </el-button>
          </div>
        </div>

        <el-table ref="tableRef" :data="dbList" stripe v-loading="dbLoading" style="width: 100%" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="50" align="center" />
          <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="db_type" label="类型" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small">{{ row.db_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="主机" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.host }}:{{ row.port }}/{{ row.database_name }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="用户名" width="110" show-overflow-tooltip />
          <el-table-column label="SSH" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.ssh_enabled && row.ssh_config_name" type="warning" size="small">
                <i class="fas fa-shield-alt"></i> {{ row.ssh_config_name }}
              </el-tag>
              <el-tag v-else-if="row.ssh_enabled" type="warning" size="small">
                <i class="fas fa-shield-alt"></i> SSH
              </el-tag>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
          <el-table-column label="操作" width="240" align="center" fixed="right">
            <template #default="{ row }">
              <el-button v-if="store.hasButtonPermission('database:test')" size="small" type="primary" text @click="testDbConnection(row)">
                <i class="fas fa-plug"></i> 测试
              </el-button>
              <el-button v-if="store.hasButtonPermission('database:edit')" size="small" type="warning" text @click="openDbDialog(row)">
                <i class="fas fa-edit"></i> 编辑
              </el-button>
              <el-popconfirm
                v-if="store.hasButtonPermission('database:delete')"
                title="确定要删除此连接吗？"
                confirm-button-text="确定"
                cancel-button-text="取消"
                @confirm="handleDbDelete(row.id)"
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
        <el-empty v-if="!dbLoading && dbList.length === 0" description="暂无数据库连接" />
      </el-tab-pane>

      <el-tab-pane label="SSH 配置" name="ssh">
        <div class="tab-header">
          <span><i class="fas fa-shield-alt"></i> SSH 配置管理</span>
          <el-button type="primary" size="small" @click="openSshDialog()">
            <i class="fas fa-plus"></i> 新建配置
          </el-button>
        </div>

        <el-table :data="sshList" stripe v-loading="sshLoading" style="width: 100%">
          <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
          <el-table-column label="主机" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.host }}:{{ row.port }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="用户名" width="130" show-overflow-tooltip />
          <el-table-column label="认证方式" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.pkey_path" type="success" size="small">密钥</el-tag>
              <el-tag v-else type="info" size="small">密码</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" align="center" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click="testSshConnection(row)">
                <i class="fas fa-plug"></i> 测试
              </el-button>
              <el-button size="small" type="warning" text @click="openSshDialog(row)">
                <i class="fas fa-edit"></i> 编辑
              </el-button>
              <el-popconfirm
                title="确定要删除此SSH配置吗？"
                confirm-button-text="确定"
                cancel-button-text="取消"
                @confirm="handleSshDelete(row.id)"
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
        <el-empty v-if="!sshLoading && sshList.length === 0" description="暂无SSH配置" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="dbDialogVisible"
      :title="isDbEdit ? '编辑数据库连接' : '新建数据库连接'"
      width="680px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="dbFormRef"
        :model="dbForm"
        :rules="dbRules"
        label-width="110px"
        label-position="right"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="dbForm.name" placeholder="请输入连接名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据库类型" prop="db_type">
              <el-select v-model="dbForm.db_type" placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="t in dbTypes"
                  :key="t.value || t"
                  :label="t.label || t.value || t"
                  :value="t.value || t"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="dbForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="14">
            <el-form-item label="主机" prop="host">
              <el-input v-model="dbForm.host" placeholder="如 127.0.0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="dbForm.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="数据库名" prop="database_name">
          <el-input v-model="dbForm.database_name" placeholder="请输入数据库名" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="dbForm.username" placeholder="请输入用户名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码" prop="password">
              <el-input v-model="dbForm.password" type="password" show-password :placeholder="isDbEdit ? '留空则不修改' : '请输入密码'" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="连接池大小">
              <el-input-number v-model="dbForm.pool_size" :min="1" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大溢出">
              <el-input-number v-model="dbForm.max_overflow" :min="0" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">SSH 隧道配置</el-divider>

        <el-form-item label="启用SSH">
          <el-switch v-model="dbForm.ssh_enabled" />
        </el-form-item>

        <template v-if="dbForm.ssh_enabled">
          <el-form-item label="SSH配置" prop="ssh_config_id">
            <el-select
              v-model="dbForm.ssh_config_id"
              placeholder="请选择SSH配置"
              style="width: 100%"
              clearable
            >
              <el-option
                v-for="ssh in sshList"
                :key="ssh.id"
                :label="`${ssh.name} (${ssh.host}:${ssh.port})`"
                :value="ssh.id"
              />
            </el-select>
            <div style="margin-top: 4px; font-size: 12px; color: #909399;">
              如需新建SSH配置，请切换到「SSH 配置」标签页
            </div>
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button @click="dbDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="dbSubmitting" @click="handleDbSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="sshDialogVisible"
      :title="isSshEdit ? '编辑SSH配置' : '新建SSH配置'"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="sshFormRef"
        :model="sshForm"
        :rules="sshRules"
        label-width="110px"
        label-position="right"
      >
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="sshForm.name" placeholder="如：生产环境跳板机" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="14">
            <el-form-item label="主机" prop="host">
              <el-input v-model="sshForm.host" placeholder="SSH服务器地址" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="sshForm.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="用户名" prop="username">
          <el-input v-model="sshForm.username" placeholder="SSH用户名" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="sshForm.password" type="password" show-password :placeholder="isSshEdit ? '留空则不修改' : 'SSH密码'" />
        </el-form-item>

        <el-form-item label="密钥路径">
          <el-input v-model="sshForm.pkey_path" placeholder="如 /home/user/.ssh/id_rsa" />
        </el-form-item>

        <el-form-item label="本地绑定端口">
          <el-input-number v-model="sshForm.local_bind_port" :min="0" :max="65535" placeholder="0为自动" style="width: 100%" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="sshDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sshSubmitting" @click="handleSshSubmit">确定</el-button>
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
const activeTab = ref('databases')

const dbLoading = ref(false)
const dbSubmitting = ref(false)
const dbDialogVisible = ref(false)
const isDbEdit = ref(false)
const dbEditId = ref(null)
const dbFormRef = ref(null)
const dbList = ref([])
const dbTypes = ref([])
const selectedRows = ref([])
const tableRef = ref(null)

const sshLoading = ref(false)
const sshSubmitting = ref(false)
const sshDialogVisible = ref(false)
const isSshEdit = ref(false)
const sshEditId = ref(null)
const sshFormRef = ref(null)
const sshList = ref([])

const defaultDbForm = {
  name: '',
  description: '',
  db_type: 'mysql',
  host: '127.0.0.1',
  port: 3306,
  database_name: '',
  username: '',
  password: '',
  pool_size: 5,
  max_overflow: 10,
  ssh_enabled: false,
  ssh_config_id: null
}
const dbForm = reactive({ ...defaultDbForm })

const defaultSshForm = {
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  pkey_path: '',
  local_bind_port: null
}
const sshForm = reactive({ ...defaultSshForm })

const dbRules = {
  name: [{ required: true, message: '请输入连接名称', trigger: 'blur' }],
  db_type: [{ required: true, message: '请选择数据库类型', trigger: 'change' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  database_name: [{ required: true, message: '请输入数据库名', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{
    validator: (rule, value, callback) => {
      if (!isDbEdit.value && !dbForm.ssh_enabled && !value) {
        callback(new Error('不通过SSH连接时密码不能为空'))
      } else {
        callback()
      }
    },
    trigger: 'blur'
  }],
  ssh_config_id: [{
    validator: (rule, value, callback) => {
      if (dbForm.ssh_enabled && !value) {
        callback(new Error('启用SSH时请选择SSH配置'))
      } else {
        callback()
      }
    },
    trigger: 'change'
  }]
}

const sshRules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }]
}

async function fetchDbList() {
  dbLoading.value = true
  try {
    const res = await api.databases.list()
    dbList.value = res.data || res || []
  } catch {
    dbList.value = []
  } finally {
    dbLoading.value = false
  }
}

async function fetchTypes() {
  try {
    const res = await api.databases.getTypes()
    dbTypes.value = res.data || res || ['mysql', 'postgresql', 'sqlite', 'oracle', 'sqlserver']
  } catch {
    dbTypes.value = ['mysql', 'postgresql', 'sqlite', 'oracle', 'sqlserver']
  }
}

async function fetchSshList() {
  sshLoading.value = true
  try {
    const res = await api.ssh.list()
    sshList.value = res.data || []
  } catch {
    sshList.value = []
  } finally {
    sshLoading.value = false
  }
}

function openDbDialog(row) {
  if (row) {
    isDbEdit.value = true
    dbEditId.value = row.id
    Object.assign(dbForm, {
      name: row.name,
      description: row.description || '',
      db_type: row.db_type,
      host: row.host,
      port: row.port,
      database_name: row.database_name,
      username: row.username,
      password: '',
      pool_size: row.pool_size,
      max_overflow: row.max_overflow,
      ssh_enabled: row.ssh_enabled || false,
      ssh_config_id: row.ssh_config_id || null
    })
  } else {
    isDbEdit.value = false
    dbEditId.value = null
    Object.assign(dbForm, { ...defaultDbForm })
  }
  dbDialogVisible.value = true
}

async function handleDbSubmit() {
  if (!dbFormRef.value) return
  await dbFormRef.value.validate()
  dbSubmitting.value = true
  try {
    const payload = { ...dbForm }
    if (isDbEdit.value && !payload.password) {
      delete payload.password
    }
    if (!payload.ssh_enabled) {
      payload.ssh_config_id = null
    }
    if (isDbEdit.value) {
      await api.databases.update(dbEditId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.databases.create(payload)
      ElMessage.success('创建成功')
    }
    dbDialogVisible.value = false
    fetchDbList()
    store.fetchDatabases()
  } catch {
  } finally {
    dbSubmitting.value = false
  }
}

async function handleDbDelete(id) {
  try {
    await api.databases.delete(id)
    ElMessage.success('删除成功')
    fetchDbList()
    store.fetchDatabases()
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
      `确定要删除选中的 ${selectedRows.value.length} 个数据库连接吗？`,
      '批量删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.databases.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchDbList()
    store.fetchDatabases()
  } catch {
  }
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除所有数据库连接吗？此操作不可恢复！',
      '删除全部确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.databases.deleteAll()
    ElMessage.success('删除全部成功')
    selectedRows.value = []
    fetchDbList()
    store.fetchDatabases()
  } catch {
  }
}

async function testDbConnection(row) {
  try {
    ElMessage.info('正在测试连接...')
    const res = await api.databases.test(row.id)
    if (res.success || res.data?.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error(res.message || res.error || '连接测试失败')
    }
  } catch {
  }
}

function openSshDialog(row) {
  if (row) {
    isSshEdit.value = true
    sshEditId.value = row.id
    Object.assign(sshForm, {
      name: row.name,
      host: row.host,
      port: row.port,
      username: row.username,
      password: '',
      pkey_path: row.pkey_path || '',
      local_bind_port: row.local_bind_port || null
    })
  } else {
    isSshEdit.value = false
    sshEditId.value = null
    Object.assign(sshForm, { ...defaultSshForm })
  }
  sshDialogVisible.value = true
}

async function handleSshSubmit() {
  if (!sshFormRef.value) return
  await sshFormRef.value.validate()
  sshSubmitting.value = true
  try {
    const payload = { ...sshForm }
    if (isSshEdit.value && !payload.password) {
      delete payload.password
    }
    if (isSshEdit.value) {
      await api.ssh.update(sshEditId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.ssh.create(payload)
      ElMessage.success('创建成功')
    }
    sshDialogVisible.value = false
    fetchSshList()
  } catch {
  } finally {
    sshSubmitting.value = false
  }
}

async function handleSshDelete(id) {
  try {
    await api.ssh.delete(id)
    ElMessage.success('删除成功')
    fetchSshList()
    fetchDbList()
  } catch {
  }
}

async function testSshConnection(row) {
  try {
    ElMessage.info('正在测试SSH连接...')
    const res = await api.ssh.test(row.id)
    if (res.success) {
      ElMessage.success('SSH连接测试成功')
    } else {
      ElMessage.error(res.message || 'SSH连接测试失败')
    }
  } catch {
  }
}

onMounted(() => {
  fetchDbList()
  fetchTypes()
  fetchSshList()
  store.fetchDatabases()
})
</script>

<style scoped>
.database-manager {
  max-width: 1400px;
}

.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  font-size: 15px;
  font-weight: 600;
}

.tab-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.tab-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
