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
        <el-table-column label="角色" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.agent_role === 'supervisor'" type="warning" size="small">监督者</el-tag>
            <el-tag v-else-if="row.agent_role === 'executor'" type="primary" size="small">执行者</el-tag>
            <el-tag v-else type="info" size="small">通用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="授权确认" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.agent_role === 'supervisor' && row.can_confirm_execution" type="success" size="small">已授权</el-tag>
            <span v-else style="color: #c0c4cc; font-size: 12px">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="启用工具" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="!row.enabled_tools" type="info" size="small">全部</el-tag>
            <el-tag v-else size="small">{{ row.enabled_tools.length }}个</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="MCP" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.mcp_server_ids && row.mcp_server_ids.length" size="small" type="warning">{{ row.mcp_server_ids.length }}个</el-tag>
            <span v-else style="color: #999; font-size: 12px">无</span>
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
        <el-form-item label="角色">
          <div style="width: 100%">
            <el-radio-group v-model="form.agent_role">
              <el-radio-button label="general">通用</el-radio-button>
              <el-radio-button label="executor">执行者</el-radio-button>
              <el-radio-button label="supervisor">监督者</el-radio-button>
            </el-radio-group>
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              通用：独立处理工单/对话；执行者：多Agent协作中负责执行工单任务；监督者：多Agent协作中负责审查执行者的处理结果是否满足要求
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'supervisor'" label="授权确认执行">
          <div style="width: 100%">
            <el-switch v-model="form.can_confirm_execution" />
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              授权后，该Agent作为监督者时，工单进入「待确认」状态（如SQL数据变更、生产环境代付提现）可直接由监督者审查并确认/拒绝执行，无需提交者人工介入
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'supervisor'" label="智能重试处理">
          <div style="width: 100%">
            <el-switch v-model="form.can_retry_processing" />
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              授权后，当工单在AI处理过程中疑似中断（处理超过10分钟无进展），监督者将自动评估并决定是否重新触发AI处理，或放弃重试转为人工介入
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'supervisor'" label="自动验收结束">
          <div style="width: 100%">
            <el-switch v-model="form.can_close_ticket" />
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              授权后，当执行者完成任务（工单变为「已处理」），监督者将自动最终验收并决定是否结束工单，无需提交者手动确认结束
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'supervisor'" label="最大监督轮次">
          <div style="width: 100%">
            <el-input-number v-model="form.max_supervisor_rounds" :min="1" :max="20" :step="1" step-strictly style="width: 180px" />
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              执行者与监督者循环协作的最大轮数，超过后强制完结并注明未完全验收（默认3轮，建议3-5轮）
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'executor'" label="对话复核">
          <div style="width: 100%">
            <el-switch v-model="form.enable_chat_review" />
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              开启后，该执行者Agent在对话中的每次回复都会由监督者Agent复核（准确性、态度等），复核不通过将鞭答执行者重新生成。需要系统中存在活跃的监督者角色Agent
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'executor' && form.enable_chat_review" label="默认监督者">
          <div style="width: 100%">
            <el-select v-model="form.default_supervisor_id" placeholder="不指定则使用全局默认监督者" clearable style="width: 100%">
              <el-option
                v-for="s in supervisorAgents"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              为该执行者指定默认的监督者Agent，不指定则使用系统中全局默认的监督者
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="form.agent_role === 'executor' && form.enable_chat_review" label="复核规则">
          <div style="width: 100%">
            <el-input v-model="form.review_rules" type="textarea" :rows="6" placeholder="自定义复核规则，监督者会按此规则评估执行者的回复质量。&#10;&#10;例如：&#10;1. 评估回复态度是否谦逊、专业，装逼飘了要鞭答改正&#10;2. 检查是否完整回答了用户问题，有无遗漏&#10;3. 验证数据是否与工具执行结果一致，严禁编造" />
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 4px;">
              自定义复核规则，监督者会严格按照此规则评估执行者回复。不填写则使用系统默认规则（准确性+态度评估）
            </div>
          </div>
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
        <el-form-item label="MCP 服务">
          <div style="width: 100%">
            <el-select v-model="form.mcp_server_ids" multiple filterable clearable placeholder="选择授予此Agent的MCP服务（可选）" style="width: 100%">
              <el-option v-for="s in mcpServers" :key="s.id" :label="`${s.name}（${s.tools_count || 0}个工具）`" :value="s.id" />
            </el-select>
            <div style="font-size: 12px; color: #999; line-height: 1.4; margin-top: 2px;">MCP工具将追加到Agent可用工具中，在AI对话和工单AI处理中可用（管理入口：MCP 服务）</div>
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
import { ref, reactive, computed, onMounted, onActivated } from 'vue'
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
const supervisorAgents = computed(() => agents.value.filter(a => a.agent_role === 'supervisor' && a.is_active))
const selectedRows = ref([])
const tableRef = ref(null)
const useAllTools = ref(true)
const mcpServers = ref([])

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
  { name: 'request_profit_share', label: '分润导出' },
  { name: 'create_ticket', label: '创建工单' },
  { name: 'list_pay_channels', label: '列出代付渠道' },
  { name: 'request_pay_withdraw', label: '代付提现' },
  { name: 'save_skill', label: '保存技能/规则' },
  { name: 'send_email', label: '发送邮件' },
]

const defaultForm = {
  name: '',
  description: '',
  agent_role: 'general',
  can_confirm_execution: false,
  can_retry_processing: false,
  can_close_ticket: false,
  enable_chat_review: false,
  review_rules: '',
  max_supervisor_rounds: 3,
  default_supervisor_id: null,
  system_prompt: '',
  enabled_tools: null,
  mcp_server_ids: [],
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
  // 兜底：下拉数据为空时按需拉取（如首次加载失败）
  if (mcpServers.value.length === 0) {
    fetchMcpServers()
  }
  if (row) {
    isEdit.value = true
    editId.value = row.id
    Object.assign(form, {
      name: row.name,
      description: row.description || '',
      agent_role: row.agent_role || 'general',
      can_confirm_execution: !!row.can_confirm_execution,
      can_retry_processing: !!row.can_retry_processing,
      can_close_ticket: !!row.can_close_ticket,
      enable_chat_review: !!row.enable_chat_review,
      review_rules: row.review_rules || '',
      max_supervisor_rounds: row.max_supervisor_rounds || 3,
      default_supervisor_id: row.default_supervisor_id || null,
      system_prompt: row.system_prompt || '',
      enabled_tools: row.enabled_tools ? [...row.enabled_tools] : null,
      mcp_server_ids: row.mcp_server_ids ? [...row.mcp_server_ids] : [],
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

// 加载MCP服务选项（仅启用的）
function fetchMcpServers() {
  return api.mcp.list().then(res => {
    mcpServers.value = (res.data || []).filter(s => s.is_active)
  }).catch(() => {})
}

// 页面被keep-alive缓存，从MCP服务管理等页面切回时自动刷新MCP选项，
// 避免新增MCP后切回本页下拉仍为旧数据
let mcpActivatedOnce = false
onActivated(() => {
  if (!mcpActivatedOnce) {
    // 首次激活时onMounted刚拉取过，跳过
    mcpActivatedOnce = true
    return
  }
  fetchMcpServers()
})

onMounted(() => {
  fetchAgents()
  fetchMcpServers()
})
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