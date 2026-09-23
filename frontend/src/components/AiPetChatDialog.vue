<template>
  <teleport to="body">
    <transition name="pet-chat-pop">
      <div v-if="modelValue" class="pet-chat-mask" @click.self="close">
        <div class="pet-chat-dialog">
          <div class="pet-chat-header">
            <div class="pet-avatar-mini" :class="{ working: sending || hasExecutingTask }">{{ petMeta.emoji }}</div>
            <div class="pet-chat-title">
              <div class="title-main">AI 宠物助手 · {{ petMeta.name }}</div>
              <div class="title-sub">{{ headerStatusText }}</div>
            </div>
            <button v-if="sending" class="header-btn stop" title="停止生成" @click="abortSend">
              <i class="fas fa-stop"></i>
            </button>
            <button class="header-btn" title="开启新对话" @click="startNewChat">
              <i class="fas fa-comment-medical"></i>
            </button>
            <button class="header-btn" title="收起" @click="close">
              <i class="fas fa-chevron-down"></i>
            </button>
          </div>

          <div ref="listRef" class="pet-chat-body">
            <div v-if="loadingHistory" class="body-loading">
              <i class="fas fa-spinner fa-spin"></i> 正在唤醒记忆…
            </div>
            <template v-else>
              <div v-if="!messages.length" class="body-empty">
                <div class="empty-pet-avatar">{{ petMeta.emoji }}</div>
                <p>你好呀～我是你的{{ petMeta.name }} (◕‿◕)</p>
                <p class="empty-tip">可以直接让我执行导出、系统任务、信息查询，我会接受监督者复核后完成～</p>
              </div>
              <div
                v-for="msg in messages"
                :key="msg.id"
                class="chat-row"
                :class="msg.role"
              >
                <div v-if="msg.role === 'assistant'" class="row-avatar">{{ petMeta.emoji }}</div>

                <!-- ═══ 普通文本消息 / 流式消息 ═══ -->
                <div v-if="!msg._type" class="bubble" :class="msg.role">
                  <div v-if="msg.role === 'assistant' && msg._thinking" class="thinking-tag" :title="msg._thinking">
                    <i class="fas fa-brain"></i>
                    {{ msg._streaming && !msg._thinking_done ? '深度思考中…' : '已深度思考' }}
                  </div>
                  <div class="bubble-content" v-html="renderMarkdown(msg.content)"></div>
                  <span v-if="msg._streaming" class="stream-cursor"></span>
                  <!-- 对话级监督者复核标记（点击展开复核详情） -->
                  <div
                    v-if="msg.role === 'assistant' && msg._supervision && !msg._streaming"
                    class="supervision-chip"
                    :class="{ flagged: msg._supervision_flagged }"
                    @click="msg._show_review_detail = !msg._show_review_detail"
                  >
                    <i :class="msg._supervision_flagged ? 'fas fa-exclamation-triangle' : 'fas fa-shield-alt'"></i>
                    <span class="supervision-text">{{ msg._supervision }}</span>
                    <i v-if="msg._supervision_records && msg._supervision_records.length" class="fas fa-angle-down review-toggle" :class="{ open: msg._show_review_detail }"></i>
                  </div>
                  <!-- 复核详情 -->
                  <div v-if="msg._show_review_detail && msg._supervision_records && msg._supervision_records.length" class="review-detail">
                    <div v-for="(record, idx) in msg._supervision_records" :key="idx" class="review-record">
                      <div class="review-record-head">
                        <span class="review-round">第{{ record.round }}轮复核</span>
                        <span class="review-verdict" :class="record.verdict">
                          {{ record.verdict === 'approved' ? '通过' : record.verdict === 'retry' ? '需改正' : '需人工复核' }}
                        </span>
                      </div>
                      <div v-if="record.assistant_content" class="review-line"><b>执行者回复：</b>{{ record.assistant_content }}</div>
                      <div v-if="record.tool_summary && record.tool_summary !== '（本次回复未调用工具）'" class="review-line"><b>工具调用：</b>{{ record.tool_summary }}</div>
                      <div class="review-line feedback"><b>监督判定：</b>{{ record.feedback || (record.verdict === 'approved' ? '回复质量合格，态度端正' : '需重新生成') }}</div>
                    </div>
                  </div>
                  <!-- 耗时/Token 概要 -->
                  <div v-if="msg.role === 'assistant' && !msg._streaming && (msg._tokens > 0 || msg._elapsed > 0)" class="msg-meta">
                    <span v-if="msg._model"><i class="fas fa-microchip"></i> {{ msg._model }}</span>
                    <span v-if="msg._elapsed > 0"><i class="fas fa-clock"></i> {{ msg._elapsed }}s</span>
                    <span v-if="msg._tokens > 0"><i class="fas fa-coins"></i> {{ msg._tokens }}</span>
                  </div>
                </div>

                <!-- ═══ 工具确认卡片（导出/查询/系统任务/分润） ═══ -->
                <div v-else-if="msg._type === 'tool' && !msg._dismissed" class="card-stack">
                  <div class="tool-card" :class="toolCardState(msg)">
                    <div class="tool-card-header">
                      <i v-if="msg._executing" class="fas fa-spinner fa-spin tool-icon"></i>
                      <i v-else-if="msg._done" class="fas fa-check-circle tool-icon ok"></i>
                      <i v-else-if="msg._failed" class="fas fa-times-circle tool-icon bad"></i>
                      <i v-else class="fas fa-magic tool-icon"></i>
                      <span class="tool-title">{{ toolCardTitle(msg) }}</span>
                      <span v-if="msg.tool_data?._supervisor_approved === true" class="sup-badge ok"><i class="fas fa-shield-alt"></i> 监督者已确认</span>
                      <span v-else-if="msg.tool_data?._supervisor_approved === false" class="sup-badge warn"><i class="fas fa-exclamation-triangle"></i> 监督者有异议</span>
                    </div>
                    <div class="tool-card-body">
                      <p class="tool-confirm-msg">{{ msg.tool_data?.confirm_message || msg.content }}</p>
                      <div v-if="msg.tool_data?._supervisor_feedback" class="sup-feedback">
                        <i class="fas fa-shield-alt"></i> 监督者评估：{{ msg.tool_data._supervisor_feedback }}
                      </div>
                      <!-- 系统任务参数预览 -->
                      <div v-if="msg.tool_data?.action_type === 'system_task' && msg.tool_data?.params && msg.tool_data.params.length && !msg._executing && !msg._done" class="param-preview">
                        <div v-for="p in msg.tool_data.params" :key="p.name" class="param-preview-row">
                          <span class="pp-label">{{ p.label || p.name }}：</span>
                          <span class="pp-value">{{ msg.tool_data.params_values && msg.tool_data.params_values[p.name] !== undefined && msg.tool_data.params_values[p.name] !== '' ? msg.tool_data.params_values[p.name] : '未设置' }}</span>
                        </div>
                      </div>
                      <p v-if="msg.tool_data?.required_missing && msg.tool_data.required_missing.length && !msg._executing && !msg._done" class="tool-warning">
                        <i class="fas fa-exclamation-triangle"></i> 缺少必填参数：{{ msg.tool_data.required_missing.join(', ') }}
                      </p>

                      <!-- 查询任务：内联执行流（上传Excel → 选参数列 → 执行） -->
                      <template v-if="msg.tool_data?.action_type === 'query' && !msg._executing && !msg._done && !msg._ignored">
                        <div class="query-flow">
                          <div class="qf-step">
                            <span class="qf-step-no" :class="{ active: msg._q_step >= 1 }">1</span>
                            <span>上传 Excel 文件</span>
                            <label class="qf-upload-btn">
                              <input type="file" accept=".xlsx,.xls" style="display:none" @change="onQueryFileChange($event, msg)" />
                              <i class="fas fa-file-excel"></i> {{ msg._q_file_name || '选择文件' }}
                            </label>
                          </div>
                          <div v-if="msg._q_step >= 2" class="qf-step">
                            <span class="qf-step-no" :class="{ active: true }">2</span>
                            <span>参数列（{{ msg._q_row_count }}行）</span>
                            <select v-model="msg._q_param_column" class="qf-select">
                              <option value="" disabled>选择参数列</option>
                              <option v-for="col in msg._q_columns" :key="col" :value="col">{{ col }}</option>
                            </select>
                          </div>
                          <div v-if="msg._q_file_name && !msg._q_columns.length && msg._q_parsing" class="qf-tip"><i class="fas fa-spinner fa-spin"></i> 正在解析文件…</div>
                        </div>
                      </template>

                      <!-- 系统任务：内联参数表单 -->
                      <template v-if="msg._need_params && !msg._executing && !msg._done">
                        <div class="inline-param-form">
                          <div v-for="p in (msg._param_task?.params || [])" :key="p.name" class="ipf-item">
                            <div class="ipf-label">
                              {{ p.label || p.name }}
                              <span v-if="p.required || msg._param_task?.task_type === 'sql'" class="req">*</span>
                            </div>
                            <div class="ipf-control">
                              <el-switch v-if="p.enum_enabled && p.enum_mode === 'neq' && p.neq_value" v-model="msg._param_values[p.name]" />
                              <el-select
                                v-else-if="p.enum_enabled && p.enum_values && p.enum_values.length"
                                v-model="msg._param_values[p.name]"
                                :multiple="p.multi" :collapse-tags="p.multi" size="small" style="width:100%"
                                placeholder="请选择"
                              >
                                <el-option v-for="item in p.enum_values" :key="item.value" :label="item.label" :value="item.value" />
                              </el-select>
                              <el-date-picker
                                v-else-if="p.type === 'date' || p.type === 'datetime'"
                                v-model="msg._param_values[p.name]"
                                :type="p.range ? 'daterange' : 'date'"
                                value-format="YYYY-MM-DD" size="small" style="width:100%"
                                :placeholder="'选择' + (p.label || p.name)"
                              />
                              <input
                                v-else
                                v-model="msg._param_values[p.name]"
                                :type="p.type === 'number' ? 'number' : 'text'"
                                class="ipf-input"
                                :placeholder="p.multi ? '多个值以逗号分隔' : '请输入' + (p.label || p.name)"
                              />
                            </div>
                          </div>
                          <div v-if="msg._databases && msg._databases.length > 1" class="ipf-item">
                            <div class="ipf-label">数据库连接<span class="req">*</span></div>
                            <select v-model="msg._db_id" class="ipf-input">
                              <option :value="null" disabled>请选择数据库</option>
                              <option v-for="db in msg._databases" :key="db.id" :value="db.id">{{ db.name }}</option>
                            </select>
                          </div>
                          <div class="ipf-actions">
                            <button class="card-btn primary" :disabled="!systemParamReady(msg)" @click="confirmSystemInline(msg)"><i class="fas fa-play"></i> 确认执行</button>
                            <button class="card-btn text" @click="msg._need_params = false">取消</button>
                          </div>
                        </div>
                      </template>

                      <!-- 执行进度 -->
                      <div v-if="msg._executing" class="progress-info">
                        <el-progress :percentage="msg._progress || 0" :stroke-width="6" />
                        <span class="progress-text">{{ msg._status_text || '正在初始化...' }}</span>
                      </div>
                      <!-- 完成下载 -->
                      <div v-if="msg._done && msg._download_url" class="download-row">
                        <button class="card-btn success" @click="downloadFile(msg._download_url)"><i class="fas fa-download"></i> 下载文件</button>
                      </div>
                      <!-- 失败信息 -->
                      <div v-if="msg._failed && msg._error_msg" class="error-msg">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>{{ msg._error_msg }}</span>
                        <div v-if="msg._ai_suggestion" class="ai-suggestion"><i class="fas fa-lightbulb"></i> {{ msg._ai_suggestion }}</div>
                      </div>
                    </div>
                    <div class="tool-card-actions">
                      <button
                        v-if="msg.tool_data?.action_type === 'export' && !msg._executing && !msg._done && !msg._ignored"
                        class="card-btn primary" :disabled="msg.tool_data?.required_missing && msg.tool_data.required_missing.length > 0"
                        @click="confirmExportCard(msg)"
                      >
                        <i class="fas fa-play"></i> 确认执行导出
                      </button>
                      <button
                        v-else-if="msg.tool_data?.action_type === 'query' && !msg._executing && !msg._done && !msg._ignored"
                        class="card-btn primary" :disabled="!queryFlowReady(msg)"
                        @click="executeQueryCard(msg)"
                      >
                        <i class="fas fa-play"></i> 执行查询
                      </button>
                      <button
                        v-else-if="msg.tool_data?.action_type === 'system_task' && !msg._executing && !msg._done && !msg._ignored"
                        class="card-btn primary" @click="confirmSystemCard(msg)"
                      >
                        <i class="fas fa-play"></i> 确认执行系统任务
                      </button>
                      <button
                        v-else-if="msg.tool_data?.action_type === 'profit_share' && !msg._executing && !msg._done && !msg._ignored"
                        class="card-btn primary" @click="confirmProfitShareCard(msg)"
                      >
                        <i class="fas fa-play"></i> 确认执行分润导出
                      </button>
                      <button v-if="msg._done && msg._download_url" class="card-btn success" @click="downloadFile(msg._download_url)"><i class="fas fa-download"></i> 下载</button>
                      <button v-if="!msg._executing" class="card-btn text" @click="dismissTool(msg)">{{ msg._done || msg._failed ? '关闭' : (msg._ignored ? '已忽略' : '忽略') }}</button>
                    </div>
                  </div>
                </div>

                <!-- ═══ 选项选择卡片 ═══ -->
                <div v-else-if="msg._type === 'select_options'" class="card-stack">
                  <div class="tool-card" :class="toolCardState(msg)">
                    <div class="tool-card-header">
                      <i v-if="msg._ignored" class="fas fa-ban tool-icon bad"></i>
                      <i v-else-if="msg._executing" class="fas fa-spinner fa-spin tool-icon"></i>
                      <i v-else-if="msg._done" class="fas fa-check-circle tool-icon ok"></i>
                      <i v-else-if="msg._failed" class="fas fa-times-circle tool-icon bad"></i>
                      <i v-else class="fas fa-list-check tool-icon"></i>
                      <span class="tool-title">
                        <template v-if="msg._ignored">已忽略</template>
                        <template v-else-if="msg._executing">正在执行...</template>
                        <template v-else-if="msg._done">执行成功</template>
                        <template v-else-if="msg._failed">执行失败</template>
                        <template v-else-if="msg._action_type === 'export'">可选导出任务</template>
                        <template v-else-if="msg._action_type === 'system_task'">可选系统任务</template>
                        <template v-else-if="msg._action_type === 'lookup'">可选信息查询</template>
                        <template v-else>可选查询任务</template>
                      </span>
                    </div>
                    <div class="tool-card-body">
                      <p v-if="msg.content" class="tool-confirm-msg">{{ msg.content }}</p>
                      <div v-if="msg._executing" class="progress-info">
                        <el-progress :percentage="msg._progress || 0" :stroke-width="6" />
                        <span class="progress-text">{{ msg._status_text || '正在初始化...' }}</span>
                      </div>
                      <div v-if="msg._done && msg._download_url" class="download-row">
                        <button class="card-btn success" @click="downloadFile(msg._download_url)"><i class="fas fa-download"></i> 下载文件</button>
                      </div>
                      <div v-if="msg._failed && msg._error_msg" class="error-msg">
                        <i class="fas fa-exclamation-circle"></i><span>{{ msg._error_msg }}</span>
                        <div v-if="msg._ai_suggestion" class="ai-suggestion"><i class="fas fa-lightbulb"></i> {{ msg._ai_suggestion }}</div>
                      </div>

                      <div v-if="!msg._executing && !msg._done" class="option-list">
                        <label v-for="s in msg._scripts" :key="s.id" class="option-item">
                          <input type="checkbox" :value="s.id" v-model="msg._selected" :disabled="msg._ignored" />
                          <div class="option-detail">
                            <span class="option-name">{{ s.name }}</span>
                            <span v-if="s.description" class="option-desc">{{ s.description }}</span>
                            <div v-if="s.params && s.params.length" class="option-params">
                              <span v-for="p in s.params" :key="p.name" class="mini-tag" :class="{ req: msg._action_type === 'system_task' || p.required }">{{ p.label || p.name }}{{ (msg._action_type === 'system_task' || p.required) ? '*' : '' }}</span>
                            </div>
                          </div>
                        </label>
                      </div>

                      <!-- 全部不筛选确认 -->
                      <div v-if="msg._allow_all_pending" class="allow-all-confirm">
                        <p>📋 所选参数将使用<b>全部不筛选</b>，是否继续？</p>
                        <div class="ipf-actions">
                          <button class="card-btn primary" @click="confirmAllowAll(msg)"><i class="fas fa-check"></i> 确认</button>
                          <button class="card-btn text" @click="openSelectParamForm(msg)">自定义参数</button>
                        </div>
                      </div>

                      <!-- 内联参数表单（导出/信息查询选择后） -->
                      <template v-if="msg._need_params && !msg._executing && !msg._done">
                        <div class="inline-param-form">
                          <div v-for="f in msg._param_fields" :key="f.key" class="ipf-item">
                            <div class="ipf-label">
                              <span v-if="msg._param_fields.length > 1 && f.scriptName && !f.shared" class="ipf-script">{{ f.scriptName }} · </span>
                              {{ f.param.label || f.param.name }}
                              <span v-if="f.param.required" class="req">*</span>
                              <label v-if="f.param.allow_all && !f.param.required" class="allow-all">
                                <input type="checkbox" v-model="msg._param_all[f.key]" /> 全部
                              </label>
                            </div>
                            <div class="ipf-control" v-if="!msg._param_all[f.key]">
                              <el-switch v-if="f.param.enum_enabled && f.param.enum_mode === 'neq' && f.param.neq_value" v-model="msg._param_form[f.key]" />
                              <el-select
                                v-else-if="f.param.enum_enabled && f.param.enum_values && f.param.enum_values.length"
                                v-model="msg._param_form[f.key]"
                                :multiple="f.param.multi" :collapse-tags="f.param.multi" size="small" style="width:100%"
                                placeholder="请选择"
                              >
                                <el-option v-for="item in f.param.enum_values" :key="item.value" :label="item.label" :value="item.value" />
                              </el-select>
                              <el-date-picker
                                v-else-if="f.param.type === 'date' || f.param.type === 'datetime'"
                                v-model="msg._param_form[f.key]"
                                :type="f.param.range ? 'daterange' : 'date'"
                                value-format="YYYY-MM-DD" size="small" style="width:100%"
                                :placeholder="'选择' + (f.param.label || f.param.name)"
                              />
                              <input
                                v-else
                                v-model="msg._param_form[f.key]"
                                :type="f.param.type === 'number' ? 'number' : 'text'"
                                class="ipf-input"
                                :placeholder="f.param.multi ? '多个值以逗号分隔' : '请输入' + (f.param.label || f.param.name)"
                              />
                            </div>
                          </div>
                          <div v-if="msg._action_type === 'system_task' && msg._databases && msg._databases.length > 1" class="ipf-item">
                            <div class="ipf-label">数据库连接<span class="req">*</span></div>
                            <select v-model="msg._db_id" class="ipf-input">
                              <option :value="null" disabled>请选择数据库</option>
                              <option v-for="db in msg._databases" :key="db.id" :value="db.id">{{ db.name }}</option>
                            </select>
                          </div>
                          <div class="ipf-actions">
                            <button class="card-btn primary" :disabled="!selectParamReady(msg)" @click="confirmSelectParams(msg)">
                              <i :class="msg._action_type === 'lookup' ? 'fas fa-search' : 'fas fa-play'"></i>
                              {{ msg._action_type === 'lookup' ? '查询' : '确认执行' }}
                            </button>
                            <button class="card-btn text" @click="msg._need_params = false">取消</button>
                          </div>
                        </div>
                      </template>
                    </div>
                    <div class="tool-card-actions" v-if="!msg._executing && !msg._done && !msg._allow_all_pending && !msg._need_params">
                      <button class="card-btn primary" :disabled="msg._ignored || !msg._selected || msg._selected.length === 0" @click="confirmSelection(msg)">
                        <template v-if="msg._ignored">已忽略</template>
                        <template v-else>确认执行所选 ({{ (msg._selected || []).length }})</template>
                      </button>
                      <button class="card-btn text" @click="dismissTool(msg)">{{ msg._ignored ? '已忽略' : '忽略' }}</button>
                    </div>
                  </div>
                </div>

                <!-- ═══ 信息查询结果卡片 ═══ -->
                <div v-else-if="msg._type === 'lookup'" class="card-stack">
                  <div class="tool-card" :class="msg._failed ? 'failed' : (msg._done ? 'done' : '')">
                    <div class="tool-card-header">
                      <i v-if="msg._failed" class="fas fa-times-circle tool-icon bad"></i>
                      <i v-else class="fas fa-search tool-icon"></i>
                      <span class="tool-title">{{ msg.tool_data?.script_name || '信息查询' }}</span>
                      <span v-if="msg._done && !msg._failed" class="mini-tag ok-tag">{{ msg.tool_data?.row_count || 0 }} 条结果</span>
                    </div>
                    <div class="tool-card-body">
                      <div v-if="msg.tool_data?.params_values && Object.keys(msg.tool_data.params_values).length" class="lookup-params">
                        <span v-for="(val, key) in msg.tool_data.params_values" :key="key" class="mini-tag">{{ key }}={{ val }}</span>
                      </div>
                      <div v-if="msg._done && msg.tool_data?.results && msg.tool_data.results.length" class="lookup-table-wrap">
                        <table class="lookup-table">
                          <thead><tr><th v-for="col in msg.tool_data.columns" :key="col">{{ col }}</th></tr></thead>
                          <tbody>
                            <tr v-for="(row, idx) in msg.tool_data.results.slice(0, 20)" :key="idx">
                              <td v-for="col in msg.tool_data.columns" :key="col">{{ row[col] ?? '-' }}</td>
                            </tr>
                          </tbody>
                        </table>
                        <div v-if="msg.tool_data.results.length > 20" class="lookup-more">仅显示前20条，共 {{ msg.tool_data.row_count }} 条</div>
                      </div>
                      <div v-else-if="msg._done && !msg._failed" class="lookup-nodata"><i class="fas fa-info-circle"></i> 未查询到匹配的数据</div>
                      <div v-if="msg._failed" class="error-msg"><i class="fas fa-exclamation-triangle"></i> {{ msg._error_msg || '查询执行失败' }}</div>
                    </div>
                  </div>
                </div>

                <!-- ═══ 工单创建卡片 ═══ -->
                <div v-else-if="msg._type === 'ticket'" class="card-stack">
                  <div class="tool-card done">
                    <div class="tool-card-header">
                      <i class="fas fa-ticket-alt tool-icon ok"></i>
                      <span class="tool-title">工单已创建</span>
                      <span class="mini-tag ok-tag">{{ msg.tool_data?.ticket_no }}</span>
                    </div>
                    <div class="tool-card-body">
                      <div v-if="msg.tool_data?.title" class="param-preview-row"><span class="pp-label">标题：</span><span class="pp-value">{{ msg.tool_data.title }}</span></div>
                      <p v-if="msg.content" class="tool-confirm-msg">{{ msg.content }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div class="pet-chat-footer">
            <div class="input-wrap">
              <textarea
                ref="inputRef"
                v-model="inputText"
                rows="1"
                placeholder="下达任务指令… (Enter 发送，Shift+Enter 换行)"
                @keydown.enter.exact.prevent="handleSend"
              ></textarea>
              <button
                v-if="!sending"
                class="send-btn"
                :disabled="!inputText.trim()"
                title="发送"
                @click="handleSend"
              >
                <i class="fas fa-paper-plane"></i>
              </button>
              <button v-else class="send-btn stop" title="停止生成" @click="abortSend">
                <i class="fas fa-stop"></i>
              </button>
            </div>
            <div class="footer-tip">与「AI 助手」页共用会话 · 支持直接执行任务并接受监督者复核</div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { emitPetEvent } from '../utils/petBus'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 宠物造型标识，与后端 PET_STYLES 白名单一致 */
  petStyle: { type: String, default: 'robot' },
})
const emit = defineEmits(['update:modelValue'])

/** 各造型对应的头像 emoji 与昵称 */
const PET_META = {
  robot: { emoji: '🤖', name: '小机器人' },
  cat: { emoji: '🐱', name: '喵喵' },
  bunny: { emoji: '🐰', name: '兔兔' },
  panda: { emoji: '🐼', name: '团团' },
  bear: { emoji: '🐻', name: '棕熊' },
  fox: { emoji: '🦊', name: '狐狐' },
  pig: { emoji: '🐷', name: '猪猪' },
  frog: { emoji: '🐸', name: '呱呱' },
  koala: { emoji: '🐨', name: '考拉' },
  chick: { emoji: '🐤', name: '小鸡' },
}
const petMeta = computed(() => PET_META[props.petStyle] || PET_META.robot)

const chats = ref([])
const currentChatId = ref(null)
const chatTitle = ref('')
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const loadingHistory = ref(false)
const listRef = ref(null)
const inputRef = ref(null)
const abortController = ref(null)
let profitShareSource = null
/** 查询流程的 File 对象存储（File 不可被 reactive 代理，按消息id存放） */
const queryFileStore = new Map()

const hasExecutingTask = computed(() => messages.value.some(m => m._executing))

const headerStatusText = computed(() => {
  if (loadingHistory.value) return '…'
  if (sending.value) return '思考与执行中…'
  const exec = messages.value.find(m => m._executing)
  if (exec) return exec._status_text || '任务执行中…'
  if (!currentChatId.value) return '新对话'
  return chatTitle.value || '对话中'
})

function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch {
    return text
  }
}

function close() {
  emit('update:modelValue', false)
}

async function scrollToBottom(smooth = true) {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTo({ top: listRef.value.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  }
}

/* ═══════════════ 会话加载与元数据恢复 ═══════════════ */

async function loadChats() {
  try {
    const res = await api.ai.getChats()
    chats.value = res.data || []
  } catch {
    chats.value = []
  }
}

/** 恢复消息元数据（与 AI 助手页 selectChat 一致） */
function hydrateMessage(m) {
  const base = {
    ...m,
    _dismissed: false,
    _tokens: m.tokens_used || 0,
    _prompt_tokens: m.prompt_tokens || 0,
    _completion_tokens: m.completion_tokens || 0,
    _elapsed: m.elapsed || 0,
    cache_creation_tokens: m.cache_creation_tokens || 0,
    cache_read_tokens: m.cache_read_tokens || 0,
  }
  if (m._metadata) {
    const meta = m._metadata
    if (meta._type === 'tool') {
      base._type = 'tool'
      base.tool_data = meta.tool_data
    } else if (meta._type === 'select_options') {
      base._type = 'select_options'
      base._select_mode = meta._select_mode
      base._scripts = meta.scripts || []
      base._selected = []
      base._action_type = meta.action_type || ''
      base._params_checked = false
      base._param_values = {}
      base._all_checked = {}
      base._selectedScripts = []
      base._missing_required_params = []
    } else if (meta._type === 'lookup') {
      base._type = 'lookup'
      base.tool_data = meta.tool_data || {}
      base._done = meta._done || false
      base._failed = meta._failed || false
      if (meta._error_msg) base._error_msg = meta._error_msg
    } else if (meta._type === 'ticket') {
      base._type = 'ticket'
      base._done = true
      base.tool_data = meta.tool_data || {}
      base.content = m.content || meta.tool_data?.confirm_message || ''
    }
    // 恢复思考内容
    if (meta._thinking) {
      base._thinking = meta._thinking
      base._thinking_done = meta._thinking_done || false
    }
    // 恢复执行状态
    if (meta._executing) base._executing = true
    if (meta._done) base._done = true
    if (meta._failed) base._failed = true
    if (meta._ignored) base._ignored = true
    if (meta._progress != null) base._progress = meta._progress
    if (meta._status_text) base._status_text = meta._status_text
    if (meta._download_url) base._download_url = meta._download_url
    if (meta._error_msg) base._error_msg = meta._error_msg
    if (meta._ai_suggestion) base._ai_suggestion = meta._ai_suggestion
    // 恢复监督者复核记录与最新状态
    if (meta.supervision_records && meta.supervision_records.length) {
      base._supervision_records = meta.supervision_records
      const latest = meta.supervision_records[meta.supervision_records.length - 1]
      if (meta.supervision?.verdict === 'flag_human' || latest.verdict === 'flag_human') {
        base._supervision = '⚠️ 监督者标记本回复需人工复核：' + (meta.supervision?.feedback || latest.feedback || '')
        base._supervision_flagged = true
      } else if (meta.supervision?.verdict === 'retry') {
        base._supervision = '监督者要求重新生成：' + (meta.supervision?.feedback || latest.feedback || '')
      } else {
        base._supervision = '✓ 监督者复核通过'
        base._supervision_flagged = false
      }
    } else if (meta.supervision) {
      if (meta.supervision.verdict === 'flag_human') {
        base._supervision = '⚠️ 监督者标记本回复需人工复核：' + (meta.supervision.feedback || '')
        base._supervision_flagged = true
      } else if (meta.supervision.verdict === 'approved') {
        base._supervision = '✓ 监督者复核通过'
      }
    }
  }
  return base
}

async function loadMessages(chatId) {
  try {
    const res = await api.ai.getMessages(chatId)
    messages.value = (res.data || []).map(hydrateMessage)
  } catch {
    messages.value = []
  }
  await scrollToBottom(false)
}

async function ensureChat() {
  loadingHistory.value = true
  await loadChats()
  const latest = chats.value[0]
  if (latest) {
    currentChatId.value = latest.id
    chatTitle.value = latest.title || ''
    await loadMessages(latest.id)
    // 恢复正在进行的流式响应（页面在别处发起时也能接续显示）
    await resumeActiveStream(latest.id)
  } else {
    await createChat()
  }
  loadingHistory.value = false
}

async function createChat() {
  try {
    const res = await api.ai.createChat({ title: '宠物对话' })
    if (res.data) {
      chats.value.unshift(res.data)
      currentChatId.value = res.data.id
      chatTitle.value = res.data.title || '宠物对话'
      messages.value = []
    }
  } catch {
    chatTitle.value = '新对话'
  }
}

async function startNewChat() {
  if (sending.value) return
  await createChat()
  await nextTick()
  inputRef.value?.focus()
}

watch(() => props.modelValue, async (val) => {
  if (val) {
    await ensureChat()
    await nextTick()
    inputRef.value?.focus()
  }
})

onUnmounted(() => {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
  if (profitShareSource) {
    profitShareSource.close()
    profitShareSource = null
  }
})

/* ═══════════════ 发送消息（流式SSE，与AI助手页同一后端端点） ═══════════════ */

async function handleSend() {
  const content = inputText.value.trim()
  if (!content || sending.value || !currentChatId.value) return
  inputText.value = ''
  messages.value.push({
    id: `local_u_${Date.now()}`,
    role: 'user',
    content,
  })
  sending.value = true
  emitPetEvent('chat_start')
  await scrollToBottom()

  const streamMsg = reactive({
    id: `local_a_${Date.now()}`,
    role: 'assistant',
    content: '',
    _streaming: true,
    _thinking: '',
    _thinking_done: false,
    _show_review_detail: false,
    _tokens: 0,
    _prompt_tokens: 0,
    _completion_tokens: 0,
    _elapsed: 0,
  })
  messages.value.push(streamMsg)
  await scrollToBottom()

  const payload = { content }
  const url = api.ai.sendMessageStream(currentChatId.value, payload)
  const token = localStorage.getItem('token')
  const controller = new AbortController()
  abortController.value = controller
  let aborted = false

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    if (!response.ok || !response.body) {
      throw new Error('stream unavailable')
    }
    await consumeSseStream(response, streamMsg)
    if (!streamMsg.content.trim() && !streamMsg._thinking) {
      streamMsg.content = '（本次没有返回内容，可稍后重试）'
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      aborted = true
      streamMsg._streaming = false
      streamMsg._thinking_done = true
      if (!streamMsg.content.trim()) {
        streamMsg.content = '任务已被用户手动终止'
      } else {
        streamMsg.content += '\n\n*任务已被用户手动终止*'
      }
    } else {
      // 流式失败 → 回退非流式发送
      const idx = messages.value.findIndex(m => m.id === streamMsg.id)
      if (idx > -1) messages.value.splice(idx, 1)
      try {
        const res = await api.ai.sendMessage(currentChatId.value, payload)
        if (res.data?.assistant_message) {
          messages.value.push(hydrateMessage(res.data.assistant_message))
        }
        if (res.data?.tool_results && res.data.tool_results.length > 0) {
          await handleToolResults(res.data.tool_results)
        }
      } catch {
        messages.value.push({
          id: `err_${Date.now()}`,
          role: 'assistant',
          content: '请求失败，请稍后重试',
        })
      }
    }
  } finally {
    sending.value = false
    abortController.value = null
    emitPetEvent('chat_end', { ok: !aborted })
    await scrollToBottom()
  }
}

/** 消费SSE流（发送与断线恢复共用） */
async function consumeSseStream(response, streamMsg) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      for (const line of block.split('\n')) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6).trim()
        if (!dataStr) continue
        try {
          processSseEvent(JSON.parse(dataStr), streamMsg)
        } catch {
          // 忽略解析失败的事件块
        }
      }
    }
    await nextTick()
    scrollToBottom()
  }
  // 处理buffer剩余数据
  if (buffer.trim()) {
    for (const line of buffer.split('\n')) {
      if (!line.startsWith('data: ')) continue
      const dataStr = line.slice(6).trim()
      if (!dataStr) continue
      try {
        processSseEvent(JSON.parse(dataStr), streamMsg)
      } catch {}
    }
  }
}

/** 统一处理SSE事件（与AI助手页 sendStreamMessage 事件面完全对齐） */
function processSseEvent(event, streamMsg) {
  switch (event.type) {
    case 'heartbeat':
      // 心跳事件，确认连接建立
      break
    case 'thinking':
      streamMsg._thinking += event.content
      break
    case 'content':
      streamMsg.content += event.content
      break
    case 'supervision':
      handleSupervisionEvent(event, streamMsg)
      break
    case 'tool_results':
      handleToolResults(event.tool_results)
      break
    case 'done':
      streamMsg._streaming = false
      streamMsg._thinking_done = true
      if (event.message_id) streamMsg.id = event.message_id
      streamMsg._tokens = event.tokens || 0
      streamMsg._prompt_tokens = event.prompt_tokens || 0
      streamMsg._completion_tokens = event.completion_tokens || 0
      streamMsg._elapsed = event.elapsed || 0
      streamMsg._model = event.model || streamMsg._model
      // 流式结束后持久化思考内容
      if (streamMsg._thinking && currentChatId.value && event.message_id) {
        saveMessageState(streamMsg).catch(() => {})
      }
      break
    case 'truncated':
      streamMsg.content += (streamMsg.content ? '\n\n' : '') + `*${event.content || 'AI输出因token上限被截断'}*`
      break
    case 'aborted':
      streamMsg._streaming = false
      streamMsg._thinking_done = true
      if (!streamMsg.content.trim()) {
        streamMsg.content = '任务已被用户手动终止'
      } else {
        streamMsg.content += '\n\n*任务已被用户手动终止*'
      }
      break
    case 'idle':
      // 无活跃流（恢复场景）：移除占位消息
      removeMessage(streamMsg.id)
      break
    case 'error':
      streamMsg._streaming = false
      streamMsg._thinking_done = true
      streamMsg.content = event.content || 'AI服务调用失败'
      break
  }
}

/** 对话级监督者复核事件 */
function handleSupervisionEvent(event, streamMsg) {
  if (event.review_record) {
    if (!streamMsg._supervision_records) streamMsg._supervision_records = []
    streamMsg._supervision_records.push(event.review_record)
  }
  if (event.status === 'reviewing') {
    streamMsg._supervision = '监督者复核中…'
    streamMsg._supervision_flagged = false
  } else if (event.status === 'retry') {
    // 监督者要求重新生成：清空已流式输出的内容，等待新回复
    streamMsg.content = ''
    streamMsg._thinking = ''
    streamMsg._supervision = '监督者要求重新生成：' + (event.content || '')
    streamMsg._supervision_flagged = false
  } else if (event.status === 'approved') {
    streamMsg._supervision = '✓ 监督者复核通过'
    streamMsg._supervision_flagged = false
  } else if (event.status === 'flagged') {
    streamMsg._supervision = event.content || '⚠️ 监督者标记本回复需人工复核'
    streamMsg._supervision_flagged = true
  } else if (event.status === 'tool_approved') {
    ElMessage.success(event.content || '监督者已评估通过，将自动执行')
  } else if (event.status === 'tool_rejected') {
    ElMessage.warning(event.content || '监督者评估不通过，请人工确认')
  }
}

/** 推送卡片消息：reactive 包装，保证创建方持有的引用可直接变更触发渲染 */
function addMsg(obj) {
  const m = reactive(obj)
  messages.value.push(m)
  return m
}

function removeMessage(id) {
  const idx = messages.value.findIndex(m => m.id === id)
  if (idx > -1) messages.value.splice(idx, 1)
}

/** 用户主动终止 */
async function abortSend() {
  if (!sending.value) return
  try {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    if (currentChatId.value) {
      await api.ai.abortRequest(currentChatId.value)
    }
  } catch {}
  // 终止标记由 handleSend 的 AbortError 分支统一写入，避免重复追加
}

/** 断线恢复：会话存在活跃流时接续接收 */
async function resumeActiveStream(chatId) {
  try {
    const status = await api.ai.getStreamStatus(chatId)
    if (!status.active) return
    // 移除可能的占位流式消息，避免重复
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === 'assistant' && lastMsg._streaming) {
      messages.value.pop()
    }
    const streamMsg = reactive({
      id: `resume_${Date.now()}`,
      role: 'assistant',
      content: status.content || '',
      _streaming: true,
      _thinking: status.thinking || '',
      _thinking_done: false,
      _show_review_detail: false,
    })
    messages.value.push(streamMsg)
    sending.value = true
    emitPetEvent('chat_start')
    await scrollToBottom()

    const token = localStorage.getItem('token')
    const response = await fetch(api.ai.resumeStreamUrl(chatId), {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'text/event-stream',
      },
    })
    if (!response.ok || !response.body) {
      removeMessage(streamMsg.id)
      sending.value = false
      await loadMessages(chatId)
      return
    }
    await consumeSseStream(response, streamMsg)
    // 恢复完成后重拉消息，保证卡片与状态一致
    await loadMessages(chatId)
  } catch {
    // 静默失败
  } finally {
    sending.value = false
    emitPetEvent('chat_end', { ok: true })
  }
}

/* ═══════════════ 工具结果 → 任务卡片（与AI助手页 handleToolResults 对齐） ═══════════════ */

async function handleToolResults(toolResults) {
  if (!toolResults || toolResults.length === 0) return
  // 预检：同一轮如存在 select_options 卡片，则跳过对应 request_* 确认卡片，避免重复
  const selectActionTypes = new Set()
  for (const tr of toolResults) {
    const r = tr.result
    if (r && r._select_mode) {
      if (tr.name === 'list_export_options') selectActionTypes.add('export')
      else if (tr.name === 'list_query_options') selectActionTypes.add('query')
      else if (tr.name === 'list_system_tasks') selectActionTypes.add('system_task')
      else if (tr.name === 'list_lookup_options') selectActionTypes.add('lookup')
    }
  }
  for (const tr of toolResults) {
    const result = tr.result
    // 工单创建：成功显示已创建卡片，失败/缺失参数由AI自然语言询问用户
    if (result && result.action_type === 'create_ticket') {
      if (result.error || !result.ticket_id) continue
      const ticketMsg = addMsg({
        id: tr.message_id || `t_${Date.now()}`,
        role: 'assistant',
        content: result.confirm_message || `工单已创建：${result.ticket_no}`,
        _type: 'ticket',
        _done: true,
        tool_data: result,
      })
      saveMessageState(ticketMsg)
      continue
    }
    if (result && ['export', 'query', 'system_task', 'lookup', 'profit_share'].includes(result.action_type)) {
      // API自动执行的系统任务，由AI二次回复反馈
      if (result.action_type === 'system_task' && result.auto_executed) continue
      // 系统任务：参数齐备直接执行；缺参数弹内联表单
      if (result.action_type === 'system_task' && !result.error) {
        const params = result.params || []
        const paramsValues = result.params_values || {}
        const databases = result.databases || []
        const databaseId = result.database_id || null
        const allParamsFilled = params.length === 0 || params.every(p => {
          const val = paramsValues[p.name]
          return val !== undefined && val !== null && val !== ''
        })
        const needsDbSelection = databases.length > 1 && !databaseId
        if (allParamsFilled && !needsDbSelection) {
          const autoMsg = addMsg({
            id: tr.message_id || `t_${Date.now()}`,
            role: 'assistant',
            content: result.confirm_message || `正在执行系统任务：${result.task_name}`,
            _type: 'tool',
            _dismissed: false,
            tool_data: result,
            _selected: [result.task_id],
            _selectedScripts: [{
              id: result.task_id,
              name: result.task_name || '系统任务',
              task_type: result.task_type || 'sql',
              params: params,
            }],
            _action_type: 'system_task',
            _param_values: paramsValues,
            _params_checked: true,
            _database_id: databaseId,
          })
          doExecuteSystemTask(autoMsg)
          continue
        } else {
          addMsg({
            id: tr.message_id || `t_${Date.now()}`,
            role: 'assistant',
            content: '',
            _type: 'tool',
            _dismissed: false,
            tool_data: result,
            _selected: [result.task_id],
            _selectedScripts: [{
              id: result.task_id,
              name: result.task_name || '系统任务',
              task_type: result.task_type || 'sql',
              params: params,
            }],
            _action_type: 'system_task',
            _param_values: paramsValues,
            _need_params: true,
            _param_task: {
              name: result.task_name || '系统任务',
              task_type: result.task_type || 'sql',
              params: params,
            },
            _databases: databases,
            _db_id: databaseId,
          })
          continue
        }
      }
      // 信息查询：仅 show_all_fields=true 时创建结果卡片
      if (result.action_type === 'lookup') {
        if (result.show_all_fields) {
          const hasError = !!result.error
          addMsg({
            id: tr.message_id || `t_${Date.now()}`,
            role: 'assistant',
            content: '',
            _type: 'lookup',
            _done: true,
            _failed: hasError,
            _error_msg: hasError ? result.error : '',
            tool_data: result,
          })
        }
        continue
      }
      // 同一轮已有选择卡片时，跳过重复确认卡片
      if (selectActionTypes.has(result.action_type)) continue
      // 监督者已自动评估通过：直接自动执行
      if (result._supervisor_auto_executed) {
        const autoMsg = addMsg({
          id: tr.message_id || `t_${Date.now()}`,
          role: 'assistant',
          content: `✅ 监督者已评估通过并自动执行：${result.confirm_message || result.task_name || result.script_name || ''}${result._supervisor_feedback ? '\n评估意见：' + result._supervisor_feedback : ''}`,
          _type: 'tool',
          _dismissed: false,
          tool_data: result,
        })
        saveMessageState(autoMsg)
        autoExecuteToolCard(autoMsg)
        continue
      }
      if (result.error) {
        messages.value.push({
          id: `e_${Date.now()}`,
          role: 'assistant',
          content: `⚠️ ${result.error}`,
        })
        continue
      }
      // 常规确认卡片
      const toolCard = addMsg({
        id: tr.message_id || `t_${Date.now()}`,
        role: 'assistant',
        content: '',
        _type: 'tool',
        _dismissed: false,
        tool_data: result,
      })
      saveMessageState(toolCard)
    } else if (result && result._select_mode) {
      addMsg({
        id: tr.message_id || `t_${Date.now()}`,
        role: 'assistant',
        content: result.message || '',
        _type: 'select_options',
        _select_mode: result._select_mode,
        _scripts: result.scripts || result.tasks || [],
        _action_type: result.action_type || (tr.name === 'list_export_options' ? 'export' : tr.name === 'list_system_tasks' ? 'system_task' : tr.name === 'list_lookup_options' ? 'lookup' : 'query'),
        _selected: [],
        _params_checked: false,
        _param_values: {},
        _all_checked: {},
        _selectedScripts: [],
        _missing_required_params: [],
      })
    } else if (result && result.error) {
      messages.value.push({
        id: `e_${Date.now()}`,
        role: 'assistant',
        content: `⚠️ ${result.error}`,
      })
    }
  }
  await nextTick()
  scrollToBottom()
}

/** 监督者自动执行：按类型分派 */
function autoExecuteToolCard(msg) {
  const at = msg.tool_data?.action_type
  if (at === 'export') confirmExportCard(msg)
  else if (at === 'profit_share') confirmProfitShareCard(msg)
  else if (at === 'query') confirmQueryCard(msg)
  else if (at === 'system_task') confirmSystemCard(msg)
}

/** 卡片状态样式 */
function toolCardState(msg) {
  if (msg._executing) return 'executing'
  if (msg._done) return 'done'
  if (msg._failed) return 'failed'
  if (msg._ignored) return 'ignored'
  return ''
}

function toolCardTitle(msg) {
  const td = msg.tool_data || {}
  if (msg._executing) return '任务执行中...'
  if (msg._done) return '执行成功'
  if (msg._failed) return '执行失败'
  return td.action_type === 'export' ? '导出任务确认'
    : td.action_type === 'system_task' ? '系统任务确认'
    : td.action_type === 'profit_share' ? '分润导出确认'
    : '查询任务确认'
}

function dismissTool(msg) {
  // 与AI助手页一致：仅标记忽略，卡片保留展示"已忽略"状态
  msg._ignored = true
  saveMessageState(msg)
}

/* ═══════════════ 状态持久化（与AI助手页 saveMessageState 对齐） ═══════════════ */

async function saveMessageState(msg) {
  if (!msg.id || !currentChatId.value || typeof msg.id !== 'number') return
  const metadata = {}
  if (msg._executing) metadata._executing = true
  if (msg._done) metadata._done = true
  if (msg._failed) metadata._failed = true
  if (msg._ignored) metadata._ignored = true
  if (msg._progress != null) metadata._progress = msg._progress
  if (msg._status_text) metadata._status_text = msg._status_text
  if (msg._download_url) metadata._download_url = msg._download_url
  if (msg._error_msg) metadata._error_msg = msg._error_msg
  if (msg._ai_suggestion) metadata._ai_suggestion = msg._ai_suggestion
  if (msg._type === 'lookup') {
    metadata._type = 'lookup'
    metadata.tool_data = msg.tool_data || {}
  }
  if (msg._type === 'ticket') {
    metadata._type = 'ticket'
    metadata.tool_data = msg.tool_data || {}
    metadata._done = true
  }
  if (msg._thinking) {
    metadata._thinking = msg._thinking
    metadata._thinking_done = msg._thinking_done || false
  }
  if (Object.keys(metadata).length > 0) {
    try {
      await api.ai.updateMessage(currentChatId.value, msg.id, { metadata })
    } catch {}
  }
}

/** 推送助手反馈消息（持久化，页面同款） */
async function pushAssistantFeedback(content) {
  let feedbackId = `fb_${Date.now()}`
  try {
    const res = await api.ai.createMessage(currentChatId.value, { content })
    feedbackId = res.data?.id || feedbackId
  } catch {}
  messages.value.push({ id: feedbackId, role: 'assistant', content })
  await scrollToBottom()
}

/* ═══════════════ 执行引擎：导出 ═══════════════ */

/** 工具卡片确认导出 */
async function confirmExportCard(msg) {
  if (msg._executing || msg._done) return
  const td = msg.tool_data
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在初始化任务...'
  msg._done = false
  msg._failed = false
  await scrollToBottom()
  try {
    const res = await api.export.execute({
      script_ids: [td.script_id],
      params_values: { ...(td.params || {}) },
      all_checked: td.all_checked || {},
      output_format: td.output_format || 'sheets',
    })
    if (!res.task_id && !res.data?.task_id) throw new Error('未获取到任务ID')
    const taskId = res.task_id || res.data?.task_id
    msg._status_text = '任务已提交，正在执行...'
    await pollExportStatus(taskId, msg)
  } catch (e) {
    msg._executing = false
    msg._failed = true
    msg._error_msg = e.message || '未知错误'
    saveMessageState(msg)
    scrollToBottom()
  }
}

/** select_options 卡片确认导出（参数构建与AI助手页 doExecuteExport 一致） */
async function doExecuteExportSelect(msg) {
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在初始化任务...'
  msg._done = false
  msg._failed = false
  msg._error_msg = ''
  msg._download_url = ''
  msg._need_params = false
  msg._allow_all_pending = false
  await scrollToBottom()
  try {
    const rawValues = msg._param_values || {}
    const rawAllChecked = msg._all_checked || {}
    const selectedScripts = msg._selectedScripts || []

    const allParamsConfig = []
    for (const s of selectedScripts) {
      if (!s.params) continue
      for (const p of s.params) {
        if (!allParamsConfig.find(ap => ap.name === p.name)) allParamsConfig.push(p)
      }
    }
    const params_values = {}
    const sharedParamNames = new Set(msg._shared_param_names || [])

    for (const name of sharedParamNames) {
      if (rawAllChecked[name]) continue
      const sv = rawValues[name]
      if (sv === '' || sv === undefined || sv === null) continue
      params_values[name] = sv
    }
    for (const script of selectedScripts) {
      if (!script.params) continue
      for (const p of script.params) {
        const dialogKey = script.id + '_' + p.name
        if (sharedParamNames.has(p.name)) continue
        if (p.allow_all && rawAllChecked[dialogKey]) continue
        const val = rawValues[dialogKey]
        if (val !== undefined && val !== '' && val !== null) {
          params_values[p.name] = val
        }
      }
    }
    // 范围参数拆分为 _start/_end
    Object.keys(params_values).forEach((k) => {
      const val = params_values[k]
      if (val === undefined || val === '' || val === null) {
        delete params_values[k]
        return
      }
      const paramConfig = allParamsConfig.find(p => p.name === k)
      if (paramConfig && paramConfig.range && Array.isArray(val) && val.length === 2) {
        params_values[`${k}_start`] = val[0]
        params_values[`${k}_end`] = val[1]
        delete params_values[k]
      }
    })
    const all_checked = {}
    for (const [key, checked] of Object.entries(rawAllChecked)) {
      if (!checked) continue
      if (sharedParamNames.has(key)) {
        all_checked[key] = true
        continue
      }
      const found = selectedScripts.find(s => key.startsWith(s.id + '_'))
      if (found) {
        const paramName = key.substring(found.id.toString().length + 1)
        all_checked[paramName] = true
      }
    }
    const res = await api.export.execute({
      script_ids: msg._selected,
      params_values,
      all_checked,
      output_format: 'sheets',
    })
    if (!res.task_id && !res.data?.task_id) throw new Error('未获取到任务ID')
    await pollExportStatus(res.task_id || res.data?.task_id, msg)
  } catch (e) {
    msg._executing = false
    msg._failed = true
    msg._error_msg = e.message || '未知错误'
    saveMessageState(msg)
    scrollToBottom()
  }
}

/** 轮询导出任务状态 */
function pollExportStatus(taskId, msg) {
  const statusTextMap = {
    pending: '任务等待中...',
    running: '正在执行导出...',
    completed: '执行完成',
    failed: '执行失败',
    cancelled: '已取消',
  }
  return new Promise((resolve) => {
    let pollCount = 0
    const maxPolls = 300
    const poll = async () => {
      try {
        pollCount++
        if (pollCount > maxPolls) {
          finishFailed(msg, '任务执行超时', '执行超时')
          resolve()
          return
        }
        const res = await api.export.status(taskId)
        const task = res.data
        if (!task) {
          setTimeout(poll, 2000)
          return
        }
        msg._progress = task.progress || 0
        msg._status_text = statusTextMap[task.status] || '执行中...'
        if (task.status === 'completed') {
          msg._executing = false
          msg._progress = 100
          if (task.output_file) {
            finishDone(msg, `/api/download/${taskId}`)
            const scriptNames = msg._selectedScripts?.map(s => s.name).join('、') || (msg.tool_data?.script_name || '导出任务')
            pushAssistantFeedback(`✅ 导出任务 **${scriptNames}** 已完成！\n\n- 任务ID：\`${taskId}\`\n\n点击卡片中的按钮即可下载文件。`)
          } else {
            finishNoData(msg)
            const scriptNames = msg._selectedScripts?.map(s => s.name).join('、') || (msg.tool_data?.script_name || '导出任务')
            pushAssistantFeedback(`⚠️ 导出任务 **${scriptNames}** 已执行完成，但 **未查询到任何数据**，未生成结果文件。\n\n请检查筛选参数是否正确。`)
          }
          resolve()
          return
        }
        if (task.status === 'failed') {
          msg._executing = false
          msg._failed = true
          msg._error_msg = task.error_message || '执行失败'
          msg._ai_suggestion = task.ai_suggestion || null
          msg._status_text = '执行失败'
          saveMessageState(msg)
          const scriptNames = msg._selectedScripts?.map(s => s.name).join('、') || (msg.tool_data?.script_name || '导出任务')
          let failContent = `❌ 导出任务执行失败：**${scriptNames}**\n\n**错误信息：** ${msg._error_msg}`
          if (msg._ai_suggestion) failContent += `\n\n**AI修正建议：**\n${msg._ai_suggestion}`
          pushAssistantFeedback(failContent)
          scrollToBottom()
          resolve()
          return
        }
        setTimeout(poll, 1500)
      } catch (e) {
        finishFailed(msg, '轮询任务状态失败: ' + (e.message || '未知错误'), '轮询失败')
        resolve()
      }
    }
    poll()
  })
}

function finishDone(msg, downloadUrl) {
  msg._done = true
  msg._status_text = '执行完成'
  msg._download_url = downloadUrl
  saveMessageState(msg)
  scrollToBottom()
  // 通知 AI 宠物提醒用户下载（对话框收起时也能收到气泡提醒）
  emitPetEvent('file_ready', {
    type: msg.tool_data?.action_type || 'export',
    label: msg.tool_data?.script_name || msg.tool_data?.task_name || '',
  })
}

function finishNoData(msg) {
  msg._done = true
  msg._status_text = '执行完成（无数据）'
  saveMessageState(msg)
  scrollToBottom()
}

function finishFailed(msg, error, statusText) {
  msg._executing = false
  msg._failed = true
  msg._error_msg = error
  msg._status_text = statusText || '执行失败'
  saveMessageState(msg)
  scrollToBottom()
}

/* ═══════════════ 执行引擎：系统任务 ═══════════════ */

/** 工具卡片确认系统任务：参数齐备直接执行，否则展开内联表单 */
function confirmSystemCard(msg) {
  if (msg._executing || msg._done) return
  const td = msg.tool_data
  msg._selected = [td.task_id]
  msg._selectedScripts = [{
    id: td.task_id,
    name: td.task_name || '系统任务',
    task_type: td.task_type || 'sql',
    params: td.params || [],
  }]
  msg._action_type = 'system_task'

  const hasParams = td.params && td.params.length > 0
  const paramsValues = td.params_values || {}
  const databases = td.databases || []
  const databaseId = td.database_id || null
  const needsDbSelection = databases.length > 1 && !databaseId
  const missingRequired = hasParams && td.params
    .filter(p => p.required)
    .some(p => !paramsValues[p.name] && paramsValues[p.name] !== 0)

  if ((hasParams && (missingRequired || Object.keys(paramsValues).length === 0)) || needsDbSelection) {
    // 展开内联参数表单
    const values = {}
    for (const p of td.params || []) {
      if (paramsValues[p.name] !== undefined && paramsValues[p.name] !== '') {
        values[p.name] = paramsValues[p.name]
      } else if (p.enum_enabled && p.enum_mode === 'neq' && p.neq_value) {
        values[p.name] = true
      } else if (p.enum_enabled && p.enum_values && p.enum_values.length > 0) {
        values[p.name] = p.multi ? [] : ''
      } else {
        values[p.name] = ''
      }
    }
    msg._need_params = true
    msg._param_task = { name: td.task_name || '系统任务', task_type: td.task_type || 'sql', params: td.params || [] }
    msg._param_values = values
    msg._databases = databases
    msg._db_id = databaseId
    return
  }
  if (hasParams) {
    msg._param_values = paramsValues
    msg._params_checked = true
  }
  msg._database_id = databaseId
  doExecuteSystemTask(msg)
}

/** 内联表单确认系统任务 */
function confirmSystemInline(msg) {
  if (!systemParamReady(msg)) return
  msg._database_id = msg._db_id || null
  doExecuteSystemTask(msg)
}

function systemParamReady(msg) {
  const task = msg._param_task
  if (!task) return false
  const values = msg._param_values || {}
  for (const p of task.params || []) {
    if ((task.task_type === 'sql' || p.required) && (values[p.name] === undefined || values[p.name] === null || values[p.name] === '' || (Array.isArray(values[p.name]) && values[p.name].length === 0))) {
      return false
    }
  }
  if (msg._databases && msg._databases.length > 1 && !msg._db_id) return false
  return true
}

/** 实际执行系统任务 */
async function doExecuteSystemTask(msg) {
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在初始化系统任务...'
  msg._done = false
  msg._failed = false
  msg._error_msg = ''
  msg._need_params = false
  await scrollToBottom()
  try {
    const task = msg._selectedScripts?.[0]
    if (!task) throw new Error('未选择系统任务')
    const params_values = {}
    if (msg._param_values) {
      if (task.params && task.params.length > 0) {
        for (const p of task.params) {
          const val = msg._param_values[p.name]
          if (val !== undefined && val !== '' && val !== null) {
            params_values[p.name] = val
          }
        }
      }
      if (Object.keys(params_values).length === 0 && Object.keys(msg._param_values).length > 0) {
        Object.assign(params_values, msg._param_values)
      }
    }
    const payload = { params_values }
    if (msg._database_id) payload.database_id = msg._database_id
    const res = await api.systemTask.execute(task.id, payload)
    if (!res.execution_id && !res.data?.execution_id) throw new Error('未获取到执行ID')
    await pollSystemTaskStatus(res.execution_id || res.data?.execution_id, msg)
  } catch (e) {
    finishFailed(msg, e.message || '未知错误')
  }
}

/** 轮询系统任务执行状态 */
function pollSystemTaskStatus(executionId, msg) {
  const statusTextMap = {
    pending: '任务等待中...',
    running: '正在执行系统任务...',
    completed: '执行完成',
    failed: '执行失败',
    cancelled: '已取消',
  }
  return new Promise((resolve) => {
    let pollCount = 0
    const maxPolls = 300
    const poll = async () => {
      try {
        pollCount++
        if (pollCount > maxPolls) {
          finishFailed(msg, '任务执行超时', '执行超时')
          resolve()
          return
        }
        const res = await api.systemTask.getExecution(executionId)
        const execution = res.data
        if (!execution) {
          setTimeout(poll, 2000)
          return
        }
        msg._progress = execution.progress || 0
        msg._status_text = statusTextMap[execution.status] || '执行中...'
        if (execution.status === 'completed') {
          msg._executing = false
          msg._done = true
          msg._progress = 100
          msg._status_text = '执行完成'
          saveMessageState(msg)
          const taskName = msg._selectedScripts?.map(s => s.name).join('、') || '系统任务'
          pushAssistantFeedback(`✅ 系统任务 **${taskName}** 已完成！\n\n- 执行ID：\`${executionId}\``)
          resolve()
          return
        }
        if (execution.status === 'failed') {
          msg._executing = false
          msg._failed = true
          msg._error_msg = execution.error_message || '执行失败'
          msg._ai_suggestion = execution.ai_suggestion || null
          msg._status_text = '执行失败'
          saveMessageState(msg)
          const taskName = msg._selectedScripts?.map(s => s.name).join('、') || '系统任务'
          let failContent = `❌ 系统任务执行失败：**${taskName}**\n\n**错误信息：** ${msg._error_msg}`
          if (msg._ai_suggestion) failContent += `\n\n**AI修正建议：**\n${msg._ai_suggestion}`
          pushAssistantFeedback(failContent)
          scrollToBottom()
          resolve()
          return
        }
        setTimeout(poll, 1500)
      } catch (e) {
        finishFailed(msg, '轮询任务状态失败: ' + (e.message || '未知错误'), '轮询失败')
        resolve()
      }
    }
    poll()
  })
}

/* ═══════════════ 执行引擎：查询（内联上传Excel执行） ═══════════════ */

/** 工具卡片确认查询：展开内联上传流 */
function confirmQueryCard(msg) {
  if (!msg._q_step) {
    msg._q_step = 1
    queryFileStore.delete(msg.id)
    msg._q_file_path = ''
    msg._q_file_name = ''
    msg._q_row_count = 0
    msg._q_columns = []
    msg._q_param_column = ''
    msg._q_parsing = false
  }
}

function queryFlowReady(msg) {
  return !!(msg._q_step >= 2 && msg._q_param_column && (queryFileStore.get(msg.id) || msg._q_file_path))
}

async function onQueryFileChange(ev, msg) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['xlsx', 'xls'].includes(ext)) {
    ElMessage.error('仅支持 xlsx/xls 格式')
    return
  }
  msg._q_file_name = file.name
  queryFileStore.set(msg.id, file)
  msg._q_parsing = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.query.uploadInfo(formData)
    if (res.success && res.data) {
      msg._q_row_count = res.data.row_count || 0
      msg._q_columns = res.columns || res.data.column_names || []
      msg._q_file_path = res.file_path || ''
      // 智能匹配参数列：优先脚本配置的 primary_key / param_column
      const scripts = msg._selectedScripts?.length ? msg._selectedScripts : (msg.tool_data ? [{
        primary_key: msg.tool_data.primary_key || '',
        param_column: msg.tool_data.param_column || '',
      }] : [])
      const defaults = []
      for (const s of scripts) {
        if (s.primary_key) defaults.push(s.primary_key)
        if (s.param_column) defaults.push(s.param_column)
      }
      for (const kw of defaults) {
        const found = msg._q_columns.find(c => c.includes(kw))
        if (found) {
          msg._q_param_column = found
          break
        }
      }
      msg._q_step = 2
    } else {
      ElMessage.error(res.message || '文件解析失败')
    }
  } catch (e) {
    ElMessage.error(e.message || '文件解析失败')
  } finally {
    msg._q_parsing = false
  }
}

/** 执行查询任务 */
async function executeQueryCard(msg) {
  if (!queryFlowReady(msg) || msg._executing) return
  const queryFile = queryFileStore.get(msg.id) || null
  if (!queryFile && !msg._q_file_path) {
    ElMessage.warning('请先上传 Excel 文件')
    return
  }
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在初始化查询任务...'
  msg._done = false
  msg._failed = false
  msg._error_msg = ''
  await scrollToBottom()
  try {
    const formData = new FormData()
    formData.append('script_ids', JSON.stringify(msg._selected || [msg.tool_data.script_id]))
    if (queryFile) formData.append('file', queryFile)
    else if (msg._q_file_path) formData.append('file_path', msg._q_file_path)
    formData.append('param_column', msg._q_param_column)
    const newSheet = msg._selectedScripts?.some(s => s.new_sheet === false) ? 'false' : 'true'
    formData.append('new_sheet', newSheet)
    const res = await api.query.execute(formData)
    if (!res.task_id && !res.data?.task_id) throw new Error('未获取到任务ID')
    await pollQueryStatus(res.task_id || res.data?.task_id, msg)
  } catch (e) {
    finishFailed(msg, e.message || '未知错误')
  }
}

/** 轮询查询任务状态 */
function pollQueryStatus(taskId, msg) {
  const statusTextMap = {
    pending: '任务等待中...',
    running: '正在执行查询...',
    completed: '执行完成',
    failed: '执行失败',
    cancelled: '已取消',
  }
  return new Promise((resolve) => {
    let pollCount = 0
    const maxPolls = 300
    const poll = async () => {
      try {
        pollCount++
        if (pollCount > maxPolls) {
          finishFailed(msg, '任务执行超时', '执行超时')
          resolve()
          return
        }
        const res = await api.query.status(taskId)
        const task = res.data
        if (!task) {
          setTimeout(poll, 2000)
          return
        }
        msg._progress = task.progress || 0
        msg._status_text = statusTextMap[task.status] || '执行中...'
        if (task.status === 'completed') {
          msg._executing = false
          msg._progress = 100
          if (task.output_file) {
            finishDone(msg, `/api/download/${taskId}`)
            const scriptNames = msg._selectedScripts?.map(s => s.name).join('、') || '查询任务'
            pushAssistantFeedback(`✅ 查询任务 **${scriptNames}** 已完成！\n\n- 任务ID：\`${taskId}\`\n\n点击卡片中的按钮即可下载文件。`)
          } else {
            finishNoData(msg)
            const scriptNames = msg._selectedScripts?.map(s => s.name).join('、') || '查询任务'
            pushAssistantFeedback(`⚠️ 查询任务 **${scriptNames}** 已执行完成，但 **未查询到任何数据**。\n\n请检查筛选参数是否正确。`)
          }
          resolve()
          return
        }
        if (task.status === 'failed') {
          msg._executing = false
          msg._failed = true
          msg._error_msg = task.error_message || '执行失败'
          msg._ai_suggestion = task.ai_suggestion || null
          msg._status_text = '执行失败'
          saveMessageState(msg)
          let failContent = `❌ 查询任务执行失败\n\n**错误信息：** ${msg._error_msg}`
          if (msg._ai_suggestion) failContent += `\n\n**AI修正建议：**\n${msg._ai_suggestion}`
          pushAssistantFeedback(failContent)
          scrollToBottom()
          resolve()
          return
        }
        setTimeout(poll, 1500)
      } catch (e) {
        finishFailed(msg, '轮询任务状态失败: ' + (e.message || '未知错误'), '轮询失败')
        resolve()
      }
    }
    poll()
  })
}

/* ═══════════════ 执行引擎：分润导出 ═══════════════ */

async function confirmProfitShareCard(msg) {
  if (msg._executing || msg._done) return
  const td = msg.tool_data
  msg._executing = true
  msg._progress = 5
  msg._status_text = '正在提交分润导出任务...'
  msg._done = false
  msg._failed = false
  msg._error_msg = ''
  await scrollToBottom()
  try {
    const data = {
      org_no: td.org_no,
      start_time: td.start_time,
      end_time: td.end_time,
    }
    if (td.database_connection_id) data.database_connection_id = td.database_connection_id
    const res = await api.profitShare.execute(data)
    const result = res.data || res
    const taskId = result.task_id
    if (!taskId) throw new Error('未获取到任务ID')
    msg._status_text = '任务已提交，正在执行...'
    saveMessageState(msg)
    subscribeProfitShareSSE(taskId, msg)
  } catch (e) {
    msg._executing = false
    msg._failed = true
    msg._error_msg = e?.response?.data?.message || e.message || '未知错误'
    msg._status_text = '提交失败'
    saveMessageState(msg)
    ElMessage.error('分润导出提交失败: ' + msg._error_msg)
  }
}

function subscribeProfitShareSSE(taskId, msg) {
  if (profitShareSource) profitShareSource.close()
  const url = api.profitShare.streamStatus(taskId)
  const eventSource = new EventSource(url)
  profitShareSource = eventSource
  const statusTextMap = {
    pending: '任务等待中...',
    running: '正在计算分润...',
    completed: '执行完成',
    failed: '执行失败',
    cancelled: '已取消',
    manual_cancelled: '已终止',
    timeout: '推送超时',
  }
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.error) {
        eventSource.close()
        profitShareSource = null
        finishFailed(msg, data.error)
        return
      }
      if (data.progress !== undefined) msg._progress = Math.round(data.progress)
      if (data.status) msg._status_text = statusTextMap[data.status] || '执行中...'
      if (['completed', 'failed', 'cancelled', 'manual_cancelled', 'timeout'].includes(data.status)) {
        eventSource.close()
        profitShareSource = null
        msg._executing = false
        if (data.status === 'completed') {
          msg._done = true
          msg._progress = 100
          msg._status_text = '执行完成'
          msg._download_url = `/api/download/${taskId}`
          saveMessageState(msg)
          const td = msg.tool_data
          const summary = data.total_rows != null && data.success_count != null
            ? `\n- 订单总数：${data.total_rows}\n- 成功：${data.success_count}，失败：${data.failure_count || 0}`
            : ''
          pushAssistantFeedback(`✅ 代理商 **${td.org_no}** 的分润导出已完成！\n\n- 任务ID：\`${taskId}\`\n- 时间范围：${td.start_time} ~ ${td.end_time}${summary}\n\n点击卡片下载文件。`)
          scrollToBottom()
        } else if (data.status === 'failed') {
          msg._failed = true
          msg._error_msg = data.error_message || '执行失败'
          msg._status_text = '执行失败'
          saveMessageState(msg)
          pushAssistantFeedback(`❌ 代理商 **${msg.tool_data?.org_no}** 的分润导出执行失败\n\n**错误信息：** ${msg._error_msg}`)
        } else if (data.status === 'timeout') {
          msg._failed = true
          msg._error_msg = '状态推送超时，请稍后在导出中心查看结果'
          msg._status_text = '推送超时'
          saveMessageState(msg)
        } else {
          msg._status_text = statusTextMap[data.status] || '已终止'
          saveMessageState(msg)
        }
      }
    } catch {}
  }
  eventSource.onerror = () => {
    eventSource.close()
    profitShareSource = null
    if (msg._executing) pollProfitShareStatus(taskId, msg)
  }
}

function pollProfitShareStatus(taskId, msg) {
  let pollCount = 0
  const maxPolls = 300
  const statusTextMap = {
    pending: '任务等待中...',
    running: '正在计算分润...',
    completed: '执行完成',
    failed: '执行失败',
    cancelled: '已取消',
    manual_cancelled: '已终止',
  }
  const poll = async () => {
    try {
      pollCount++
      if (pollCount > maxPolls) {
        finishFailed(msg, '任务执行超时', '执行超时')
        return
      }
      const res = await api.profitShare.status(taskId)
      const data = res.data || res
      if (!data) {
        setTimeout(poll, 2000)
        return
      }
      msg._progress = Math.round(data.progress || 0)
      msg._status_text = statusTextMap[data.status] || '执行中...'
      if (data.status === 'completed') {
        msg._executing = false
        msg._done = true
        msg._progress = 100
        msg._status_text = '执行完成'
        msg._download_url = `/api/download/${taskId}`
        saveMessageState(msg)
        const td = msg.tool_data
        const summary = data.total_rows != null && data.success_count != null
          ? `\n- 订单总数：${data.total_rows}\n- 成功：${data.success_count}，失败：${data.failure_count || 0}`
          : ''
        pushAssistantFeedback(`✅ 代理商 **${td.org_no}** 的分润导出已完成！\n\n- 任务ID：\`${taskId}\`\n- 时间范围：${td.start_time} ~ ${td.end_time}${summary}`)
        return
      }
      if (['failed', 'cancelled', 'manual_cancelled'].includes(data.status)) {
        msg._executing = false
        if (data.status === 'failed') {
          msg._failed = true
          msg._error_msg = data.error_message || '执行失败'
          msg._status_text = '执行失败'
          pushAssistantFeedback(`❌ 代理商 **${msg.tool_data?.org_no}** 的分润导出执行失败\n\n**错误信息：** ${msg._error_msg}`)
        } else {
          msg._status_text = statusTextMap[data.status] || '已终止'
        }
        saveMessageState(msg)
        return
      }
      setTimeout(poll, 1500)
    } catch (e) {
      finishFailed(msg, '轮询任务状态失败: ' + (e.message || '未知错误'), '轮询失败')
    }
  }
  poll()
}

/* ═══════════════ select_options 卡片：选择与执行 ═══════════════ */

function confirmSelection(msg) {
  const selectedIds = msg._selected
  if (!selectedIds || selectedIds.length === 0) {
    ElMessage.warning('请至少选择一个选项')
    return
  }
  msg._selectedScripts = (msg._scripts || []).filter(s => selectedIds.includes(s.id)) || []

  if (msg._action_type === 'query') {
    // 查询任务：内联上传执行流
    msg._q_step = 1
    queryFileStore.delete(msg.id)
    msg._q_file_path = ''
    msg._q_file_name = ''
    msg._q_row_count = 0
    msg._q_columns = []
    msg._q_param_column = ''
    msg._q_parsing = false
    // 复用tool卡片模板渲染查询流：转换卡片类型
    msg._type = 'tool'
    msg.tool_data = {
      action_type: 'query',
      confirm_message: `已选择 ${msg._selectedScripts.map(s => s.name).join('、')}，请上传 Excel 文件执行查询`,
      script_id: msg._selectedScripts[0]?.id,
    }
    scrollToBottom()
    return
  }

  if (msg._action_type === 'system_task') {
    const hasAnyParams = msg._selectedScripts.some(s => s.params && s.params.length > 0)
    if (!hasAnyParams) {
      doExecuteSystemTask(msg)
      return
    }
    openSelectParamForm(msg)
    return
  }

  if (msg._action_type === 'lookup') {
    const hasAnyParams = msg._selectedScripts.some(s => s.params && s.params.length > 0)
    if (!hasAnyParams) {
      doExecuteLookupSelect(msg)
      return
    }
    openSelectParamForm(msg)
    return
  }

  // 导出任务
  const hasAnyParams = msg._selectedScripts.some(s => s.params && s.params.length > 0)
  if (!hasAnyParams) {
    doExecuteExportSelect(msg)
    return
  }
  const allParamsAllowAll = msg._selectedScripts.every(s =>
    !s.params || s.params.length === 0 || s.params.every(p => p.allow_all && !p.required)
  )
  if (allParamsAllowAll) {
    msg._allow_all_pending = true
    scrollToBottom()
    return
  }
  openSelectParamForm(msg)
}

function confirmAllowAll(msg) {
  // 全部允许筛选的参数勾选"全部"
  const selectedScripts = msg._selectedScripts || []
  const sharedParamNames = new Set()
  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (p.allow_all) {
        msg._all_checked[script.id + '_' + p.name] = true
      }
    }
  }
  const paramNameCount = {}
  for (const script of selectedScripts) {
    if (!script.params) continue
    for (const p of script.params) {
      if (!paramNameCount[p.name]) paramNameCount[p.name] = 0
      paramNameCount[p.name]++
    }
  }
  for (const [name, count] of Object.entries(paramNameCount)) {
    if (count > 1) sharedParamNames.add(name)
  }
  msg._shared_param_names = [...sharedParamNames]
  msg._params_checked = true
  msg._allow_all_pending = false
  doExecuteExportSelect(msg)
}

/** 构建内联参数表单（公共参数共享，独立参数按脚本隔离，与AI助手页参数对话框逻辑一致） */
function openSelectParamForm(msg) {
  const selectedScripts = msg._selectedScripts || []
  const paramCountMap = {}
  const scriptParamMap = {}
  for (const script of selectedScripts) {
    if (!script.params || script.params.length === 0) continue
    scriptParamMap[script.id] = []
    for (const p of script.params) {
      if (!paramCountMap[p.name]) {
        paramCountMap[p.name] = { param: p, scriptIds: [] }
      }
      paramCountMap[p.name].scriptIds.push(script.id)
      scriptParamMap[script.id].push(p)
    }
  }
  const sharedNames = new Set()
  for (const info of Object.values(paramCountMap)) {
    if (info.scriptIds.length > 1) sharedNames.add(info.param.name)
  }
  const fields = []
  const values = {}
  const allChecked = {}

  const initValue = (p) => {
    if (p.enum_enabled && p.enum_mode === 'neq' && p.neq_value) return true
    if (p.enum_enabled && p.enum_values && p.enum_values.length > 0) return p.multi ? [] : ''
    return ''
  }

  // 公共参数（key为纯参数名）
  for (const p of selectedScripts[0]?.params || []) {
    if (!sharedNames.has(p.name)) continue
    fields.push({ key: p.name, param: p, scriptId: null, scriptName: '', shared: true })
    values[p.name] = initValue(p)
    if (p.allow_all) allChecked[p.name] = false
  }
  // 独立参数（key为scriptId_paramName）
  for (const script of selectedScripts) {
    const params = (scriptParamMap[script.id] || []).filter(p => !sharedNames.has(p.name))
    for (const p of params) {
      const key = script.id + '_' + p.name
      fields.push({ key, param: p, scriptId: script.id, scriptName: script.name, shared: false })
      values[key] = initValue(p)
      if (p.allow_all) allChecked[key] = false
    }
  }
  msg._param_fields = fields
  msg._param_form = values
  msg._param_all = allChecked
  // 系统任务：初始化参数（含AI已解析值）与数据库
  if (msg._action_type === 'system_task') {
    const task = selectedScripts[0]
    if (task) {
      const existing = msg.tool_data?.params_values || {}
      const sv = {}
      for (const p of task.params || []) {
        if (existing[p.name] !== undefined && existing[p.name] !== '') sv[p.name] = existing[p.name]
        else sv[p.name] = values[p.name] ?? ''
      }
      msg._param_values = sv
      msg._databases = msg.tool_data?.databases || []
      msg._db_id = msg.tool_data?.database_id || null
    }
  } else {
    msg._param_values = values
    msg._all_checked = allChecked
  }
  msg._need_params = true
  msg._allow_all_pending = false
  scrollToBottom()
}

/** 汇总系统任务表单值（表单键 scriptId_name → 纯参数名，覆盖AI已解析初值） */
function systemTaskFormValues(msg) {
  const merged = { ...(msg._param_values || {}) }
  for (const f of msg._param_fields || []) {
    merged[f.param.name] = msg._param_form?.[f.key]
  }
  return merged
}

function selectParamReady(msg) {
  if (msg._action_type === 'system_task') {
    const task = msg._selectedScripts?.[0] || msg._param_task
    if (!task) return false
    const values = systemTaskFormValues(msg)
    const isSql = task.task_type === 'sql'
    for (const p of task.params || []) {
      const required = isSql || p.required
      if (!required) continue
      const v = values[p.name]
      if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) return false
    }
    if (msg._databases && msg._databases.length > 1 && !msg._db_id) return false
    return true
  }
  const fields = msg._param_fields || []
  const values = msg._param_form || {}
  for (const f of fields) {
    if (f.param.required && msg._param_all && !msg._param_all[f.key]) {
      const v = values[f.key]
      if (v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)) return false
    }
  }
  return true
}

/** 内联参数表单确认：按类型分派执行 */
function confirmSelectParams(msg) {
  if (!selectParamReady(msg)) return
  if (msg._action_type === 'system_task') {
    msg._param_values = systemTaskFormValues(msg)
    msg._database_id = msg._db_id || null
    doExecuteSystemTask(msg)
    return
  }
  if (msg._action_type === 'lookup') {
    const values = {}
    for (const f of msg._param_fields || []) {
      if (msg._param_all?.[f.key]) continue
      const v = msg._param_form?.[f.key]
      if (v !== undefined && v !== '' && v !== null) values[f.param.name] = v
    }
    msg._lookup_params = values
    doExecuteLookupSelect(msg)
    return
  }
  // 导出：将表单值写入 _param_values/_all_checked（键规则与AI助手页一致）
  const values = {}
  for (const f of msg._param_fields || []) {
    values[f.key] = msg._param_form?.[f.key]
  }
  msg._param_values = values
  msg._all_checked = { ...(msg._param_all || {}) }
  msg._shared_param_names = (msg._param_fields || []).filter(f => f.shared).map(f => f.param.name)
  msg._params_checked = true
  doExecuteExportSelect(msg)
}

/** 执行信息查询（select_options 入口，创建独立结果卡片） */
async function doExecuteLookupSelect(msg) {
  const script = msg._selectedScripts?.[0]
  if (!script) return
  const params_values = {}
  if (msg._lookup_params) {
    // 表单确认路径：已按纯参数名归集
    Object.assign(params_values, msg._lookup_params)
  } else if (msg._param_values) {
    if (script.params && script.params.length > 0) {
      for (const p of script.params) {
        const val = msg._param_values[p.name]
        if (val !== undefined && val !== '' && val !== null) params_values[p.name] = val
      }
    }
    if (Object.keys(params_values).length === 0 && Object.keys(msg._param_values).length > 0) {
      Object.assign(params_values, msg._param_values)
    }
  }
  msg._need_params = false
  msg._lookup_params = null

  let cardMsgId = `lk_${Date.now()}`
  try {
    const createRes = await api.ai.createMessage(currentChatId.value, { content: `正在执行信息查询：${script.name}` })
    cardMsgId = createRes.data?.id || cardMsgId
  } catch {}
  const cardMsg = reactive({
    id: cardMsgId,
    role: 'assistant',
    content: '',
    _type: 'lookup',
    _done: false,
    _failed: false,
    tool_data: {
      script_name: script.name,
      params_values,
      results: [],
      columns: [],
      row_count: 0,
    },
  })
  messages.value.push(cardMsg)
  msg._executing = true
  msg._status_text = '正在执行信息查询...'
  await scrollToBottom()
  try {
    const res = await api.lookup.execute({
      script_id: script.id,
      params_values,
    })
    cardMsg._done = true
    const data = res.data || res
    cardMsg._failed = !data.success
    if (data.success) {
      cardMsg.tool_data.results = data.results || []
      cardMsg.tool_data.columns = data.columns || []
      cardMsg.tool_data.row_count = data.row_count || 0
    } else {
      cardMsg._error_msg = data.error_message || res.message || '查询执行失败'
    }
  } catch (e) {
    cardMsg._done = true
    cardMsg._failed = true
    cardMsg._error_msg = e.message || '查询执行失败'
  }
  msg._executing = false
  msg._done = true
  msg._status_text = '执行完成'
  saveMessageState(cardMsg)
  saveMessageState(msg)
  await scrollToBottom()
}

/* ═══════════════ 文件下载 ═══════════════ */

function downloadFile(url) {
  const token = localStorage.getItem('token')
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  fetch(url, { headers })
    .then(res => {
      if (!res.ok) {
        return res.json().then(data => {
          throw new Error(data.message || '下载失败')
        }).catch(e => {
          if (e.message && e.message !== 'Unexpected end of JSON input') {
            ElMessage.error(e.message)
          } else {
            ElMessage.error('文件下载失败，请稍后重试')
          }
          throw e
        })
      }
      const disposition = res.headers.get('Content-Disposition')
      let filename = 'result.xlsx'
      if (disposition) {
        const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;\n]+)/i)
        if (match) filename = decodeURIComponent(match[1].replace(/['"]/g, ''))
      }
      return res.blob().then(blob => ({ blob, filename }))
    })
    .then(({ blob, filename }) => {
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(blobUrl)
    })
    .catch(() => {})
}
</script>

<style scoped>
.pet-chat-mask {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: 0 28px 108px 0;
}

.pet-chat-dialog {
  width: 520px;
  height: 680px;
  max-height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  background: var(--main-bg, #fff);
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.22), 0 0 0 1px rgba(64, 158, 255, 0.08);
}

/* ── 头部 ── */
.pet-chat-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #a8c8f8 0%, #7ea6ee 50%, #b7d5f7 100%);
  position: relative;
}

.pet-chat-header::before,
.pet-chat-header::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
}

.pet-chat-header::before {
  width: 90px;
  height: 90px;
  top: -34px;
  left: -20px;
}

.pet-chat-header::after {
  width: 52px;
  height: 52px;
  bottom: -18px;
  right: 64px;
}

.pet-chat-title {
  flex: 1;
  min-width: 0;
  position: relative;
  z-index: 1;
}

.title-main {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.title-sub {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.85);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 2px;
}

.header-btn {
  position: relative;
  z-index: 1;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.header-btn:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: translateY(-1px);
}

.header-btn.stop {
  background: rgba(245, 108, 108, 0.85);
}

.header-btn.stop:hover {
  background: #f56c6c;
}

/* ── 宠物头像 ── */
.pet-avatar-mini {
  position: relative;
  z-index: 1;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.28);
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.5);
  animation: mini-float 2.8s ease-in-out infinite;
}

.pet-avatar-mini.working {
  box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.5), 0 0 12px rgba(255, 217, 61, 0.9);
}

@keyframes mini-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

/* ── 消息区 ── */
.pet-chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px 12px;
  background: var(--main-bg, #f7f9fc);
  background-image: radial-gradient(circle at 12px 12px, rgba(126, 166, 238, 0.08) 2px, transparent 2.5px);
  background-size: 34px 34px;
}

.body-loading {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 40px 0;
}

.body-empty {
  text-align: center;
  padding: 40px 0 20px;
  color: #606266;
  font-size: 13px;
}

.empty-pet-avatar {
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  line-height: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 32%, #ffffff, #eaf1fd);
  box-shadow: 0 4px 14px rgba(126, 166, 238, 0.28);
  animation: mini-float 2.8s ease-in-out infinite;
}

.empty-tip {
  color: #a0a6b0;
  font-size: 12px;
  margin-top: 6px;
  padding: 0 24px;
}

.chat-row {
  display: flex;
  margin-bottom: 12px;
  gap: 8px;
}

.chat-row.user {
  justify-content: flex-end;
}

.chat-row.user .bubble.user {
  margin-left: auto;
}

.row-avatar {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  align-self: flex-end;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  line-height: 1;
  border-radius: 50%;
  background: radial-gradient(circle at 40% 32%, #ffffff, #eaf1fd);
  box-shadow: 0 2px 6px rgba(139, 163, 201, 0.2);
}

.bubble {
  max-width: 86%;
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.65;
  border-radius: 14px;
  word-break: break-word;
}

.bubble.user {
  background: linear-gradient(135deg, #6ea3f0, #5288e0);
  color: #fff;
  border-bottom-right-radius: 5px;
}

.bubble.assistant {
  background: #fff;
  color: var(--text-primary, #303133);
  border: 1px solid rgba(126, 166, 238, 0.25);
  border-bottom-left-radius: 5px;
  box-shadow: 0 2px 8px rgba(139, 163, 201, 0.12);
}

.bubble-content :deep(p) {
  margin: 0 0 6px;
}

.bubble-content :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble-content :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
}

.bubble-content :deep(code) {
  font-family: Consolas, Monaco, monospace;
  background: rgba(126, 166, 238, 0.14);
  padding: 1px 5px;
  border-radius: 4px;
  color: #4a6fb5;
}

.bubble-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.bubble-content :deep(ul),
.bubble-content :deep(ol) {
  padding-left: 18px;
  margin: 4px 0;
}

.bubble-content :deep(table) {
  border-collapse: collapse;
  font-size: 12px;
  margin: 6px 0;
}

.bubble-content :deep(th),
.bubble-content :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
}

.bubble-content :deep(blockquote) {
  margin: 4px 0;
  padding: 2px 10px;
  border-left: 3px solid #a8c8f8;
  color: #909399;
}

.thinking-tag {
  font-size: 11px;
  color: #9b7ee0;
  margin-bottom: 6px;
  animation: thinking-pulse 1.4s ease-in-out infinite;
  cursor: help;
}

@keyframes thinking-pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.stream-cursor {
  display: inline-block;
  width: 7px;
  height: 14px;
  margin-left: 2px;
  vertical-align: -2px;
  background: #7ea6ee;
  border-radius: 2px;
  animation: cursor-blink 0.9s steps(2) infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.msg-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
  font-size: 10px;
  color: #b0b6c0;
}

/* ── 监督者复核 ── */
.supervision-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 8px;
  font-size: 11px;
  background: rgba(103, 194, 58, 0.1);
  color: #529b2e;
  cursor: pointer;
  transition: background 0.2s;
}

.supervision-chip:hover {
  background: rgba(103, 194, 58, 0.18);
}

.supervision-chip.flagged {
  background: rgba(230, 162, 60, 0.14);
  color: #b88230;
}

.supervision-chip.flagged:hover {
  background: rgba(230, 162, 60, 0.24);
}

.supervision-text {
  flex: 1;
  min-width: 0;
}

.review-toggle {
  transition: transform 0.2s;
}

.review-toggle.open {
  transform: rotate(180deg);
}

.review-detail {
  margin-top: 6px;
  border-top: 1px dashed rgba(126, 166, 238, 0.35);
  padding-top: 6px;
}

.review-record {
  padding: 6px;
  border-radius: 8px;
  background: rgba(126, 166, 238, 0.06);
  margin-bottom: 6px;
}

.review-record-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.review-round {
  font-size: 11px;
  font-weight: 600;
  color: #606266;
}

.review-verdict {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 6px;
  font-weight: 600;
}

.review-verdict.approved {
  background: rgba(103, 194, 58, 0.15);
  color: #529b2e;
}

.review-verdict.retry {
  background: rgba(230, 162, 60, 0.15);
  color: #b88230;
}

.review-verdict.flag_human {
  background: rgba(245, 108, 108, 0.15);
  color: #c45656;
}

.review-line {
  font-size: 11px;
  color: #6b7280;
  line-height: 1.6;
  margin-top: 2px;
}

.review-line b {
  color: #4a5568;
}

.review-line.feedback {
  color: #4a6fb5;
}

/* ── 卡片通用 ── */
.card-stack {
  max-width: 92%;
  min-width: 0;
}

.tool-card {
  background: #fff;
  border: 1px solid rgba(126, 166, 238, 0.28);
  border-radius: 14px;
  border-bottom-left-radius: 5px;
  box-shadow: 0 2px 10px rgba(139, 163, 201, 0.14);
  overflow: hidden;
  font-size: 12px;
}

.tool-card.executing {
  border-color: rgba(230, 162, 60, 0.55);
}

.tool-card.done {
  border-color: rgba(103, 194, 58, 0.55);
}

.tool-card.failed {
  border-color: rgba(245, 108, 108, 0.55);
}

.tool-card.ignored {
  opacity: 0.55;
}

.tool-card-header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px 12px;
  background: linear-gradient(135deg, rgba(168, 200, 248, 0.16), rgba(126, 166, 238, 0.1));
  border-bottom: 1px solid rgba(126, 166, 238, 0.16);
}

.tool-icon {
  font-size: 13px;
  color: #7ea6ee;
}

.tool-icon.ok {
  color: #67c23a;
}

.tool-icon.bad {
  color: #f56c6c;
}

.tool-title {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  color: #4a5568;
  font-size: 12px;
}

.sup-badge {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 8px;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.sup-badge.ok {
  background: rgba(103, 194, 58, 0.14);
  color: #529b2e;
}

.sup-badge.warn {
  background: rgba(230, 162, 60, 0.16);
  color: #b88230;
}

.tool-card-body {
  padding: 10px 12px;
}

.tool-confirm-msg {
  margin: 0 0 6px;
  color: #4a5568;
  line-height: 1.6;
  white-space: pre-wrap;
}

.sup-feedback {
  font-size: 11px;
  color: #529b2e;
  background: rgba(103, 194, 58, 0.08);
  border-radius: 8px;
  padding: 5px 8px;
  margin-bottom: 6px;
}

.param-preview {
  border: 1px dashed rgba(126, 166, 238, 0.35);
  border-radius: 8px;
  padding: 6px 8px;
  margin-bottom: 6px;
}

.param-preview-row {
  display: flex;
  font-size: 11px;
  line-height: 1.7;
}

.pp-label {
  color: #8a94a6;
  flex-shrink: 0;
}

.pp-value {
  color: #4a5568;
  word-break: break-all;
}

.tool-warning {
  font-size: 11px;
  color: #b88230;
  margin: 0 0 6px;
}

/* ── 查询内联流 ── */
.query-flow {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 6px;
}

.qf-step {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: #6b7280;
}

.qf-step-no {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #e5eaf3;
  color: #909399;
  font-size: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.qf-step-no.active {
  background: #7ea6ee;
  color: #fff;
}

.qf-upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 8px;
  background: rgba(126, 166, 238, 0.12);
  color: #4a6fb5;
  cursor: pointer;
  font-size: 11px;
  border: 1px dashed rgba(126, 166, 238, 0.45);
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qf-upload-btn:hover {
  background: rgba(126, 166, 238, 0.2);
}

.qf-select {
  flex: 1;
  min-width: 0;
  height: 24px;
  border: 1px solid rgba(126, 166, 238, 0.4);
  border-radius: 6px;
  font-size: 11px;
  color: #4a5568;
  background: #fff;
  padding: 0 4px;
}

.qf-tip {
  font-size: 11px;
  color: #909399;
}

/* ── 内联参数表单 ── */
.inline-param-form {
  border: 1px dashed rgba(126, 166, 238, 0.4);
  border-radius: 10px;
  padding: 8px;
  margin-top: 6px;
  background: rgba(126, 166, 238, 0.04);
}

.ipf-item {
  margin-bottom: 8px;
}

.ipf-item:last-of-type {
  margin-bottom: 6px;
}

.ipf-label {
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.ipf-script {
  color: #7ea6ee;
  font-weight: 600;
}

.ipf-label .req {
  color: #f56c6c;
}

.allow-all {
  font-size: 10px;
  color: #909399;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  margin-left: auto;
}

.ipf-control {
  min-height: 24px;
}

.ipf-input {
  width: 100%;
  height: 26px;
  border: 1px solid rgba(126, 166, 238, 0.4);
  border-radius: 7px;
  font-size: 12px;
  color: var(--text-primary, #303133);
  background: #fff;
  padding: 0 8px;
  outline: none;
  box-sizing: border-box;
}

.ipf-input:focus {
  border-color: #7ea6ee;
  box-shadow: 0 0 0 2px rgba(126, 166, 238, 0.15);
}

.ipf-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

/* ── 选项列表 ── */
.option-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 4px 0;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 6px 8px;
  border-radius: 9px;
  border: 1px solid rgba(126, 166, 238, 0.18);
  cursor: pointer;
  transition: all 0.15s;
  font-size: 12px;
}

.option-item:hover {
  border-color: rgba(126, 166, 238, 0.5);
  background: rgba(126, 166, 238, 0.05);
}

.option-item input {
  margin-top: 2px;
  accent-color: #5288e0;
}

.option-detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.option-name {
  font-weight: 600;
  color: #4a5568;
}

.option-desc {
  font-size: 10px;
  color: #98a2b3;
}

.option-params {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.mini-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(144, 147, 153, 0.12);
  color: #6b7280;
}

.mini-tag.req {
  background: rgba(245, 108, 108, 0.1);
  color: #c45656;
}

.mini-tag.ok-tag {
  background: rgba(103, 194, 58, 0.14);
  color: #529b2e;
}

.allow-all-confirm {
  border: 1px dashed rgba(230, 162, 60, 0.5);
  border-radius: 10px;
  padding: 8px;
  margin-top: 6px;
  background: rgba(230, 162, 60, 0.05);
}

.allow-all-confirm p {
  margin: 0 0 6px;
  font-size: 11px;
  color: #8a6d3b;
}

/* ── 进度/下载/错误 ── */
.progress-info {
  margin: 6px 0;
}

.progress-text {
  display: block;
  font-size: 11px;
  color: #8a94a6;
  margin-top: 3px;
}

.download-row {
  margin-top: 6px;
}

.error-msg {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  font-size: 11px;
  color: #c45656;
  margin-top: 6px;
  line-height: 1.6;
  word-break: break-all;
}

.ai-suggestion {
  margin-top: 3px;
  color: #b88230;
}

/* ── 卡片按钮 ── */
.tool-card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border-top: 1px solid rgba(126, 166, 238, 0.14);
  background: rgba(126, 166, 238, 0.03);
}

.card-btn {
  border: none;
  border-radius: 8px;
  font-size: 11px;
  padding: 5px 11px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  font-family: inherit;
}

.card-btn.primary {
  background: linear-gradient(135deg, #6ea3f0, #5288e0);
  color: #fff;
}

.card-btn.primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(82, 136, 224, 0.4);
}

.card-btn.primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.card-btn.success {
  background: linear-gradient(135deg, #67c23a, #4caf50);
  color: #fff;
}

.card-btn.success:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(76, 175, 80, 0.4);
}

.card-btn.text {
  background: transparent;
  color: #8a94a6;
  padding: 5px 7px;
}

.card-btn.text:hover {
  color: #4a6fb5;
}

/* ── lookup 结果 ── */
.lookup-params {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
}

.lookup-table-wrap {
  overflow-x: auto;
  border: 1px solid rgba(126, 166, 238, 0.2);
  border-radius: 8px;
}

.lookup-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 11px;
}

.lookup-table th {
  background: rgba(126, 166, 238, 0.1);
  color: #4a5568;
  font-weight: 600;
  text-align: left;
}

.lookup-table th,
.lookup-table td {
  border-bottom: 1px solid rgba(126, 166, 238, 0.12);
  padding: 4px 8px;
  white-space: nowrap;
}

.lookup-more {
  font-size: 10px;
  color: #98a2b3;
  padding: 4px 8px;
}

.lookup-nodata {
  font-size: 11px;
  color: #8a94a6;
}

/* ── 输入区 ── */
.pet-chat-footer {
  padding: 10px 12px 12px;
  background: var(--header-bg, #fff);
  border-top: 1px solid var(--border-color, #e4e7ed);
}

.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--main-bg, #f5f7fa);
  border: 1.5px solid rgba(126, 166, 238, 0.35);
  border-radius: 14px;
  padding: 8px 8px 8px 14px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-wrap:focus-within {
  border-color: #7ea6ee;
  box-shadow: 0 0 0 3px rgba(126, 166, 238, 0.15);
}

.input-wrap textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-size: 13px;
  line-height: 1.6;
  max-height: 96px;
  color: var(--text-primary, #303133);
  font-family: inherit;
}

.input-wrap textarea::placeholder {
  color: #a8adb8;
}

.send-btn {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 11px;
  background: linear-gradient(135deg, #6ea3f0, #5288e0);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px) scale(1.04);
  box-shadow: 0 4px 10px rgba(82, 136, 224, 0.4);
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.send-btn.stop {
  background: linear-gradient(135deg, #f56c6c, #d94646);
}

.footer-tip {
  font-size: 11px;
  color: #a8adb8;
  text-align: center;
  margin-top: 8px;
}

/* ── 弹窗动画 ── */
.pet-chat-pop-enter-active {
  transition: all 0.32s cubic-bezier(0.34, 1.4, 0.64, 1);
}

.pet-chat-pop-leave-active {
  transition: all 0.22s ease;
}

.pet-chat-pop-enter-from,
.pet-chat-pop-leave-to {
  opacity: 0;
}

.pet-chat-pop-enter-from .pet-chat-dialog {
  transform: translateY(28px) scale(0.92);
}

.pet-chat-pop-enter-active .pet-chat-dialog,
.pet-chat-pop-leave-active .pet-chat-dialog {
  transition: transform 0.32s cubic-bezier(0.34, 1.4, 0.64, 1);
}

.pet-chat-pop-leave-to .pet-chat-dialog {
  transform: translateY(20px) scale(0.95);
}
</style>
