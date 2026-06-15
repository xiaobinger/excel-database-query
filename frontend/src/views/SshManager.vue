<template>
  <div class="ssh-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-shield-alt"></i> SSH 配置管理</span>
          <div>
            <el-button type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建配置
            </el-button>
            <el-button type="danger" :disabled="!selectedRows.length" v-hasPermi="['ssh:delete']" @click="handleBatchDelete">
              <i class="fas fa-trash-alt"></i> 批量删除
            </el-button>
            <el-button type="danger" v-hasPermi="['ssh:delete']" @click="handleDeleteAll">
              <i class="fas fa-trash"></i> 删除全部
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="sshList" stripe v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange" ref="tableRef">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column label="主机" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.host }}:{{ row.port }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="140" show-overflow-tooltip />
        <el-table-column label="认证方式" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.pkey_path" type="success" size="small">密钥</el-tag>
            <el-tag v-else type="info" size="small">密码</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联连接" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ getConnectionCount(row.id) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="testConnection(row)">
              <i class="fas fa-plug"></i> 测试
            </el-button>
            <el-button size="small" type="warning" text @click="openDialog(row)">
              <i class="fas fa-edit"></i> 编辑
            </el-button>
            <el-popconfirm
              title="确定要删除此SSH配置吗？"
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
      <el-empty v-if="!loading && sshList.length === 0" description="暂无SSH配置" />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑SSH配置' : '新建SSH配置'"
      width="560px"
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
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="如：生产环境跳板机" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="14">
            <el-form-item label="主机" prop="host">
              <el-input v-model="form.host" placeholder="SSH服务器地址" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="端口" prop="port">
              <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="SSH用户名" />
        </el-form-item>

        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? '留空则不修改' : 'SSH密码'" />
        </el-form-item>

        <el-form-item label="密钥路径">
          <el-input v-model="form.pkey_path" placeholder="如 /home/user/.ssh/id_rsa" />
        </el-form-item>

        <el-form-item label="本地绑定端口">
          <el-input-number v-model="form.local_bind_port" :min="0" :max="65535" placeholder="0为自动" style="width: 100%" />
        </el-form-item>
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
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref(null)
const tableRef = ref(null)
const selectedRows = ref([])
const sshList = ref([])
const dbList = ref([])

const defaultForm = {
  name: '',
  host: '',
  port: 22,
  username: '',
  password: '',
  pkey_path: '',
  local_bind_port: null
}

const form = reactive({ ...defaultForm })

const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  host: [{ required: true, message: '请输入主机地址', trigger: 'blur' }],
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }]
}

async function fetchList() {
  loading.value = true
  try {
    const res = await api.ssh.list()
    sshList.value = res.data || []
  } catch {
    sshList.value = []
  } finally {
    loading.value = false
  }
}

async function fetchDbList() {
  try {
    const res = await api.databases.list()
    dbList.value = res.data || []
  } catch {
    dbList.value = []
  }
}

function getConnectionCount(sshId) {
  return dbList.value.filter(db => db.ssh_config_id === sshId).length
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(form, {
      name: row.name,
      host: row.host,
      port: row.port,
      username: row.username,
      password: '',
      pkey_path: row.pkey_path || '',
      local_bind_port: row.local_bind_port || null
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
    if (isEdit.value && !payload.password) {
      delete payload.password
    }
    if (isEdit.value) {
      await api.ssh.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.ssh.create(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch {
  } finally {
    submitting.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 条SSH配置吗？`,
      '批量删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.ssh.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    fetchList()
    fetchDbList()
  } catch {}
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除所有SSH配置吗？此操作不可恢复！',
      '删除全部',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.ssh.deleteAll()
    ElMessage.success('删除全部成功')
    fetchList()
    fetchDbList()
  } catch {}
}

async function handleDelete(id) {
  try {
    await api.ssh.delete(id)
    ElMessage.success('删除成功')
    fetchList()
    fetchDbList()
  } catch {
  }
}

async function testConnection(row) {
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
  fetchList()
  fetchDbList()
})
</script>

<style scoped>
.ssh-manager {
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
</style>
