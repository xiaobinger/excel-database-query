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
                <el-button type="warning" size="small" @click="openStrategyDialog()">
                  <i class="fas fa-random"></i> 策略配置
                </el-button>
                <el-button type="primary" size="small" @click="openAiConfigDialog()">
                  <i class="fas fa-plus"></i> 添加配置
                </el-button>
              </div>
            </div>

            <el-table :data="aiConfigs" stripe style="width: 100%; margin-top: 16px">
              <el-table-column prop="name" label="名称" min-width="120" />
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
                <el-form-item label="模型名称" prop="model_name">
                  <el-input v-model="aiConfigForm.model_name" placeholder="如: gpt-4o, glm-4, deepseek-chat" />
                </el-form-item>
                <div style="display: flex; gap: 12px">
                  <el-form-item label="最大Tokens" style="flex: 1">
                    <el-input-number v-model="aiConfigForm.max_tokens" :min="256" :max="128000" :step="256" style="width: 100%" controls-position="right" />
                  </el-form-item>
                  <el-form-item label="温度" style="flex: 1">
                    <el-slider v-model="aiConfigForm.temperature" :min="0" :max="2" :step="0.1" show-input size="small" />
                  </el-form-item>
                </div>
                <el-form-item label="设为默认">
                  <el-switch v-model="aiConfigForm.is_default" active-text="是" inactive-text="否" />
                </el-form-item>
                <el-form-item label="启用">
                  <el-switch v-model="aiConfigForm.is_active" active-text="是" inactive-text="否" />
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
            <el-dialog v-model="strategyDialogVisible" title="AI模型调度策略" width="650px" destroy-on-close>
              <el-form :model="strategyForm" label-width="120px">
                <el-form-item label="策略名称">
                  <el-input v-model="strategyForm.name" placeholder="如: 默认策略" />
                </el-form-item>
                <el-form-item label="启用策略">
                  <el-switch v-model="strategyForm.is_active" active-text="启用" inactive-text="禁用" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">启用后将按策略调度模型，禁用时使用默认模型</span>
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
                  <el-select v-model="strategyForm.model_ids" multiple style="width: 100%" placeholder="选择参与调度的模型（按优先级排序）">
                    <el-option
                      v-for="c in aiConfigs.filter(c => c.is_active)"
                      :key="c.id"
                      :label="`${c.name} (${c.model_name || '?'})`"
                      :value="c.id"
                    />
                  </el-select>
                  <div style="color: #909399; font-size: 12px; margin-top: 4px">按选择的顺序确定优先级（第一个为最高优先级）</div>
                </el-form-item>
                <el-divider />
                <el-form-item label="故障转移">
                  <el-switch v-model="strategyForm.failover_enabled" active-text="启用" inactive-text="禁用" />
                  <span style="margin-left: 12px; color: #909399; font-size: 12px">当前模型调用失败时自动尝试下一个可用模型</span>
                </el-form-item>
                <el-form-item label="重试次数" v-if="strategyForm.failover_enabled">
                  <el-input-number v-model="strategyForm.failover_max_retries" :min="1" :max="10" style="width: 120px" />
                </el-form-item>
                <el-form-item label="描述">
                  <el-input v-model="strategyForm.description" type="textarea" :rows="2" placeholder="策略说明（可选）" />
                </el-form-item>
                <el-form-item label="Token统计" v-if="currentStrategy && Object.keys(currentStrategy.token_usage || {}).length > 0">
                  <div style="font-size: 13px">
                    <div v-for="(tokens, modelId) in currentStrategy.token_usage" :key="modelId" style="margin-bottom: 4px">
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
                <el-button v-if="currentStrategy" type="danger" plain @click="handleDeleteStrategy">删除策略</el-button>
                <el-button @click="strategyDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="savingStrategy" @click="handleSaveStrategy">保存</el-button>
              </template>
            </el-dialog>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

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

const defaultAiConfigForm = {
  name: '',
  provider: 'openai',
  api_base: '',
  api_key: '',
  model_name: '',
  max_tokens: 4096,
  temperature: 0.7,
  is_default: false,
  is_active: true,
  system_prompt: '',
}

const aiConfigForm = reactive({ ...defaultAiConfigForm })

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

function openAiConfigDialog(row) {
  if (row) {
    isEditAiConfig.value = true
    editAiConfigId.value = row.id
    Object.assign(aiConfigForm, {
      name: row.name,
      provider: row.provider,
      api_base: row.api_base || '',
      api_key: '',
      model_name: row.model_name || '',
      max_tokens: row.max_tokens || 4096,
      temperature: row.temperature ?? 0.7,
      is_default: row.is_default || false,
      is_active: row.is_active !== false,
      system_prompt: row.system_prompt || '',
    })
  } else {
    isEditAiConfig.value = false
    editAiConfigId.value = null
    Object.assign(aiConfigForm, { ...defaultAiConfigForm })
  }
  aiConfigDialogVisible.value = true
}

async function handleSaveAiConfig() {
  if (!aiConfigFormRef.value) return
  await aiConfigFormRef.value.validate()
  savingAiConfig.value = true
  try {
    const payload = { ...aiConfigForm }
    if (!payload.api_key) delete payload.api_key
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
})

// AI Strategy
const strategyDialogVisible = ref(false)
const savingStrategy = ref(false)
const currentStrategy = ref(null)
const strategyForm = reactive({
  name: '默认策略',
  strategy_type: 'priority',
  model_ids: [],
  is_active: true,
  failover_enabled: true,
  failover_max_retries: 3,
  description: '',
})

async function fetchStrategy() {
  try {
    const res = await api.ai.getStrategy()
    if (res.data) {
      currentStrategy.value = res.data
      Object.assign(strategyForm, {
        name: res.data.name || '默认策略',
        strategy_type: res.data.strategy_type || 'priority',
        model_ids: res.data.model_ids || [],
        is_active: res.data.is_active !== false,
        failover_enabled: res.data.failover_enabled !== false,
        failover_max_retries: res.data.failover_max_retries || 3,
        description: res.data.description || '',
      })
    } else {
      currentStrategy.value = null
      Object.assign(strategyForm, {
        name: '默认策略',
        strategy_type: 'priority',
        model_ids: [],
        is_active: true,
        failover_enabled: true,
        failover_max_retries: 3,
        description: '',
      })
    }
  } catch {
    currentStrategy.value = null
  }
}

function openStrategyDialog() {
  strategyDialogVisible.value = true
}

async function handleSaveStrategy() {
  savingStrategy.value = true
  try {
    await api.ai.saveStrategy({ ...strategyForm })
    ElMessage.success('策略已保存')
    strategyDialogVisible.value = false
    fetchStrategy()
  } catch {} finally {
    savingStrategy.value = false
  }
}

async function handleDeleteStrategy() {
  try {
    await ElMessageBox.confirm('确定要删除当前策略吗？删除后将使用默认模型。', '确认', { type: 'warning' })
    await api.ai.deleteStrategy()
    ElMessage.success('策略已删除')
    currentStrategy.value = null
    strategyDialogVisible.value = false
    fetchStrategy()
  } catch {}
}

async function handleResetTokens() {
  try {
    await api.ai.resetStrategyTokens()
    ElMessage.success('Token统计已重置')
    fetchStrategy()
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
