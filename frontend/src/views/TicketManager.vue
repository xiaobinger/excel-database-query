<template>
  <div class="ticket-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-ticket"></i> 工单管理</span>
          <div class="header-actions">
            <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 130px" @change="fetchTickets">
              <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
            </el-select>
            <el-input v-model="keyword" placeholder="搜索工单编号/标题" clearable style="width: 220px" @keyup.enter="fetchTickets" @clear="fetchTickets">
              <template #prefix><i class="fas fa-search"></i></template>
            </el-input>
            <el-button type="primary" @click="openCreateDialog">
              <i class="fas fa-plus"></i> 提交工单
            </el-button>
            <el-button @click="fetchTickets">
              <i class="fas fa-sync-alt"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="tickets" stripe v-loading="loading" style="width: 100%" @row-click="openDetail">
        <el-table-column prop="ticket_no" label="工单编号" width="150" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="creator_name" label="提交人" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.creator_name || row.creator_username || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name" label="指派人" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.assignee_type === 'ai'" style="color: #722ed1">
              <i class="fas fa-robot"></i> {{ row.assignee_name || 'AI助手' }}
            </span>
            <span v-else-if="row.assignee_name">{{ row.assignee_name }}</span>
            <span v-else style="color: #c0c4cc">未指派</span>
          </template>
        </el-table-column>
        <el-table-column prop="business_system_name" label="涉及系统" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.business_system_name" size="small" effect="plain">{{ row.business_system_name }}</el-tag>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="130" align="center">
          <template #default="{ row }">
            <!-- AI处理中：带动画的特殊标签 -->
            <span v-if="row.assignee_type === 'ai' && row.status === 'processing'" class="ai-status-tag">
              <i class="fas fa-robot fa-spin"></i> AI处理中
            </span>
            <!-- AI待确认：橙色警告标签 -->
            <el-tag v-else-if="row.assignee_type === 'ai' && row.status === 'pending_confirmation'" type="warning" effect="dark" size="small">
              <i class="fas fa-exclamation-triangle"></i> 待确认
            </el-tag>
            <el-tag v-else :type="statusTagType(row.status)" size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" width="170" show-overflow-tooltip />
        <el-table-column prop="processed_at" label="处理时间" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.processed_at">{{ row.processed_at }}</span>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click.stop="openDetail(row)">
              <i class="fas fa-eye"></i> 详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-area">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchTickets"
          @current-change="fetchTickets"
        />
      </div>

      <el-empty v-if="!loading && tickets.length === 0" description="暂无工单" />
    </el-card>

    <!-- 创建工单对话框 -->
    <el-dialog v-model="createVisible" title="提交工单" width="780px" destroy-on-close top="5vh">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="createForm.title" placeholder="请输入工单标题" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="涉及系统" prop="business_system_id">
          <el-select v-model="createForm.business_system_id" placeholder="选择涉及的业务系统（可选）" clearable filterable style="width: 100%">
            <el-option v-for="s in businessSystems" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="指派类型" prop="assignee_type">
          <el-radio-group v-model="createForm.assignee_type">
            <el-radio-button label="user">指派给具体人</el-radio-button>
            <el-radio-button label="ai">指派给AI</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="createForm.assignee_type === 'user'" label="指派给" prop="assignee_id">
          <el-select v-model="createForm.assignee_id" placeholder="选择处理人" filterable style="width: 100%">
            <el-option v-for="u in assignees" :key="u.id" :label="u.display_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="AI Agent" prop="assignee_agent_id">
          <el-select v-if="canSwitchAgent" v-model="createForm.assignee_agent_id" placeholder="选择AI Agent（留空使用默认）" clearable filterable style="width: 100%">
            <el-option v-for="a in aiAgents" :key="a.id" :label="a.name + (a.is_default ? '（默认）' : '')" :value="a.id" />
          </el-select>
          <div v-else class="form-tip">
            <i class="fas fa-info-circle"></i> 将指派给默认AI Agent自动处理（无切换Agent权限）
          </div>
          <div v-if="canSwitchAgent" class="form-tip"><i class="fas fa-info-circle"></i> 指派给AI后，AI将自动处理该工单。处理失败会转为"待指派"状态。</div>
        </el-form-item>
        <el-form-item label="工单内容" prop="content">
          <MarkdownEditor v-model="createForm.content" :upload-fn="uploadAttachment" placeholder="详细描述工单内容，支持图片、视频和 Markdown 格式" :height="280" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">提交工单</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情对话框 -->
    <el-dialog v-model="detailVisible" :title="`工单详情 - ${detailData.ticket_no || ''}`" width="900px" destroy-on-close top="3vh" @close="stopAiPolling">
      <div class="detail-content" v-loading="detailLoading">
        <!-- 状态进度条 -->
        <div class="status-progress">
          <el-steps :active="currentStep" finish-status="success" align-center>
            <el-step title="已提交" :description="detailData.submitted_at" />
            <el-step title="已接收" :description="detailData.received_at" />
            <el-step title="已处理" :description="detailData.processed_at" />
            <el-step title="结束" :description="detailData.closed_at" />
          </el-steps>
          <div v-if="detailData.status === 'rejected'" class="rejected-banner">
            <i class="fas fa-ban"></i> 工单已被拒绝：
            <span v-if="detailData.reject_reason">{{ detailData.reject_reason }}</span>
          </div>
          <div v-if="detailData.status === 'pending_assignment'" class="pending-banner">
            <i class="fas fa-exclamation-triangle"></i> AI处理失败，工单待重新指派：
            <span v-if="detailData.assignee_type === 'ai'">请重新指派给具体的人进行人工介入处理</span>
          </div>
          <!-- AI处理中提示 -->
          <div v-if="isAiProcessing" class="ai-processing-banner">
            <i class="fas fa-robot fa-spin"></i>
            <div class="ai-processing-info">
              <div class="ai-processing-title">AI正在处理中，请稍候...</div>
              <div class="ai-processing-meta">
                <span v-if="aiElapsedText" class="ai-processing-elapsed">
                  <i class="fas fa-clock"></i> 已处理：{{ aiElapsedText }}
                </span>
                <span class="ai-processing-hint">页面会自动刷新，处理完成后会通知您</span>
              </div>
            </div>
          </div>
          <!-- 待确认执行提示 -->
          <div v-if="isPendingConfirmation" class="pending-confirmation-banner">
            <i class="fas fa-exclamation-triangle"></i>
            <div class="pending-confirmation-info">
              <div class="pending-confirmation-title">⚠️ AI需执行数据变更操作，等待您确认</div>
              <div class="pending-confirmation-detail" v-if="detailData.pending_action">
                任务：{{ detailData.pending_action.task_name }} | 参数：{{ JSON.stringify(detailData.pending_action.params_values) }}
              </div>
              <div class="pending-confirmation-hint">请在下方评论「同意」或「确认执行」，或点击下方按钮确认执行</div>
            </div>
          </div>
        </div>

        <el-descriptions :column="2" border size="small" style="margin-top: 16px">
          <el-descriptions-item label="工单编号">{{ detailData.ticket_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detailData.status)" size="small">{{ statusLabels[detailData.status] || detailData.status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="标题" :span="2">{{ detailData.title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="提交人">{{ detailData.creator_name || detailData.creator_username || '-' }}</el-descriptions-item>
          <el-descriptions-item label="指派人">
            <span v-if="detailData.assignee_type === 'ai'" style="color: #722ed1">
              <i class="fas fa-robot"></i> {{ detailData.assignee_name || 'AI助手' }}
            </span>
            <span v-else>{{ detailData.assignee_name || detailData.assignee_username || '未指派' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="涉及系统">
            <el-tag v-if="detailData.business_system_name" size="small" effect="plain">{{ detailData.business_system_name }}</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ detailData.submitted_at || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 工单内容 -->
        <el-divider content-position="left">工单内容</el-divider>
        <div class="ticket-content" v-html="renderMarkdown(detailData.content)"></div>

        <!-- AI处理结果 -->
        <div v-if="detailData.ai_result" class="reason-block ai-result">
          <div class="reason-title"><i class="fas fa-robot"></i> AI处理结果</div>
          <div class="reason-content" v-html="renderMarkdown(detailData.ai_result)"></div>
        </div>

        <!-- 拒绝/申诉信息 -->
        <div v-if="detailData.reject_reason" class="reason-block reject">
          <div class="reason-title"><i class="fas fa-ban"></i> 拒绝原因</div>
          <div class="reason-content" v-html="renderMarkdown(detailData.reject_reason)"></div>
        </div>
        <div v-if="detailData.appeal_reason" class="reason-block appeal">
          <div class="reason-title"><i class="fas fa-gavel"></i> 申诉理由</div>
          <div class="reason-content" v-html="renderMarkdown(detailData.appeal_reason)"></div>
        </div>

        <!-- 操作按钮区 -->
        <el-divider content-position="left">操作</el-divider>
        <div class="action-bar">
          <!-- 指派人操作 -->
          <template v-if="isAssignee">
            <el-button v-if="detailData.status === 'submitted'" type="primary" @click="handleAction('receive')">
              <i class="fas fa-check"></i> 接收工单
            </el-button>
            <el-button v-if="detailData.status === 'received'" type="primary" @click="handleAction('process')">
              <i class="fas fa-cog"></i> 开始处理
            </el-button>
            <el-button v-if="detailData.status === 'processing'" type="success" @click="handleAction('complete')">
              <i class="fas fa-check-double"></i> 完成处理
            </el-button>
            <el-button v-if="['submitted', 'received'].includes(detailData.status)" type="danger" @click="openReasonDialog('reject')">
              <i class="fas fa-ban"></i> 拒绝
            </el-button>
          </template>
          <!-- 提交人操作 -->
          <template v-if="isCreator">
            <el-button v-if="detailData.status === 'processed'" type="success" @click="handleAction('confirm')">
              <i class="fas fa-check-circle"></i> 核实通过
            </el-button>
            <el-button v-if="detailData.status === 'processed'" type="warning" @click="openReassignDialog('reopen')">
              <i class="fas fa-redo"></i> 重新发起
            </el-button>
            <el-button v-if="detailData.status === 'rejected'" type="primary" @click="openReasonDialog('appeal')">
              <i class="fas fa-gavel"></i> 申诉重启
            </el-button>
            <!-- 待指派：提交人重新指派 -->
            <el-button v-if="detailData.status === 'pending_assignment'" type="primary" @click="openReassignDialog('reassign')">
              <i class="fas fa-user-plus"></i> 重新指派
            </el-button>
            <!-- 待确认：提交人确认执行或取消 -->
            <el-button v-if="detailData.status === 'pending_confirmation'" type="success" @click="handleConfirmAction">
              <i class="fas fa-check-circle"></i> 确认执行
            </el-button>
            <el-button v-if="detailData.status === 'pending_confirmation'" type="warning" @click="handleCancelAction">
              <i class="fas fa-times-circle"></i> 取消执行
            </el-button>
            <el-button v-if="detailData.status === 'pending_confirmation'" type="primary" @click="openReassignDialog('reassign')">
              <i class="fas fa-user-plus"></i> 重新指派
            </el-button>
          </template>
          <!-- 管理员也可重新指派 -->
          <el-button v-if="isAdmin && detailData.status === 'pending_assignment' && !isCreator" type="primary" @click="openReassignDialog('reassign')">
            <i class="fas fa-user-plus"></i> 重新指派
          </el-button>
          <!-- 重试AI处理（指派给AI且处于待指派/已提交状态） -->
          <el-button v-if="detailData.assignee_type === 'ai' && detailData.status === 'pending_assignment'" type="warning" plain @click="handleRetryAi">
            <i class="fas fa-redo"></i> 重试AI处理
          </el-button>
          <!-- 管理员操作 -->
          <el-button v-if="isAdmin && detailData.status !== 'closed'" type="info" @click="handleAction('close')">
            <i class="fas fa-times-circle"></i> 关闭工单
          </el-button>
          <el-popconfirm v-if="isAdmin" title="确定删除此工单？此操作不可恢复" @confirm="handleDelete">
            <template #reference>
              <el-button type="danger" plain><i class="fas fa-trash"></i> 删除</el-button>
            </template>
          </el-popconfirm>
        </div>

        <!-- 评论列表 -->
        <el-divider content-position="left">评论 ({{ (detailData.comments || []).length }})</el-divider>
        <div class="comments-list">
          <div v-if="!detailData.comments || detailData.comments.length === 0" class="no-comments">暂无评论</div>
          <div v-for="c in detailData.comments" :key="c.id" class="comment-item" :class="c.action">
            <div class="comment-avatar">
              <i :class="commentActionIcon(c.action)"></i>
            </div>
            <div class="comment-body">
              <div class="comment-head">
                <span class="comment-author">{{ c.user_name || c.user_username || '未知' }}</span>
                <el-tag v-if="c.action !== 'comment'" :type="commentActionTagType(c.action)" size="small" effect="plain">
                  {{ commentActionLabel(c.action) }}
                </el-tag>
                <span class="comment-time">{{ c.created_at }}</span>
              </div>
              <div class="comment-content" v-html="renderMarkdown(c.content)"></div>
            </div>
          </div>
        </div>

        <!-- 添加评论 -->
        <div class="comment-input-area">
          <MarkdownEditor v-model="commentText" :upload-fn="uploadAttachment" :placeholder="commentPlaceholder" :height="120" :toolbar="true" />
          <el-button type="primary" :loading="commenting" :disabled="!commentText.trim()" @click="submitComment" style="margin-top: 8px">
            <i class="fas fa-paper-plane"></i> 发表评论
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 拒绝/申诉原因对话框 -->
    <el-dialog v-model="reasonVisible" :title="reasonTitle" width="600px" append-to-body destroy-on-close>
      <el-form :model="reasonForm">
        <el-form-item label="原因说明" required>
          <MarkdownEditor v-model="reasonForm.reason" :upload-fn="uploadAttachment" :placeholder="reasonPlaceholder" :height="180" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reasonVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="submitReason">确认</el-button>
      </template>
    </el-dialog>

    <!-- 重新指派/重新发起来 对话框 -->
    <el-dialog v-model="reassignVisible" :title="reassignAction === 'reopen' ? '重新发起工单' : '重新指派工单'" width="520px" append-to-body destroy-on-close>
      <el-form :model="reassignForm" label-width="90px">
        <el-form-item label="指派类型">
          <el-radio-group v-model="reassignForm.assignee_type">
            <el-radio-button label="user">指派给具体人</el-radio-button>
            <el-radio-button label="ai">指派给AI</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="reassignForm.assignee_type === 'user'" label="指派给" required>
          <el-select v-model="reassignForm.assignee_id" placeholder="选择处理人" filterable style="width: 100%">
            <el-option v-for="u in assignees" :key="u.id" :label="u.display_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="AI Agent">
          <el-select v-if="canSwitchAgent" v-model="reassignForm.assignee_agent_id" placeholder="选择AI Agent（留空使用默认）" clearable filterable style="width: 100%">
            <el-option v-for="a in aiAgents" :key="a.id" :label="a.name + (a.is_default ? '（默认）' : '')" :value="a.id" />
          </el-select>
          <div v-else class="form-tip">
            <i class="fas fa-info-circle"></i> 将指派给默认AI Agent自动处理（无切换Agent权限）
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="submitReassign">确认指派</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import MarkdownEditor from '../components/MarkdownEditor.vue'

const store = useAppStore()
const isAdmin = computed(() => store.isAdmin)

// 状态配置
const statusLabels = {
  submitted: '已提交',
  received: '已接收',
  processing: '处理中',
  rejected: '拒绝',
  processed: '已处理',
  pending_assignment: '待指派',
  pending_confirmation: '待确认',
  closed: '结束',
}

const statusTagType = (status) => {
  const map = {
    submitted: 'info',
    received: 'warning',
    processing: 'warning',
    rejected: 'danger',
    processed: 'success',
    pending_assignment: 'danger',
    pending_confirmation: 'warning',
    closed: '',
  }
  return map[status] || 'info'
}

// 列表数据
const loading = ref(false)
const tickets = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const keyword = ref('')

// 列表中是否有AI处理中的工单（用于自动轮询刷新）
const hasAiProcessing = computed(() =>
  tickets.value.some(t => t.assignee_type === 'ai' && t.status === 'processing')
)

// 列表自动轮询定时器（仅当有AI处理中的工单时启动）
let listPollingTimer = null
function startListPolling() {
  stopListPolling()
  listPollingTimer = setInterval(() => {
    if (!hasAiProcessing.value) {
      stopListPolling()
      return
    }
    fetchTickets(true) // 静默刷新
  }, 5000)
}
function stopListPolling() {
  if (listPollingTimer) {
    clearInterval(listPollingTimer)
    listPollingTimer = null
  }
}

async function fetchTickets(silent = false) {
  if (!silent) loading.value = true
  try {
    const params = { page: currentPage.value, per_page: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    const res = await api.tickets.list(params)
    const data = res.data || res || {}
    const oldList = tickets.value
    tickets.value = Array.isArray(data) ? data : (data.data || [])
    total.value = data.total || tickets.value.length
    // 静默刷新时：检测是否有工单从AI处理中变为已完成，给出提示
    if (silent && oldList.length) {
      const oldAiProcessing = new Set(
        oldList.filter(t => t.assignee_type === 'ai' && t.status === 'processing').map(t => t.id)
      )
      const changed = tickets.value.filter(t => oldAiProcessing.has(t.id))
      for (const t of changed) {
        if (t.status === 'processed') {
          ElMessage.success(`工单 ${t.ticket_no} AI已处理完成`)
        } else if (t.status === 'pending_assignment') {
          ElMessage.warning(`工单 ${t.ticket_no} AI处理失败，已转为待指派`)
        }
      }
    }
    // 根据是否有AI处理中的工单，启动或停止列表轮询
    if (hasAiProcessing.value) {
      startListPolling()
    } else {
      stopListPolling()
    }
  } catch {
    if (!silent) {
      tickets.value = []
      total.value = 0
    }
  } finally {
    if (!silent) loading.value = false
  }
}

// 创建工单
const createVisible = ref(false)
const submitting = ref(false)
const createFormRef = ref(null)
const createForm = ref({ title: '', content: '', assignee_type: 'user', assignee_id: null, assignee_agent_id: null, business_system_id: null })
const createRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入工单内容', trigger: 'blur' }],
}
const assignees = ref([])
const businessSystems = ref([])
const aiAgents = ref([])
const canSwitchAgent = ref(false)

async function openCreateDialog() {
  createForm.value = { title: '', content: '', assignee_type: 'user', assignee_id: null, assignee_agent_id: null, business_system_id: null }
  createVisible.value = true
  // 并行加载选项数据
  Promise.all([fetchAssignees(), fetchBusinessSystems(), fetchAiAgents()])
}

async function fetchAssignees() {
  if (assignees.value.length > 0) return
  try {
    const res = await api.tickets.assignees()
    assignees.value = res.data || res || []
  } catch {}
}

async function fetchBusinessSystems() {
  if (businessSystems.value.length > 0) return
  try {
    const res = await api.business.listSystems()
    const data = res.data || res || []
    businessSystems.value = Array.isArray(data) ? data : (data.data || [])
  } catch {}
}

async function fetchAiAgents() {
  try {
    const res = await api.tickets.aiAgents()
    aiAgents.value = res.data || []
    canSwitchAgent.value = res.can_switch_agent || false
  } catch {
    aiAgents.value = []
    canSwitchAgent.value = false
  }
}

async function submitCreate() {
  if (!createFormRef.value) return
  // 根据指派类型校验
  if (createForm.value.assignee_type === 'user' && !createForm.value.assignee_id) {
    ElMessage.warning('请选择指派人')
    return
  }
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      // 构造提交数据（按指派类型清理字段）
      const payload = { ...createForm.value }
      if (payload.assignee_type === 'ai') {
        delete payload.assignee_id
      } else {
        delete payload.assignee_agent_id
      }
      await api.tickets.create(payload)
      ElMessage.success('工单已提交')
      createVisible.value = false
      fetchTickets()
    } catch (e) {
      ElMessage.error(e?.response?.data?.message || '提交失败')
    } finally {
      submitting.value = false
    }
  })
}

// 详情
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref({})
// AI处理中轮询定时器
let aiPollingTimer = null
// AI处理时长计时器（每秒更新，用于显示已处理时长）
let aiElapsedTimer = null
const aiElapsedSeconds = ref(0)

// 计算AI已处理时长（基于received_at）
const aiElapsedText = computed(() => {
  const secs = aiElapsedSeconds.value
  if (secs <= 0) return ''
  if (secs < 60) return `${secs}秒`
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}分${s.toString().padStart(2, '0')}秒`
})

function startAiElapsedTimer() {
  stopAiElapsedTimer()
  // 根据received_at初始化已处理时长（后端返回北京时间ISO格式）
  const receivedAt = detailData.value.received_at
  if (receivedAt) {
    const start = new Date(receivedAt).getTime()
    const now = Date.now()
    aiElapsedSeconds.value = isNaN(start) ? 0 : Math.max(0, Math.floor((now - start) / 1000))
  } else {
    aiElapsedSeconds.value = 0
  }
  aiElapsedTimer = setInterval(() => {
    aiElapsedSeconds.value += 1
  }, 1000)
}

function stopAiElapsedTimer() {
  if (aiElapsedTimer) {
    clearInterval(aiElapsedTimer)
    aiElapsedTimer = null
  }
  aiElapsedSeconds.value = 0
}

const isAssignee = computed(() => detailData.value.assignee_id === store.user?.id)
const isCreator = computed(() => detailData.value.created_by === store.user?.id)
// 是否AI处理中（用于显示进度提示和轮询）
const isAiProcessing = computed(() =>
  detailData.value.assignee_type === 'ai' && detailData.value.status === 'processing'
)

// 是否待确认执行（AI需执行数据变更操作，等待提交人确认）
const isPendingConfirmation = computed(() =>
  detailData.value.assignee_type === 'ai' && detailData.value.status === 'pending_confirmation'
)

// 进度条当前步骤
const currentStep = computed(() => {
  const s = detailData.value.status
  if (s === 'submitted') return 0
  if (s === 'received' || s === 'processing') return 1
  if (s === 'processed') return 2
  if (s === 'closed') return 3
  if (s === 'rejected') return 0
  if (s === 'pending_assignment') return 0
  return 0
})

// 启动AI处理轮询
function startAiPolling() {
  stopAiPolling()
  startAiElapsedTimer()
  aiPollingTimer = setInterval(async () => {
    if (!detailData.value.id || !detailVisible.value) {
      stopAiPolling()
      return
    }
    try {
      const res = await api.tickets.get(detailData.value.id)
      const newData = res.data || res || {}
      detailData.value = newData
      // AI处理完成（状态不再是processing），停止轮询并刷新列表
      if (!(newData.assignee_type === 'ai' && newData.status === 'processing')) {
        stopAiPolling()
        fetchTickets()
        if (newData.status === 'processed') {
          ElMessage.success('AI已处理完成')
        } else if (newData.status === 'pending_assignment') {
          ElMessage.warning('AI处理失败，工单已转为待指派状态')
        }
      }
    } catch {}
  }, 3000)
}

// 停止AI处理轮询
function stopAiPolling() {
  if (aiPollingTimer) {
    clearInterval(aiPollingTimer)
    aiPollingTimer = null
  }
  stopAiElapsedTimer()
}

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = {}
  commentText.value = ''
  stopAiPolling()
  try {
    const res = await api.tickets.get(row.id)
    detailData.value = res.data || res || {}
    // 如果是AI处理中，启动轮询
    if (isAiProcessing.value) {
      startAiPolling()
    }
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function refreshDetail() {
  if (!detailData.value.id) return
  try {
    const res = await api.tickets.get(detailData.value.id)
    detailData.value = res.data || res || {}
    // 如果是AI处理中，启动轮询
    if (isAiProcessing.value) {
      startAiPolling()
    } else {
      stopAiPolling()
    }
  } catch {}
}

// 状态操作
const actionLoading = ref(false)

async function handleAction(action) {
  const actionLabels = {
    receive: '接收',
    process: '开始处理',
    complete: '完成处理',
    confirm: '核实通过',
    close: '关闭工单',
  }
  try {
    await ElMessageBox.confirm(`确定要执行「${actionLabels[action]}」操作吗？`, '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: action === 'close' ? 'warning' : 'info',
    })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    const res = await api.tickets.updateStatus(detailData.value.id, { action })
    ElMessage.success(res.message || '操作成功')
    detailData.value = res.data || detailData.value
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

// 拒绝/申诉原因对话框
const reasonVisible = ref(false)
const reasonForm = ref({ reason: '' })
const reasonAction = ref('')
const reasonTitle = computed(() => reasonAction.value === 'reject' ? '拒绝工单' : '申诉重启')
const reasonPlaceholder = computed(() => reasonAction.value === 'reject' ? '请详细说明拒绝原因（必填）' : '请说明申诉重启的理由（必填）')

function openReasonDialog(action) {
  reasonAction.value = action
  reasonForm.value = { reason: '' }
  reasonVisible.value = true
}

async function submitReason() {
  if (!reasonForm.value.reason.trim()) {
    ElMessage.warning('请填写原因')
    return
  }
  actionLoading.value = true
  try {
    const res = await api.tickets.updateStatus(detailData.value.id, {
      action: reasonAction.value,
      reason: reasonForm.value.reason,
    })
    ElMessage.success(res.message || '操作成功')
    reasonVisible.value = false
    detailData.value = res.data || detailData.value
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

// 重新指派/重新发起 对话框
const reassignVisible = ref(false)
const reassignForm = ref({ assignee_type: 'user', assignee_id: null, assignee_agent_id: null })
const reassignAction = ref('reassign')

async function openReassignDialog(action = 'reassign') {
  reassignAction.value = action
  // 默认填充当前指派信息，方便用户修改
  const cur = detailData.value
  reassignForm.value = {
    assignee_type: cur.assignee_type || 'user',
    assignee_id: cur.assignee_type !== 'ai' ? cur.assignee_id : null,
    assignee_agent_id: cur.assignee_type === 'ai' ? cur.assignee_agent_id : null,
  }
  reassignVisible.value = true
  // 加载指派人和AI Agent选项
  Promise.all([fetchAssignees(), fetchAiAgents()])
}

async function submitReassign() {
  if (reassignForm.value.assignee_type === 'user' && !reassignForm.value.assignee_id) {
    ElMessage.warning('请选择指派人')
    return
  }
  actionLoading.value = true
  try {
    const payload = { action: reassignAction.value, ...reassignForm.value }
    if (payload.assignee_type === 'ai') {
      delete payload.assignee_id
    } else {
      delete payload.assignee_agent_id
    }
    const res = await api.tickets.updateStatus(detailData.value.id, payload)
    ElMessage.success(res.message || '操作成功')
    reassignVisible.value = false
    detailData.value = res.data || detailData.value
    // 如果是AI处理中，启动轮询
    if (isAiProcessing.value) {
      startAiPolling()
    }
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

// 重试AI处理
async function handleRetryAi() {
  try {
    await ElMessageBox.confirm('确定要重新触发AI处理该工单吗？', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info',
    })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    const res = await api.tickets.retryAi(detailData.value.id)
    ElMessage.success(res.message || 'AI处理已重新触发')
    refreshDetail()
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

// 确认执行待确认的数据变更操作
async function handleConfirmAction() {
  const taskName = detailData.value.pending_action?.task_name || ''
  try {
    await ElMessageBox.confirm(
      `确定要执行数据变更操作「${taskName}」吗？\n此操作会直接影响生产数据，请谨慎确认！`,
      '确认执行数据变更',
      {
        confirmButtonText: '确认执行',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }
  actionLoading.value = true
  try {
    const res = await api.tickets.confirmAction(detailData.value.id)
    ElMessage.success(res.message || '已确认执行，AI正在处理中')
    detailData.value = res.data || detailData.value
    if (isAiProcessing.value) {
      startAiPolling()
    }
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

// 取消执行待确认的数据变更操作
async function handleCancelAction() {
  try {
    await ElMessageBox.confirm('确定要取消执行此数据变更操作吗？工单将转为待指派状态。', '取消执行', {
      confirmButtonText: '确定取消',
      cancelButtonText: '再想想',
      type: 'info',
    })
  } catch {
    return
  }
  actionLoading.value = true
  try {
    const res = await api.tickets.cancelAction(detailData.value.id)
    ElMessage.success(res.message || '已取消执行')
    detailData.value = res.data || detailData.value
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  } finally {
    actionLoading.value = false
  }
}

// 评论
const commentText = ref('')
const commenting = ref(false)
// 评论输入框placeholder（待确认状态时提示可输入"同意"确认执行）
const commentPlaceholder = computed(() => {
  if (isPendingConfirmation.value && isCreator.value) {
    return '发表评论（支持 Markdown、图片、视频）。如需确认执行数据变更操作，可直接输入「同意」或「确认执行」'
  }
  return '发表评论（支持 Markdown、图片、视频）'
})

async function submitComment() {
  if (!commentText.value.trim()) return
  commenting.value = true
  try {
    await api.tickets.addComment(detailData.value.id, { content: commentText.value })
    ElMessage.success('评论已发表')
    commentText.value = ''
    refreshDetail()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '评论失败')
  } finally {
    commenting.value = false
  }
}

function commentActionLabel(action) {
  const map = { comment: '评论', reject: '拒绝', appeal: '申诉', status_change: '状态变更' }
  return map[action] || action
}

function commentActionIcon(action) {
  const map = {
    comment: 'fas fa-comment',
    reject: 'fas fa-ban',
    appeal: 'fas fa-gavel',
    status_change: 'fas fa-flag',
  }
  return map[action] || 'fas fa-comment'
}

function commentActionTagType(action) {
  const map = { comment: '', reject: 'danger', appeal: 'warning', status_change: 'info' }
  return map[action] || ''
}

// 删除
async function handleDelete() {
  try {
    await api.tickets.delete(detailData.value.id)
    ElMessage.success('工单已删除')
    detailVisible.value = false
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

// 上传附件
async function uploadAttachment(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await api.tickets.upload(formData)
  return res.data || res
}

// Markdown 渲染
function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text
  }
}

onMounted(() => {
  fetchTickets()
})

onUnmounted(() => {
  stopAiPolling()
  stopListPolling()
})
</script>

<style scoped>
.ticket-manager {
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
  gap: 8px;
}

.pagination-area {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

.detail-content {
  max-height: 78vh;
  overflow-y: auto;
  padding-right: 8px;
}

/* 状态进度条 */
.status-progress {
  padding: 12px 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.rejected-banner {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fef0f0;
  border: 1px solid #fde2e2;
  border-radius: 6px;
  color: #f56c6c;
  font-size: 13px;
}

.rejected-banner i {
  margin-right: 6px;
}

.pending-banner {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fff7e6;
  border: 1px solid #ffe7ba;
  border-radius: 6px;
  color: #fa8c16;
  font-size: 13px;
}

.pending-banner i {
  margin-right: 6px;
}

/* 待确认执行提示 */
.pending-confirmation-banner {
  margin-top: 12px;
  padding: 12px 14px;
  background: linear-gradient(90deg, #fff4e6 0%, #ffe8cc 100%);
  border: 1px solid #ffcc7a;
  border-radius: 6px;
  color: #d46b08;
  font-size: 13px;
  display: flex;
  align-items: flex-start;
}

.pending-confirmation-banner > i {
  margin-right: 10px;
  margin-top: 2px;
  font-size: 16px;
  color: #fa8c16;
}

.pending-confirmation-info {
  flex: 1;
}

.pending-confirmation-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.pending-confirmation-detail {
  font-size: 12px;
  color: #ad6800;
  margin-bottom: 4px;
  word-break: break-all;
}

.pending-confirmation-hint {
  font-size: 12px;
  color: #fa8c16;
  opacity: 0.85;
}

/* AI处理中提示 */
.ai-processing-banner {
  margin-top: 12px;
  padding: 10px 14px;
  background: linear-gradient(90deg, #f6f0ff 0%, #ece4ff 100%);
  border: 1px solid #d9d2ec;
  border-radius: 6px;
  color: #722ed1;
  font-size: 13px;
  display: flex;
  align-items: center;
}

.ai-processing-banner > i {
  margin-right: 10px;
  font-size: 18px;
}

.ai-processing-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ai-processing-title {
  font-size: 14px;
  font-weight: 500;
}

.ai-processing-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.ai-processing-elapsed {
  color: #9254de;
  font-weight: 500;
}

.ai-processing-elapsed i {
  margin-right: 4px;
}

.ai-processing-hint {
  color: #9254de;
  opacity: 0.8;
}

@keyframes fa-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.ai-processing-banner .fa-spin {
  animation: fa-spin 2s infinite linear;
}

/* 列表中AI处理中状态标签 */
.ai-status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: #722ed1;
  background: linear-gradient(90deg, #f6f0ff 0%, #ece4ff 100%);
  border: 1px solid #d9d2ec;
  white-space: nowrap;
}

.ai-status-tag .fa-spin {
  animation: fa-spin 2s infinite linear;
}

/* 表单提示 */
.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.form-tip i {
  margin-right: 4px;
  color: #409eff;
}

/* 工单内容 */
.ticket-content {
  padding: 12px 16px;
  background: #fafafa;
  border-radius: 6px;
  line-height: 1.7;
}

.ticket-content :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}

.ticket-content :deep(video) {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}

.ticket-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.ticket-content :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.ticket-content :deep(pre code) {
  background: transparent;
  padding: 0;
}

/* 拒绝/申诉原因块 */
.reason-block {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: 6px;
}

.reason-block.reject {
  background: #fef0f0;
  border: 1px solid #fde2e2;
}

.reason-block.appeal {
  background: #fdf6ec;
  border: 1px solid #faecd8;
}

.reason-block.ai-result {
  background: #f6f0ff;
  border: 1px solid #d9d2ec;
}

.reason-title {
  font-weight: 600;
  margin-bottom: 6px;
  font-size: 14px;
}

.reason-block.reject .reason-title {
  color: #f56c6c;
}

.reason-block.appeal .reason-title {
  color: #e6a23c;
}

.reason-block.ai-result .reason-title {
  color: #722ed1;
}

.reason-content {
  line-height: 1.6;
  font-size: 13px;
}

.reason-content :deep(img) {
  max-width: 100%;
  border-radius: 4px;
}

/* 操作区 */
.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px 0;
}

/* 评论 */
.comments-list {
  max-height: 320px;
  overflow-y: auto;
}

.no-comments {
  text-align: center;
  color: #c0c4cc;
  padding: 24px 0;
  font-size: 13px;
}

.comment-item {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #606266;
  flex-shrink: 0;
}

.comment-item.reject .comment-avatar {
  background: #fef0f0;
  color: #f56c6c;
}

.comment-item.appeal .comment-avatar {
  background: #fdf6ec;
  color: #e6a23c;
}

.comment-item.status_change .comment-avatar {
  background: #f4f4f5;
  color: #909399;
}

.comment-body {
  flex: 1;
  min-width: 0;
}

.comment-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.comment-author {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.comment-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-left: auto;
}

.comment-content {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  word-break: break-word;
}

.comment-content :deep(img) {
  max-width: 100%;
  border-radius: 4px;
}

.comment-content :deep(video) {
  max-width: 100%;
  border-radius: 4px;
}

.comment-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
}

/* 评论输入区 */
.comment-input-area {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #dcdfe6;
}
</style>
