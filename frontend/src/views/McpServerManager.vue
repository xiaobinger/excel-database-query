<template>
  <div class="mcp-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-plug"></i> MCP 服务管理</span>
          <div class="header-actions">
            <el-button v-if="store.hasButtonPermission('mcp:create') || store.isAdmin" @click="importDialogVisible = true">
              <i class="fas fa-file-import"></i> JSON 导入
            </el-button>
            <el-button v-if="store.hasButtonPermission('mcp:create') || store.isAdmin" type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建 MCP 服务
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="mcp-tabs">
        <!-- ============ 我的 MCP 服务 ============ -->
        <el-tab-pane label="我的 MCP 服务" name="servers">
          <el-alert type="info" :closable="false" style="margin-bottom: 12px"
            title="MCP Server 独立配置，在 Agent 管理中授予给 Agent 后，其工具即可在 AI 对话和工单 AI 处理中使用（工具名格式: mcp__{服务名}__{工具名}）" />

          <el-table :data="servers" stripe v-loading="loading" style="width: 100%">
            <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
            <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
            <el-table-column label="类型" width="130" align="center">
              <template #default="{ row }">
                <el-tag :type="transportTag[row.transport_type] || 'info'" size="small">{{ transportLabel[row.transport_type] || row.transport_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="连接信息" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.transport_type === 'stdio' ? row.command : row.url }}
              </template>
            </el-table-column>
            <el-table-column label="工具数" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.tools_count > 0" size="small" type="success">{{ row.tools_count }}</el-tag>
                <el-tag v-else size="small" type="info">0</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="tools_updated_at" label="工具刷新时间" width="160" align="center" />
            <el-table-column label="操作" width="300" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="handleViewTools(row)" title="查看工具">
                  <i class="fas fa-list"></i> 工具
                </el-button>
                <el-button size="small" type="primary" text @click="openDialog(row)">
                  <i class="fas fa-edit"></i> 编辑
                </el-button>
                <el-button size="small" type="success" text @click="handleRefreshTools(row)" :loading="refreshingId === row.id">
                  <i class="fas fa-sync-alt"></i> 刷新工具
                </el-button>
                <el-button size="small" type="warning" text @click="handleTest(row)" :loading="testingId === row.id">
                  <i class="fas fa-vial"></i> 测试
                </el-button>
                <el-popconfirm title="确定删除此MCP服务？（将从所有Agent的授予列表中移除）" @confirm="handleDelete(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger" text>
                      <i class="fas fa-trash"></i> 删除
                    </el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && servers.length === 0" description="暂无MCP服务，点击右上角新建" />
        </el-tab-pane>

        <!-- ============ MCP 市场 ============ -->
        <el-tab-pane label="MCP 市场" name="market">
          <div class="market-toolbar">
            <el-input v-model="marketSearch" placeholder="搜索名称 / 描述 / 分类" clearable style="width: 300px">
              <template #prefix><i class="fas fa-search"></i></template>
            </el-input>
            <el-button type="primary" :loading="marketLoading" @click="handleRefreshMarket">
              <i class="fas fa-sync-alt"></i> 刷新市场
            </el-button>
            <span class="market-count">共 {{ filteredMarketItems.length }} 个服务</span>
          </div>

          <el-table :data="filteredMarketItems" stripe size="small" v-loading="marketLoading" style="width: 100%" max-height="500">
            <el-table-column label="服务" width="150">
              <template #default="{ row }">
                <div style="font-weight: 600">{{ row.title }}</div>
                <div style="font-size: 12px; color: #999">{{ row.name }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="分类" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.category }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
            <el-table-column label="需配置凭证" width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.env_keys?.length">{{ row.env_keys.map(k => k.key).join(', ') }}</span>
                <span v-else style="color: #999">无需凭证</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.imported" type="success" size="small">已引入</el-tag>
                <el-tag v-else type="info" size="small">未引入</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="handleMarketImport(row)" :disabled="row.imported">
                  {{ row.imported ? '已引入' : '引入' }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-alert type="info" :closable="false" style="margin-top: 12px"
            title="stdio 服务需服务器已安装对应运行时（npx 需 Node.js、uvx 需 uv）；引入后可在编辑表单中调整参数与凭证" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑 MCP 服务' : '新建 MCP 服务'" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="以字母开头，仅含字母/数字/下划线/中划线，如 weather、db-tools" />
          <div class="form-tip">用于生成工具名前缀：mcp__{名称}__{工具名}</div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="描述此MCP服务的用途" />
        </el-form-item>
        <el-form-item label="传输类型" prop="transport_type">
          <el-radio-group v-model="form.transport_type">
            <el-radio value="stdio">stdio（本地命令）</el-radio>
            <el-radio value="streamable_http">Streamable HTTP</el-radio>
            <el-radio value="sse">SSE</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.transport_type === 'stdio'">
          <el-form-item label="启动命令" prop="command">
            <el-input v-model="form.command" placeholder="如: uvx mcp-server-time 或 npx -y @modelcontextprotocol/server-everything" />
            <div class="form-tip">服务器上需已安装对应运行时（uvx/npx/python 等），命令不经 shell 执行</div>
          </el-form-item>
          <el-form-item label="环境变量">
            <el-input v-model="form.env" type="textarea" :rows="3"
              :placeholder="isEdit && editRow?.has_env ? '已配置（加密存储），留空保持不变；填写则覆盖' : envPlaceholder" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="服务URL" prop="url">
            <el-input v-model="form.url" placeholder="如: https://example.com/mcp" />
          </el-form-item>
          <el-form-item label="请求头">
            <el-input v-model="form.headers" type="textarea" :rows="3"
              :placeholder="isEdit && editRow?.has_headers ? '已配置（加密存储），留空保持不变；填写则覆盖' : headersPlaceholder" />
          </el-form-item>
        </template>

        <div style="display: flex; gap: 12px">
          <el-form-item label="超时(秒)" style="flex: 1">
            <el-input-number v-model="form.timeout_seconds" :min="5" :max="600" />
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

    <!-- 工具查看对话框 -->
    <el-dialog v-model="toolsDialogVisible" :title="`工具列表 - ${toolsServerName}`" width="700px" destroy-on-close>
      <el-table :data="toolsServerTools" stripe size="small" style="width: 100%">
        <el-table-column label="工具名（AI调用名）" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" type="warning">mcp__{{ toolsServerName }}__{{ row.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="toolsServerTools.length === 0" description="暂无工具，请先点击列表中的「刷新工具」" :image-size="60" />
    </el-dialog>

    <!-- JSON 导入对话框 -->
    <el-dialog v-model="importDialogVisible" title="JSON 导入" width="780px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom: 12px"
        title="粘贴 Claude Desktop / Cursor / VS Code 风格的 mcpServers JSON 配置，支持批量导入；含路径/参数/凭证的条目导入后可在编辑中调整" />
      <el-input v-model="importConfigText" type="textarea" :rows="10" :placeholder="importPlaceholder" />
      <div style="margin-top: 12px; display: flex; gap: 8px; justify-content: flex-end">
        <el-button :loading="importParsing" @click="handleImportPreview">解析预览</el-button>
        <el-button type="primary" :disabled="importPreview.length === 0" :loading="importSubmitting" @click="handleImportConfirm">
          确认导入（{{ importPreview.filter(i => !i.conflict).length }} 个）
        </el-button>
      </div>
      <el-table v-if="importPreview.length > 0" :data="importPreview" stripe size="small" style="margin-top: 12px">
        <el-table-column prop="name" label="名称" width="140" show-overflow-tooltip />
        <el-table-column label="类型" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="transportTag[row.transport_type] || 'info'" size="small">{{ transportLabel[row.transport_type] || row.transport_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="连接信息" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.command || row.url }}</template>
        </el-table-column>
        <el-table-column label="凭证" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.env_keys?.length || row.header_keys?.length">{{ [...(row.env_keys || []), ...(row.header_keys || [])].join(', ') }}</span>
            <span v-else style="color: #999">无</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.conflict" type="danger" size="small">名称冲突</el-tag>
            <el-tag v-else-if="row.imported" type="success" size="small">已导入</el-tag>
            <el-tag v-else type="info" size="small">可导入</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage } from 'element-plus'

const store = useAppStore()
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const editRow = ref(null)
const formRef = ref(null)
const servers = ref([])
const testingId = ref(null)
const refreshingId = ref(null)

// Tab 切换：我的服务 / 市场
const activeTab = ref('servers')

// 工具查看
const toolsDialogVisible = ref(false)
const toolsServerName = ref('')
const toolsServerTools = ref([])

// JSON 导入
const importDialogVisible = ref(false)
const importConfigText = ref('')
const importPreview = ref([])
const importParsing = ref(false)
const importSubmitting = ref(false)
const importPlaceholder = `支持格式示例：
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx" }
    },
    "context7": { "url": "https://mcp.context7.com/mcp" }
  }
}
也支持：顶层直接是服务映射，或单个 {"command": ...} / {"url": ...} 条目`

// MCP 市场
const marketLoading = ref(false)
const marketItems = ref([])
const marketSearch = ref('')
const filteredMarketItems = computed(() => {
  const kw = marketSearch.value.trim().toLowerCase()
  if (!kw) return marketItems.value
  return marketItems.value.filter(i =>
    [i.name, i.title, i.description, i.category].some(v => (v || '').toLowerCase().includes(kw)))
})

const transportLabel = { stdio: 'stdio', streamable_http: 'Streamable HTTP', sse: 'SSE' }
const transportTag = { stdio: 'primary', streamable_http: 'success', sse: 'warning' }
const envPlaceholder = 'JSON对象，如 { "API_KEY": "xxx" }（键值均为字符串）'
const headersPlaceholder = 'JSON对象，如 { "Authorization": "Bearer xxx" }（键值均为字符串）'

const defaultForm = {
  name: '',
  description: '',
  transport_type: 'stdio',
  command: '',
  env: '',
  url: '',
  headers: '',
  timeout_seconds: 60,
  is_active: true,
}

const form = reactive({ ...defaultForm })
const rules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { pattern: /^(?!.*__)[a-zA-Z][a-zA-Z0-9_-]{0,63}$/, message: '以字母开头，仅含字母/数字/下划线/中划线，且不能含连续下划线', trigger: 'blur' },
  ],
  transport_type: [{ required: true, message: '请选择传输类型', trigger: 'change' }],
  command: [{ required: true, message: '请输入启动命令', trigger: 'blur' }],
  url: [{ required: true, message: '请输入服务URL', trigger: 'blur' }],
}

async function fetchServers() {
  loading.value = true
  try {
    const res = await api.mcp.list()
    servers.value = res.data || []
  } catch {
    servers.value = []
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    editRow.value = row
    Object.assign(form, {
      name: row.name,
      description: row.description || '',
      transport_type: row.transport_type,
      command: row.command || '',
      env: '',
      url: row.url || '',
      headers: '',
      timeout_seconds: row.timeout_seconds || 60,
      is_active: row.is_active,
    })
  } else {
    isEdit.value = false
    editId.value = null
    editRow.value = null
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

  // env/headers 仅在填写时提交（空 = 编辑时保持不变 / 新建时不设置）
  const payload = {
    name: form.name,
    description: form.description,
    transport_type: form.transport_type,
    timeout_seconds: form.timeout_seconds,
    is_active: form.is_active,
  }
  if (form.transport_type === 'stdio') {
    payload.command = form.command
    if (form.env.trim()) payload.env = form.env.trim()
  } else {
    payload.url = form.url
    if (form.headers.trim()) payload.headers = form.headers.trim()
  }

  submitting.value = true
  try {
    if (isEdit.value) {
      await api.mcp.update(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      const res = await api.mcp.create(payload)
      const toolsCount = res?.data?.tools_count || 0
      ElMessage.success(toolsCount > 0
        ? `创建成功，已自动发现 ${toolsCount} 个工具`
        : '创建成功，但未能自动获取工具清单，请点击「刷新工具」重试')
    }
    dialogVisible.value = false
    fetchServers()
    // 同步刷新市场已引入标记
    fetchMarket()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleTest(row) {
  testingId.value = row.id
  try {
    const res = await api.mcp.test(row.id)
    if (res.success) {
      ElMessage.success(`连接成功，发现 ${res.tools_count} 个工具`)
      // 展示工具列表
      toolsServerName.value = row.name
      toolsServerTools.value = res.tools || []
      toolsDialogVisible.value = true
      fetchServers()
    } else {
      ElMessage.error(res.message || '连接失败')
      fetchServers()
    }
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '测试失败')
  } finally {
    testingId.value = null
  }
}

async function handleRefreshTools(row) {
  refreshingId.value = row.id
  try {
    const res = await api.mcp.refreshTools(row.id)
    if (res.success) {
      ElMessage.success(`已刷新，发现 ${res.tools_count} 个工具`)
    } else {
      ElMessage.error(res.message || '刷新失败')
    }
    fetchServers()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '刷新失败')
  } finally {
    refreshingId.value = null
  }
}

function handleViewTools(row) {
  toolsServerName.value = row.name
  toolsServerTools.value = row.tools || []
  toolsDialogVisible.value = true
}

async function handleDelete(id) {
  try {
    await api.mcp.delete(id)
    ElMessage.success('删除成功')
    fetchServers()
    // 同步刷新市场已引入标记
    fetchMarket()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '删除失败')
  }
}

// ============ JSON 导入 ============

async function handleImportPreview() {
  if (!importConfigText.value.trim()) {
    ElMessage.warning('请先粘贴JSON配置')
    return
  }
  importParsing.value = true
  try {
    const res = await api.mcp.importJson({ config: importConfigText.value, dry_run: true })
    importPreview.value = res.data || []
    ElMessage.success(`解析成功，共 ${importPreview.value.length} 个服务`)
  } catch (err) {
    importPreview.value = []
    ElMessage.error(err.response?.data?.message || '解析失败')
  } finally {
    importParsing.value = false
  }
}

async function handleImportConfirm() {
  importSubmitting.value = true
  try {
    const res = await api.mcp.importJson({ config: importConfigText.value, dry_run: false })
    ElMessage.success(res.message || '导入成功')
    importDialogVisible.value = false
    importConfigText.value = ''
    importPreview.value = []
    fetchServers()
    // 同步刷新市场已引入标记
    fetchMarket()
  } catch (err) {
    ElMessage.error(err.response?.data?.message || '导入失败')
  } finally {
    importSubmitting.value = false
  }
}

// ============ MCP 市场 ============

async function fetchMarket() {
  marketLoading.value = true
  try {
    const res = await api.mcp.marketplace()
    marketItems.value = res.data || []
  } catch {
    ElMessage.error('获取市场目录失败')
    marketItems.value = []
  } finally {
    marketLoading.value = false
  }
}

async function handleRefreshMarket() {
  marketLoading.value = true
  try {
    const res = await api.mcp.refreshMarketplace()
    marketItems.value = res.data || []
    ElMessage.success('市场目录已刷新')
  } catch {
    ElMessage.error('刷新市场目录失败')
  } finally {
    marketLoading.value = false
  }
}

function handleMarketImport(row) {
  isEdit.value = false
  editId.value = null
  editRow.value = null
  // 需要凭证的条目预填 env 骨架，便于直接填入密钥
  const envSkeleton = (row.env_keys || []).length
    ? JSON.stringify(Object.fromEntries(row.env_keys.map(k => [k.key, ''])), null, 2)
    : ''
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    transport_type: row.transport_type,
    command: row.command || '',
    env: envSkeleton,
    url: row.url || '',
    headers: '',
    timeout_seconds: 60,
    is_active: true,
  })
  if (row.note) {
    ElMessage.info({ message: row.note, duration: 6000 })
  }
  dialogVisible.value = true
}

onMounted(() => {
  fetchServers()
  fetchMarket()
})
</script>

<style scoped>
.mcp-manager {
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
.form-tip {
  font-size: 12px;
  color: #999;
  line-height: 1.4;
  margin-top: 2px;
}
.market-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.market-count {
  font-size: 13px;
  color: #999;
}
</style>