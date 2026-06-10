import { createRouter, createWebHistory } from 'vue-router'

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
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { menu: 'dashboard' } },
      { path: 'databases', name: 'Databases', component: () => import('../views/DatabaseManager.vue'), meta: { menu: 'databases' } },
      { path: 'scripts', name: 'Scripts', component: () => import('../views/ScriptManager.vue'), meta: { menu: 'scripts' } },
      { path: 'query', name: 'Query', component: () => import('../views/QueryExecutor.vue'), meta: { menu: 'query' } },
      { path: 'exports', name: 'ExportManager', component: () => import('../views/ExportManager.vue'), meta: { menu: 'exports' } },
      { path: 'export-exec', name: 'ExportExec', component: () => import('../views/ExportExecutor.vue'), meta: { menu: 'export_exec' } },
      { path: 'auto-export', name: 'AutoExport', component: () => import('../views/AutoExportManager.vue'), meta: { menu: 'auto_export' } },
      { path: 'system', name: 'SystemConfig', component: () => import('../views/SystemConfig.vue'), meta: { menu: 'system' } },
      { path: 'history', name: 'History', component: () => import('../views/History.vue'), meta: { menu: 'history' } },
      { path: 'users', name: 'Users', component: () => import('../views/UserManager.vue'), meta: { menu: 'users' } },
      { path: 'roles', name: 'Roles', component: () => import('../views/RoleManager.vue'), meta: { menu: 'roles' } },
      { path: 'ai-chat', name: 'AiChat', component: () => import('../views/AiChat.vue'), meta: { menu: 'ai_chat' } },
      { path: 'ai-sessions', name: 'AiSessionManager', component: () => import('../views/AiSessionManager.vue'), meta: { menu: 'ai_sessions' } },
      { path: 'skills', name: 'Skills', component: () => import('../views/SkillManager.vue'), meta: { menu: 'skills' } },
      { path: 'business', name: 'BusinessSystems', component: () => import('../views/BusinessSystems.vue'), meta: { menu: 'business_systems' } }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const menuRouteMap = {
  '/': 'dashboard',
  '/databases': 'databases',
  '/scripts': 'scripts',
  '/query': 'query',
  '/exports': 'exports',
  '/export-exec': 'export_exec',
  '/auto-export': 'auto_export',
  '/system': 'system',
  '/history': 'history',
  '/users': 'users',
  '/roles': 'roles',
  '/ai-chat': 'ai_chat',
  '/ai-sessions': 'ai_sessions',
  '/skills': 'skills',
  '/business': 'business_systems'
}

const menuRoutes = [
  { path: '/', menu: 'dashboard' },
  { path: '/databases', menu: 'databases' },
  { path: '/scripts', menu: 'scripts' },
  { path: '/query', menu: 'query' },
  { path: '/exports', menu: 'exports' },
  { path: '/export-exec', menu: 'export_exec' },
  { path: '/auto-export', menu: 'auto_export' },
  { path: '/system', menu: 'system' },
  { path: '/history', menu: 'history' },
  { path: '/users', menu: 'users' },
  { path: '/roles', menu: 'roles' },
  { path: '/ai-chat', menu: 'ai_chat' },
  { path: '/ai-sessions', menu: 'ai_sessions' },
  { path: '/skills', menu: 'skills' },
  { path: '/business', menu: 'business_systems' }
]

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
    const firstAllowed = menuRoutes.find(r => store.hasMenuPermission(r.menu))
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
