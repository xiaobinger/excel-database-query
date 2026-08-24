<template>
  <div class="open-api-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-key"></i> 开放API — AI 能力对外输出</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- ============ 设置 ============ -->
        <el-tab-pane label="全局设置" name="settings">
          <el-form label-width="120px" style="max-width: 640px" v-loading="settingsLoading">
            <el-form-item label="启用开放API">
              <el-switch v-model="settings.enabled" />
              <div class="form-tip">关闭后所有对外端点返回 404</div>
            </el-form-item>
            <el-form-item label="暴露端点">
              <el-radio-group v-model="settings.endpoint_mode">
                <el-radio value="openai">仅 OpenAI 兼容</el-radio>
                <el-radio value="custom">仅自定义接口</el-radio>
                <el-radio value="both">两者都开放</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="settingsSaving" @click="saveSettings">保存设置</el-button>
            </el-form-item>
          </el-form>

          <el-divider content-position="left">调用示例</el-divider>
          <div class="example-block">
            <div class="example-title">OpenAI 兼容端点（可直接用 openai SDK，base_url 指向本系统）</div>
            <pre class="example-code">POST /v1/chat/completions
Authorization: Bearer sk-xxxxxxxx

{
  "model": "auto",            // 外部映射名或 auto（走系统模型路由策略）
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "stream": false             // 可选，true 为流式
}</pre>
            <div class="example-title" style="margin-top: 10px">自定义端点</div>
            <pre class="example-code">POST /api/v1/chat
Authorization: Bearer sk-xxxxxxxx

{ "model": "auto", "messages": [...], "stream": false }
// 响应: { "success": true, "data": { "content", "model", "usage", "elapsed" } }</pre>
            <div class="example-title" style="margin-top: 10px">模型列表（OpenAI 兼容）</div>
            <pre class="example-code">GET /v1/models
Authorization: Bearer sk-xxxxxxxx</pre>
          </div>
        </el-tab-pane>

        <!-- ============ Token 管理 ============ -->
        <el-tab-pane :label="`API 密钥 (${keys.length})`" name="keys">
          <div style="margin-bottom: 12px; display: flex; justify-content: flex-end">
            <el-button type="primary" @click="openKeyDialog()"><i class="fas fa-plus"></i> 新建密钥</el-button>
          </div>
          <el-table :data="keys" stripe v-loading="keysLoading" style="width: 100%">
            <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
            <el-table-column label="API Key" min-width="220">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 6px">
                  <span class="mono">{{ revealedKeys[row.id] || 'sk-************************' }}</span>
                  <el-button size="small" text type="primary" @click="handleRevealKey(row)">
                    <i class="fas fa-eye"></i>
                  </el-button>
                  <el-button v-if="revealedKeys[row.id]" size="small" text type="success" @click="copyKey(revealedKeys[row.id])">
                    <i class="fas fa-copy"></i>
                  </el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="模型映射" min-width="200">
              <template #default="{ row }">
                <template v-if="row.model_mapping && row.model_mapping.length">
                  <el-tag v-for="m in row.model_mapping" :key="m.external" size="small" style="margin-right: 4px">
                    {{ m.external }}
                  </el-tag>
                </template>
                <el-tag v-else size="small" type="info">仅 auto</el-tag>
                <el-tag size="small" type="warning" style="margin-left: 4px">auto</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="IP白名单" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.ip_whitelist && row.ip_whitelist.length">{{ row.ip_whitelist.join(', ') }}</span>
                <span v-else style="color: #999">不限</span>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_used_at" label="最近使用" width="160" align="center" />
            <el-table-column label="操作" width="240" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="openKeyDialog(row)"><i class="fas fa-edit"></i> 编辑</el-button>
                <el-button size="small" type="warning" text @click="handleTestKey(row)"><i class="fas fa-vial"></i> 测试</el-button>
                <el-popconfirm title="重新生成后旧密钥立即失效，确定？" @confirm="handleRegenerate(row.id)">
                  <template #reference>
                    <el-button size="small" type="info" text><i class="fas fa-sync-alt"></i> 重置</el-button>
                  </template>
                </el-popconfirm>
                <el-popconfirm title="确定删除此密钥？（调用记录保留）" @confirm="handleDeleteKey(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger" text><i class="fas fa-trash"></i></el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!keysLoading && keys.length === 0" description="暂无API密钥" />
        </el-tab-pane>

        <!-- ============ 调用记录 ============ -->
        <el-tab-pane label="调用记录与统计" name="logs">
          <el-row :gutter="12" style="margin-bottom: 12px">
            <el-col :span="4"><div class="stat-box"><div class="stat-num">{{ stats.total || 0 }}</div><div class="stat-label">总调用</div></div></el-col>
            <el-col :span="4"><div class="stat-box"><div class="stat-num">{{ stats.success_rate ?? 0 }}%</div><div class="stat-label">成功率</div></div></el-col>
            <el-col :span="4"><div class="stat-box"><div class="stat-num">{{ stats.total_tokens || 0 }}</div><div class="stat-label">总Token</div></div></el-col>
            <el-col :span="4"><div class="stat-box"><div class="stat-num">{{ (stats.cache_read_tokens || 0) + (stats.cache_creation_tokens || 0) }}</div><div class="stat-label">缓存Token</div></div></el-col>
            <el-col :span="4"><div class="stat-box"><div class="stat-num">{{ stats.avg_elapsed || 0 }}s</div><div class="stat-label">平均耗时</div></div></el-col>
          </el-row>

          <div style="margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-select v-model="logFilter.api_key_id" placeholder="按密钥筛选" clearable style="width: 180px">
              <el-option v-for="k in keys" :key="k.id" :label="k.name" :value="k.id" />
            </el-select>
            <el-select v-model="logFilter.status" placeholder="按状态筛选" clearable style="width: 140px">
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-date-picker v-model="logTimeRange" type="datetimerange" range-separator="至"
              start-placeholder="开始时间" end-placeholder="结束时间" style="width: 360px" />
            <el-button type="primary" @click="fetchLogs"><i class="fas fa-search"></i> 查询</el-button>
          </div>

          <el-table :data="logs" stripe v-loading="logsLoading" style="width: 100%" size="small">
            <el-table-column prop="created_at" label="时间" width="160" align="center" />
            <el-table-column prop="api_key_name" label="密钥" min-width="100" show-overflow-tooltip />
            <el-table-column label="端点" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.endpoint === 'openai' ? 'primary' : 'success'" size="small">{{ row.endpoint }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模型（请求→实际）" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.model_requested }}<span v-if="row.model_used && row.model_used !== row.model_requested"> → {{ row.model_used }}</span>
              </template>
            </el-table-column>
            <el-table-column label="Token（↑/↓/缓存）" width="170" align="center">
              <template #default="{ row }">
                {{ row.tokens_used }} <span style="color:#999">({{ row.prompt_tokens }}/{{ row.completion_tokens }}<template v-if="row.cache_read_tokens > 0">, 命中{{ row.cache_read_tokens }}</template>)</span>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="80" align="center">
              <template #default="{ row }">{{ row.elapsed }}s</template>
            </el-table-column>
            <el-table-column prop="caller_ip" label="调用方IP" width="130" align="center" />
            <el-table-column label="状态" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_success ? 'success' : 'danger'" size="small">{{ row.is_success ? '成功' : '失败' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" text @click="showLogDetail(row.id)"><i class="fas fa-file-alt"></i></el-button>
                <el-popconfirm title="确定删除此条调用记录？" @confirm="handleDeleteLog(row.id)">
                  <template #reference>
                    <el-button size="small" type="danger" text><i class="fas fa-trash"></i></el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <div style="margin-top: 12px; display: flex; justify-content: flex-end">
            <el-pagination background layout="total, prev, pager, next" :total="logTotal"
              :page-size="logFilter.per_page" v-model:current-page="logFilter.page" @current-change="fetchLogs" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑密钥对话框 -->
    <el-dialog v-model="keyDialogVisible" :title="isEdit ? '编辑 API 密钥' : '新建 API 密钥'" width="680px" destroy-on-close>
      <el-form ref="keyFormRef" :model="keyForm" :rules="keyRules" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="keyForm.name" placeholder="用途备注，如：订单系统对接" />
        </el-form-item>
        <el-form-item label="模型映射">
          <div style="width: 100%">
            <div v-for="(m, idx) in keyForm.model_mapping" :key="idx" style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center">
              <el-input v-model="m.external" placeholder="外部模型名（调用方传的 model）" style="flex: 1" />
              <span style="color: #999">→</span>
              <el-select v-model="m.config_id" placeholder="内部模型" style="width: 220px" filterable>
                <el-option v-for="c in aiConfigs" :key="c.id" :label="`${c.name} (${c.model_name})`" :value="c.id" />
              </el-select>
              <el-button size="small" type="danger" text @click="keyForm.model_mapping.splice(idx, 1)">
                <i class="fas fa-minus"></i>
              </el-button>
            </div>
            <el-button size="small" @click="keyForm.model_mapping.push({ external: '', config_id: null })">
              <i class="fas fa-plus"></i> 添加映射
            </el-button>
            <div class="form-tip">调用方 model 传映射的外部名时使用指定内部模型；传 auto 或未匹配名时走系统模型路由策略</div>
          </div>
        </el-form-item>
        <el-form-item label="IP白名单">
          <el-input v-model="keyForm.ip_whitelist_text" type="textarea" :rows="3"
            placeholder="每行一个，支持精确IP与CIDR（如 1.2.3.4、10.0.0.0/8）；留空表示不限制" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="keyForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="keyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="keySubmitting" @click="submitKey">保存</el-button>
      </template>
    </el-dialog>

    <!-- 创建成功提示密钥对话框 -->
    <el-dialog v-model="newKeyDialogVisible" title="密钥已创建" width="560px">
      <el-alert type="warning" :closable="false" style="margin-bottom: 12px"
        title="请立即复制保存，密钥不会再次完整展示（可通过列表中的查看按钮再次查看）" />
      <div class="mono new-key-box">{{ newKeyValue }}</div>
      <template #footer>
        <el-button type="primary" @click="copyKey(newKeyValue)"><i class="fas fa-copy"></i> 复制</el-button>
        <el-button @click="newKeyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 调用详情对话框 -->
    <el-dialog v-model="logDetailVisible" title="调用详情" width="720px" destroy-on-close>
      <template v-if="logDetail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="时间">{{ logDetail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="密钥">{{ logDetail.api_key_name }}</el-descriptions-item>
          <el-descriptions-item label="端点">{{ logDetail.endpoint }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ logDetail.model_requested }} → {{ logDetail.model_used }}</el-descriptions-item>
          <el-descriptions-item label="Token">{{ logDetail.tokens_used }}（↑{{ logDetail.prompt_tokens }} / ↓{{ logDetail.completion_tokens }}）</el-descriptions-item>
          <el-descriptions-item label="缓存Token">写入 {{ logDetail.cache_creation_tokens }} / 命中 {{ logDetail.cache_read_tokens }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ logDetail.elapsed }}s</el-descriptions-item>
          <el-descriptions-item label="调用方IP">{{ logDetail.caller_ip }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="logDetail.error_msg" style="margin-top: 12px">
          <el-alert type="error" :closable="false" :title="logDetail.error_msg" />
        </div>
        <div style="margin-top: 12px">
          <div style="font-weight: 600; margin-bottom: 6px">用户本次指令</div>
          <div class="msg-item" style="white-space: pre-wrap">{{ lastUserMessage || '（无）' }}</div>
        </div>
        <div style="margin-top: 12px">
          <div style="font-weight: 600; margin-bottom: 6px">AI 回复</div>
          <div class="msg-item" style="white-space: pre-wrap">{{ logDetail.response_content || '（空）' }}</div>
        </div>
        <div style="margin-top: 12px">
          <el-collapse>
            <el-collapse-item :title="`完整对话内容（${(logDetail.messages || []).length}条，点击展开）`" name="messages">
              <div v-for="(m, i) in logDetail.messages" :key="i" class="msg-item">
                <el-tag size="small" :type="m.role === 'user' ? 'primary' : (m.role === 'assistant' ? 'success' : 'info')">{{ m.role }}</el-tag>
                <span style="margin-left: 8px; white-space: pre-wrap">{{ m.content }}</span>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const activeTab = ref('settings')

// ===== 设置 =====
const settings = reactive({ enabled: false, endpoint_mode: 'both' })
const settingsLoading = ref(false)
const settingsSaving = ref(false)

async function fetchSettings() {
  settingsLoading.value = true
  try {
    const res = await api.openApi.getSettings()
    Object.assign(settings, res.data || {})
  } catch { /* 拦截器已提示 */ } finally { settingsLoading.value = false }
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    const res = await api.openApi.saveSettings({ enabled: settings.enabled, endpoint_mode: settings.endpoint_mode })
    Object.assign(settings, res.data || {})
    ElMessage.success('设置已保存')
  } catch { /* 拦截器已提示 */ } finally { settingsSaving.value = false }
}

// ===== 密钥管理 =====
const keys = ref([])
const keysLoading = ref(false)
const revealedKeys = reactive({})
const aiConfigs = ref([])
const keyDialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const keySubmitting = ref(false)
const keyFormRef = ref(null)
const newKeyDialogVisible = ref(false)
const newKeyValue = ref('')

const defaultKeyForm = { name: '', model_mapping: [], ip_whitelist_text: '', is_active: true }
const keyForm = reactive({ ...defaultKeyForm })
const keyRules = { name: [{ required: true, message: '请输入名称', trigger: 'blur' }] }

async function fetchKeys() {
  keysLoading.value = true
  try {
    const res = await api.openApi.listKeys()
    keys.value = res.data || []
  } catch { keys.value = [] } finally { keysLoading.value = false }
}

async function fetchAiConfigs() {
  try {
    const res = await api.ai.getConfigs()
    aiConfigs.value = (res.data || []).filter(c => c.is_active)
  } catch { aiConfigs.value = [] }
}

function openKeyDialog(row) {
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(keyForm, {
      name: row.name,
      model_mapping: (row.model_mapping || []).map(m => ({ ...m })),
      ip_whitelist_text: (row.ip_whitelist || []).join('\n'),
      is_active: row.is_active,
    })
  } else {
    isEdit.value = false
    editId.value = null
    Object.assign(keyForm, JSON.parse(JSON.stringify(defaultKeyForm)))
  }
  keyDialogVisible.value = true
}

async function submitKey() {
  try { await keyFormRef.value.validate() } catch { return }
  const mapping = keyForm.model_mapping.filter(m => m.external.trim() && m.config_id)
  if (keyForm.model_mapping.some(m => (m.external.trim() || m.config_id) && !(m.external.trim() && m.config_id))) {
    ElMessage.warning('模型映射行需同时填写外部模型名和内部模型')
    return
  }
  const ips = keyForm.ip_whitelist_text.split('\n').map(s => s.trim()).filter(Boolean)
  const payload = { name: keyForm.name, model_mapping: mapping, ip_whitelist: ips, is_active: keyForm.is_active }

  keySubmitting.value = true
  try {
    if (isEdit.value) {
      await api.openApi.updateKey(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      const res = await api.openApi.createKey(payload)
      if (res.data?.api_key) {
        newKeyValue.value = res.data.api_key
        newKeyDialogVisible.value = true
      }
      ElMessage.success('创建成功')
    }
    keyDialogVisible.value = false
    fetchKeys()
  } catch { /* 拦截器已提示 */ } finally { keySubmitting.value = false }
}

async function handleRevealKey(row) {
  if (revealedKeys[row.id]) { delete revealedKeys[row.id]; return }
  try {
    const res = await api.openApi.revealKey(row.id)
    if (res.data?.api_key) revealedKeys[row.id] = res.data.api_key
  } catch { /* 拦截器已提示 */ }
}

function copyKey(val) {
  navigator.clipboard?.writeText(val).then(() => ElMessage.success('已复制')).catch(() => ElMessage.warning('复制失败，请手动复制'))
}

async function handleRegenerate(id) {
  try {
    const res = await api.openApi.regenerateKey(id)
    if (res.data?.api_key) {
      newKeyValue.value = res.data.api_key
      newKeyDialogVisible.value = true
    }
    delete revealedKeys[id]
    fetchKeys()
  } catch { /* 拦截器已提示 */ }
}

async function handleDeleteKey(id) {
  try {
    await api.openApi.deleteKey(id)
    ElMessage.success('删除成功')
    fetchKeys()
  } catch { /* 拦截器已提示 */ }
}

async function handleTestKey(row) {
  try {
    const res = await api.openApi.testKey(row.id)
    const d = res.data || {}
    if (d.ok) ElMessage.success('密钥配置有效')
    else ElMessage.warning('配置存在问题：' + (!d.key_active ? '密钥已禁用；' : '') + (!d.strategy_available ? '无可用模型路由；' : '') + '详见映射校验')
  } catch { /* 拦截器已提示 */ }
}

// ===== 调用记录 =====
const logs = ref([])
const logsLoading = ref(false)
const logTotal = ref(0)
const logFilter = reactive({ page: 1, per_page: 20, api_key_id: null, status: '' })
const logTimeRange = ref(null)
const logDetail = ref(null)
const logDetailVisible = ref(false)
const stats = ref({})

async function fetchLogs() {
  logsLoading.value = true
  try {
    const params = { page: logFilter.page, per_page: logFilter.per_page }
    if (logFilter.api_key_id) params.api_key_id = logFilter.api_key_id
    if (logFilter.status) params.status = logFilter.status
    if (logTimeRange && logTimeRange.value && logTimeRange.value.length === 2) {
      params.start_time = logTimeRange.value[0].toISOString()
      params.end_time = logTimeRange.value[1].toISOString()
    }
    const res = await api.openApi.getLogs(params)
    logs.value = res.data || []
    logTotal.value = res.total || 0
  } catch { logs.value = [] } finally { logsLoading.value = false }
}

async function fetchStats() {
  try {
    const res = await api.openApi.getStats()
    stats.value = res.data || {}
  } catch { stats.value = {} }
}

async function showLogDetail(id) {
  try {
    const res = await api.openApi.getLogDetail(id)
    logDetail.value = res.data
    logDetailVisible.value = true
  } catch { /* 拦截器已提示 */ }
}

// 用户本次指令：取对话中最后一条user消息（agent场景最后一条可能是tool结果）
const lastUserMessage = computed(() => {
  const msgs = logDetail.value?.messages || []
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') return msgs[i].content
  }
  return ''
})

async function handleDeleteLog(id) {
  try {
    await api.openApi.deleteLog(id)
    ElMessage.success('删除成功')
    fetchLogs()
    fetchStats()
  } catch { /* 拦截器已提示 */ }
}

onMounted(() => {
  fetchSettings()
  fetchKeys()
  fetchAiConfigs()
  fetchLogs()
  fetchStats()
})
</script>

<style scoped>
.open-api-manager {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.form-tip {
  font-size: 12px;
  color: #999;
  line-height: 1.4;
  margin-top: 2px;
}
.example-block {
  max-width: 720px;
}
.example-title {
  font-weight: 600;
  margin-bottom: 6px;
  font-size: 13px;
}
.example-code {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: Consolas, Monaco, monospace;
}
.mono {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
}
.new-key-box {
  background: #f5f7fa;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  padding: 14px;
  word-break: break-all;
  user-select: all;
}
.stat-box {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 12px;
  text-align: center;
}
.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
}
.stat-label {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.msg-item {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 8px 10px;
  margin-bottom: 6px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
</style>
