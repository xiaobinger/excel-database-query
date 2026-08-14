import { createRouter, createWebHistory } from 'vue-router'
import { menuRouteMap, flatMenuItems } from '../config/menuConfig'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { menu: 'dashboard', title: '仪表盘' } },
      { path: 'databases', name: 'Databases', component: () => import('../views/DatabaseManager.vue'), meta: { menu: 'databases', title: '数据库管理' } },
      { path: 'scripts', name: 'Scripts', component: () => import('../views/ScriptManager.vue'), meta: { menu: 'scripts', title: '脚本管理' } },
      { path: 'query', name: 'Query', component: () => import('../views/QueryExecutor.vue'), meta: { menu: 'query', title: '查询执行' } },
      { path: 'exports', name: 'ExportManager', component: () => import('../views/ExportManager.vue'), meta: { menu: 'exports', title: '导出管理' } },
      { path: 'export-exec', name: 'ExportExec', component: () => import('../views/ExportExecutor.vue'), meta: { menu: 'export_exec', title: '导出任务' } },
      { path: 'profit-share', name: 'ProfitShare', component: () => import('../views/ProfitShare.vue'), meta: { menu: 'profit_share', title: '分润导出' } },
      { path: 'auto-export', name: 'AutoExport', component: () => import('../views/AutoExportManager.vue'), meta: { menu: 'auto_export', title: '自动导出' } },
      { path: 'system', name: 'SystemConfig', component: () => import('../views/SystemConfig.vue'), meta: { menu: 'system', title: '系统配置' } },
      { path: 'history', name: 'History', component: () => import('../views/History.vue'), meta: { menu: 'history', title: '执行历史' } },
      { path: 'users', name: 'Users', component: () => import('../views/UserManager.vue'), meta: { menu: 'users', title: '用户管理' } },
      { path: 'roles', name: 'Roles', component: () => import('../views/RoleManager.vue'), meta: { menu: 'roles', title: '角色管理' } },
      { path: 'ai-chat', name: 'AiChat', component: () => import('../views/AiChat.vue'), meta: { menu: 'ai_chat', title: 'AI 助手' } },
      { path: 'ai-sessions', name: 'AiSessionManager', component: () => import('../views/AiSessionManager.vue'), meta: { menu: 'ai_sessions', title: 'AI会话管理' } },
      { path: 'skills', name: 'Skills', component: () => import('../views/SkillManager.vue'), meta: { menu: 'skills', title: 'Skills' } },
      { path: 'agents', name: 'Agents', component: () => import('../views/AgentManager.vue'), meta: { menu: 'agent_manager', title: 'Agent 管理' } },
      { path: 'cache-stats', name: 'CacheStats', component: () => import('../views/CacheManager.vue'), meta: { menu: 'cache_stats', title: '缓存统计' } },
      { path: 'business', name: 'BusinessSystems', component: () => import('../views/BusinessSystems.vue'), meta: { menu: 'business_systems', title: '业务系统' } },
      { path: 'system-tasks', name: 'SystemTasks', component: () => import('../views/SystemTaskManager.vue'), meta: { menu: 'system_tasks', title: '系统任务' } },
      { path: 'system-map', name: 'SystemMap', component: () => import('../views/SystemMap.vue'), meta: { menu: 'system_map', title: '系统地图' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.public) {
    if (token && to.path === '/login') {
      next('/')
      return
    }
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  const { useAppStore } = await import('../stores')
  const store = useAppStore()

  if (!store.user) {
    await store.fetchCurrentUser()
  }

  if (!store.user) {
    next('/login')
    return
  }

  const menu = to.meta.menu || menuRouteMap[to.path]
  if (menu && !store.hasMenuPermission(menu)) {
    const firstAllowed = flatMenuItems.find(r => store.hasMenuPermission(r.menu))
    if (firstAllowed) {
      next(firstAllowed.path)
    } else {
      store.logout()
      next('/login')
    }
    return
  }

  next()
})

export default router
