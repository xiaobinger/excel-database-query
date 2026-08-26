<template>
  <div class="page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span><i class="fa fa-project-diagram"></i> 代付流程编排</span>
          <div class="header-actions">
            <el-button type="primary" @click="openTemplateDialog()">
              <i class="fa fa-plus"></i> 新建模板
            </el-button>
            <el-button @click="loadTemplates">
              <i class="fa fa-refresh"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="templates" stripe border style="width:100%" empty-text="暂无流程模板">
        <el-table-column prop="name" label="模板名称" width="180" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="节点数" width="80" align="center">
          <template #default="{ row }">{{ row.nodes?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openTemplateDialog(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="toggleTemplate(row)">{{ row.is_enabled ? '禁用' : '启用' }}</el-button>
            <el-button size="small" type="danger" @click="deleteTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 模板编辑 Dialog -->
    <el-dialog v-model="templateDialogVisible" :title="editingTemplate ? '编辑流程模板' : '新建流程模板'" width="1100px" :close-on-click-modal="false">
      <div class="template-editor">
        <el-form :model="templateForm" label-width="100px" class="template-meta">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="模板名称" required>
                <el-input v-model="templateForm.name" placeholder="如: 合利宝代付流程" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="描述">
                <el-input v-model="templateForm.description" placeholder="流程描述" />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="启用">
                <el-switch v-model="templateForm.is_enabled" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <div class="nodes-section">
          <div class="nodes-header">
            <span class="nodes-title"><i class="fa fa-list-ol"></i> 流程节点编排</span>
            <el-button type="primary" size="small" @click="addNode">
              <i class="fa fa-plus"></i> 添加节点
            </el-button>
          </div>

          <div v-if="!templateForm.nodes.length" class="empty-nodes">
            <el-empty description="暂无节点，点击上方按钮添加流程节点" :image-size="80" />
          </div>

          <div v-else class="nodes-list">
            <div v-for="(node, idx) in templateForm.nodes" :key="node.id" class="node-card" :class="{ 'node-active': selectedNodeIdx === idx }">
              <div class="node-card-header" @click="selectedNodeIdx = idx">
                <span class="node-index">{{ idx + 1 }}</span>
                <span class="node-name">{{ node.name }}</span>
                <el-tag :type="node.type === 'pay' ? 'warning' : 'success'" size="small">{{ node.type === 'pay' ? '代付' : '通知' }}</el-tag>
                <i v-if="node.loop?.enabled" class="fa fa-repeat loop-icon" title="循环节点"></i>
                <i class="fa fa-chevron-down node-arrow"></i>
              </div>

              <div v-if="selectedNodeIdx === idx" class="node-card-body">
                <!-- 节点基本信息 -->
                <el-form label-width="90px" size="small">
                  <el-row :gutter="12">
                    <el-col :span="8">
                      <el-form-item label="节点名称">
                        <el-input v-model="node.name" placeholder="如: 发起代付" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="节点类型">
                        <el-select v-model="node.type" style="width:100%">
                          <el-option label="代付动作" value="pay" />
                          <el-option label="通知" value="notify" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="操作">
                        <el-button type="danger" size="small" @click="removeNode(idx)">删除节点</el-button>
                        <el-button size="small" @click="moveNode(idx, -1)" :disabled="idx === 0">上移</el-button>
                        <el-button size="small" @click="moveNode(idx, 1)" :disabled="idx === templateForm.nodes.length - 1">下移</el-button>
                      </el-form-item>
                    </el-col>
                  </el-row>
                </el-form>

                <!-- 代付节点配置 -->
                <div v-if="node.type === 'pay'" class="node-config">
                  <div class="config-title">代付动作配置</div>
                  <el-form label-width="90px" size="small">
                    <el-row :gutter="12">
                      <el-col :span="8">
                        <el-form-item label="渠道" required>
                          <el-select v-model="node.action.channel" style="width:100%" placeholder="选择渠道">
                            <el-option v-for="c in channels" :key="c.channel" :label="c.name" :value="c.channel" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-col :span="8">
                        <el-form-item label="接口类型">
                          <el-select v-model="node.action.interface_type" style="width:100%">
                            <el-option label="代付" value="代付" />
                            <el-option label="查询" value="查询" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-col :span="8">
                        <el-form-item label="环境">
                          <el-radio-group v-model="node.action.environment" size="small">
                            <el-radio-button label="test">测试</el-radio-button>
                            <el-radio-button label="pro">生产</el-radio-button>
                          </el-radio-group>
                        </el-form-item>
                      </el-col>
                    </el-row>
                  </el-form>
                </div>

                <!-- 通知节点配置 -->
                <div v-else class="node-config">
                  <div class="config-title">通知配置</div>
                  <el-form label-width="90px" size="small">
                    <el-row :gutter="12">
                      <el-col :span="12">
                        <el-form-item label="通知类型">
                          <el-select v-model="node.action.notify_type" style="width:100%">
                            <el-option label="邮件" value="email" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-col :span="12">
                        <el-form-item label="收件人">
                          <el-input v-model="node.action.to_addresses_str" placeholder="多个用逗号分隔" />
                        </el-form-item>
                      </el-col>
                    </el-row>
                    <el-form-item label="主题">
                      <el-input v-model="node.action.subject" placeholder="邮件主题" />
                    </el-form-item>
                    <el-form-item label="内容">
                      <el-input v-model="node.action.content" type="textarea" :rows="3" placeholder="支持变量: {accountName} {businessNo} {amount} {execution_id} {template_name} {status}" />
                    </el-form-item>
                  </el-form>
                </div>

                <!-- 循环配置 -->
                <div class="node-config">
                  <div class="config-title">
                    循环配置
                    <el-switch v-model="node.loop.enabled" size="small" style="margin-left:8px" />
                  </div>
                  <div v-if="node.loop.enabled">
                    <el-form label-width="110px" size="small">
                      <el-row :gutter="12">
                        <el-col :span="8">
                          <el-form-item label="循环间隔(秒)">
                            <el-input-number v-model="node.loop.interval_seconds" :min="5" :max="86400" />
                          </el-form-item>
                        </el-col>
                        <el-col :span="8">
                          <el-form-item label="最大循环次数">
                            <el-input-number v-model="node.loop.max_iterations" :min="1" :max="1000" />
                          </el-form-item>
                        </el-col>
                        <el-col :span="8">
                          <el-form-item label="退出条件">
                            <el-select v-model="node.loop.exit_condition_op" style="width:100%">
                              <el-option label="代付成功" value="success" />
                              <el-option label="代付失败" value="fail" />
                              <el-option label="等于指定值" value="eq" />
                            </el-select>
                          </el-form-item>
                        </el-col>
                      </el-row>
                      <el-form-item v-if="node.loop.exit_condition_op === 'eq'" label="退出字段">
                        <el-input v-model="node.loop.exit_field" placeholder="如: orderStatus" style="width:180px" />
                        <span style="margin:0 8px">=</span>
                        <el-input v-model="node.loop.exit_value" placeholder="如: 1" style="width:180px" />
                      </el-form-item>
                    </el-form>
                  </div>
                </div>

                <!-- 流转条件 -->
                <div class="node-config">
                  <div class="config-title">流转条件</div>
                  <div v-if="!node.transitions.length" class="empty-tips">无条件设置时，顺序执行下一节点</div>
                  <div v-for="(trans, tIdx) in node.transitions" :key="tIdx" class="transition-row">
                    <span class="trans-label">条件 {{ tIdx + 1 }}:</span>
                    <el-select v-model="trans.condition.field" placeholder="字段" size="small" style="width:140px" @change="onFieldChange(trans)">
                      <el-option v-for="f in availableFields" :key="f.value" :label="f.label" :value="f.value" />
                    </el-select>
                    <el-select v-model="trans.condition.operator" placeholder="操作符" size="small" style="width:120px">
                      <el-option v-for="(label, val) in operators" :key="val" :label="label" :value="val" />
                    </el-select>
                    <el-input v-if="!['success','fail'].includes(trans.condition.operator)" v-model="trans.condition.value" placeholder="值" size="small" style="width:140px" />
                    <span class="trans-arrow">→</span>
                    <el-select v-model="trans.target_node_index" size="small" style="width:140px">
                      <el-option :value="-1" label="流程失败 ❌" />
                      <el-option :value="idx + 1" :label="`下一节点 (${idx + 2 <= templateForm.nodes.length ? templateForm.nodes[idx + 1].name : '—'})`" />
                      <el-option v-for="(n, nIdx) in templateForm.nodes" :key="nIdx" :value="nIdx" :label="`跳转到: ${n.name}`" :disabled="nIdx <= idx" />
                    </el-select>
                    <el-button type="danger" size="small" circle @click="node.transitions.splice(tIdx, 1)"><i class="fa fa-times"></i></el-button>
                  </div>
                  <el-button size="small" @click="addTransition(node)" style="margin-top:4px">
                    <i class="fa fa-plus"></i> 添加条件
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="templateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTemplate">保存模板</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import dayjs from 'dayjs'

const templates = ref([])
const channels = ref([])
const operators = ref({})
const templateDialogVisible = ref(false)
const editingTemplate = ref(null)
const saving = ref(false)
const selectedNodeIdx = ref(null)

const templateForm = reactive({
  name: '',
  description: '',
  is_enabled: true,
  nodes: [],
})

const availableFields = computed(() => {
  const prevNodes = templateForm.nodes.slice(0, selectedNodeIdx.value)
  const fields = []
  for (const n of prevNodes) {
    if (n.type === 'pay') {
      fields.push(
        { value: `${n.id}.success`, label: `${n.name} → 成功` },
        { value: `${n.id}.message`, label: `${n.name} → 消息` },
        { value: `${n.id}.retCode`, label: `${n.name} → retCode` },
        { value: `${n.id}.orderStatus`, label: `${n.name} → orderStatus` },
        { value: `${n.id}.error_code`, label: `${n.name} → error_code` },
        { value: `${n.id}.state`, label: `${n.name} → state` },
      )
    }
  }
  return fields
})

function formatTime(ts) {
  return ts ? dayjs(ts).format('YYYY-MM-DD HH:mm:ss') : '-'
}

async function loadTemplates() {
  try {
    const res = await api.payFlow.templates({ per_page: 100 })
    templates.value = res.data.items || []
  } catch (e) { /* ignore */ }
}

async function loadChannels() {
  try {
    const res = await api.pay.channels()
    channels.value = res.data
  } catch (e) { /* ignore */ }
}

async function loadNodeFields() {
  try {
    const res = await api.payFlow.nodeFields()
    operators.value = res.data.operators || {}
  } catch (e) { /* ignore */ }
}

function openTemplateDialog(row) {
  editingTemplate.value = row
  if (row) {
    templateForm.name = row.name
    templateForm.description = row.description || ''
    templateForm.is_enabled = row.is_enabled
    templateForm.nodes = JSON.parse(JSON.stringify(row.nodes || []))
  } else {
    templateForm.name = ''
    templateForm.description = ''
    templateForm.is_enabled = true
    templateForm.nodes = []
  }
  selectedNodeIdx.value = null
  templateDialogVisible.value = true
}

function addNode() {
  const idx = templateForm.nodes.length
  templateForm.nodes.push({
    id: `node_${Date.now()}`,
    name: `节点 ${idx + 1}`,
    type: 'pay',
    action: { channel: '', interface_type: '代付', environment: 'test', real_time: '是', execute_type: '创建代付', notify_type: 'email', to_addresses: [], to_addresses_str: '', subject: '', content: '' },
    loop: { enabled: false, interval_seconds: 60, max_iterations: 10, exit_condition_op: 'success', exit_field: '', exit_value: '' },
    transitions: [],
  })
  selectedNodeIdx.value = idx
}

function removeNode(idx) {
  templateForm.nodes.splice(idx, 1)
  if (selectedNodeIdx.value >= templateForm.nodes.length) {
    selectedNodeIdx.value = templateForm.nodes.length - 1
  }
}

function moveNode(idx, dir) {
  const target = idx + dir
  if (target < 0 || target >= templateForm.nodes.length) return
  const temp = templateForm.nodes[idx]
  templateForm.nodes[idx] = templateForm.nodes[target]
  templateForm.nodes[target] = temp
  selectedNodeIdx.value = target
}

function addTransition(node) {
  node.transitions.push({
    condition: { field: '', operator: 'eq', value: '' },
    target_node_index: null,
  })
}

function onFieldChange(trans) {
  trans.condition.value = ''
}

async function saveTemplate() {
  if (!templateForm.name) { ElMessage.warning('请填写模板名称'); return }
  if (!templateForm.nodes.length) { ElMessage.warning('至少添加一个节点'); return }
  for (const node of templateForm.nodes) {
    if (!node.name) { ElMessage.warning('所有节点必须填写名称'); return }
    if (node.type === 'pay' && !node.action.channel) { ElMessage.warning(`节点 "${node.name}" 未选择渠道`); return }
    if (node.type === 'notify') {
      node.action.to_addresses = (node.action.to_addresses_str || '').split(',').map(s => s.trim()).filter(Boolean)
    }
  }
  saving.value = true
  try {
    const payload = {
      name: templateForm.name,
      description: templateForm.description,
      is_enabled: templateForm.is_enabled,
      nodes: templateForm.nodes,
    }
    if (editingTemplate.value) {
      await api.payFlow.updateTemplate(editingTemplate.value.id, payload)
      ElMessage.success('模板更新成功')
    } else {
      await api.payFlow.createTemplate(payload)
      ElMessage.success('模板创建成功')
    }
    templateDialogVisible.value = false
    loadTemplates()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleTemplate(row) {
  try {
    await api.payFlow.updateTemplate(row.id, { is_enabled: !row.is_enabled })
    ElMessage.success(row.is_enabled ? '已禁用' : '已启用')
    loadTemplates()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  }
}

async function deleteTemplate(row) {
  await ElMessageBox.confirm(`确定删除模板 "${row.name}"？`, '提示', { type: 'warning' })
  try {
    await api.payFlow.deleteTemplate(row.id)
    ElMessage.success('已删除')
    loadTemplates()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

onMounted(() => {
  loadTemplates()
  loadChannels()
  loadNodeFields()
})
</script>

<style scoped>
.page { padding: 0; }
.page-card { border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-header > span:first-child { font-size: 15px; font-weight: 600; }
.header-actions { display: flex; gap: 8px; }
.template-editor { max-height: 70vh; overflow-y: auto; }
.nodes-section { margin-top: 16px; }
.nodes-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.nodes-title { font-size: 14px; font-weight: 600; }
.empty-nodes { padding: 24px 0; }
.node-card { border: 1px solid #ebeef5; border-radius: 8px; margin-bottom: 8px; transition: box-shadow 0.2s; }
.node-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.node-active { border-color: #409eff; }
.node-card-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; cursor: pointer; background: #fafafa; border-radius: 8px 8px 0 0; }
.node-index { width: 26px; height: 26px; border-radius: 50%; background: #409eff; color: #fff; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.node-name { font-weight: 500; }
.loop-icon { color: #e6a23c; font-size: 13px; }
.node-arrow { margin-left: auto; color: #909399; font-size: 12px; }
.node-card-body { padding: 14px; }
.node-config { margin-bottom: 12px; padding: 10px; background: #f8f9fa; border-radius: 6px; }
.config-title { font-weight: 600; font-size: 13px; margin-bottom: 8px; color: #303133; }
.empty-tips { color: #909399; font-size: 12px; padding: 4px 0; }
.transition-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; }
.trans-label { font-size: 12px; color: #606266; min-width: 50px; }
.trans-arrow { color: #909399; font-size: 12px; }
.template-meta { margin-bottom: 8px; }
</style>
