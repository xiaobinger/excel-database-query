import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const http = axios.create({
  baseURL: '/api',
  timeout: 60000
})

http.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      const currentPath = router.currentRoute.value.path
      if (currentPath !== '/login') {
        router.push('/login')
      }
      return Promise.reject(error)
    }
    const msg = error.response?.data?.message || error.response?.data?.error || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

const auth = {
  login: (data) => http.post('/auth/login', data),
  me: () => http.get('/auth/me'),
  changePassword: (data) => http.put('/auth/password', data),
}

const users = {
  list: () => http.get('/users'),
  create: (data) => http.post('/users', data),
  update: (id, data) => http.put(`/users/${id}`, data),
  delete: (id) => http.delete(`/users/${id}`),
  batchDelete: (ids) => http.post('/users/batch-delete', { ids }),
  deleteAll: () => http.delete('/users/all'),
  setScripts: (id, data) => http.put(`/users/${id}/scripts`, data),
}

const roles = {
  list: () => http.get('/roles'),
  create: (data) => http.post('/roles', data),
  update: (id, data) => http.put(`/roles/${id}`, data),
  delete: (id) => http.delete(`/roles/${id}`),
  batchDelete: (ids) => http.post('/roles/batch-delete', { ids }),
  deleteAll: () => http.delete('/roles/all'),
}

const ssh = {
  list: () => http.get('/ssh'),
  get: (id) => http.get(`/ssh/${id}`),
  create: (data) => http.post('/ssh', data),
  update: (id, data) => http.put(`/ssh/${id}`, data),
  delete: (id) => http.delete(`/ssh/${id}`),
  batchDelete: (ids) => http.post('/ssh/batch-delete', { ids }),
  deleteAll: () => http.delete('/ssh/all'),
  test: (id) => http.post(`/ssh/${id}/test`)
}

const databases = {
  list: () => http.get('/databases'),
  get: (id) => http.get(`/databases/${id}`),
  create: (data) => http.post('/databases', data),
  update: (id, data) => http.put(`/databases/${id}`, data),
  delete: (id) => http.delete(`/databases/${id}`),
  batchDelete: (ids) => http.post('/databases/batch-delete', { ids }),
  deleteAll: () => http.delete('/databases/all'),
  test: (id) => http.post(`/databases/${id}/test`),
  getTables: (id) => http.get(`/databases/${id}/tables`),
  getTableColumns: (id, table) => http.get(`/databases/${id}/tables/${table}/columns`),
  getTypes: () => http.get('/databases/types')
}

const scripts = {
  list: (params) => http.get('/scripts', { params }),
  get: (id) => http.get(`/scripts/${id}`),
  create: (data) => http.post('/scripts', data),
  update: (id, data) => http.put(`/scripts/${id}`, data),
  delete: (id) => http.delete(`/scripts/${id}`),
  batchDelete: (ids) => http.post('/scripts/batch-delete', { ids }),
  deleteAll: () => http.delete('/scripts/all'),
  validate: (id) => http.post(`/scripts/${id}/validate`),
  validateSql: (data) => http.post('/scripts/validate', data),
  formatSql: (data) => http.post('/scripts/format', data),
  simplifySql: (data) => http.post('/scripts/simplify', data),
  extractColumns: (data) => http.post('/scripts/extract-columns', data),
  getTags: () => http.get('/scripts/tags'),
  renderTemplate: (data) => http.post('/scripts/render-template', data),
  renderScriptTemplate: (id, data) => http.post(`/scripts/${id}/render-template`, data),
}

const query = {
  execute: (formData) => http.post('/query/execute', formData),
  status: (taskId) => http.get(`/query/status/${taskId}`),
  streamStatus: (taskId) => {
    const token = localStorage.getItem('token')
    const sep = token ? `?token=${encodeURIComponent(token)}` : ''
    return `/api/query/stream/${taskId}${sep}`
  },
  cancel: (taskId) => http.post(`/query/cancel/${taskId}`),
  tasks: (params) => http.get('/query/tasks', { params: { ...params, per_page: params.page_size || params.per_page || 20 } }),
  deleteTask: (id) => http.delete(`/query/tasks/${id}`),
  batchDeleteTasks: (ids) => http.post('/query/tasks/batch-delete', { ids }),
  deleteAllTasks: () => http.delete('/query/tasks/all'),
  uploadInfo: (formData) => http.post('/query/upload-info', formData),
  dashboard: () => http.get('/query/dashboard'),
  smartMatch: (filename) => http.post('/query/smart-match', { filename }),
  fuzzyMatchColumns: (data) => http.post('/query/fuzzy-match-columns', data),
  retry: (taskId) => http.post(`/query/retry/${taskId}`),
  config: () => http.get('/query/config')
}

const exportApi = {
  execute: (data) => http.post('/export/execute', data),
  status: (taskId) => http.get(`/export/status/${taskId}`),
  streamStatus: (taskId) => {
    const token = localStorage.getItem('token')
    const sep = token ? `?token=${encodeURIComponent(token)}` : ''
    return `/api/export/stream/${taskId}${sep}`
  },
  cancel: (taskId) => http.post(`/export/cancel/${taskId}`),
  retry: (taskId) => http.post(`/export/retry/${taskId}`),
  deleteTask: (id) => http.delete(`/export/tasks/${id}`),
  batchDeleteTasks: (ids) => http.post('/export/tasks/batch-delete', { ids }),
  deleteAllTasks: () => http.delete('/export/tasks/all'),
  tasks: (params) => http.get('/export/tasks', { params }),
}

const autoExport = {
  list: () => http.get('/auto-export'),
  create: (data) => http.post('/auto-export', data),
  update: (id, data) => http.put(`/auto-export/${id}`, data),
  delete: (id) => http.delete(`/auto-export/${id}`),
  batchDelete: (ids) => http.post('/auto-export/batch-delete', { ids }),
  deleteAll: () => http.delete('/auto-export/all'),
  toggle: (id) => http.post(`/auto-export/${id}/toggle`),
  runNow: (id) => http.post(`/auto-export/${id}/run-now`),
  paramOptions: () => http.get('/auto-export/param-options'),
}

const system = {
  getConfig: () => http.get('/system/config'),
  updateConfig: (data) => http.put('/system/config', data),
  testEmail: (data) => http.post('/system/test-email', data),
  batchDelete: (ids) => http.post('/system/config/batch-delete', { ids }),
  deleteAll: () => http.delete('/system/config/all'),
  getMenuConfig: () => http.get('/system/menu-config'),
  saveMenuConfig: (data) => http.put('/system/menu-config', { menu_config: data }),
  getMenuItems: () => http.get('/system/menu-items'),
}

const download = {
  file: (taskId) => `/api/download/${taskId}`
}

const tasks = {
  getActive: () => http.get('/tasks/active'),
  getRecent: (params) => http.get('/tasks/recent', { params }),
}

const ai = {
  getConfigs: () => http.get('/ai/configs'),
  getActiveModels: () => http.get('/ai/active-models'),
  createConfig: (data) => http.post('/ai/configs', data),
  updateConfig: (id, data) => http.put(`/ai/configs/${id}`, data),
  deleteConfig: (id) => http.delete(`/ai/configs/${id}`),
  batchDeleteConfigs: (ids) => http.post('/ai/configs/batch-delete', { ids }),
  deleteAllConfigs: () => http.delete('/ai/configs/all'),
  testConfig: (id) => http.post(`/ai/configs/${id}/test`),
  getSkills: (params) => http.get('/ai/skills', { params }),
  createSkill: (data) => http.post('/ai/skills', data),
  updateSkill: (id, data) => http.put(`/ai/skills/${id}`, data),
  deleteSkill: (id) => http.delete(`/ai/skills/${id}`),
  batchDeleteSkills: (ids) => http.post('/ai/skills/batch-delete', { ids }),
  deleteAllSkills: () => http.delete('/ai/skills/all'),
  trackBehavior: (data) => http.post('/ai/behaviors', data),
  getBehaviors: (params) => http.get('/ai/behaviors', { params }),
  getChats: () => http.get('/ai/chats'),
  createChat: (data) => http.post('/ai/chats', data),
  updateChat: (id, data) => http.put(`/ai/chats/${id}`, data),
  deleteChat: (id) => http.delete(`/ai/chats/${id}`),
  hardDeleteChat: (id) => http.delete(`/ai/chats/${id}/hard`),
  batchHardDeleteChats: (ids) => http.post('/ai/chats/batch-hard-delete', { ids }),
  hardDeleteAllChats: () => http.delete('/ai/chats/all-hard'),
  clearChatMessages: (id, data) => http.post(`/ai/chats/${id}/clear`, data),
  compressChatContext: (id, data) => http.post(`/ai/chats/${id}/compress`, data),
  retryMessage: (chatId, msgId) => http.post(`/ai/chats/${chatId}/messages/${msgId}/retry`),
  getMessages: (chatId) => http.get(`/ai/chats/${chatId}/messages`),
  sendMessage: (chatId, data) => http.post(`/ai/chats/${chatId}/send`, data, { timeout: 180000 }),
  sendMessageStream: (chatId, data) => `/api/ai/chats/${chatId}/send-stream`,
  abortRequest: (chatId) => http.post(`/ai/chats/${chatId}/abort`),
  getStreamStatus: (chatId) => http.get(`/ai/chats/${chatId}/stream-status`),
  resumeStreamUrl: (chatId) => `/api/ai/chats/${chatId}/resume-stream`,
  uploadFile: (formData) => http.post('/ai/upload-file', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  matchQuery: (data) => http.post('/ai/match-query', data),
  updateMessage: (chatId, msgId, data) => http.put(`/ai/chats/${chatId}/messages/${msgId}`, data),
  createMessage: (chatId, data) => http.post(`/ai/chats/${chatId}/messages`, data),
  deleteMessage: (chatId, msgId) => http.delete(`/ai/chats/${chatId}/messages/${msgId}`),
  hardDeleteMessage: (chatId, msgId) => http.delete(`/ai/chats/${chatId}/messages/${msgId}/hard`),
  adminListChats: (params) => http.get('/ai/admin/chats', { params }),
  adminRestoreChat: (chatId) => http.put(`/ai/admin/chats/${chatId}/restore`),
  batchRestoreChats: (ids) => http.post('/ai/admin/chats/batch-restore', { ids }),
  restoreAllChats: () => http.put('/ai/admin/chats/restore-all'),
  listStrategies: () => http.get('/ai-strategy/list'),
  getStrategy: (id) => http.get(`/ai-strategy/${id}`),
  createStrategy: (data) => http.post('/ai-strategy', data),
  updateStrategy: (id, data) => http.put(`/ai-strategy/${id}`, data),
  deleteStrategy: (id) => http.delete(`/ai-strategy/${id}`),
  resetStrategyTokens: (id) => http.post(`/ai-strategy/${id}/reset-tokens`),
  getCacheStats: () => http.get('/ai/cache/stats'),
}

const agent = {
  list: () => http.get('/agents'),
  getAll: () => http.get('/agents/all'),
  getDefault: () => http.get('/agents/default'),
  create: (data) => http.post('/agents', data),
  update: (id, data) => http.put(`/agents/${id}`, data),
  delete: (id) => http.delete(`/agents/${id}`),
  batchDelete: (ids) => http.post('/agents/batch-delete', { ids }),
  deleteAll: () => http.delete('/agents/all'),
  setDefault: (id) => http.post(`/agents/${id}/set-default`),
  // Agent记忆管理
  getMemories: (agentId, params) => http.get(`/agents/${agentId}/memories`, { params }),
  addMemory: (agentId, data) => http.post(`/agents/${agentId}/memories`, data),
  updateMemory: (agentId, memoryId, data) => http.put(`/agents/${agentId}/memories/${memoryId}`, data),
  deleteMemory: (agentId, memoryId) => http.delete(`/agents/${agentId}/memories/${memoryId}`),
}

const business = {
  listSystems: () => http.get('/business/systems'),
  listAllSystems: () => http.get('/business/systems/all'),
  createSystem: (data) => http.post('/business/systems', data),
  updateSystem: (id, data) => http.put(`/business/systems/${id}`, data),
  deleteSystem: (id) => http.delete(`/business/systems/${id}`),
  batchDeleteSystems: (ids) => http.post('/business/systems/batch-delete', { ids }),
  deleteAllSystems: () => http.delete('/business/systems/all'),
  generateSsoUrl: (id, data) => http.post(`/business/systems/${id}/sso`, data),
  getCategories: () => http.get('/business/categories'),
}

const systemTask = {
  list: () => http.get('/system-tasks'),
  get: (id) => http.get(`/system-tasks/${id}`),
  create: (data) => http.post('/system-tasks', data),
  update: (id, data) => http.put(`/system-tasks/${id}`, data),
  delete: (id) => http.delete(`/system-tasks/${id}`),
  batchDelete: (ids) => http.post('/system-tasks/batch-delete', { ids }),
  deleteAll: () => http.delete('/system-tasks/all'),
  execute: (id, data) => http.post(`/system-tasks/${id}/execute`, data),
  executions: (params) => http.get('/system-tasks/executions', { params }),
  getExecution: (executionId) => http.get(`/system-tasks/executions/${executionId}`),
  cancelExecution: (executionId) => http.post(`/system-tasks/executions/${executionId}/cancel`),
  deleteExecution: (executionId) => http.delete(`/system-tasks/executions/${executionId}`),
  batchDeleteExecutions: (ids) => http.post('/system-tasks/executions/batch-delete', { ids }),
  deleteAllExecutions: () => http.delete('/system-tasks/executions/all'),
  streamExecution: (executionId) => {
    const token = localStorage.getItem('token')
    const sep = token ? `?token=${encodeURIComponent(token)}` : ''
    return `/api/system-tasks/executions/${executionId}/stream${sep}`
  },
  getEnums: () => http.get('/system-tasks/enums'),
  saveEnums: (data) => http.put('/system-tasks/enums', data),
  uploadScript: (formData) => http.post('/system-tasks/upload-script', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000 }),
}

const lookup = {
  execute: (data) => http.post('/lookup/execute', data),
}

const profitShare = {
  execute: (data) => http.post('/profit-share/export', data),
  status: (taskId) => http.get(`/profit-share/status/${taskId}`),
  streamStatus: (taskId) => {
    const token = localStorage.getItem('token')
    const sep = token ? `?token=${encodeURIComponent(token)}` : ''
    return `/api/profit-share/stream/${taskId}${sep}`
  },
  cancel: (taskId) => http.post(`/profit-share/cancel/${taskId}`),
  databases: () => http.get('/profit-share/databases'),
}

const tickets = {
 list: (params) => http.get('/tickets', { params }),
 get: (id) => http.get(`/tickets/${id}`),
 create: (data) => http.post('/tickets', data),
 updateStatus: (id, data) => http.put(`/tickets/${id}/status`, data),
 updateDraft: (id, data) => http.put(`/tickets/${id}/draft`, data),
 submitDraft: (id) => http.post(`/tickets/${id}/submit`),
 addComment: (id, data) => http.post(`/tickets/${id}/comments`, data),
 delete: (id) => http.delete(`/tickets/${id}`),
 assignees: () => http.get('/tickets/assignees'),
 aiAgents: () => http.get('/tickets/ai-agents'),
 retryAi: (id) => http.post(`/tickets/${id}/retry-ai`),
 confirmAction: (id) => http.post(`/tickets/${id}/confirm-action`),
 cancelAction: (id) => http.post(`/tickets/${id}/cancel-action`),
 upload: (formData) => http.post('/tickets/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
 uploadAttachment: (formData) => http.post('/tickets/attachments/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
 deleteAttachment: (attId) => http.delete(`/tickets/attachments/${attId}`),
 stats: () => http.get('/tickets/stats'),
 analytics: (params) => http.get('/tickets/analytics', { params }),
}

const pay = {
  channels: () => http.get('/pay/channels'),
  listConfigs: () => http.get('/pay/configs'),
  getConfig: (id) => http.get(`/pay/configs/${id}`),
  createConfig: (data) => http.post('/pay/configs', data),
  updateConfig: (id, data) => http.put(`/pay/configs/${id}`, data),
  deleteConfig: (id) => http.delete(`/pay/configs/${id}`),
  sheets: (formData) => http.post('/pay/sheets', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  execute: (formData) => http.post('/pay/execute', formData, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600000 }),
}

const payFlow = {
  templates: (params) => http.get('/pay-flow/templates', { params }),
  getTemplate: (id) => http.get(`/pay-flow/templates/${id}`),
  createTemplate: (data) => http.post('/pay-flow/templates', data),
  updateTemplate: (id, data) => http.put(`/pay-flow/templates/${id}`, data),
  deleteTemplate: (id) => http.delete(`/pay-flow/templates/${id}`),
  nodeFields: () => http.get('/pay-flow/node-fields'),
  start: (data) => http.post('/pay-flow/start', data),
  executions: (params) => http.get('/pay-flow/executions', { params }),
  getExecution: (id) => http.get(`/pay-flow/executions/${id}`),
  cancelExecution: (id) => http.post(`/pay-flow/executions/${id}/cancel`),
  retryExecution: (id) => http.post(`/pay-flow/executions/${id}/retry`),
  deleteExecution: (id) => http.delete(`/pay-flow/executions/${id}`),
  batchDeleteExecutions: (ids) => http.post('/pay-flow/executions/batch-delete', { ids }),
  batches: (params) => http.get('/pay-flow/batches', { params }),
  batchSummary: (batchId) => http.get(`/pay-flow/batches/${batchId}/summary`),
  batchDetail: (batchId) => http.get(`/pay-flow/batches/${batchId}/detail`),
  retryBatch: (batchId) => http.post(`/pay-flow/batches/${batchId}/retry`),
  batchExecutions: (batchId, params) => http.get(`/pay-flow/batches/${batchId}/executions`, { params }),
  getNotifyTemplates: (params) => http.get('/pay-flow/notify-templates', { params }),
  getNotifyTemplate: (id) => http.get(`/pay-flow/notify-templates/${id}`),
  createNotifyTemplate: (data) => http.post('/pay-flow/notify-templates', data),
  updateNotifyTemplate: (id, data) => http.put(`/pay-flow/notify-templates/${id}`, data),
  deleteNotifyTemplate: (id) => http.delete(`/pay-flow/notify-templates/${id}`),
}

const mcp = {
  list: () => http.get('/mcp'),
  create: (data) => http.post('/mcp', data),
  update: (id, data) => http.put(`/mcp/${id}`, data),
  delete: (id) => http.delete(`/mcp/${id}`),
  batchDelete: (ids) => http.post('/mcp/batch-delete', { ids }),
  test: (id) => http.post(`/mcp/${id}/test`),
  refreshTools: (id) => http.post(`/mcp/${id}/refresh-tools`),
  importJson: (data) => http.post('/mcp/import', data),
  marketplace: () => http.get('/mcp/marketplace'),
}

const openApi = {
  getSettings: () => http.get('/open-api/settings'),
  saveSettings: (data) => http.put('/open-api/settings', data),
  listKeys: () => http.get('/open-api/keys'),
  createKey: (data) => http.post('/open-api/keys', data),
  updateKey: (id, data) => http.put(`/open-api/keys/${id}`, data),
  deleteKey: (id) => http.delete(`/open-api/keys/${id}`),
  regenerateKey: (id) => http.post(`/open-api/keys/${id}/regenerate`),
  revealKey: (id) => http.post(`/open-api/keys/${id}/reveal`),
  testKey: (id) => http.post(`/open-api/keys/${id}/test`),
  getLogs: (params) => http.get('/open-api/logs', { params }),
  getLogDetail: (id) => http.get(`/open-api/logs/${id}`),
  deleteLog: (id) => http.delete(`/open-api/logs/${id}`),
  deleteLogs: (params) => http.delete('/open-api/logs', { params }),
  getLogModels: () => http.get('/open-api/logs/models'),
  getSessionLogs: (params) => http.get('/open-api/logs/sessions', { params }),
  getStats: (params) => http.get('/open-api/stats', { params }),
}

const dataDashboard = {
  listScripts: () => http.get('/dashboard/scripts'),
  createScript: (data) => http.post('/dashboard/scripts', data),
  updateScript: (id, data) => http.put(`/dashboard/scripts/${id}`, data),
  deleteScript: (id) => http.delete(`/dashboard/scripts/${id}`),
  listQuickQueries: () => http.get('/dashboard/quick-queries'),
  createQuickQuery: (data) => http.post('/dashboard/quick-queries', data),
  updateQuickQuery: (id, data) => http.put(`/dashboard/quick-queries/${id}`, data),
  deleteQuickQuery: (id) => http.delete(`/dashboard/quick-queries/${id}`),
  listConnections: () => http.get('/dashboard/connections'),
  execute: (data) => http.post('/dashboard/execute', data),
  parseParams: (data) => http.post('/dashboard/parse-params', data),
  parseColumns: (data) => http.post('/dashboard/parse-columns', data),
  getMetaConfig: () => http.get('/dashboard/config'),
  getSettings: () => http.get('/dashboard/settings'),
  saveSettings: (data) => http.post('/dashboard/settings', data),
  clearCache: () => http.post('/dashboard/cache/clear'),
}

export default { auth, users, roles, ssh, databases, scripts, query, export: exportApi, autoExport, system, download, tasks, ai, agent, mcp, openApi, business, systemTask, lookup, profitShare, tickets, pay, payFlow, dataDashboard }
