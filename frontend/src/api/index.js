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
  streamStatus: (taskId) => `/api/query/stream/${taskId}`,
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
  streamStatus: (taskId) => `/api/export/stream/${taskId}`,
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
}

const download = {
  file: (taskId) => `/api/download/${taskId}`
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
  getStrategy: () => http.get('/ai-strategy'),
  saveStrategy: (data) => http.post('/ai-strategy', data),
  deleteStrategy: () => http.delete('/ai-strategy'),
  resetStrategyTokens: () => http.post('/ai-strategy/reset-tokens'),
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
  streamExecution: (executionId) => `/api/system-tasks/executions/${executionId}/stream`,
}

const lookup = {
  execute: (data) => http.post('/lookup/execute', data),
}

export default { auth, users, roles, ssh, databases, scripts, query, export: exportApi, autoExport, system, download, ai, agent, business, systemTask, lookup }
