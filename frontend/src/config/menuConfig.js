/**
 * 菜单配置（一级/二级分组结构）
 *
 * type: 'item' 单独一级菜单 | 'group' 分组菜单（含 children）
 * permission: 权限 key，对应 role.menu_permissions
 * path: 路由路径
 * affix: 是否固定标签（不可关闭），仪表盘为 true
 */

// 路由路径 → 菜单权限 key 映射（供路由守卫使用）
export const menuRouteMap = {
  '/': 'dashboard',
  '/databases': 'databases',
  '/scripts': 'scripts',
  '/query': 'query',
  '/export-exec': 'export_exec',
  '/profit-share': 'profit_share',
  '/auto-export': 'auto_export',
  '/system': 'system',
  '/history': 'history',
  '/users': 'users',
  '/roles': 'roles',
  '/ai-chat': 'ai_chat',
  '/ai-sessions': 'ai_sessions',
  '/skills': 'skills',
  '/agents': 'agent_manager',
  '/cache-stats': 'cache_stats',
  '/business': 'business_systems',
  '/system-tasks': 'system_tasks'
}

export const menuConfig = [
  {
    type: 'item',
    path: '/',
    title: '仪表盘',
    icon: 'fa-tachometer-alt',
    permission: 'dashboard',
    affix: true
  },
  {
    type: 'group',
    title: '数据管理',
    icon: 'fa-database',
    children: [
      { path: '/databases', title: '数据库管理', icon: 'fa-database', permission: 'databases' },
      { path: '/scripts', title: '脚本管理', icon: 'fa-clipboard-list', permission: 'scripts' },
      { path: '/query', title: '查询执行', icon: 'fa-play-circle', permission: 'query' },
      { path: '/history', title: '执行历史', icon: 'fa-history', permission: 'history' }
    ]
  },
  {
    type: 'group',
    title: '导出中心',
    icon: 'fa-download',
    children: [
      { path: '/export-exec', title: '导出任务', icon: 'fa-download', permission: 'export_exec' },
      { path: '/profit-share', title: '分润导出', icon: 'fa-hand-holding-usd', permission: 'profit_share' },
      { path: '/auto-export', title: '自动导出', icon: 'fa-clock', permission: 'auto_export' }
    ]
  },
  {
    type: 'group',
    title: 'AI 智能',
    icon: 'fa-robot',
    children: [
      { path: '/ai-chat', title: 'AI 助手', icon: 'fa-robot', permission: 'ai_chat' },
      { path: '/ai-sessions', title: 'AI会话管理', icon: 'fa-comments', permission: 'ai_sessions' },
      { path: '/skills', title: 'Skills', icon: 'fa-brain', permission: 'skills' }
    ]
  },
  {
    type: 'group',
    title: '系统管理',
    icon: 'fa-cog',
    children: [
      { path: '/system', title: '系统配置', icon: 'fa-cog', permission: 'system' },
      { path: '/users', title: '用户管理', icon: 'fa-users', permission: 'users' },
      { path: '/roles', title: '角色管理', icon: 'fa-user-shield', permission: 'roles' },
      { path: '/agents', title: 'Agent 管理', icon: 'fa-robot', permission: 'agent_manager' },
      { path: '/cache-stats', title: '缓存统计', icon: 'fa-bolt', permission: 'cache_stats' },
      { path: '/business', title: '业务系统', icon: 'fa-th-large', permission: 'business_systems' },
      { path: '/system-tasks', title: '系统任务', icon: 'fa-cogs', permission: 'system_tasks' }
    ]
  }
]

/**
 * 扁平化所有菜单项（用于路由守卫查找首个可访问菜单）
 */
export const flatMenuItems = menuConfig.reduce((acc, group) => {
  if (group.type === 'item') {
    acc.push({ path: group.path, menu: group.permission })
  } else if (group.children) {
    group.children.forEach(child => {
      acc.push({ path: child.path, menu: child.permission })
    })
  }
  return acc
}, [])

/**
 * 路由路径 → 标题映射
 */
export const titleMap = flatMenuItems.reduce((acc, item) => {
  acc[item.path] = item.title
  return acc
}, {})
