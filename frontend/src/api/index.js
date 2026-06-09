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
  setScripts: (id, data) => http.put(`/users/${id}/scripts`, data),
}

const roles = {
  list: () => http.get('/roles'),
  create: (data) => http.post('/roles', data),
  update: (id, data) => http.put(`/roles/${id}`, data),
  delete: (id) => http.delete(`/roles/${id}`),
}

const ssh = {
  list: () => http.get('/ssh'),
  get: (id) => http.get(`/ssh/${id}`),
  create: (data) => http.post('/ssh', data),
  update: (id, data) => http.put(`/ssh/${id}`, data),
  delete: (id) => http.delete(`/ssh/${id}`),
  test: (id) => http.post(`/ssh/${id}/test`)
}

const databases = {
  list: () => http.get('/databases'),
  get: (id) => http.get(`/databases/${id}`),
  create: (data) => http.post('/databases', data),
  update: (id, data) => http.put(`/databases/${id}`, data),
  delete: (id) => http.delete(`/databases/${id}`),
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
  tasks: (params) => http.get('/export/tasks', { params }),
}

const autoExport = {
  list: () => http.get('/auto-export'),
  create: (data) => http.post('/auto-export', data),
  update: (id, data) => http.put(`/auto-export/${id}`, data),
  delete: (id) => http.delete(`/auto-export/${id}`),
  toggle: (id) => http.post(`/auto-export/${id}/toggle`),
  runNow: (id) => http.post(`/auto-export/${id}/run-now`),
  paramOptions: () => http.get('/auto-export/param-options'),
}

const system = {
  getConfig: () => http.get('/system/config'),
  updateConfig: (data) => http.put('/system/config', data),
  testEmail: (data) => http.post('/system/test-email', data),
}

const download = {
  file: (taskId) => `/api/download/${taskId}`
}

const ai = {
  getConfigs: () => http.get('/ai/configs'),
  createConfig: (data) => http.post('/ai/configs', data),
  updateConfig: (id, data) => http.put(`/ai/configs/${id}`, data),
  deleteConfig: (id) => http.delete(`/ai/configs/${id}`),
  testConfig: (id) => http.post(`/ai/configs/${id}/test`),
  getSkills: (params) => http.get('/ai/skills', { params }),
  createSkill: (data) => http.post('/ai/skills', data),
  updateSkill: (id, data) => http.put(`/ai/skills/${id}`, data),
  deleteSkill: (id) => http.delete(`/ai/skills/${id}`),
  trackBehavior: (data) => http.post('/ai/behaviors', data),
  getBehaviors: (params) => http.get('/ai/behaviors', { params }),
  getChats: () => http.get('/ai/chats'),
  createChat: (data) => http.post('/ai/chats', data),
  deleteChat: (id) => http.delete(`/ai/chats/${id}`),
  getMessages: (chatId) => http.get(`/ai/chats/${chatId}/messages`),
  sendMessage: (chatId, data) => http.post(`/ai/chats/${chatId}/send`, data, { timeout: 180000 }),
  uploadFile: (formData) => http.post('/ai/upload-file', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  matchQuery: (data) => http.post('/ai/match-query', data),
}

const business = {
  listSystems: () => http.get('/business/systems'),
  listAllSystems: () => http.get('/business/systems/all'),
  createSystem: (data) => http.post('/business/systems', data),
  updateSystem: (id, data) => http.put(`/business/systems/${id}`, data),
  deleteSystem: (id) => http.delete(`/business/systems/${id}`),
  generateSsoUrl: (id, data) => http.post(`/business/systems/${id}/sso`, data),
  getCategories: () => http.get('/business/categories'),
}

export default { auth, users, roles, ssh, databases, scripts, query, export: exportApi, autoExport, system, download, ai, business }
