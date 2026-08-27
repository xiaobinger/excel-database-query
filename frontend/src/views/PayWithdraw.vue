<template>
  <div class="page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <span><i class="fa fa-money-bill-wave"></i> 代付提现</span>
          <span class="hint">上传 Excel 批量执行代付/查询，支持合利宝、电银、乐商通PLUS、快乐刷 4 个渠道</span>
        </div>
      </template>

      <!-- 参数区 -->
      <el-form :model="form" label-width="110px" class="pay-form">
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="渠道">
              <el-select v-model="form.channel" placeholder="请选择渠道" style="width:100%" @change="onChannelChange">
                <el-option v-for="c in channels" :key="c.channel" :label="c.name" :value="c.channel" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="接口类型">
              <el-select v-model="form.interface_type" style="width:100%" :disabled="!currentChannel">
                <el-option v-for="t in currentChannel?.interface_types || []" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="环境">
              <el-radio-group v-model="form.environment">
                <el-radio-button label="test">测试</el-radio-button>
                <el-radio-button label="pro">生产</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="实时代付">
              <el-select v-model="form.real_time" style="width:100%" :disabled="!isKls">
                <el-option label="是" value="是" />
                <el-option label="否" value="否" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16" v-if="isKls && form.interface_type === '代付' && form.real_time === '否'">
          <el-col :span="6">
            <el-form-item label="跑批步骤">
              <el-select v-model="form.execute_type" style="width:100%">
                <el-option v-for="t in currentChannel?.execute_types || []" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <!-- 文件上传 -->
      <el-form label-width="110px">
        <el-form-item label="Excel 文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".xls,.xlsx"
            :on-change="onFileChange"
            :on-exceed="onExceed"
            :file-list="fileList"
          >
            <el-button type="primary" plain><i class="fa fa-upload"></i> 选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .xls / .xlsx，列顺序需符合渠道模板（姓名/流水号/手机号/身份证/银行卡/金额(分) 等）</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>

      <!-- 工作表选择 -->
      <el-form label-width="110px" v-if="sheetList.length > 0">
        <el-form-item label="工作表">
          <el-select v-model="selectedSheetIndex" style="width:100%" placeholder="请选择要执行的工作表">
            <el-option v-for="(s, idx) in sheetList" :key="idx" :label="`${idx + 1}. ${s.name}（${s.row_count} 行数据）`" :value="idx" />
          </el-select>
        </el-form-item>
      </el-form>

      <!-- 执行按钮 -->
      <div class="action-bar">
        <el-button type="primary" :loading="executing" :disabled="!canExecute" @click="doExecute">
          <i class="fa fa-play"></i> 执行{{ form.interface_type }}
        </el-button>
        <el-button type="success" :loading="startingFlow" :disabled="!canExecute" @click="openStartFlowDialog">
          <i class="fa fa-project-diagram"></i> 发起代付流程
        </el-button>
        <el-button @click="resetForm">重置</el-button>
        <span v-if="form.environment === 'pro'" class="pro-warn"><i class="fa fa-exclamation-triangle"></i> 生产环境，请谨慎操作</span>
      </div>

      <!-- 发起代付流程 Dialog -->
      <el-dialog v-model="startFlowDialogVisible" title="发起代付流程" width="600px" :close-on-click-modal="false">
        <el-form :model="startFlowForm" label-width="100px">
          <el-form-item label="流程模板" required>
            <el-select v-model="startFlowForm.template_id" placeholder="请选择流程模板" style="width:100%" filterable>
              <el-option v-for="t in flowTemplates" :key="t.id" :label="t.name" :value="t.id" :disabled="!t.is_enabled">
                <span>{{ t.name }}</span>
                <span v-if="!t.is_enabled" style="color:#909399;font-size:12px;margin-left:8px">(已禁用)</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="渠道" required>
            <el-select v-model="startFlowForm.channel" placeholder="选择渠道" style="width:100%">
              <el-option v-for="c in channels" :key="c.channel" :label="c.name" :value="c.channel" />
            </el-select>
          </el-form-item>
          <el-form-item label="环境" required>
            <el-radio-group v-model="startFlowForm.environment">
              <el-radio-button label="test">测试</el-radio-button>
              <el-radio-button label="pro">生产</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="接口类型">
            <el-select v-model="startFlowForm.interface_type" style="width:100%">
              <el-option label="代付" value="代付" />
              <el-option label="查询" value="查询" />
            </el-select>
          </el-form-item>
          <el-form-item label="数据行数">
            <el-tag type="info">{{ sheetList[selectedSheetIndex]?.row_count || 0 }} 行</el-tag>
          </el-form-item>
          <el-form-item label="汇总通知">
            <el-switch v-model="startFlowForm.summary_notify_enabled" active-text="启用" inactive-text="关闭" />
            <el-tooltip content="启用后，所有流程执行完毕时发送一条汇总通知（成功/失败笔数、金额、明细），节点上的单笔通知将不生效" placement="top">
              <i class="fa fa-question-circle" style="margin-left:8px;cursor:help;color:#909399"></i>
            </el-tooltip>
          </el-form-item>
          <el-form-item v-if="startFlowForm.summary_notify_enabled" label="通知模板">
            <el-select v-model="startFlowForm.summary_notify_template_id" placeholder="选择汇总通知模板" style="width:100%" filterable>
              <el-option v-for="t in notifyTemplates" :key="t.id" :label="t.name" :value="t.id">
                <span>{{ t.name }}</span>
                <span v-if="!t.is_enabled" style="color:#909399;font-size:12px;margin-left:8px">(已禁用)</span>
              </el-option>
            </el-select>
            <div style="margin-top:6px;font-size:12px;color:#909399">
              可用变量：{summary.total} {summary.success_count} {summary.fail_count} {summary.success_amount} {summary.fail_amount} {summary.success_list} {summary.fail_list}
            </div>
          </el-form-item>
          <el-form-item>
            <template #label>
              <span>管理流程</span>
              <el-tooltip content="前往流程编排页面管理模板" placement="top">
                <i class="fa fa-question-circle" style="margin-left:4px;cursor:help"></i>
              </el-tooltip>
            </template>
            <el-button size="small" @click="$router.push('/pay-flow')">
              <i class="fa fa-cog"></i> 流程编排
            </el-button>
            <el-button size="small" @click="$router.push('/pay-flow-executions')">
              <i class="fa fa-stream"></i> 执行记录
            </el-button>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="startFlowDialogVisible = false">取消</el-button>
          <el-button type="success" :loading="startingFlow" :disabled="!startFlowForm.template_id || !startFlowForm.channel" @click="doStartFlow">发起流程</el-button>
        </template>
      </el-dialog>

      <!-- 结果区 -->
      <el-divider v-if="result" />
      <div v-if="result" class="result-area">
        <el-alert :title="result.message" type="success" :closable="false" show-icon class="result-msg" />
        <div class="result-actions">
          <el-button type="primary" plain size="small" @click="downloadResult">
            <i class="fa fa-download"></i> 下载结果 Excel
          </el-button>
          <el-button size="small" @click="showLogs = !showLogs">
            <i class="fa fa-list"></i> {{ showLogs ? '隐藏' : '查看' }}执行日志 ({{ result.logs.length }})
          </el-button>
        </div>
        <el-collapse v-if="showLogs" class="log-collapse">
          <el-collapse-item title="执行日志">
            <pre class="log-pre">{{ result.logs.join('\n') }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useRouter } from 'vue-router'

const channels = ref([])
const fileList = ref([])
const uploadRef = ref()
const executing = ref(false)
const result = ref(null)
const showLogs = ref(false)
const sheetList = ref([])
const selectedSheetIndex = ref(0)
const uploadedFilePath = ref('')

const form = reactive({
  channel: '',
  interface_type: '代付',
  environment: 'test',
  real_time: '是',
  execute_type: '创建代付',
})

const currentChannel = computed(() => channels.value.find(c => c.channel === form.channel))
const isKls = computed(() => form.channel === 'kls')
const canExecute = computed(() => !!form.channel && fileList.value.length > 0 && sheetList.value.length > 0)

function onChannelChange() {
  const c = currentChannel.value
  form.interface_type = c?.interface_types?.[0] || '代付'
  form.real_time = c?.real_time ? '是' : '是'
  form.execute_type = c?.execute_types?.[0] || '创建代付'
}

async function onFileChange(file) {
  fileList.value = [file]
  result.value = null
  sheetList.value = []
  selectedSheetIndex.value = 0
  uploadedFilePath.value = ''

  const fd = new FormData()
  fd.append('file', file.raw)
  try {
    const res = await api.pay.sheets(fd)
    sheetList.value = res.data.sheets || []
    uploadedFilePath.value = res.data.file_path || ''
    if (sheetList.value.length > 0) {
      selectedSheetIndex.value = 0
      ElMessage.success(`识别到 ${sheetList.value.length} 个工作表，共 ${sheetList.value.reduce((a, b) => a + (b.row_count || 0), 0)} 行数据`)
    } else {
      ElMessage.warning('未识别到有效数据工作表')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '工作表识别失败')
    fileList.value = []
    uploadRef.value?.clearFiles()
  }
}
function onExceed() {
  ElMessage.warning('一次只能上传一个文件，请先移除已有文件')
}

function resetForm() {
  form.channel = ''
  form.interface_type = '代付'
  form.environment = 'test'
  form.real_time = '是'
  form.execute_type = '创建代付'
  fileList.value = []
  sheetList.value = []
  selectedSheetIndex.value = 0
  uploadedFilePath.value = ''
  uploadRef.value?.clearFiles()
  result.value = null
}

async function doExecute() {
  if (!form.channel) { ElMessage.warning('请选择渠道'); return }
  if (!fileList.value.length) { ElMessage.warning('请选择 Excel 文件'); return }
  if (!sheetList.value.length) { ElMessage.warning('请等待工作表识别完成'); return }
  const fd = new FormData()
  if (uploadedFilePath.value) {
    fd.append('file_path', uploadedFilePath.value)
  } else {
    fd.append('file', fileList.value[0].raw)
  }
  fd.append('channel', form.channel)
  fd.append('environment', form.environment)
  fd.append('interface_type', form.interface_type)
  fd.append('real_time', form.real_time)
  fd.append('execute_type', form.execute_type)
  fd.append('sheet_index', String(selectedSheetIndex.value))

  executing.value = true
  result.value = null
  try {
    const res = await api.pay.execute(fd)
    result.value = res.data
    const sheetHint = res.data?.sheet_name ? `（工作表: ${res.data.sheet_name}）` : ''
    if (form.environment === 'pro') {
      ElMessage.warning('生产环境执行完成：' + res.data.message + sheetHint)
    } else {
      ElMessage.success(res.data.message + sheetHint)
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '执行失败')
  } finally {
    executing.value = false
  }
}

function downloadResult() {
  if (result.value?.result_url) {
    window.open(result.value.result_url, '_blank')
  }
}

const router = useRouter()
const flowTemplates = ref([])
const notifyTemplates = ref([])
const startFlowDialogVisible = ref(false)
const startingFlow = ref(false)

const startFlowForm = reactive({
  template_id: null,
  channel: '',
  environment: 'test',
  interface_type: '代付',
  summary_notify_enabled: false,
  summary_notify_template_id: null,
})

async function loadFlowTemplates() {
  try {
    const res = await api.payFlow.templates({ per_page: 100 })
    flowTemplates.value = res.data.items || []
  } catch (e) { /* ignore */ }
}

async function loadNotifyTemplates() {
  try {
    const res = await api.payFlow.getNotifyTemplates({ per_page: 100 })
    const d = res.data
    notifyTemplates.value = Array.isArray(d) ? d : (d.items || [])
  } catch (e) { /* ignore */ }
}

function openStartFlowDialog() {
  if (!form.channel) { ElMessage.warning('请选择渠道'); return }
  if (!sheetList.value.length) { ElMessage.warning('请等待工作表识别完成'); return }
  startFlowForm.template_id = null
  startFlowForm.channel = form.channel
  startFlowForm.environment = form.environment
  startFlowForm.interface_type = form.interface_type
  startFlowForm.summary_notify_enabled = false
  startFlowForm.summary_notify_template_id = null
  startFlowDialogVisible.value = true
  loadFlowTemplates()
  loadNotifyTemplates()
}

async function doStartFlow() {
  if (!startFlowForm.template_id) { ElMessage.warning('请选择流程模板'); return }
  if (!startFlowForm.channel) { ElMessage.warning('请选择渠道'); return }
  if (!sheetList.value.length) { ElMessage.warning('请等待工作表识别完成'); return }
  if (startFlowForm.summary_notify_enabled && !startFlowForm.summary_notify_template_id) {
    ElMessage.warning('启用汇总通知时，请选择通知模板'); return
  }
  startingFlow.value = true
  try {
    const res = await api.payFlow.start({
      template_id: startFlowForm.template_id,
      file_path: uploadedFilePath.value,
      sheet_index: selectedSheetIndex.value,
      params: {
        channel: startFlowForm.channel,
        environment: startFlowForm.environment,
        interface_type: startFlowForm.interface_type,
        real_time: form.real_time,
        execute_type: form.execute_type,
        summary_notify_enabled: startFlowForm.summary_notify_enabled,
        summary_notify_template_id: startFlowForm.summary_notify_template_id,
      },
    })
    const d = res.data
    let msg = `流程已发起，共 ${d.total} 笔数据`
    if (d.summary_notify_enabled) {
      msg += '（已启用汇总通知）'
    }
    ElMessage.success(msg)
    startFlowDialogVisible.value = false
    router.push('/pay-flow-executions')
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '发起流程失败')
  } finally {
    startingFlow.value = false
  }
}

onMounted(async () => {
  try {
    const res = await api.pay.channels()
    channels.value = res.data
  } catch (e) { /* ignore */ }
})
</script>

<style scoped>
.page { padding: 0; }
.page-card { border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-header > span:first-child { font-size: 15px; font-weight: 600; }
.hint { font-size: 12px; color: #909399; }
.pay-form { margin-bottom: 8px; }
.action-bar { display: flex; align-items: center; gap: 12px; margin: 8px 0 4px; }
.pro-warn { color: #e6a23c; font-size: 13px; }
.result-msg { margin-bottom: 12px; }
.result-actions { display: flex; gap: 8px; margin-bottom: 12px; }
.log-pre {
  max-height: 320px; overflow: auto; margin: 0;
  background: #f5f7fa; border-radius: 6px; padding: 12px;
  font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-all;
  font-family: 'Consolas', monospace;
}
</style>
