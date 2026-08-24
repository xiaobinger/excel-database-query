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

      <!-- 执行按钮 -->
      <div class="action-bar">
        <el-button type="primary" :loading="executing" :disabled="!canExecute" @click="doExecute">
          <i class="fa fa-play"></i> 执行{{ form.interface_type }}
        </el-button>
        <el-button @click="resetForm">重置</el-button>
        <span v-if="form.environment === 'pro'" class="pro-warn"><i class="fa fa-exclamation-triangle"></i> 生产环境，请谨慎操作</span>
      </div>

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

const channels = ref([])
const fileList = ref([])
const uploadRef = ref()
const executing = ref(false)
const result = ref(null)
const showLogs = ref(false)

const form = reactive({
  channel: '',
  interface_type: '代付',
  environment: 'test',
  real_time: '是',
  execute_type: '创建代付',
})

const currentChannel = computed(() => channels.value.find(c => c.channel === form.channel))
const isKls = computed(() => form.channel === 'kls')
const canExecute = computed(() => !!form.channel && fileList.value.length > 0)

function onChannelChange() {
  const c = currentChannel.value
  form.interface_type = c?.interface_types?.[0] || '代付'
  form.real_time = c?.real_time ? '是' : '是'
  form.execute_type = c?.execute_types?.[0] || '创建代付'
}

function onFileChange(file) {
  fileList.value = [file]
  result.value = null
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
  uploadRef.value?.clearFiles()
  result.value = null
}

async function doExecute() {
  if (!form.channel) { ElMessage.warning('请选择渠道'); return }
  if (!fileList.value.length) { ElMessage.warning('请选择 Excel 文件'); return }
  const fd = new FormData()
  fd.append('file', fileList.value[0].raw)
  fd.append('channel', form.channel)
  fd.append('environment', form.environment)
  fd.append('interface_type', form.interface_type)
  fd.append('real_time', form.real_time)
  fd.append('execute_type', form.execute_type)

  executing.value = true
  result.value = null
  try {
    const res = await api.pay.execute(fd)
    result.value = res.data
    if (form.environment === 'pro') {
      ElMessage.warning('生产环境执行完成：' + res.data.message)
    } else {
      ElMessage.success(res.data.message)
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
