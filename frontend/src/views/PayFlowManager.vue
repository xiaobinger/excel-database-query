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
            <el-button type="success" @click="openNotifyTemplateListDialog">
              <i class="fa fa-envelope-open-text"></i> 通知模板
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
                <el-tag v-if="node.is_end_node" type="danger" size="small">结束节点</el-tag>
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
                      <el-form-item label="操作">
                        <el-button type="danger" size="small" @click="removeNode(idx)">删除节点</el-button>
                        <el-button size="small" @click="moveNode(idx, -1)" :disabled="idx === 0">上移</el-button>
                        <el-button size="small" @click="moveNode(idx, 1)" :disabled="idx === templateForm.nodes.length - 1">下移</el-button>
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="结束节点">
                        <el-switch v-model="node.is_end_node" active-text="是" inactive-text="否" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                </el-form>

                <!-- 代付动作配置 -->
                <div class="node-config">
                  <div class="config-title">代付动作配置</div>
                  <el-form label-width="90px" size="small">
                    <el-row :gutter="12">
                      <el-col :span="6">
                        <el-form-item label="渠道" required>
                          <el-select v-model="node.action.channel" style="width:100%" placeholder="选择渠道" @change="onNodeChannelChange(node)">
                            <el-option v-for="c in channels" :key="c.channel" :label="c.name" :value="c.channel" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-col :span="6">
                        <el-form-item label="接口类型">
                          <el-select v-model="node.action.interface_type" style="width:100%" @change="onInterfaceTypeChange(node)">
                            <el-option v-for="t in currentNodeChannel(node)?.interface_types || []" :key="t" :label="t" :value="t" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                      <el-col :span="6">
                        <el-form-item label="环境">
                          <el-radio-group v-model="node.action.environment" size="small">
                            <el-radio-button label="test">测试</el-radio-button>
                            <el-radio-button label="pro">生产</el-radio-button>
                          </el-radio-group>
                        </el-form-item>
                      </el-col>
                      <el-col :span="6" v-if="node.action.interface_type === '代付' && currentNodeChannel(node)?.real_time">
                        <el-form-item label="实时代付">
                          <el-select v-model="node.action.real_time" style="width:100%">
                            <el-option label="是" value="是" />
                            <el-option label="否" value="否" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                    </el-row>
                    <el-row :gutter="12" v-if="node.action.interface_type === '代付' && node.action.real_time === '否' && currentNodeChannel(node)?.execute_types?.length">
                      <el-col :span="8">
                        <el-form-item label="跑批步骤">
                          <el-select v-model="node.action.execute_type" style="width:100%">
                            <el-option v-for="t in currentNodeChannel(node)?.execute_types || []" :key="t" :label="t" :value="t" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                    </el-row>
                  </el-form>
                </div>

                <!-- 通知配置（可插拔模块） -->
                <div class="node-config">
                  <div class="config-title">
                    通知配置
                    <el-switch v-model="node.notify_enabled" size="small" style="margin-left:8px" active-text="启用" inactive-text="禁用" />
                    <el-tooltip content="启用后，节点执行失败或结束时会发送通知；若发起流程时选择了「汇总通知」，节点通知将不生效" placement="top">
                      <i class="fa fa-question-circle" style="margin-left:6px;cursor:help;color:#909399;font-size:12px"></i>
                    </el-tooltip>
                  </div>
                  <el-form v-if="node.notify_enabled" label-width="90px" size="small">
                    <el-row :gutter="12">
                      <el-col :span="6">
                        <el-form-item label="失败通知">
                          <el-switch v-model="node.notify_on_failure" active-text="开启" inactive-text="关闭" />
                        </el-form-item>
                      </el-col>
                      <el-col :span="6" v-if="node.is_end_node">
                        <el-form-item label="结束通知">
                          <el-switch v-model="node.notify_on_end" active-text="开启" inactive-text="关闭" />
                        </el-form-item>
                      </el-col>
                      <el-col :span="12">
                        <el-form-item label="通知模板">
                          <el-select v-model="node.action.notify_template_id" placeholder="选择通知模板（留空使用下方自定义配置）" style="width:100%" clearable>
                            <el-option v-for="t in notifyTemplates" :key="t.id" :label="t.name" :value="t.id" />
                          </el-select>
                        </el-form-item>
                      </el-col>
                    </el-row>
                    <template v-if="!node.action.notify_template_id">
                      <el-row :gutter="12">
                        <el-col :span="8">
                          <el-form-item label="通知类型">
                            <el-select v-model="node.action.notify_type" style="width:100%">
                              <el-option label="邮件" value="email" />
                            </el-select>
                          </el-form-item>
                        </el-col>
                        <el-col :span="16">
                          <el-form-item label="收件人">
                            <el-input v-model="node.action.to_addresses_str" placeholder="多个用逗号分隔" />
                          </el-form-item>
                        </el-col>
                      </el-row>
                      <el-form-item label="主题">
                        <el-input v-model="node.action.subject" placeholder="邮件主题" />
                      </el-form-item>
                      <el-form-item label="内容">
                        <el-input v-model="node.action.content" type="textarea" :rows="4" placeholder="邮件内容模板，支持变量替换" />
                        <div class="variable-help">
                          <span class="help-label">可用变量：</span>
                          <el-tag size="small" v-for="v in notificationVariables" :key="v.value" class="var-tag" @click="insertVariable(node, v.value)">{{ v.label }}</el-tag>
                        </div>
                      </el-form-item>
                    </template>
                    <template v-else>
                      <div class="notify-template-hint">
                        <i class="fa fa-info-circle"></i>
                        当前引用通知模板：<strong>{{ getNotifyTemplateNameById(node.action.notify_template_id) }}</strong>
                      </div>
                    </template>
                  </el-form>
                  <div v-else class="notify-disabled-hint">
                    <i class="fa fa-info-circle"></i> 通知模块已禁用，该节点不会发送任何通知
                  </div>
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
                          <el-form-item label="条件关系">
                            <el-radio-group v-model="node.loop.exit_logic" size="small">
                              <el-radio-button label="and">全部满足(AND)</el-radio-button>
                              <el-radio-button label="or">任一满足(OR)</el-radio-button>
                            </el-radio-group>
                          </el-form-item>
                        </el-col>
                      </el-row>
                    </el-form>
                    <div class="loop-exit-conditions">
                      <div class="config-subtitle">退出条件（满足时退出循环）</div>
                      <div v-if="!node.loop.exit_conditions?.length" class="empty-tips">暂无退出条件，将按最大循环次数执行</div>
                      <div v-for="(cond, cIdx) in node.loop.exit_conditions" :key="cIdx" class="transition-row">
                        <span class="trans-label">条件 {{ cIdx + 1 }}:</span>
                        <el-select v-model="cond.field" placeholder="选择或输入字段" size="small" style="width:160px" filterable allow-create>
                          <el-option v-for="f in availableFields" :key="f.value" :label="f.label" :value="f.value" />
                        </el-select>
                        <el-select v-model="cond.operator" placeholder="操作符" size="small" style="width:120px">
                          <el-option v-for="(label, val) in operators" :key="val" :label="label" :value="val" />
                        </el-select>
                        <el-input v-if="!['success','fail'].includes(cond.operator)" v-model="cond.value" placeholder="值（多个值用逗号分隔）" size="small" style="width:180px" />
                        <el-button type="danger" size="small" circle @click="node.loop.exit_conditions.splice(cIdx, 1)"><i class="fa fa-times"></i></el-button>
                      </div>
                      <el-button size="small" @click="addExitCondition(node)" style="margin-top:4px">
                        <i class="fa fa-plus"></i> 添加退出条件
                      </el-button>
                    </div>
                  </div>
                </div>

                <!-- 流转条件 -->
                <div class="node-config">
                  <div class="config-title">流转条件</div>
                  <div v-if="!node.transitions.length" class="empty-tips">无条件设置时，顺序执行下一节点</div>
                  <div v-for="(trans, tIdx) in node.transitions" :key="tIdx" class="transition-row">
                    <span class="trans-label">条件 {{ tIdx + 1 }}:</span>
                    <el-select v-model="trans.condition.field" placeholder="选择或输入字段" size="small" style="width:160px" filterable allow-create @change="onFieldChange(trans)">
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
                  <div v-if="availableFields.length" class="field-tips">
                    <i class="fa fa-info-circle"></i> 可选字段（本节点+前面节点结果，点击复制）:
                    <el-tag v-for="f in availableFields" :key="f.value" size="small" class="field-tag" @click="copyField(f.value)">{{ f.label }}</el-tag>
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

    <!-- 通知模板管理 Dialog -->
    <el-dialog v-model="notifyTemplateListDialogVisible" title="通知模板管理" width="900px" :close-on-click-modal="false">
      <div class="notify-template-toolbar">
        <el-button type="primary" size="small" @click="openNotifyTemplateDialog()">
          <i class="fa fa-plus"></i> 新建模板
        </el-button>
        <el-button size="small" @click="loadNotifyTemplates">
          <i class="fa fa-refresh"></i> 刷新
        </el-button>
      </div>
      <el-table :data="notifyTemplates" stripe border style="width:100%;margin-top:12px" empty-text="暂无通知模板">
        <el-table-column prop="name" label="模板名称" width="150" />
        <el-table-column prop="title" label="通知标题" width="200" show-overflow-tooltip />
        <el-table-column label="接收人" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.receivers || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openNotifyTemplateDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteNotifyTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 通知模板编辑 Dialog -->
    <el-dialog v-model="notifyTemplateDialogVisible" :title="editingNotifyTemplate ? '编辑通知模板' : '新建通知模板'" width="600px" :close-on-click-modal="false">
      <el-form :model="notifyTemplateForm" label-width="100px">
        <el-form-item label="模板名称" required>
          <el-input v-model="notifyTemplateForm.name" placeholder="如: 代付失败通知" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="notifyTemplateForm.description" placeholder="模板用途说明" />
        </el-form-item>
        <el-form-item label="通知标题">
          <el-input v-model="notifyTemplateForm.title" placeholder="如: 【代付流程{notify_type}】{template_name}" />
        </el-form-item>
        <el-form-item label="接收人">
          <el-input v-model="notifyTemplateForm.receivers" placeholder="多个用逗号分隔，如: a@b.com,c@d.com" />
        </el-form-item>
        <el-form-item label="通知内容">
          <el-input v-model="notifyTemplateForm.content" type="textarea" :rows="6" placeholder="通知正文模板，支持变量替换" />
          <div class="variable-help">
            <span class="help-label">可用变量：</span>
            <el-tag size="small" v-for="v in notificationVariables" :key="v.value" class="var-tag" @click="insertVarToTplForm(v.value)">{{ v.label }}</el-tag>
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="notifyTemplateForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="notifyTemplateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="notifyTemplateSaving" @click="saveNotifyTemplate">保存</el-button>
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

// 通知模板管理
const notifyTemplates = ref([])
const notifyTemplateListDialogVisible = ref(false)
const notifyTemplateDialogVisible = ref(false)
const editingNotifyTemplate = ref(null)
const notifyTemplateSaving = ref(false)

const notifyTemplateForm = reactive({
  name: '',
  description: '',
  title: '',
  content: '',
  webhook_url: '',
  receivers: '',
  is_enabled: true,
})

const templateForm = reactive({
  name: '',
  description: '',
  is_enabled: true,
  nodes: [],
})

const CHANNEL_RESPONSE_FIELDS = {
  kls: [
    { value: 'retCode', label: 'retCode' },
    { value: 'orderStatus', label: 'orderStatus' },
    { value: 'error_code', label: 'error_code' },
    { value: 'error_msg', label: 'error_msg' },
    { value: 'message', label: 'message' },
    { value: 'state', label: 'state' },
    { value: 'data.orderNo', label: 'data.orderNo' },
    { value: 'data.amount', label: 'data.amount' },
  ],
  lep: [
    { value: 'retCode', label: 'retCode' },
    { value: 'error_code', label: 'error_code' },
    { value: 'error_msg', label: 'error_msg' },
    { value: 'message', label: 'message' },
    { value: 'data.orderNo', label: 'data.orderNo' },
  ],
  lstop: [
    { value: 'retCode', label: 'retCode' },
    { value: 'error_code', label: 'error_code' },
    { value: 'error_msg', label: 'error_msg' },
    { value: 'message', label: 'message' },
    { value: 'data.orderNo', label: 'data.orderNo' },
  ],
}

const DEFAULT_RESPONSE_FIELDS = [
  { value: 'retCode', label: 'retCode' },
  { value: 'orderStatus', label: 'orderStatus' },
  { value: 'error_code', label: 'error_code' },
  { value: 'error_msg', label: 'error_msg' },
  { value: 'message', label: 'message' },
  { value: 'state', label: 'state' },
  { value: 'data.orderNo', label: 'data.orderNo' },
  { value: 'data.amount', label: 'data.amount' },
]

const availableFields = computed(() => {
  if (selectedNodeIdx.value == null) return []
  const currentNodeId = templateForm.nodes[selectedNodeIdx.value]?.id
  const fields = []
  const fieldSet = new Set()

  const currentChannel = templateForm.nodes[selectedNodeIdx.value]?.action?.channel
  const currentFields = CHANNEL_RESPONSE_FIELDS[currentChannel] || DEFAULT_RESPONSE_FIELDS
  for (const f of currentFields) {
    const fieldValue = `${currentNodeId}.${f.value}`
    if (!fieldSet.has(fieldValue)) {
      fieldSet.add(fieldValue)
      fields.push({ value: fieldValue, label: `${f.label}` })
    }
  }

  const prevNodes = templateForm.nodes.slice(0, selectedNodeIdx.value)
  for (const n of prevNodes) {
    if (n.type === 'pay') {
      const prevChannel = n.action?.channel
      const prevFields = CHANNEL_RESPONSE_FIELDS[prevChannel] || DEFAULT_RESPONSE_FIELDS
      for (const f of prevFields) {
        const fieldValue = `${n.id}.${f.value}`
        if (!fieldSet.has(fieldValue)) {
          fieldSet.add(fieldValue)
          fields.push({ value: fieldValue, label: `${n.name}.${f.value}` })
        }
      }
    }
  }
  return fields
})

const notificationVariables = computed(() => {
  const vars = [
    { value: '{execution_id}', label: '执行ID' },
    { value: '{template_name}', label: '模板名称' },
    { value: '{status}', label: '状态' },
    { value: '{node_name}', label: '节点名称' },
    { value: '{notify_type}', label: '通知类型' },
    { value: '{error_message}', label: '错误信息' },
    { value: '{row_index}', label: '行序号' },
    { value: '{batch_id}', label: '批次ID' },
    { value: '{accountName}', label: '账户名' },
    { value: '{businessNo}', label: '商户号' },
    { value: '{amount}', label: '金额' },
    { value: '{result.success}', label: '结果.成功' },
    { value: '{result.message}', label: '结果.消息' },
    // 汇总通知专用变量（发起流程时启用汇总通知后生效）
    { value: '{summary.total}', label: '汇总.总笔数' },
    { value: '{summary.success_count}', label: '汇总.成功笔数' },
    { value: '{summary.fail_count}', label: '汇总.失败笔数' },
    { value: '{summary.success_amount}', label: '汇总.成功金额' },
    { value: '{summary.fail_amount}', label: '汇总.失败金额' },
    { value: '{summary.success_list}', label: '汇总.成功明细' },
    { value: '{summary.fail_list}', label: '汇总.失败明细' },
  ]

  // 添加当前节点和前面节点的结果字段作为模板变量
  if (selectedNodeIdx.value != null) {
    const currentNodeId = templateForm.nodes[selectedNodeIdx.value]?.id
    const currentChannel = templateForm.nodes[selectedNodeIdx.value]?.action?.channel
    const currentFields = CHANNEL_RESPONSE_FIELDS[currentChannel] || DEFAULT_RESPONSE_FIELDS
    for (const f of currentFields) {
      vars.push({ value: `{result.fields.${f.value}}`, label: `结果.${f.label}` })
    }

    const prevNodes = templateForm.nodes.slice(0, selectedNodeIdx.value)
    for (const n of prevNodes) {
      if (n.type === 'pay') {
        const prevChannel = n.action?.channel
        const prevFields = CHANNEL_RESPONSE_FIELDS[prevChannel] || DEFAULT_RESPONSE_FIELDS
        for (const f of prevFields) {
          vars.push({ value: `{${n.id}.${f.value}}`, label: `${n.name}.${f.label}` })
        }
      }
    }
  }

  return vars
})

function insertVariable(node, variable) {
  if (!node.action.content) {
    node.action.content = variable
  } else {
    node.action.content += variable
  }
}

function copyField(fieldValue) {
  navigator.clipboard?.writeText(fieldValue)
}

function currentNodeChannel(node) {
  return channels.value.find(c => c.channel === node?.action?.channel)
}

function onNodeChannelChange(node) {
  const ch = currentNodeChannel(node)
  if (ch) {
    node.action.interface_type = ch.interface_types?.[0] || '代付'
    node.action.real_time = ch.real_time ? '是' : '是'
    node.action.execute_type = ch.execute_types?.[0] || '创建代付'
  }
}

function onInterfaceTypeChange(node) {
  if (node.action.interface_type !== '代付') {
    node.action.real_time = '是'
    node.action.execute_type = '创建代付'
  }
}

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
  const firstChannel = channels.value[0]
  templateForm.nodes.push({
    id: `node_${Date.now()}`,
    name: `节点 ${idx + 1}`,
    type: 'pay',
    is_end_node: false,
    notify_on_failure: false,
    notify_on_end: false,
    notify_enabled: false,
    action: {
      channel: firstChannel?.channel || '',
      interface_type: firstChannel?.interface_types?.[0] || '代付',
      environment: 'test',
      real_time: '是',
      execute_type: firstChannel?.execute_types?.[0] || '创建代付',
      notify_template_id: null,
      notify_type: 'email',
      to_addresses: [],
      to_addresses_str: '',
      subject: '',
      content: '',
    },
    loop: { enabled: false, interval_seconds: 60, max_iterations: 10, exit_logic: 'and', exit_conditions: [] },
    transitions: [],
  })
  selectedNodeIdx.value = idx
}

function addExitCondition(node) {
  if (!node.loop.exit_conditions) {
    node.loop.exit_conditions = []
  }
  node.loop.exit_conditions.push({ field: '', operator: 'eq', value: '' })
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

async function loadNotifyTemplates() {
  try {
    const res = await api.payFlow.getNotifyTemplates({ per_page: 100 })
    const d = res.data
    notifyTemplates.value = Array.isArray(d) ? d : (d.items || [])
  } catch (e) {
    ElMessage.error('加载通知模板失败')
  }
}

function openNotifyTemplateListDialog() {
  loadNotifyTemplates()
  notifyTemplateListDialogVisible.value = true
}

function openNotifyTemplateDialog(row) {
  editingNotifyTemplate.value = row
  if (row) {
    notifyTemplateForm.name = row.name
    notifyTemplateForm.description = row.description || ''
    notifyTemplateForm.title = row.title || ''
    notifyTemplateForm.content = row.content || ''
    notifyTemplateForm.webhook_url = row.webhook_url || ''
    notifyTemplateForm.receivers = row.receivers || ''
    notifyTemplateForm.is_enabled = row.is_enabled
  } else {
    notifyTemplateForm.name = ''
    notifyTemplateForm.description = ''
    notifyTemplateForm.title = ''
    notifyTemplateForm.content = ''
    notifyTemplateForm.webhook_url = ''
    notifyTemplateForm.receivers = ''
    notifyTemplateForm.is_enabled = true
  }
  notifyTemplateDialogVisible.value = true
}

async function saveNotifyTemplate() {
  if (!notifyTemplateForm.name) { ElMessage.warning('请填写模板名称'); return }
  notifyTemplateSaving.value = true
  try {
    const payload = {
      name: notifyTemplateForm.name,
      description: notifyTemplateForm.description,
      title: notifyTemplateForm.title,
      content: notifyTemplateForm.content,
      webhook_url: notifyTemplateForm.webhook_url,
      receivers: notifyTemplateForm.receivers,
      is_enabled: notifyTemplateForm.is_enabled,
    }
    if (editingNotifyTemplate.value) {
      await api.payFlow.updateNotifyTemplate(editingNotifyTemplate.value.id, payload)
      ElMessage.success('模板更新成功')
    } else {
      await api.payFlow.createNotifyTemplate(payload)
      ElMessage.success('模板创建成功')
    }
    notifyTemplateDialogVisible.value = false
    loadNotifyTemplates()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '保存失败')
  } finally {
    notifyTemplateSaving.value = false
  }
}

async function deleteNotifyTemplate(row) {
  await ElMessageBox.confirm(`确定删除通知模板 "${row.name}"？`, '提示', { type: 'warning' })
  try {
    await api.payFlow.deleteNotifyTemplate(row.id)
    ElMessage.success('已删除')
    loadNotifyTemplates()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}

function getNotifyTemplateNameById(id) {
  const tpl = notifyTemplates.value.find(t => t.id === id)
  return tpl ? tpl.name : '未知模板'
}

function insertVarToTplForm(variable) {
  if (!notifyTemplateForm.content) {
    notifyTemplateForm.content = variable
  } else {
    notifyTemplateForm.content += variable
  }
}

onMounted(() => {
  loadTemplates()
  loadChannels()
  loadNodeFields()
  loadNotifyTemplates()
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
.field-tips { font-size: 12px; color: #909399; margin: 6px 0; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.field-tag { cursor: pointer; }
.field-tag:hover { background: #ecf5ff; }
.config-subtitle { font-size: 13px; color: #606266; font-weight: 500; margin: 8px 0; padding-left: 8px; border-left: 3px solid #e6a23c; }
.loop-exit-conditions { background: #fafafa; padding: 10px; border-radius: 4px; margin-top: 8px; }
.template-meta { margin-bottom: 8px; }
.variable-help { margin-top: 6px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.help-label { font-size: 12px; color: #909399; }
.var-tag { cursor: pointer; font-size: 11px; }
.var-tag:hover { background: #ecf5ff; }
.notify-template-toolbar { display: flex; gap: 8px; }
.notify-template-hint { font-size: 12px; color: #67c23a; padding: 6px 8px; background: #f0f9eb; border-radius: 4px; display: flex; align-items: center; gap: 6px; }
</style>
