<template>
  <div class="ticket-manager">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-tasks"></i> 工单管理</span>
          <div class="header-actions">
            <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 130px" @change="fetchTickets">
              <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
            </el-select>
            <el-select v-model="assigneeFilter" placeholder="指派人" clearable style="width: 150px" @change="fetchTickets">
              <el-option label="未指派" :value="''" />
              <el-option v-for="u in assignees" :key="u.id" :label="u.name || u.username" :value="u.id" />
            </el-select>
            <el-select v-model="businessSystemFilter" placeholder="涉及系统" clearable style="width: 150px" @change="fetchTickets">
              <el-option label="全部系统" :value="''" />
              <el-option v-for="sys in businessSystems" :key="sys.id" :label="sys.name" :value="sys.id" />
            </el-select>
            <el-date-picker
              v-model="dateFilter"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 280px"
              @change="fetchTickets"
            />
            <el-input v-model="keyword" placeholder="搜索工单编号/标题" clearable style="width: 220px" @keyup.enter="fetchTickets" @clear="fetchTickets">
              <template #prefix><i class="fas fa-search"></i></template>
            </el-input>
            <el-button @click="resetTicketFilters" style="margin-left: 8px">重置</el-button>
            <el-button type="primary" v-hasPermi="['ticket:create']" @click="openCreateDialog">
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
            <!-- 草稿：可点击进入编辑（仅创建人可见） -->
            <el-tag v-else-if="row.status === 'draft'" type="info" effect="plain" size="small" style="cursor: pointer" @click.stop="editDraftFromList(row)">
              <i class="fas fa-edit"></i> 草稿
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
    <el-dialog v-model="createVisible" :title="editingDraftId ? '编辑草稿' : '提交工单'" width="800px" destroy-on-close top="5vh" :before-close="handleCreateDialogClose" class="ticket-create-dialog">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="96px">
        <!-- 基本信息 -->
        <div class="form-section">
          <div class="form-section-title"><i class="fas fa-edit"></i> 基本信息</div>
          <el-form-item label="标题" prop="title">
            <el-input v-model="createForm.title" placeholder="请输入工单标题" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="涉及系统">
            <el-select v-model="createForm.business_system_id" placeholder="选择涉及的业务系统（可选）" clearable filterable style="width: 100%">
              <el-option v-for="s in businessSystems" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
          </el-form-item>
        </div>

        <!-- 指派设置 -->
        <div class="form-section">
          <div class="form-section-title"><i class="fas fa-user-tag"></i> 指派设置</div>
          <el-form-item label="指派方式">
            <el-radio-group v-model="createForm.assignee_type">
              <el-radio-button label="user"><i class="fas fa-user"></i> 指派给具体人</el-radio-button>
              <el-radio-button label="ai"><i class="fas fa-robot"></i> 指派给AI</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="createForm.assignee_type === 'user'" label="处理人" prop="assignee_id">
            <el-select v-model="createForm.assignee_id" placeholder="选择处理人" filterable style="width: 100%">
              <el-option v-for="u in assignees" :key="u.id" :label="u.display_name" :value="u.id" />
            </el-select>
          </el-form-item>
          <template v-else>
            <!-- 有切换权限：显示Agent选择 -->
            <template v-if="canSwitchAgent">
              <el-form-item label="执行者Agent">
                <el-select v-model="createForm.assignee_agent_id" placeholder="选择执行者Agent（留空使用默认）" clearable filterable style="width: 100%">
                  <el-option v-for="a in executorAgentOptions" :key="a.id" :label="a.name + (a.is_default ? '（默认）' : '')" :value="a.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="监督者Agent">
                <el-select v-model="createForm.supervisor_agent_id" placeholder="选择监督者Agent（可选，监督执行结果）" clearable filterable style="width: 100%">
                  <el-option v-for="a in supervisorAgentOptions" :key="a.id" :label="a.name + (a.can_confirm_execution ? '（可自动确认）' : '')" :value="a.id" />
                </el-select>
                <div class="form-tip" v-if="createForm.supervisor_agent_id"><i class="fas fa-users"></i> 已启用多Agent协作：执行者执行任务，监督者审查结果直到验收通过</div>
              </el-form-item>
            </template>
            <!-- 无切换权限：优雅的默认指派卡片 -->
            <div v-else class="ai-assign-card">
              <div class="ai-assign-card-icon"><i class="fas fa-robot"></i></div>
              <div class="ai-assign-card-body">
                <div class="ai-assign-card-title">AI 自动处理</div>
                <div class="ai-assign-card-desc">系统将使用默认的执行者Agent处理工单，处理失败时自动转为「待指派」状态。</div>
              </div>
            </div>
          </template>
        </div>

        <!-- 工单内容 -->
        <div class="form-section">
          <div class="form-section-title"><i class="fas fa-file-alt"></i> 工单内容</div>
          <el-form-item label="内容详情" prop="content">
            <MarkdownEditor v-model="createForm.content" :upload-fn="uploadAttachment" placeholder="详细描述工单需求，支持 Markdown 格式" :height="260" />
          </el-form-item>
          <el-form-item label="工单附件">
            <div class="attachment-area">
              <el-upload
                :file-list="attachmentFileList"
                :auto-upload="true"
                :http-request="customAttUpload"
                :on-remove="handleAttRemove"
                :show-file-list="true"
                multiple
              >
                <el-button type="primary" plain size="small">
                  <i class="fas fa-paperclip"></i> 上传附件
                </el-button>
              </el-upload>
              <div class="el-upload__tip">支持 Excel/CSV/文档/图片/压缩包，单个不超过50MB（查询任务需上传Excel数据文件）</div>
            </div>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <div class="footer-left">
            <el-button @click="handleCreateCancel">取消</el-button>
          </div>
          <div class="footer-right">
            <el-button :loading="submitting" @click="submitCreateDraft">
              <i class="fas fa-save"></i> 暂存草稿
            </el-button>
            <el-button type="primary" :loading="submitting" @click="submitCreate">
              <i class="fas fa-paper-plane"></i> 提交工单
            </el-button>
          </div>
        </div>
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
                <template v-if="Array.isArray(detailData.pending_action.tasks)">
                  共 {{ detailData.pending_action.tasks.length }} 个待确认任务：
                  <ul style="margin: 4px 0; padding-left: 20px">
                    <li v-for="(t, i) in detailData.pending_action.tasks" :key="i">
                      {{ i + 1 }}. {{ t.task_name || '未命名任务' }}
                      <span style="color: #999; font-size: 12px">（{{ JSON.stringify(t.params_values) }}）</span>
                    </li>
                  </ul>
                </template>
                <template v-else>
                  任务：{{ detailData.pending_action.task_name }} | 参数：{{ JSON.stringify(detailData.pending_action.params_values) }}
                </template>
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
          <el-descriptions-item v-if="detailData.assignee_type === 'ai' && detailData.supervisor_agent_id" label="监督者">
            <span style="color: #fa8c16">
              <i class="fas fa-user-check"></i> {{ detailData.supervisor_agent_name || detailData.supervisor_agent_id }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailData.final_score != null" label="监督评分">
            <span :style="{ color: scoreColor(detailData.final_score), fontWeight: '600' }">
              <i class="fas fa-star"></i> {{ detailData.final_score }}分
            </span>
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

        <!-- 工单附件 -->
        <template v-if="detailData.attachments && detailData.attachments.length">
          <el-divider content-position="left">工单附件（{{ detailData.attachments.length }}）</el-divider>
          <div class="ticket-attachments">
            <div v-for="att in detailData.attachments" :key="att.id" class="attachment-item">
              <i class="fas fa-file-alt"></i>
              <a href="#" @click.prevent="downloadTicketAttachment(detailData.id, att.id, att.file_name)">{{ att.file_name }}</a>
              <span class="attachment-meta">{{ formatFileSize(att.file_size) }} · {{ att.uploader_name }} · {{ (att.created_at || '').slice(0, 16).replace('T', ' ') }}</span>
            </div>
          </div>
        </template>

        <!-- AI处理结果 -->
        <div v-if="detailData.ai_result" class="reason-block ai-result">
          <div class="reason-title"><i class="fas fa-robot"></i> AI处理结果</div>
          <div class="reason-content" v-html="renderMarkdown(detailData.ai_result)"></div>
        </div>

        <!-- 多Agent协作日志 -->
        <div v-if="collaborationLog.length" class="reason-block collab-log">
          <div class="reason-title"><i class="fas fa-users"></i> 多Agent协作日志（{{ detailData.collaboration_rounds || collaborationLog.length }}轮）</div>
          <div class="collab-timeline">
            <div v-for="(entry, idx) in collaborationLog" :key="idx" class="collab-entry" :class="entry.role">
              <div class="collab-entry-header">
                <el-tag :type="entry.role === 'supervisor' ? 'warning' : 'primary'" size="small" effect="dark">{{ entry.role === 'supervisor' ? '监督者' : '执行者' }}</el-tag>
                <span class="collab-agent">{{ entry.agent_name }}</span>
                <span class="collab-round">第{{ entry.round }}轮</span>
                <el-tag v-if="entry.role === 'supervisor' && entry.approved === true" type="success" size="small">验收通过</el-tag>
                <el-tag v-else-if="entry.role === 'supervisor' && entry.approved === false" type="danger" size="small">需返工</el-tag>
                <el-tag v-if="entry.role === 'supervisor' && entry.decision === 'confirm'" type="success" size="small">确认执行</el-tag>
                <el-tag v-else-if="entry.role === 'supervisor' && entry.decision === 'reject'" type="danger" size="small">拒绝执行</el-tag>
                <span v-if="entry.role === 'supervisor' && entry.score != null" class="collab-score" :style="{ color: scoreColor(entry.score) }">
                  <i class="fas fa-star"></i> {{ entry.score }}分
                </span>
              </div>
              <div v-if="entry.summary" class="collab-entry-body" v-html="renderMarkdown(entry.summary)"></div>
            </div>
          </div>
        </div>

        <!-- AI Token 消耗指标 -->
        <div v-if="hasAiTokenUsage" class="reason-block ai-token-usage">
          <div class="reason-title"><i class="fas fa-chart-bar"></i> AI Token 消耗指标</div>
          <div class="token-metrics">
            <div class="token-metrics-header">
              <el-tag type="primary" size="small" effect="dark">
                <i class="fas fa-coins"></i> 总消耗 {{ formatTokens(detailData.ai_total_tokens) }}
              </el-tag>
              <el-tag v-if="detailData.ai_models_used && detailData.ai_models_used.length" type="info" size="small" effect="plain">
                <i class="fas fa-microchip"></i> 参与模型：{{ detailData.ai_models_used.join(', ') }}
              </el-tag>
            </div>
            <el-descriptions :column="3" border size="small" class="token-descriptions">
              <el-descriptions-item label="Prompt Tokens">
                <span class="token-value">{{ formatTokens(detailData.ai_prompt_tokens) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Completion Tokens">
                <span class="token-value">{{ formatTokens(detailData.ai_completion_tokens) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="缓存创建">
                <span class="token-value">{{ formatTokens(detailData.ai_cache_creation_tokens) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="缓存读取">
                <span class="token-value">{{ formatTokens(detailData.ai_cache_read_tokens) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Headroom 原始">
                <span class="token-value">{{ formatTokens(detailData.ai_headroom_original_tokens) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="Headroom 节省">
                <span class="token-value highlight-saved">{{ formatTokens(detailData.ai_headroom_saved_tokens) }}</span>
                <el-tag v-if="detailData.ai_headroom_compression_ratio > 0" type="success" size="small" effect="plain" style="margin-left: 6px">
                  压缩 {{ (detailData.ai_headroom_compression_ratio * 100).toFixed(1) }}%
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </div>
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
            <!-- 被指派人移交工单（已接收/处理中状态，且当前指派给具体人） -->
            <el-button v-if="detailData.assignee_type === 'user' && ['received', 'processing'].includes(detailData.status)" type="primary" plain v-hasPermi="['ticket:reassign']" @click="openReassignDialog('transfer')">
              <i class="fas fa-share"></i> 移交工单
            </el-button>
          </template>
          <!-- 提交人操作 -->
          <template v-if="isCreator">
            <!-- 草稿状态：支持编辑和提交 -->
            <el-button v-if="detailData.is_draft || detailData.status === 'draft'" type="warning" @click="editDraft">
              <i class="fas fa-edit"></i> 编辑草稿
            </el-button>
            <el-button v-if="detailData.is_draft || detailData.status === 'draft'" type="primary" :loading="submitting" @click="submitDraftItem">
              <i class="fas fa-paper-plane"></i> 提交工单
            </el-button>
            <el-button v-if="detailData.status === 'processed'" type="success" @click="handleAction('confirm')">
              <i class="fas fa-check-circle"></i> 核实通过
            </el-button>
            <el-button v-if="detailData.status === 'processed'" type="warning" v-hasPermi="['ticket:reassign']" @click="openReassignDialog('reopen')">
              <i class="fas fa-redo"></i> 重新发起
            </el-button>
            <el-button v-if="detailData.status === 'rejected'" type="primary" @click="openReasonDialog('appeal')">
              <i class="fas fa-gavel"></i> 申诉重启
            </el-button>
            <!-- 待指派：提交人重新指派 -->
            <el-button v-if="detailData.status === 'pending_assignment'" type="primary" v-hasPermi="['ticket:reassign']" @click="openReassignDialog('reassign')">
              <i class="fas fa-user-plus"></i> 重新指派
            </el-button>
            <!-- 待确认：提交人确认执行或取消 -->
            <el-button v-if="detailData.status === 'pending_confirmation'" type="success" v-hasPermi="['ticket:confirm_action']" @click="handleConfirmAction">
              <i class="fas fa-check-circle"></i> 确认执行
            </el-button>
            <el-button v-if="detailData.status === 'pending_confirmation'" type="warning" v-hasPermi="['ticket:confirm_action']" @click="handleCancelAction">
              <i class="fas fa-times-circle"></i> 取消执行
            </el-button>
            <el-button v-if="detailData.status === 'pending_confirmation'" type="primary" v-hasPermi="['ticket:reassign']" @click="openReassignDialog('reassign')">
              <i class="fas fa-user-plus"></i> 重新指派
            </el-button>
          </template>
          <!-- 管理员也可重新指派 -->
          <el-button v-if="isAdmin && detailData.status === 'pending_assignment' && !isCreator" type="primary" v-hasPermi="['ticket:reassign']" @click="openReassignDialog('reassign')">
            <i class="fas fa-user-plus"></i> 重新指派
          </el-button>
          <!-- 重试AI处理（指派给AI且处于待指派/已提交状态） -->
          <el-button v-if="detailData.assignee_type === 'ai' && detailData.status === 'pending_assignment'" type="warning" plain v-hasPermi="['ticket:retry_ai']" @click="handleRetryAi">
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
              <div v-if="c.attachment_path" class="comment-attachment">
                <i class="fas fa-paperclip"></i>
                <a href="#" @click.prevent="downloadCommentAttachment(detailData.id, c.id, c.attachment_name)">
                  {{ c.attachment_name || '下载附件' }}
                </a>
              </div>
            </div>
          </div>
        </div>

        <!-- 添加评论 -->
        <div v-if="detailData.status !== 'closed'" class="comment-input-area">
          <MarkdownEditor v-model="commentText" :upload-fn="uploadAttachment" :placeholder="commentPlaceholder" :height="120" :toolbar="true" />
          <el-button type="primary" :loading="commenting" :disabled="!commentText.trim()" @click="submitComment" style="margin-top: 8px">
            <i class="fas fa-paper-plane"></i> 发表评论
          </el-button>
        </div>
        <div v-else class="comment-closed-tip">
          <i class="fas fa-lock"></i> 工单已结束，无法发表评论
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

    <!-- 重新指派/重新发起/移交工单 对话框 -->
    <el-dialog v-model="reassignVisible" :title="reassignDialogTitle" width="520px" append-to-body destroy-on-close>
      <el-form :model="reassignForm" label-width="90px">
        <div v-if="reassignAction === 'transfer'" class="form-tip" style="margin-bottom: 12px">
          <i class="fas fa-info-circle"></i> 移交后工单将重新进入"已提交"状态，由新指派人接收处理。
          <span v-if="reassignForm.assignee_type === 'ai'">移交给AI后将自动处理，处理失败会转为"待指派"状态。</span>
        </div>
        <el-form-item label="指派类型">
          <el-radio-group v-model="reassignForm.assignee_type">
            <el-radio-button label="user">指派给具体人</el-radio-button>
            <el-radio-button label="ai">指派给AI</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="reassignForm.assignee_type === 'user'" label="指派给" required>
          <el-select v-model="reassignForm.assignee_id" placeholder="选择处理人" filterable style="width: 100%">
            <el-option v-for="u in assignees" :key="u.id" :label="u.display_name" :value="u.id" :disabled="reassignAction === 'transfer' && u.id === detailData.assignee_id" />
          </el-select>
        </el-form-item>
        <template v-else>
          <template v-if="canSwitchAgent">
            <el-form-item label="执行者Agent">
              <el-select v-model="reassignForm.assignee_agent_id" placeholder="选择执行者Agent（留空使用默认）" clearable filterable style="width: 100%">
                <el-option v-for="a in reassignExecutorOptions" :key="a.id" :label="a.name + (a.is_default ? '（默认）' : '')" :value="a.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="监督者Agent">
              <el-select v-model="reassignForm.supervisor_agent_id" placeholder="选择监督者Agent（可选，监督执行结果）" clearable filterable style="width: 100%">
                <el-option v-for="a in reassignSupervisorAgentOptions" :key="a.id" :label="a.name + (a.can_confirm_execution ? '（可自动确认）' : '')" :value="a.id" />
              </el-select>
            </el-form-item>
          </template>
          <div v-else class="ai-assign-card">
            <div class="ai-assign-card-icon"><i class="fas fa-robot"></i></div>
            <div class="ai-assign-card-body">
              <div class="ai-assign-card-title">AI 自动处理</div>
              <div class="ai-assign-card-desc">系统将使用默认的执行者Agent处理工单。</div>
            </div>
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="submitReassign">确认</el-button>
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
  draft: '草稿',
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
    draft: 'info',
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
const assigneeFilter = ref('')
const businessSystemFilter = ref('')
const dateFilter = ref(null)
const keyword = ref('')

function resetTicketFilters() {
  statusFilter.value = ''
  assigneeFilter.value = ''
  businessSystemFilter.value = ''
  dateFilter.value = null
  keyword.value = ''
  currentPage.value = 1
  fetchTickets()
}

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
    if (assigneeFilter.value !== '' && assigneeFilter.value !== null) params.assignee_id = assigneeFilter.value
    if (businessSystemFilter.value !== '' && businessSystemFilter.value !== null) params.business_system_id = businessSystemFilter.value
    if (dateFilter.value && dateFilter.value.length === 2) {
      params.start_date = dateFilter.value[0]
      params.end_date = dateFilter.value[1]
    }
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
const justSubmitted = ref(false)
const createForm = ref({ title: '', content: '', assignee_type: 'user', assignee_id: null, assignee_agent_id: null, supervisor_agent_id: null, business_system_id: null })
// 工单附件：fileList供el-upload展示，ids为已上传的附件ID（提交时关联）
const attachmentFileList = ref([])
const attachmentIds = ref([])
const createRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  // content 不强制必填：暂存草稿时允许为空，提交时再单独校验
  content: [],
}
const assignees = ref([])
const businessSystems = ref([])
const aiAgents = ref([])
const canSwitchAgent = ref(false)

// 创建工单时可选执行者：只显示通用和执行者角色的Agent
const executorAgentOptions = computed(() => {
  return aiAgents.value.filter(a => a.agent_role !== 'supervisor')
})

// 创建工单时可选监督者：只显示监督者角色，且排除当前选中的执行者
const supervisorAgentOptions = computed(() => {
  const executorId = createForm.value.assignee_agent_id
  return aiAgents.value.filter(a => a.agent_role === 'supervisor' && a.id !== executorId)
})

// 重指派时可选执行者：只显示通用和执行者角色
const reassignExecutorOptions = computed(() => {
  return aiAgents.value.filter(a => a.agent_role !== 'supervisor')
})

// 重指派时可选监督者：只显示监督者角色，且排除当前选中的执行者
const reassignSupervisorAgentOptions = computed(() => {
  const executorId = reassignForm.value.assignee_agent_id
  return aiAgents.value.filter(a => a.agent_role === 'supervisor' && a.id !== executorId)
})

async function openCreateDialog() {
  createForm.value = { title: '', content: '', assignee_type: 'user', assignee_id: null, assignee_agent_id: null, supervisor_agent_id: null, business_system_id: null }
  attachmentFileList.value = []
  attachmentIds.value = []
  editingDraftId.value = null
  justSubmitted.value = false
  createVisible.value = true
  // 并行加载选项数据
  Promise.all([fetchAssignees(), fetchBusinessSystems(), fetchAiAgents()])
}

// 关闭创建对话框前的自动暂存逻辑
function handleCreateDialogClose(done) {
  autoSaveDraftIfNeeded().finally(() => {
    justSubmitted.value = false
    editingDraftId.value = null
    attachmentFileList.value = []
    attachmentIds.value = []
    done()
  })
}

function handleCreateCancel() {
  autoSaveDraftIfNeeded().finally(() => {
    justSubmitted.value = false
    editingDraftId.value = null
    attachmentFileList.value = []
    attachmentIds.value = []
    createVisible.value = false
  })
}

// 静默自动暂存草稿（关闭对话框时触发，有内容才保存）
async function autoSaveDraftIfNeeded() {
  // 刚刚成功提交/暂存过，不重复保存
  if (justSubmitted.value) return
  const title = (createForm.value.title || '').trim()
  const content = (createForm.value.content || '').trim()
  // 没有标题且没有内容，不保存
  if (!title && !content) return
  try {
    const payload = { ...createForm.value, is_draft: true }
    if (payload.assignee_type === 'ai') {
      delete payload.assignee_id
    } else {
      delete payload.assignee_agent_id
      delete payload.supervisor_agent_id
    }
    if (attachmentIds.value.length) {
      payload.attachment_ids = [...attachmentIds.value]
    }
    if (editingDraftId.value) {
      await api.tickets.updateDraft(editingDraftId.value, payload)
    } else {
      await api.tickets.create(payload)
    }
    ElMessage.success('草稿已自动暂存')
    fetchTickets()
  } catch {
    // 静默失败，不打扰用户
  }
}

// 工单附件上传（选择文件即上传，暂存待提交时关联）
async function customAttUpload(option) {
  const formData = new FormData()
  formData.append('file', option.file)
  try {
    const res = await api.tickets.uploadAttachment(formData)
    const att = res.data || res
    attachmentIds.value.push(att.id)
    attachmentFileList.value.push({ name: att.file_name, uid: option.file.uid, attId: att.id })
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '附件上传失败')
    attachmentFileList.value = attachmentFileList.value.filter(f => f.uid !== option.file.uid)
  }
}

// 移除暂存附件（前端列表移除 + 后端删除）
async function handleAttRemove(file) {
  const attId = file.attId || (file.response?.data?.id)
  attachmentFileList.value = attachmentFileList.value.filter(f => f.uid !== file.uid)
  if (attId) {
    attachmentIds.value = attachmentIds.value.filter(id => id !== attId)
    try {
      await api.tickets.deleteAttachment(attId)
    } catch {
      // 后端删除失败不阻断（提交时关联校验兜底）
    }
  }
}

// 工单附件下载（fetch带token下载）
async function downloadTicketAttachment(ticketId, attId, fileName) {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`/api/tickets/${ticketId}/attachments/${attId}/download`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.message || '下载失败')
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    console.error('下载附件失败:', err)
    ElMessage.error(err?.message || '下载附件失败')
  }
}

function formatFileSize(size) {
  if (size == null) return '-'
  if (size < 1024) return `${size}B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`
  return `${(size / 1024 / 1024).toFixed(1)}MB`
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
  if (!(createForm.value.content || '').trim()) {
    ElMessage.warning('请输入工单内容')
    return
  }
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      // 构造提交数据（按指派类型清理字段）
      const payload = { ...createForm.value, is_draft: false }
      if (payload.assignee_type === 'ai') {
        delete payload.assignee_id
      } else {
        delete payload.assignee_agent_id
        delete payload.supervisor_agent_id
      }
      if (attachmentIds.value.length) {
        payload.attachment_ids = [...attachmentIds.value]
      }
      // 如果正在编辑草稿，调用 updateDraft + submitDraft；否则调用 create
      if (editingDraftId.value) {
        await api.tickets.updateDraft(editingDraftId.value, payload)
        await api.tickets.submitDraft(editingDraftId.value)
        ElMessage.success('草稿已更新并提交')
      } else {
        await api.tickets.create(payload)
        ElMessage.success('工单已提交')
      }
      justSubmitted.value = true
      createVisible.value = false
      editingDraftId.value = null
      attachmentFileList.value = []
      attachmentIds.value = []
      fetchTickets()
    } catch (e) {
      ElMessage.error(e?.response?.data?.message || '提交失败')
    } finally {
      submitting.value = false
    }
  })
}

// 暂存草稿：仅标题必填，内容与指派人可为空
async function submitCreateDraft() {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = { ...createForm.value, is_draft: true }
      if (payload.assignee_type === 'ai') {
        delete payload.assignee_id
      } else {
        delete payload.assignee_agent_id
        delete payload.supervisor_agent_id
      }
      if (attachmentIds.value.length) {
        payload.attachment_ids = [...attachmentIds.value]
      }
      // 如果正在编辑草稿，调用 updateDraft；否则调用 create
      if (editingDraftId.value) {
        await api.tickets.updateDraft(editingDraftId.value, payload)
        ElMessage.success('草稿已更新')
      } else {
        await api.tickets.create(payload)
        ElMessage.success('草稿已暂存')
      }
      justSubmitted.value = true
      createVisible.value = false
      editingDraftId.value = null
      attachmentFileList.value = []
      attachmentIds.value = []
      fetchTickets()
    } catch (e) {
      ElMessage.error(e?.response?.data?.message || '暂存失败')
    } finally {
      submitting.value = false
    }
  })
}

// 从列表点击草稿标签，直接打开编辑草稿
async function editDraftFromList(row) {
  // 先加载完整工单详情（包含 attachments）
  try {
    const res = await api.tickets.get(row.id)
    detailData.value = res.data || res || {}
  } catch {}
  editDraft()
}

// 编辑草稿：从详情对话框打开创建对话框，预填草稿数据
async function editDraft() {
  const t = detailData.value
  if (!t || !t.id) return
  // 预填表单
  createForm.value = {
    title: t.title || '',
    content: t.content || '',
    assignee_type: t.assignee_type || 'user',
    assignee_id: t.assignee_id || null,
    assignee_agent_id: t.assignee_agent_id || null,
    business_system_id: t.business_system_id || null,
  }
  // 加载已有附件
  attachmentFileList.value = []
  attachmentIds.value = []
  if (Array.isArray(t.attachments) && t.attachments.length) {
    for (const a of t.attachments) {
      attachmentIds.value.push(a.id)
      attachmentFileList.value.push({ name: a.file_name, uid: a.id, attId: a.id })
    }
  }
  // 标记当前正在编辑的草稿ID（提交时调用 updateDraft 而非 create）
  editingDraftId.value = t.id
  justSubmitted.value = false
  // 关闭详情对话框
  detailVisible.value = false
  // 打开创建对话框
  createVisible.value = true
  // 并行加载选项数据
  Promise.all([fetchAssignees(), fetchBusinessSystems(), fetchAiAgents()])
}

// 提交草稿：调用 submitDraft API
async function submitDraftItem() {
  const t = detailData.value
  if (!t || !t.id) return
  submitting.value = true
  try {
    await api.tickets.submitDraft(t.id)
    ElMessage.success('工单已提交')
    detailVisible.value = false
    fetchTickets()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}

// 详情
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref({})
const editingDraftId = ref(null)
// 多agent协作日志（来自工单详情 collaboration_log 字段）
const collaborationLog = computed(() => detailData.value.collaboration_log || [])

// 监督者评分颜色：>=80绿，>=60橙黄，否则红
function scoreColor(score) {
  const s = Number(score)
  if (Number.isNaN(s)) return '#909399'
  if (s >= 80) return '#67c23a'
  if (s >= 60) return '#e6a23c'
  return '#f56c6c'
}
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

// AI 是否产生了 token 消耗（用于控制是否渲染 token 指标区块）
const hasAiTokenUsage = computed(() => {
  const d = detailData.value
  if (!d) return false
  return (d.ai_total_tokens || 0) > 0
    || (d.ai_prompt_tokens || 0) > 0
    || (d.ai_completion_tokens || 0) > 0
    || (d.ai_cache_creation_tokens || 0) > 0
    || (d.ai_cache_read_tokens || 0) > 0
    || (d.ai_headroom_original_tokens || 0) > 0
    || (d.ai_headroom_saved_tokens || 0) > 0
})

// 格式化 token 数字（千分位 + 简写）
function formatTokens(n) {
  if (n == null || isNaN(n)) return '0'
  const v = Number(n)
  if (v < 1000) return String(v)
  if (v < 10000) return v.toLocaleString()
  if (v < 1000000) return `${(v / 1000).toFixed(1)}K`
  return `${(v / 1000000).toFixed(2)}M`
}

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
const reassignForm = ref({ assignee_type: 'user', assignee_id: null, assignee_agent_id: null, supervisor_agent_id: null })
const reassignAction = ref('reassign')

const reassignDialogTitle = computed(() => {
  if (reassignAction.value === 'reopen') return '重新发起工单'
  if (reassignAction.value === 'transfer') return '移交工单'
  return '重新指派工单'
})

async function openReassignDialog(action = 'reassign') {
  reassignAction.value = action
  // 默认填充当前指派信息，方便用户修改
  const cur = detailData.value
  reassignForm.value = {
    assignee_type: cur.assignee_type || 'user',
    assignee_id: cur.assignee_type !== 'ai' ? cur.assignee_id : null,
    assignee_agent_id: cur.assignee_type === 'ai' ? cur.assignee_agent_id : null,
    supervisor_agent_id: cur.assignee_type === 'ai' ? cur.supervisor_agent_id : null,
  }
  // 移交工单时，清空原指派人，强制选择新的指派对象
  if (action === 'transfer') {
    reassignForm.value.assignee_id = null
    reassignForm.value.assignee_agent_id = null
    reassignForm.value.supervisor_agent_id = null
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
      delete payload.supervisor_agent_id
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
  const action = detailData.value.pending_action || {}
  let confirmMsg = ''
  if (Array.isArray(action.tasks)) {
    const names = action.tasks.map((t, i) => `${i + 1}. ${t.task_name}`).join('\n')
    confirmMsg = `确定要执行以下 ${action.tasks.length} 个数据变更操作吗？\n\n${names}\n\n此操作会直接影响生产数据，请谨慎确认！`
  } else {
    const taskName = action.task_name || ''
    confirmMsg = `确定要执行数据变更操作「${taskName}」吗？\n此操作会直接影响生产数据，请谨慎确认！`
  }
  try {
    await ElMessageBox.confirm(confirmMsg, '确认执行数据变更', {
      confirmButtonText: '确认执行',
      cancelButtonText: '取消',
      type: 'warning',
      dangerouslyUseHTMLString: false,
    })
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

// 评论附件下载（通过fetch带token下载）
async function downloadCommentAttachment(ticketId, commentId, fileName) {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`/api/tickets/${ticketId}/comments/${commentId}/attachment`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.message || '下载失败')
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName || 'download'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (err) {
    console.error('下载附件失败:', err)
    ElMessage.error(err.message || '下载附件失败')
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

/* 创建工单对话框 - 分区样式 */
.form-section {
  background: #fafbfc;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 16px;
}

.form-section:last-child {
  margin-bottom: 0;
}

.form-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.form-section-title i {
  margin-right: 6px;
  color: #409eff;
}

/* AI默认指派卡片（无切换权限用户） */
.ai-assign-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  background: linear-gradient(135deg, #f0f5ff 0%, #f6f0ff 100%);
  border: 1px solid #d9d2ec;
  border-radius: 8px;
  padding: 14px 18px;
  margin-left: 96px;
  margin-bottom: 12px;
}

.ai-assign-card-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #722ed1 0%, #9254de 100%);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-assign-card-icon i {
  color: #fff;
  font-size: 18px;
}

.ai-assign-card-body {
  flex: 1;
}

.ai-assign-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.ai-assign-card-desc {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

/* 附件区域 */
.attachment-area {
  width: 100%;
}

/* 底部按钮布局 */
.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.footer-left,
.footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
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

.reason-block.ai-token-usage {
  background: #f0f9ff;
  border: 1px solid #cfe8ff;
}

.reason-block.ai-token-usage .reason-title {
  color: #1677ff;
}

.reason-block.collab-log {
  background: #fdfaf0;
  border: 1px solid #f5e8c8;
}

.reason-block.collab-log .reason-title {
  color: #b88230;
}

.collab-timeline {
  margin-top: 8px;
}

.collab-entry {
  padding: 8px 12px;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  background: #fff;
  margin-bottom: 8px;
}

.collab-entry.supervisor {
  border-left-color: #e6a23c;
}

.collab-entry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.collab-agent {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.collab-round {
  font-size: 12px;
  color: #909399;
}

.collab-score {
  font-size: 12px;
  font-weight: 600;
}

.collab-entry-body {
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  max-height: 220px;
  overflow-y: auto;
}

.token-metrics {
  margin-top: 8px;
}

.token-metrics-header {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.token-descriptions .token-value {
  font-weight: 600;
  font-family: 'Consolas', 'Monaco', monospace;
  color: #303133;
}

.token-descriptions .token-value.highlight-saved {
  color: #67c23a;
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

.comment-attachment {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 4px;
  font-size: 13px;
}
.comment-attachment i {
  color: #67c23a;
  margin-right: 6px;
}
.comment-attachment a {
  color: #409eff;
  text-decoration: none;
}
.comment-attachment a:hover {
  text-decoration: underline;
}

/* 工单附件列表 */
.ticket-attachments {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.attachment-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  font-size: 13px;
}
.attachment-item i {
  color: #409eff;
}
.attachment-item a {
  color: #409eff;
  text-decoration: none;
}
.attachment-item a:hover {
  text-decoration: underline;
}
.attachment-meta {
  color: #909399;
  font-size: 12px;
}

/* 评论输入区 */
.comment-input-area {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #dcdfe6;
}

/* 工单已结束提示 */
.comment-closed-tip {
  margin-top: 12px;
  padding: 12px 16px;
  border-top: 1px dashed #dcdfe6;
  color: #909399;
  font-size: 13px;
  text-align: center;
}

.comment-closed-tip i {
  margin-right: 6px;
  color: #c0c4cc;
}
</style>
