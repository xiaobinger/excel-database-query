<template>
  <div class="login-logs">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-sign-in-alt"></i> 登录日志</span>
          <div class="header-actions">
            <el-select v-model="statusFilter" placeholder="登录状态" clearable style="width: 120px" @change="fetchData">
              <el-option label="成功" value="success" />
              <el-option label="失败" value="failed" />
            </el-select>
            <el-input
              v-model="keywordFilter"
              placeholder="搜索用户名/IP"
              clearable
              style="width: 200px"
              @keyup.enter="fetchData"
              @clear="fetchData"
            >
              <template #prefix><i class="fas fa-search"></i></template>
            </el-input>
            <el-date-picker
              v-model="dateFilter"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width: 280px"
              @change="fetchData"
            />
            <el-button @click="resetFilters">重置</el-button>
            <el-button type="danger" size="small" plain @click="handleClearAll">
              <i class="fas fa-trash"></i> 清空日志
            </el-button>
            <el-button type="primary" @click="fetchData" style="margin-left: 12px">
              <i class="fas fa-sync-alt"></i> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="logList" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip />
        <el-table-column label="IP地址" width="150">
          <template #default="{ row }">
            <span class="ip-text">{{ row.ip_address || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="失败原因" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.fail_reason" style="color: #f56c6c">{{ row.fail_reason }}</span>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="浏览器标识" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="ua-text">{{ row.user_agent || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="登录时间" width="180" show-overflow-tooltip />
      </el-table>

      <div class="pagination-area">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>

      <el-empty v-if="!loading && logList.length === 0" description="暂无登录日志" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const logList = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const keywordFilter = ref('')
const dateFilter = ref(null)

async function fetchData() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      per_page: pageSize.value,
    }
    if (statusFilter.value) params.status = statusFilter.value
    if (keywordFilter.value) params.keyword = keywordFilter.value
    if (dateFilter.value && dateFilter.value.length === 2) {
      params.start_date = dateFilter.value[0]
      params.end_date = dateFilter.value[1]
    }
    const res = await api.logs.login(params)
    logList.value = res.data || []
    total.value = res.total || 0
  } catch {
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  statusFilter.value = ''
  keywordFilter.value = ''
  dateFilter.value = null
  currentPage.value = 1
  fetchData()
}

async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有登录日志吗？此操作不可恢复！',
      '清空确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await api.logs.clearLogin()
    ElMessage.success('登录日志已清空')
    currentPage.value = 1
    fetchData()
  } catch {
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.login-logs {
  max-width: 1400px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 600;
  flex-wrap: wrap;
  gap: 10px;
}

.card-header i {
  margin-right: 8px;
  color: var(--primary-color, #409eff);
}

.header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.ip-text {
  font-family: Consolas, Monaco, monospace;
  font-size: 13px;
}

.ua-text {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}

.pagination-area {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
