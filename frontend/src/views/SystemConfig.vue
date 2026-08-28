<template>
  <div class="system-config">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-cog"></i> 系统配置</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="邮件服务" name="email">
          <el-form ref="emailFormRef" :model="emailForm" label-width="120px" style="max-width: 600px; margin-top: 16px">
            <el-form-item label="SMTP服务器">
              <el-input v-model="emailForm.email_smtp_host" placeholder="如: smtp.qq.com" />
            </el-form-item>
            <el-form-item label="SMTP端口">
              <el-input-number v-model="emailForm.email_smtp_port" :min="1" :max="65535" :step="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="SMTP用户名">
              <el-input v-model="emailForm.email_smtp_user" placeholder="邮箱账号" />
            </el-form-item>
            <el-form-item label="SMTP密码/授权码">
              <el-input v-model="emailForm.email_smtp_password" type="password" show-password placeholder="邮箱密码或授权码" />
            </el-form-item>
            <el-form-item label="使用SSL">
              <el-switch v-model="emailForm.email_smtp_ssl" active-text="是" inactive-text="否" />
            </el-form-item>
            <el-form-item label="发件人名称">
              <el-input v-model="emailForm.email_from_name" placeholder="发件人显示名称" />
            </el-form-item>
            <el-form-item label="发件人地址">
              <el-input v-model="emailForm.email_from_address" placeholder="发件人邮箱地址" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="handleSaveEmail">
                <i class="fas fa-save"></i> 保存配置
              </el-button>
              <el-button :loading="testing" @click="handleTestEmail">
                <i class="fas fa-paper-plane"></i> 发送测试邮件
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="列名同义词" name="synonym">
          <div class="synonym-section">
            <div class="synonym-header">
              <p class="synonym-desc">配置列名模糊匹配时使用的同义词组，同一组内的词视为同义词。查询执行时，SQL字段名与Excel列名会根据同义词组进行自动匹配。</p>
              <el-button type="primary" size="small" @click="addSynonymGroup">
                <i class="fas fa-plus"></i> 添加同义词组
              </el-button>
            </div>

            <div class="synonym-groups">
              <div v-for="(group, gIdx) in synonymGroups" :key="gIdx" class="synonym-group">
                <div class="group-header">
                  <span class="group-index">第 {{ gIdx + 1 }} 组</span>
                  <el-button type="danger" text size="small" @click="removeSynonymGroup(gIdx)">
                    <i class="fas fa-trash"></i> 删除组
                  </el-button>
                </div>
                <div class="group-words">
                  <el-tag
                    v-for="(word, wIdx) in group"
                    :key="wIdx"
                    closable
                    :type="wIdx === 0 ? '' : 'info'"
                    size="large"
                    class="synonym-tag"
                    @close="removeWord(gIdx, wIdx)"
                  >
                    {{ word }}
                  </el-tag>
                  <el-input
                    v-if="addingWordIndex === gIdx"
                    ref="addWordInputRef"
                    v-model="newWord"
                    size="small"
                    style="width: 120px"
                    placeholder="输入同义词"
                    @keyup.enter="confirmAddWord(gIdx)"
                    @blur="confirmAddWord(gIdx)"
                  />
                  <el-button v-else size="small" type="primary" text @click="startAddWord(gIdx)">
                    <i class="fas fa-plus"></i> 添加词
                  </el-button>
                </div>
              </div>
            </div>

            <div v-if="synonymGroups.length === 0" class="synonym-empty">
              暂无同义词组，点击上方按钮添加
            </div>

            <div class="synonym-actions">
              <el-button type="primary" :loading="savingSynonym" @click="handleSaveSynonym">
                <i class="fas fa-save"></i> 保存同义词配置
              </el-button>
              <el-button @click="handleResetSynonym">
                <i class="fas fa-undo"></i> 恢复默认
              </el-button>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="AI模型" name="ai">
          <div class="ai-section">
            <div class="ai-header">
              <p class="ai-desc">配置AI模型，用于智能对话、SQL生成、行为学习等功能。</p>
              <div>
                <el-button v-hasPermi="['system:delete']" type="danger" size="small" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
                  <i class="fas fa-trash-alt"></i> 批量删除
                </el-button>
                <el-button v-hasPermi="['system:delete']" type="danger" size="small" plain @click="handleDeleteAll">
                  <i class="fas fa-trash"></i> 删除全部
                </el-button>
                <el-button type="primary" size="small" @click="openAiConfigDialog()">
                  <i class="fas fa-plus"></i> 添加配置
                </el-button>
              </div>
            </div>

            <el-table ref="tableRef" :data="aiConfigs" stripe style="width: 100%; margin-top: 16px" @selection-change="handleSelectionChange">
              <el-table-column type="selection" width="55" />
              <el-table-column prop="name" label="名称" min-width="120">
                <template #default="{ row }">
                  <div style="display: flex; align-items: center; gap: 6px">
                    <ProviderLogo :provider="row.provider" :api-base="row.api_base" :model-name="row.model_name" :logo-url="row.logo_url" :size="16" />
                    <span>{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="provider" label="提供商" width="120" align="center">
                <template #default="{ row }">
                  <el-tag size="small">{{ providerLabel(row.provider) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="model_name" label="模型" min-width="140" show-overflow-tooltip />
              <el-table-column prop="is_default" label="默认" width="80" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.is_default" type="success" size="small">是</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="is_free" label="免费" width="70" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.is_free" type="warning" size="small">免费</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="is_active" label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="220" align="center">
                <template #default="{ row }">
                  <el-button size="small" type="primary" text @click="openAiConfigDialog(row)">
                    <i class="fas fa-edit"></i> 编辑
                  </el-button>
                  <el-button size="small" type="success" text @click="testAiConfig(row.id)" :loading="testingAi === row.id">
                    <i class="fas fa-plug"></i> 测试
                  </el-button>
                  <el-button size="small" type="danger" text @click="deleteAiConfig(row.id)">
                    <i class="fas fa-trash"></i>
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <div style="margin-top: 24px">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px">
                <div style="font-weight: 600; font-size: 15px">
                  <i class="fas fa-random" style="color: #E6A23C; margin-right: 6px"></i>路由策略
                  <span style="color: #909399; font-size: 12px; font-weight: 400; margin-left: 8px">按权重从高到低匹配，scope 匹配优先于通用策略</span>
                </div>
                <el-button type="warning" size="small" @click="openStrategyDialog()">
                  <i class="fas fa-plus"></i> 添加策略
                </el-button>
              </div>
              <el-table :data="strategies" stripe style="width: 100%">
                <el-table-column prop="name" label="策略名称" min-width="120" />
                <el-table-column label="类型" width="110" align="center">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.strategy_type === 'priority' ? 'primary' : row.strategy_type === 'round_robin' ? 'success' : 'warning'">
                      {{ row.strategy_type === 'priority' ? '优先级' : row.strategy_type === 'round_robin' ? '轮询' : 'Token均衡' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="模型" min-width="180">
                  <template #default="{ row }">
                    <el-tag v-for="m in (row.models || []).slice(0, 3)" :key="m.id" size="small" style="margin: 2px 4px 2px 0">{{ m.name }}</el-tag>
                    <span v-if="(row.models || []).length > 3" style="color: #909399; font-size: 12px">+{{ row.models.length - 3 }}</span>
                    <span v-if="!row.models || row.models.length === 0" style="color: #909399">-</span>
                  </template>
                </el-table-column>
                <el-table-column label="作用域" width="200" align="center">
                  <template #default="{ row }">
                    <template v-if="row.scope && row.scope.length > 0">
                      <el-tag v-for="s in row.scope" :key="s" size="small" type="info" style="margin: 2px">
                        {{ s === 'system_chat' ? '系统对话' : s === 'open_api' ? '对外API' : s === 'ticket' ? '工单' : s }}
                      </el-tag>
                    </template>
                    <el-tag v-else size="small" type="info">全部</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="免费" width="70" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.route_to_free_only" type="warning" size="small">仅免费</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="sort_order" label="权重" width="70" align="center" />
                <el-table-column label="状态" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="160" align="center">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" text @click="openStrategyDialog(row)">
                      <i class="fas fa-edit"></i> 编辑
                    </el-button>
                    <el-button size="small" type="danger" text @click="handleDeleteStrategy(row.id)">
                      <i class="fas fa-trash"></i>
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <el-dialog v-model="aiConfigDialogVisible" :title="isEditAiConfig ? '编辑AI配置' : '添加AI配置'" width="550px" destroy-on-close>
              <el-form ref="aiConfigFormRef" :model="aiConfigForm" :rules="aiConfigRules" label-width="120px">
                <el-form-item label="配置名称" prop="name">
                  <el-input v-model="aiConfigForm.name" placeholder="如: GPT-4o" />
                </el-form-item>
                <el-form-item label="AI提供商" prop="provider">
                  <el-select v-model="aiConfigForm.provider" style="width: 100%">
                    <el-option label="OpenAI" value="openai" />
                    <el-option label="智谱AI" value="zhipu" />
                    <el-option label="DeepSeek" value="deepseek" />
                    <el-option label="自定义" value="custom" />
                  </el-select>
                </el-form-item>
                <el-form-item label="API地址" prop="api_base">
                  <el-input v-model="aiConfigForm.api_base" placeholder="如: https://api.openai.com/v1" />
                </el-form-item>
                <el-form-item label="API密钥" prop="api_key">
                  <el-input v-model="aiConfigForm.api_key" type="password" show-password placeholder="API Key" />
                </el-form-item>
                <el-form-item label="模型列表" prop="models">
                  <div style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center">
                    <el-tag
                      v-for="(m, idx) in currentModels"
                      :key="idx"
                      closable
                      :disable-transitions="false"
                      @close="removeModel(idx)"
                      style="margin-bottom: 4px"
                    >
                      {{ m }}
                    </el-tag>
                    <el-input
                      v-if="showModelInput"
                      ref="modelInputRef"
                      v-model="newModelName"
                      size="small"
                      placeholder="输入模型名称"
                      style="width: 160px"
                      @keyup.enter="addModel"
                      @blur="addModel"
                    />
                    <el-button
                      v-else
                      size="small"
                      @click="showModelInput = true"
                    >
                      + 添加模型
                    </el-button>
                  </div>
                </el-form-item>
                <el-form-item label="当前模型" prop="model_name">
                  <el-select
                    v-model="aiConfigForm.model_name"
                    filterable
                    allow-create
                    default-first-option
                    placeholder="从该配置的模型列表中选择"
                    style="width: 100%"
                    @create="onCreateModel"
                  >
                    <el-option
                      v-for="name in currentModels"
                      :key="name"
                      :label="name"
                      :value="name"
                    />
                  </el-select>
                </el-form-item>
                <div style="display: flex; gap: 12px">
                  <el-form-item label="最大Tokens" style="flex: 1">
                    <el-input-number v-model="aiConfigForm.max_tokens" :min="256" :max="128000" :step="256" style="width: 100%" controls-position="right" />
                  </el-form-item>
                  <el-form-item label="温度" style="flex: 1">
                    <el-slider v-model="aiConfigForm.temperature" :min="0" :max="2" :step="0.1" show-input size="small" />
                  </el-form-item>
                </div>
                <el-form-item label="上下文窗口">
                  <el-select
                    v-model="aiConfigForm.context_window"
                    filterable
                    allow-create
                    default-first-option
                    placeholder="选择或输入模型上下文窗口大小"
                    style="width: 100%"
                  >
                    <el-option label="8K (8,192 tokens)" :value="8192" />
                    <el-option label="32K (32,768 tokens)" :value="32768" />
                    <el-option label="64K (65,536 tokens)" :value="65536" />
                    <el-option label="128K (131,072 tokens)" :value="131072" />
                    <el-option label="256K (262,144 tokens)" :value="262144" />
                    <el-option label="1M (1,048,576 tokens)" :value="1048576" />
                  </el-select>
                  <div style="width: 100%; color: #909399; font-size: 12px; line-height: 1.4; margin-top: 4px">
                    模型支持的上下文窗口大小，历史消息按此自适应保留（窗口越大保留的历史越多）
                  </div>
                </el-form-item>
                <el-form-item label="设为默认">
                  <el-switch v-model="aiConfigForm.is_default" active-text="是" inactive-text="否" />
                </el-form-item>
                <el-form-item label="启用">
                  <el-switch v-model="aiConfigForm.is_active" active-text="是" inactive-text="否" />
                </el-form-item>
                <el-form-item label="深度思考">
                  <el-switch v-model="aiConfigForm.enable_thinking" active-text="是" inactive-text="否" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">启用后展示模型的思考过程</span>
                </el-form-item>
                <el-form-item label="流式输出">
                  <el-switch v-model="aiConfigForm.enable_streaming" active-text="是" inactive-text="否" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">启用后逐字打印AI回复内容</span>
                </el-form-item>
                <el-form-item label="Headroom压缩">
                  <el-switch v-model="aiConfigForm.enable_headroom" active-text="是" inactive-text="否" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">启用后对上下文进行智能压缩，节省60-95%输入token（JSON/日志/代码等）</span>
                </el-form-item>
                <el-form-item label="免费模型">
                  <el-switch v-model="aiConfigForm.is_free" active-text="是" inactive-text="否" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">标记为免费模型，可配合路由策略的「仅免费」过滤使用</span>
                </el-form-item>
                <el-form-item label="系统提示词">
                  <el-input v-model="aiConfigForm.system_prompt" type="textarea" :rows="4" placeholder="AI助手的行为设定（可选）" />
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="aiConfigDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="savingAiConfig" @click="handleSaveAiConfig">保存</el-button>
              </template>
            </el-dialog>

            <!-- Strategy Dialog -->
            <el-dialog v-model="strategyDialogVisible" :title="isEditStrategy ? '编辑路由策略' : '添加路由策略'" width="650px" destroy-on-close>
              <el-form :model="strategyForm" label-width="120px">
                <el-form-item label="策略名称">
                  <el-input v-model="strategyForm.name" placeholder="如: 对外API免费模型" />
                </el-form-item>
                <el-form-item label="权重">
                  <el-input-number v-model="strategyForm.sort_order" :min="0" :max="999" style="width: 120px" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">越大优先级越高，相同 scope 内按权重匹配</span>
                </el-form-item>
                <el-form-item label="启用策略">
                  <el-switch v-model="strategyForm.is_active" active-text="启用" inactive-text="禁用" />
                </el-form-item>
                <el-divider />
                <el-form-item label="调度策略">
                  <el-radio-group v-model="strategyForm.strategy_type">
                    <el-radio value="priority">优先级</el-radio>
                    <el-radio value="round_robin">轮询</el-radio>
                    <el-radio value="token_balanced">Token均衡</el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item>
                  <template #label>&nbsp;</template>
                  <div style="color: #909399; font-size: 12px; line-height: 1.6">
                    <div v-if="strategyForm.strategy_type === 'priority'">• 按模型列表顺序优先调用，第一个失败则自动切换下一个</div>
                    <div v-if="strategyForm.strategy_type === 'round_robin'">• 每次请求轮换使用不同的模型，实现负载均衡</div>
                    <div v-if="strategyForm.strategy_type === 'token_balanced'">• 优先使用累计Token消耗最少的模型，实现成本均衡</div>
                  </div>
                </el-form-item>
                <el-form-item label="模型列表">
                  <el-select v-model="strategyForm.model_ids" multiple clearable style="width: 100%" placeholder="留空=所有启用的模型均参与调度">
                    <el-option
                      v-for="c in aiConfigs.filter(c => c.is_active)"
                      :key="c.id"
                      :label="`${c.name} (${c.model_name || '?'})`"
                      :value="c.id"
                    />
                  </el-select>
                  <div style="color: #909399; font-size: 12px; margin-top: 4px">留空表示所有启用的模型参与调度；选择后按顺序确定优先级</div>
                </el-form-item>
                <el-divider />
                <el-form-item label="故障转移">
                  <el-switch v-model="strategyForm.failover_enabled" active-text="启用" inactive-text="禁用" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">当前模型调用失败时自动尝试下一个可用模型</span>
                </el-form-item>
                <el-form-item label="重试次数" v-if="strategyForm.failover_enabled">
                  <el-input-number v-model="strategyForm.failover_max_retries" :min="1" :max="10" style="width: 120px" />
                </el-form-item>
                <el-divider />
                <el-form-item label="仅免费模型">
                  <el-switch v-model="strategyForm.route_to_free_only" active-text="是" inactive-text="否" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">开启后仅路由到标记为免费的AI模型配置</span>
                </el-form-item>
                <el-form-item label="作用域">
                  <el-select v-model="strategyForm.scope" multiple style="width: 100%" placeholder="留空表示对所有场景生效">
                    <el-option label="系统AI对话" value="system_chat" />
                    <el-option label="对外API" value="open_api" />
                    <el-option label="系统工单" value="ticket" />
                  </el-select>
                  <div style="color: #909399; font-size: 12px; margin-top: 4px">留空=全部场景生效；选择后仅在对应场景使用此策略（未命中场景回退到通用策略）</div>
                </el-form-item>
                <el-form-item label="描述">
                  <el-input v-model="strategyForm.description" type="textarea" :rows="2" placeholder="策略说明（可选）" />
                </el-form-item>
                <el-form-item label="Token统计" v-if="editingStrategyId && editingStrategyTokenUsage && Object.keys(editingStrategyTokenUsage).length > 0">
                  <div style="font-size: 13px">
                    <div v-for="(tokens, modelId) in editingStrategyTokenUsage" :key="modelId" style="margin-bottom: 4px">
                      <el-tag size="small">{{ getModelNameById(parseInt(modelId)) }}</el-tag>
                      <span style="margin-left: 8px">{{ Number(tokens).toLocaleString() }} tokens</span>
                    </div>
                    <el-button type="warning" size="small" text style="margin-top: 4px; padding: 0" @click="handleResetTokens">
                      <i class="fas fa-redo"></i> 重置统计
                    </el-button>
                  </div>
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="strategyDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="savingStrategy" @click="handleSaveStrategy">保存</el-button>
              </template>
            </el-dialog>
          </div>
        </el-tab-pane>

        <!-- 代付配置 -->
        <el-tab-pane label="代付配置" name="pay">
          <div class="tab-content">
            <div class="tab-toolbar">
              <el-button type="primary" size="small" @click="openPayConfigDialog()"><i class="fa fa-plus"></i> 添加渠道</el-button>
            </div>
            <el-table :data="payConfigs" v-loading="payConfigsLoading" stripe border>
              <el-table-column prop="name" label="渠道" width="140" />
              <el-table-column prop="channel" label="标识" width="100" />
              <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
              <el-table-column label="生产配置" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.pro_config && Object.keys(row.pro_config).length ? 'success' : 'info'" size="small">
                    {{ row.pro_config && Object.keys(row.pro_config).length ? '已配置' : '未配置' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="测试配置" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.test_config && Object.keys(row.test_config).length ? 'success' : 'info'" size="small">
                    {{ row.test_config && Object.keys(row.test_config).length ? '已配置' : '未配置' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" link @click="openPayConfigDialog(row)">编辑</el-button>
                  <el-button size="small" type="danger" link @click="deletePayConfig(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 运营数据看板配置 -->
        <el-tab-pane label="运营数据看板" name="dashboard">
          <el-form label-width="140px" style="max-width: 640px; margin-top: 16px">
            <el-form-item label="启用查询缓存">
              <el-switch v-model="dashboardForm.cache_enabled" active-text="是" inactive-text="否" />
              <span style="margin-left: 12px; color: #909399; font-size: 12px">开启后相同查询在有效期内直接返回缓存结果</span>
            </el-form-item>
            <el-form-item label="缓存有效期(秒)">
              <el-input-number v-model="dashboardForm.cache_ttl" :min="0" :max="86400" :step="60" style="width: 200px" />
            </el-form-item>
            <el-form-item label="单次最大返回行数">
              <el-input-number v-model="dashboardForm.max_rows" :min="100" :max="100000" :step="1000" style="width: 200px" />
            </el-form-item>
            <el-form-item label="默认统计维度">
              <el-radio-group v-model="dashboardForm.default_dimension">
                <el-radio-button value="day">按天</el-radio-button>
                <el-radio-button value="month">按月</el-radio-button>
                <el-radio-button value="year">按年</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="最大图表数量">
              <el-input-number v-model="dashboardForm.max_chart_count" :min="1" :max="6" style="width: 200px" />
              <span style="margin-left: 12px; color: #909399; font-size: 12px">看板页可同时展示的图表卡片数</span>
            </el-form-item>
            <el-form-item label="图表动画">
              <el-switch v-model="dashboardForm.animation_enabled" active-text="是" inactive-text="否" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingDashboard" @click="handleSaveDashboard">
                <i class="fas fa-save"></i> 保存配置
              </el-button>
              <el-button :loading="clearingCache" @click="handleClearDashboardCache">
                <i class="fas fa-broom"></i> 清空查询缓存
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 代付配置编辑弹窗 -->
    <el-dialog v-model="payConfigDialogVisible" :title="payConfigForm.id ? '编辑代付渠道' : '添加代付渠道'" width="720px" :close-on-click-modal="false">
      <el-form :model="payConfigForm" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="渠道标识">
              <el-select v-model="payConfigForm.channel" placeholder="选择渠道" style="width:100%" :disabled="!!payConfigForm.id">
                <el-option v-for="c in payChannelOptions" :key="c.channel" :label="c.name" :value="c.channel" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="渠道名称">
              <el-input v-model="payConfigForm.name" placeholder="渠道名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="payConfigForm.description" placeholder="渠道描述" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="转账类型">
              <el-select v-model="payConfigForm.online_bank_type" style="width:100%">
                <el-option label="B2C 对私" value="B2C" />
                <el-option label="B2B 对公" value="B2B" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="银行编码">
              <el-input v-model="payConfigForm.bank_code" placeholder="如 CCB" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="代付模式">
              <el-input v-model="payConfigForm.transfer_mode" placeholder="6/7（乐商通/快乐刷）" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="跑批类型">
              <el-input v-model="payConfigForm.busi_type" placeholder="144（快乐刷）" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="渠道码">
              <el-input v-model="payConfigForm.channel_code" placeholder="kls / lepass" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="payConfigForm.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-divider content-position="left">生产环境配置 (JSON)</el-divider>
        <el-form-item label="生产配置">
          <el-input v-model="payConfigForm.pro_config_text" type="textarea" :rows="6" placeholder='{"agentNo":"...","userId":"...","baseUrl":"...","key":"...","sign":"..."}' />
        </el-form-item>
        <el-divider content-position="left">测试环境配置 (JSON)</el-divider>
        <el-form-item label="测试配置">
          <el-input v-model="payConfigForm.test_config_text" type="textarea" :rows="6" placeholder='{"agentNo":"...","userId":"...","baseUrl":"...","key":"...","sign":"..."}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="payConfigSaving" @click="savePayConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import ProviderLogo from '../components/ProviderLogo.vue'
import { autoFetchLogo } from '../utils/providerLogo.js'

const activeTab = ref('email')
const saving = ref(false)
const testing = ref(false)
const emailFormRef = ref(null)

const defaultSynonymGroups = [
  ['编号', '号', '代码', '编码', 'ID', 'id', 'No', 'no'],
  ['名称', '名', '名字', 'NAME', 'name'],
  ['金额', '数额', '额度', '数目'],
  ['日期', '时间', 'Date', 'date', 'Time', 'time'],
  ['商户', '商户号', '商户编号'],
  ['我方', '我司', '系统', '本方'],
  ['对方', '他方', '渠道', '通道'],
  ['注册', '入驻', '登记'],
]

const emailForm = reactive({
  email_smtp_host: '',
  email_smtp_port: 465,
  email_smtp_user: '',
  email_smtp_password: '',
  email_smtp_ssl: true,
  email_from_name: '',
  email_from_address: ''
})

const synonymGroups = ref([])
const savingSynonym = ref(false)
const addingWordIndex = ref(-1)
const newWord = ref('')
const addWordInputRef = ref(null)

async function fetchConfig() {
  try {
    const res = await api.system.getConfig()
    const items = res.data || res || []
    for (const item of items) {
      const key = item.config_key
      const value = item.config_value
      if (key && key in emailForm) {
        if (key === 'email_smtp_port') {
          emailForm[key] = parseInt(value) || 465
        } else if (key === 'email_smtp_ssl') {
          emailForm[key] = value === true || value === 'true' || value === '1'
        } else {
          emailForm[key] = value ?? ''
        }
      }
      if (key === 'column_synonym_groups' && value) {
        try {
          const groups = JSON.parse(value)
          if (Array.isArray(groups) && groups.length > 0) {
            synonymGroups.value = groups
          }
        } catch {}
      }
    }
    if (synonymGroups.value.length === 0) {
      synonymGroups.value = defaultSynonymGroups.map(g => [...g])
    }
  } catch {
    synonymGroups.value = defaultSynonymGroups.map(g => [...g])
  }
}

async function handleSaveEmail() {
  saving.value = true
  try {
    const items = []
    for (const [key, value] of Object.entries(emailForm)) {
      if (key === 'email_smtp_password' && !value) continue
      items.push({
        key,
        value: typeof value === 'boolean' ? String(value) : value
      })
    }
    await api.system.updateConfig({ items })
    ElMessage.success('配置保存成功')
  } catch {
  } finally {
    saving.value = false
  }
}

async function handleTestEmail() {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入测试邮件接收地址',
      '发送测试邮件',
      {
        confirmButtonText: '发送',
        cancelButtonText: '取消',
        inputPattern: /@/,
        inputErrorMessage: '请输入有效的邮箱地址'
      }
    )
    testing.value = true
    await api.system.testEmail({ recipient: value })
    ElMessage.success('测试邮件已发送')
  } catch {
  } finally {
    testing.value = false
  }
}

// 同义词组操作
function addSynonymGroup() {
  synonymGroups.value.push(['新词'])
}

function removeSynonymGroup(idx) {
  synonymGroups.value.splice(idx, 1)
}

function removeWord(gIdx, wIdx) {
  if (synonymGroups.value[gIdx].length <= 1) {
    ElMessage.warning('每组至少保留一个词')
    return
  }
  synonymGroups.value[gIdx].splice(wIdx, 1)
}

function startAddWord(gIdx) {
  addingWordIndex.value = gIdx
  newWord.value = ''
  nextTick(() => {
    if (addWordInputRef.value) {
      const inputs = Array.isArray(addWordInputRef.value) ? addWordInputRef.value : [addWordInputRef.value]
      inputs[0]?.focus()
    }
  })
}

function confirmAddWord(gIdx) {
  const word = newWord.value.trim()
  if (word && !synonymGroups.value[gIdx].includes(word)) {
    synonymGroups.value[gIdx].push(word)
  }
  addingWordIndex.value = -1
  newWord.value = ''
}

async function handleSaveSynonym() {
  savingSynonym.value = true
  try {
    await api.system.updateConfig({
      items: [{
        key: 'column_synonym_groups',
        value: JSON.stringify(synonymGroups.value)
      }]
    })
    ElMessage.success('同义词配置保存成功')
  } catch {
  } finally {
    savingSynonym.value = false
  }
}

function handleResetSynonym() {
  synonymGroups.value = defaultSynonymGroups.map(g => [...g])
  ElMessage.info('已恢复默认同义词配置，请点击保存生效')
}

// AI Config
const aiConfigs = ref([])
const aiConfigDialogVisible = ref(false)
const isEditAiConfig = ref(false)
const editAiConfigId = ref(null)
const savingAiConfig = ref(false)
const testingAi = ref(null)
const aiConfigFormRef = ref(null)
const tableRef = ref(null)
const selectedRows = ref([])

// ============ 代付配置 ============
const payConfigs = ref([])
const payConfigsLoading = ref(false)
const payChannelOptions = ref([])
const payConfigDialogVisible = ref(false)
const payConfigSaving = ref(false)
const payConfigForm = ref({})

async function loadPayConfigs() {
  payConfigsLoading.value = true
  try { const res = await api.pay.listConfigs(); payConfigs.value = res.data }
  finally { payConfigsLoading.value = false }
}

async function loadPayChannels() {
  try { const res = await api.pay.channels(); payChannelOptions.value = res.data } catch (e) { /* ignore */ }
}

function openPayConfigDialog(row) {
  if (row) {
    payConfigForm.value = {
      ...row,
      pro_config_text: row.pro_config ? JSON.stringify(row.pro_config, null, 2) : '',
      test_config_text: row.test_config ? JSON.stringify(row.test_config, null, 2) : '',
    }
  } else {
    payConfigForm.value = {
      channel: '', name: '', description: '', is_active: true,
      online_bank_type: 'B2C', bank_code: 'CCB', transfer_mode: '', busi_type: '144', channel_code: '',
      pro_config_text: '', test_config_text: '',
    }
  }
  payConfigDialogVisible.value = true
}

function parseConfigText(text) {
  if (!text || !text.trim()) return null
  try { return JSON.parse(text) } catch (e) { throw new Error('JSON 格式错误: ' + e.message) }
}

async function savePayConfig() {
  const f = payConfigForm.value
  if (!f.channel) { ElMessage.warning('请选择渠道'); return }
  let pro_config = null, test_config = null
  try {
    pro_config = parseConfigText(f.pro_config_text)
    test_config = parseConfigText(f.test_config_text)
  } catch (e) { ElMessage.error(e.message); return }

  const payload = {
    name: f.name, description: f.description, is_active: f.is_active,
    online_bank_type: f.online_bank_type, bank_code: f.bank_code,
    transfer_mode: f.transfer_mode, busi_type: f.busi_type, channel_code: f.channel_code,
    pro_config, test_config,
  }
  payConfigSaving.value = true
  try {
    if (f.id) {
      await api.pay.updateConfig(f.id, payload)
      ElMessage.success('更新成功')
    } else {
      await api.pay.createConfig({ ...payload, channel: f.channel })
      ElMessage.success('创建成功')
    }
    payConfigDialogVisible.value = false
    await loadPayConfigs()
  } catch (e) { /* handled by interceptor */ }
  finally { payConfigSaving.value = false }
}

async function deletePayConfig(row) {
  try {
    await ElMessageBox.confirm(`确定删除渠道「${row.name}」？`, '提示', { type: 'warning' })
    await api.pay.deleteConfig(row.id)
    ElMessage.success('删除成功')
    await loadPayConfigs()
  } catch (e) { /* cancelled */ }
}

// ============ 运营数据看板配置 ============
const dashboardForm = reactive({
  cache_enabled: true,
  cache_ttl: 600,
  max_rows: 10000,
  default_dimension: 'day',
  max_chart_count: 4,
  animation_enabled: true,
})
const savingDashboard = ref(false)
const clearingCache = ref(false)

async function fetchDashboardConfig() {
  try {
    const res = await api.dataDashboard.getSettings()
    if (res.data) Object.assign(dashboardForm, res.data)
  } catch {}
}

async function handleSaveDashboard() {
  savingDashboard.value = true
  try {
    await api.dataDashboard.saveSettings({ ...dashboardForm })
    ElMessage.success('看板配置已保存')
  } catch {} finally {
    savingDashboard.value = false
  }
}

async function handleClearDashboardCache() {
  clearingCache.value = true
  try {
    const res = await api.dataDashboard.clearCache()
    ElMessage.success(res.message || '缓存已清空')
  } catch {} finally {
    clearingCache.value = false
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 条配置吗？`,
      '批量删除确认',
      { type: 'warning' }
    )
    await api.system.batchDelete(selectedRows.value.map(r => r.id))
    ElMessage.success('批量删除成功')
    selectedRows.value = []
    fetchAiConfigs()
  } catch {}
}

async function handleDeleteAll() {
  try {
    await ElMessageBox.confirm(
      '确定要删除全部配置吗？此操作不可恢复！',
      '删除全部确认',
      { type: 'warning' }
    )
    await api.system.deleteAll()
    ElMessage.success('全部删除成功')
    selectedRows.value = []
    fetchAiConfigs()
  } catch {}
}

const defaultAiConfigForm = {
  name: '',
  provider: 'openai',
  api_base: '',
  api_key: '',
  model_name: '',
  max_tokens: 4096,
  context_window: 131072,
  temperature: 0.7,
  is_default: false,
  is_active: true,
  enable_thinking: false,
  enable_streaming: true,
  enable_headroom: false,
  is_free: false,
  system_prompt: '',
}

const aiConfigForm = reactive({ ...defaultAiConfigForm })

const currentModels = ref([])
const showModelInput = ref(false)
const newModelName = ref('')
const modelInputRef = ref(null)

const aiConfigRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  provider: [{ required: true, message: '请选择提供商', trigger: 'change' }],
}

function providerLabel(p) {
  return { openai: 'OpenAI', zhipu: '智谱AI', deepseek: 'DeepSeek', custom: '自定义' }[p] || p
}

async function fetchAiConfigs() {
  try {
    const res = await api.ai.getConfigs()
    aiConfigs.value = res.data || []
  } catch {}
}

function addModel() {
  const name = newModelName.value.trim()
  if (name && !currentModels.value.includes(name)) {
    currentModels.value.push(name)
  }
  newModelName.value = ''
  showModelInput.value = false
}

function removeModel(idx) {
  const removed = currentModels.value[idx]
  currentModels.value.splice(idx, 1)
  // 如果删除的是当前选中的模型，清空选择
  if (aiConfigForm.model_name === removed) {
    aiConfigForm.model_name = ''
  }
}

function onCreateModel(val) {
  // el-select allow-create 触发，追加到模型列表
  if (val && !currentModels.value.includes(val)) {
    currentModels.value.push(val)
  }
  aiConfigForm.model_name = val
}

function openAiConfigDialog(row) {
  if (row) {
    isEditAiConfig.value = true
    editAiConfigId.value = row.id
    currentModels.value = [...(row.models || [])]
    Object.assign(aiConfigForm, {
      name: row.name,
      provider: row.provider,
      api_base: row.api_base || '',
      api_key: '',
      model_name: row.model_name || '',
      max_tokens: row.max_tokens || 4096,
      context_window: row.context_window || 131072,
      temperature: row.temperature ?? 0.7,
      is_default: row.is_default || false,
      is_active: row.is_active !== false,
      enable_thinking: row.enable_thinking || false,
      enable_streaming: row.enable_streaming || false,
      enable_headroom: row.enable_headroom || false,
      is_free: row.is_free || false,
      system_prompt: row.system_prompt || '',
    })
  } else {
    isEditAiConfig.value = false
    editAiConfigId.value = null
    currentModels.value = []
    Object.assign(aiConfigForm, { ...defaultAiConfigForm })
  }
  aiConfigDialogVisible.value = true
}

async function handleSaveAiConfig() {
  if (!aiConfigFormRef.value) return
  await aiConfigFormRef.value.validate()
  savingAiConfig.value = true
  try {
    const payload = { ...aiConfigForm, models: currentModels.value }
    if (!payload.api_key) delete payload.api_key
    // 保存前自动适配 logo：若当前 provider/api_base/model_name 未匹配内置品牌，
    // 则尝试从聚合平台/厂商网站抓取 logo 图片 URL 并回写
    if (!payload.logo_url) {
      payload.logo_url = await autoFetchLogo(payload.provider, payload.api_base, payload.model_name)
    }
    if (isEditAiConfig.value) {
      await api.ai.updateConfig(editAiConfigId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await api.ai.createConfig(payload)
      ElMessage.success('添加成功')
    }
    aiConfigDialogVisible.value = false
    fetchAiConfigs()
  } catch {} finally {
    savingAiConfig.value = false
  }
}

async function testAiConfig(id) {
  testingAi.value = id
  try {
    const res = await api.ai.testConfig(id)
    if (res.success) {
      ElMessage.success('连接测试成功')
    }
  } catch {
    ElMessage.error('连接测试失败')
  } finally {
    testingAi.value = null
  }
}

async function deleteAiConfig(id) {
  try {
    await api.ai.deleteConfig(id)
    ElMessage.success('删除成功')
    fetchAiConfigs()
  } catch {}
}

onMounted(() => {
  fetchConfig()
  fetchAiConfigs()
  fetchStrategy()
  loadPayConfigs()
  loadPayChannels()
  fetchDashboardConfig()
})

// AI Strategy
const strategyDialogVisible = ref(false)
const savingStrategy = ref(false)
const isEditStrategy = ref(false)
const editingStrategyId = ref(null)
const editingStrategyTokenUsage = ref(null)
const strategies = ref([])
const defaultStrategyForm = {
  name: '',
  strategy_type: 'priority',
  model_ids: [],
  is_active: true,
  failover_enabled: true,
  failover_max_retries: 3,
  route_to_free_only: false,
  scope: [],
  sort_order: 0,
  description: '',
}
const strategyForm = reactive({ ...defaultStrategyForm })

async function fetchStrategies() {
  try {
    const res = await api.ai.listStrategies()
    strategies.value = res.data || []
  } catch {
    strategies.value = []
  }
}

function fetchStrategy() {
  fetchStrategies()
}

function openStrategyDialog(row) {
  if (row) {
    isEditStrategy.value = true
    editingStrategyId.value = row.id
    editingStrategyTokenUsage.value = row.token_usage || null
    Object.assign(strategyForm, {
      name: row.name || '',
      strategy_type: row.strategy_type || 'priority',
      model_ids: row.model_ids || [],
      is_active: row.is_active !== false,
      failover_enabled: row.failover_enabled !== false,
      failover_max_retries: row.failover_max_retries || 3,
      route_to_free_only: row.route_to_free_only || false,
      scope: row.scope || [],
      sort_order: row.sort_order || 0,
      description: row.description || '',
    })
  } else {
    isEditStrategy.value = false
    editingStrategyId.value = null
    editingStrategyTokenUsage.value = null
    Object.assign(strategyForm, { ...defaultStrategyForm })
  }
  strategyDialogVisible.value = true
}

async function handleSaveStrategy() {
  savingStrategy.value = true
  try {
    if (isEditStrategy.value && editingStrategyId.value) {
      await api.ai.updateStrategy(editingStrategyId.value, { ...strategyForm })
    } else {
      await api.ai.createStrategy({ ...strategyForm })
    }
    ElMessage.success('策略已保存')
    strategyDialogVisible.value = false
    fetchStrategies()
  } catch {} finally {
    savingStrategy.value = false
  }
}

async function handleDeleteStrategy(id) {
  try {
    await ElMessageBox.confirm('确定要删除该策略吗？', '确认', { type: 'warning' })
    await api.ai.deleteStrategy(id)
    ElMessage.success('策略已删除')
    fetchStrategies()
  } catch {}
}

async function handleResetTokens() {
  if (!editingStrategyId.value) return
  try {
    await api.ai.resetStrategyTokens(editingStrategyId.value)
    ElMessage.success('Token统计已重置')
    editingStrategyTokenUsage.value = null
    fetchStrategies()
  } catch {}
}

function getModelNameById(id) {
  const cfg = aiConfigs.value.find(c => c.id === id)
  return cfg ? `${cfg.name} (${cfg.model_name || '?'})` : `ID: ${id}`
}
</script>

<style scoped>
.system-config {
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

.synonym-section {
  margin-top: 16px;
}

.synonym-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.synonym-desc {
  color: #909399;
  font-size: 13px;
  margin: 0;
  max-width: 600px;
  line-height: 1.6;
}

.synonym-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.synonym-group {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px 18px;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.group-index {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.group-words {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.synonym-tag {
  font-size: 13px;
}

.synonym-empty {
  text-align: center;
  color: #c0c4cc;
  padding: 40px 0;
  font-size: 14px;
}

.synonym-actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.ai-section {
  margin-top: 16px;
}

.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.ai-desc {
  color: #909399;
  font-size: 13px;
  margin: 0;
  max-width: 600px;
  line-height: 1.6;
}
</style>
