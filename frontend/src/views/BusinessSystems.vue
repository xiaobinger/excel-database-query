<template>
  <div class="business-systems">
    <!-- 顶部操作栏 -->
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title"><i class="fas fa-th-large"></i> 业务系统</h2>
        <p class="page-desc">快速访问各业务系统，支持单点登录</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索系统..."
          clearable
          style="width: 220px"
        >
          <template #prefix><i class="fas fa-search"></i></template>
        </el-input>
        <el-button v-if="store.hasButtonPermission('business:delete')" type="danger" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
          <i class="fas fa-trash-alt"></i> 批量删除{{ selectedRows.length > 0 ? `(${selectedRows.length})` : '' }}
        </el-button>
        <el-button v-if="store.hasButtonPermission('business:delete')" type="danger" plain @click="handleDeleteAll">
          <i class="fas fa-trash"></i> 删除全部
        </el-button>
        <el-button v-if="store.hasButtonPermission('business:create')" type="primary" @click="openDialog()">
          <i class="fas fa-plus"></i> 添加系统
        </el-button>
      </div>
    </div>

    <!-- 分类标签 -->
    <div v-if="categories.length > 0" class="category-bar">
      <span
        class="category-tag"
        :class="{ active: activeCategory === '' }"
        @click="activeCategory = ''"
      >全部</span>
      <span
        v-for="cat in categories"
        :key="cat"
        class="category-tag"
        :class="{ active: activeCategory === cat }"
        @click="activeCategory = cat"
      >{{ cat }}</span>
    </div>

    <!-- 系统列表表格 -->
    <el-table
      v-if="filteredSystems.length > 0"
      ref="tableRef"
      :data="filteredSystems"
      @selection-change="handleSelectionChange"
      stripe
      border
      style="width: 100%"
    >
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column prop="name" label="系统名称" min-width="160">
        <template #default="{ row }">
          <div style="display: flex; align-items: center; gap: 8px;">
            <img v-if="row.logo_url && !row.logo_url.startsWith('fas')" :src="row.logo_url" :alt="row.name" style="width: 28px; height: 28px; border-radius: 6px; object-fit: contain;" @error="onLogoError($event, row)" />
            <i v-else :class="row.logo_url || 'fas fa-globe'" style="font-size: 18px; color: #409eff;"></i>
            <span style="font-weight: 600;">{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="website_url" label="系统网址" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <el-link :href="row.website_url" target="_blank" type="primary" :underline="false">{{ row.website_url }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.category" size="small" effect="plain">{{ row.category }}</el-tag>
          <span v-else style="color: #c0c4cc;">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '-' }}</template>
      </el-table-column>
      <el-table-column label="SSO" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.sso_enabled" type="success" size="small" effect="dark">启用</el-tag>
          <el-tag v-else type="info" size="small" effect="plain">关闭</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="80" align="center" />
      <el-table-column label="操作" width="200" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" text @click="handleCardClick(row)">
            <i class="fas fa-external-link-alt"></i> 访问
          </el-button>
          <el-button v-if="isAdmin" size="small" type="primary" text @click="openDialog(row)">
            <i class="fas fa-edit"></i>
          </el-button>
          <el-popconfirm
            v-if="isAdmin"
            title="确定要删除此业务系统吗？"
            confirm-button-text="确定"
            cancel-button-text="取消"
            @confirm="handleDelete(row.id)"
          >
            <template #reference>
              <el-button size="small" type="danger" text>
                <i class="fas fa-trash"></i>
              </el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else-if="!loading" description="暂无业务系统" />

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑业务系统' : '添加业务系统'"
      width="680px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" label-position="right">
        <el-form-item label="系统名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入系统名称" />
        </el-form-item>
        <el-form-item label="系统网址" prop="website_url">
          <el-input v-model="form.website_url" placeholder="https://example.com" />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="Logo URL" class="form-row-item">
            <el-input v-model="form.logo_url" placeholder="图片URL或fas fa-xxx图标" />
          </el-form-item>
          <el-form-item label="分类" class="form-row-item">
            <el-input v-model="form.category" placeholder="如：支付、运营" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="系统描述" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" controls-position="right" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>

        <el-divider content-position="left">SSO 单点登录配置</el-divider>

        <el-form-item label="启用SSO">
          <el-switch v-model="form.sso_enabled" />
        </el-form-item>
        <template v-if="form.sso_enabled">
          <el-form-item label="SSO地址">
            <el-input v-model="form.sso_url" placeholder="SSO登录接口地址（留空则使用系统网址）" />
          </el-form-item>
          <div class="form-row">
            <el-form-item label="请求方式" class="form-row-item">
              <el-select v-model="form.sso_method" style="width: 100%">
                <el-option value="POST" label="POST" />
                <el-option value="GET" label="GET" />
              </el-select>
            </el-form-item>
            <el-form-item label="签名密钥" class="form-row-item">
              <el-input v-model="form.sso_token_key" :type="isEdit && !form.sso_token_key ? 'text' : 'password'" placeholder="HMAC签名密钥" show-password />
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="手机号字段" class="form-row-item">
              <el-input v-model="form.sso_phone_field" placeholder="如 phone / mobile" />
            </el-form-item>
            <el-form-item label="Token字段" class="form-row-item">
              <el-input v-model="form.sso_token_field" placeholder="如 token / sign" />
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="响应Token路径" class="form-row-item">
              <el-input v-model="form.sso_response_token_key" placeholder="如 token 或 data.token" />
            </el-form-item>
            <el-form-item label="传参名称" class="form-row-item">
              <el-input v-model="form.sso_token_pass_key" placeholder="跳转网站时传token的参数名" />
            </el-form-item>
          </div>
          <el-form-item label="额外参数">
            <el-input v-model="extraParamsStr" type="textarea" :rows="2" placeholder='JSON格式，如 {"app_id":"xxx","version":"1.0"}' />
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
import { ref, reactive, computed, onMounted } from 'vue'
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
const systemList = ref([])
const categories = ref([])
const searchText = ref('')
const activeCategory = ref('')
const extraParamsStr = ref('')
const selectedRows = ref([])

const defaultForm = {
  name: '',
  website_url: '',
  logo_url: '',
  category: '',
  description: '',
  sort_order: 0,
  is_active: true,
  sso_enabled: false,
  sso_url: '',
  sso_method: 'POST',
  sso_phone_field: 'phone',
  sso_token_field: 'token',
  sso_token_key: '',
  sso_extra_params: {},
  sso_response_token_key: 'token',
  sso_token_pass_key: 'token',
}

const form = reactive({ ...defaultForm })

const rules = {
  name: [{ required: true, message: '请输入系统名称', trigger: 'blur' }],
  website_url: [{ required: true, message: '请输入系统网址', trigger: 'blur' }],
}

const filteredSystems = computed(() => {
  let list = systemList.value
  if (activeCategory.value) {
    list = list.filter(s => s.category === activeCategory.value)
  }
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    list = list.filter(s =>
      s.name.toLowerCase().includes(kw) ||
      (s.description || '').toLowerCase().includes(kw) ||
      (s.category || '').toLowerCase().includes(kw)
    )
  }
  return list
})

const isAdmin = computed(() => {
  return store.user?.role?.is_admin || false
})

async function fetchList() {
  loading.value = true
  try {
    const isAdmin = store.user?.role?.is_admin
    const res = isAdmin ? await api.business.listAllSystems() : await api.business.listSystems()
    systemList.value = res.data || []
    // 提取分类
    const cats = new Set()
    systemList.value.forEach(s => { if (s.category) cats.add(s.category) })
    categories.value = [...cats]
  } catch {
    systemList.value = []
  } finally {
    loading.value = false
  }
}

function onLogoError(event, sys) {
  event.target.style.display = 'none'
  const parent = event.target.parentElement
  const icon = document.createElement('i')
  icon.className = 'fas fa-globe logo-icon'
  parent.appendChild(icon)
}

async function handleCardClick(sys) {
  if (sys.sso_enabled) {
    try {
      const res = await api.business.generateSsoUrl(sys.id, {})
      if (res.success) {
        if (res.method === 'GET') {
          window.open(res.redirect_url, '_blank')
        } else if (res.method === 'POST') {
          if (res.sso_token) {
            // 在新窗口中先设置localStorage.token，再跳转网站
            const newWin = window.open('', '_blank')
            if (!newWin) {
              ElMessage.error('弹窗被浏览器拦截，请允许弹窗后重试')
              return
            }
            const tokenKey = res.token_pass_key || 'token'
            newWin.document.write(`<!DOCTYPE html><html><head><title>正在跳转...</title>
<style>body{margin:0;display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui;background:#f5f7fa;color:#909399}.spinner{width:36px;height:36px;border:3px solid #e4e7ed;border-top-color:#409eff;border-radius:50%;animation:spin .8s linear infinite;margin-right:12px}@keyframes spin{to{transform:rotate(360deg)}}</style>
</head><body><div class="spinner"></div>正在登录，请稍候...</body></html>`)
            newWin.document.close()
            // 先导航到目标网站域名下（同源才能写localStorage）
            newWin.location.href = res.website_url
            // 等页面加载后写入localStorage并刷新
            newWin.addEventListener('load', () => {
              try {
                newWin.localStorage.setItem(tokenKey, res.sso_token)
                newWin.location.reload()
              } catch (e) {
                // 跨域无法写localStorage，回退到URL传参方式
                const separator = '?'
                newWin.location.href = res.website_url_with_token || res.website_url
              }
            }, { once: true })
            ElMessage.success('登录成功，正在进入系统...')
          } else {
            // 没有token，直接打开网站
            window.open(res.website_url, '_blank')
            ElMessage.warning('SSO登录未获取到token，请检查响应token路径配置')
          }
        }
      } else {
        ElMessage.error('SSO登录失败: ' + (res.message || '未知错误'))
      }
    } catch (e) {
      ElMessage.error('SSO登录失败: ' + (e?.response?.data?.message || '未知错误'))
    }
  } else {
    window.open(sys.website_url, '_blank')
  }
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(form, { ...defaultForm, ...row })
    extraParamsStr.value = row.sso_extra_params ? JSON.stringify(row.sso_extra_params, null, 2) : ''
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(form, { ...defaultForm })
    extraParamsStr.value = ''
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = { ...form }
    // 解析额外参数
    if (extraParamsStr.value.trim()) {
      try {
        payload.sso_extra_params = JSON.parse(extraParamsStr.value)
      } catch {
        ElMessage.warning('额外参数JSON格式错误')
        submitting.value = false
        return
      }
    } else {
      payload.sso_extra_params = {}
    }
    // 编辑时如果token_key为空则不传（保留原值）
    if (isEdit.value && !payload.sso_token_key) {
      delete payload.sso_token_key
    }

    if (isEdit.value) {
      await api.business.updateSystem(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.business.createSystem(payload)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch {
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确定要删除此业务系统吗？', '提示', { type: 'warning' })
    await api.business.deleteSystem(id)
    ElMessage.success('删除成功')
    fetchList()
  } catch {}
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的系统')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedRows.value.length} 个业务系统吗？`, '批量删除', { type: 'warning' })
    await api.business.batchDeleteSystems(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchList()
  } catch {}
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm('确定要删除所有业务系统吗？此操作不可恢复！', '删除全部', { type: 'warning' })
    await api.business.deleteAllSystems()
    ElMessage.success('删除全部成功')
    selectedRows.value = []
    fetchList()
  } catch {}
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
.business-systems {
  max-width: 1400px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-title i {
  color: var(--primary-color, #409eff);
}

.page-desc {
  font-size: 13px;
  color: var(--text-muted, #909399);
  margin: 4px 0 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.category-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.category-tag {
  cursor: pointer;
  transition: all 0.2s;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  background: var(--card-bg, #f5f7fa);
  color: var(--text-muted, #909399);
  border: 1px solid var(--border-color, #e4e7ed);
  user-select: none;
}

.category-tag:hover {
  transform: translateY(-1px);
  color: var(--primary-color, #409eff);
  border-color: var(--primary-color, #409eff);
}

.category-tag.active {
  background: var(--primary-color, #409eff);
  color: #fff;
  border-color: var(--primary-color, #409eff);
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row-item {
  flex: 1;
  min-width: 0;
}
</style>
