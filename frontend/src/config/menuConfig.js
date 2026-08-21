/**
 * 菜单配置
 *
 * 菜单项固定来源于 ALL_MENU_ITEMS，不可新增/删除
 * 管理员可通过"系统地图"调整分组归属、排序、可见性
 * 菜单配置存储在后端数据库，启动时动态加载
 */

// 所有可用菜单项（来源于系统路由，不可增删）
export const ALL_MENU_ITEMS = [
  { path: '/', title: '仪表盘', icon: 'fa-tachometer-alt', permission: 'dashboard', affix: true },
  { path: '/databases', title: '数据库管理', icon: 'fa-database', permission: 'databases' },
  { path: '/scripts', title: '脚本管理', icon: 'fa-clipboard-list', permission: 'scripts' },
  { path: '/query', title: '查询执行', icon: 'fa-play-circle', permission: 'query' },
  { path: '/history', title: '执行历史', icon: 'fa-history', permission: 'history' },
  { path: '/export-exec', title: '导出任务', icon: 'fa-download', permission: 'export_exec' },
  { path: '/profit-share', title: '分润导出', icon: 'fa-hand-holding-usd', permission: 'profit_share' },
  { path: '/auto-export', title: '自动导出', icon: 'fa-clock', permission: 'auto_export' },
  { path: '/ai-chat', title: 'AI 助手', icon: 'fa-robot', permission: 'ai_chat' },
  { path: '/ai-sessions', title: 'AI会话管理', icon: 'fa-comments', permission: 'ai_sessions' },
  { path: '/skills', title: 'Skills', icon: 'fa-brain', permission: 'skills' },
  { path: '/system', title: '系统配置', icon: 'fa-cog', permission: 'system' },
  { path: '/users', title: '用户管理', icon: 'fa-users', permission: 'users' },
  { path: '/roles', title: '角色管理', icon: 'fa-user-shield', permission: 'roles' },
  { path: '/agents', title: 'Agent 管理', icon: 'fa-robot', permission: 'agent_manager' },
  { path: '/mcp-servers', title: 'MCP 服务', icon: 'fa-plug', permission: 'mcp_servers' },
  { path: '/open-api', title: '开放API', icon: 'fa-key', permission: 'open_api' },
  { path: '/cache-stats', title: '缓存统计', icon: 'fa-bolt', permission: 'cache_stats' },
  { path: '/business', title: '业务系统', icon: 'fa-th-large', permission: 'business_systems' },
  { path: '/system-tasks', title: '系统任务', icon: 'fa-cogs', permission: 'system_tasks' },
  { path: '/tickets', title: '工单管理', icon: 'fa-ticket', permission: 'tickets' },
  { path: '/ticket-analytics', title: '工单统计', icon: 'fa-chart-bar', permission: 'ticket_analytics' },
  { path: '/system-map', title: '系统地图', icon: 'fa-sitemap', permission: 'system_map' },
]

// 默认菜单配置（含分组结构，首次加载时使用）
export const DEFAULT_MENU_CONFIG = [
  { type: 'item', path: '/', title: '仪表盘', icon: 'fa-tachometer-alt', permission: 'dashboard', affix: true, visible: true },
  { type: 'group', title: '数据管理', icon: 'fa-database', visible: true, children: [
    { path: '/databases', title: '数据库管理', icon: 'fa-database', permission: 'databases', visible: true },
    { path: '/scripts', title: '脚本管理', icon: 'fa-clipboard-list', permission: 'scripts', visible: true },
  ]},
  { type: 'group', title: '导出中心', icon: 'fa-download', visible: true, children: [
    { path: '/query', title: '查询执行', icon: 'fa-play-circle', permission: 'query', visible: true },
    { path: '/history', title: '执行历史', icon: 'fa-history', permission: 'history', visible: true },
    { path: '/export-exec', title: '导出任务', icon: 'fa-download', permission: 'export_exec', visible: true },
    { path: '/profit-share', title: '分润导出', icon: 'fa-hand-holding-usd', permission: 'profit_share', visible: true },
    { path: '/auto-export', title: '自动导出', icon: 'fa-clock', permission: 'auto_export', visible: true },
  ]},
  { type: 'group', title: 'AI 智能', icon: 'fa-robot', visible: true, children: [
    { path: '/ai-chat', title: 'AI 助手', icon: 'fa-robot', permission: 'ai_chat', visible: true },
    { path: '/ai-sessions', title: 'AI会话管理', icon: 'fa-comments', permission: 'ai_sessions', visible: true },
    { path: '/skills', title: 'Skills', icon: 'fa-brain', permission: 'skills', visible: true },
  ]},
  { type: 'group', title: '系统管理', icon: 'fa-cog', visible: true, children: [
    { path: '/system', title: '系统配置', icon: 'fa-cog', permission: 'system', visible: true },
    { path: '/users', title: '用户管理', icon: 'fa-users', permission: 'users', visible: true },
    { path: '/roles', title: '角色管理', icon: 'fa-user-shield', permission: 'roles', visible: true },
    { path: '/agents', title: 'Agent 管理', icon: 'fa-robot', permission: 'agent_manager', visible: true },
    { path: '/mcp-servers', title: 'MCP 服务', icon: 'fa-plug', permission: 'mcp_servers', visible: true },
    { path: '/open-api', title: '开放API', icon: 'fa-key', permission: 'open_api', visible: true },
    { path: '/cache-stats', title: '缓存统计', icon: 'fa-bolt', permission: 'cache_stats', visible: true },
    { path: '/business', title: '业务系统', icon: 'fa-th-large', permission: 'business_systems', visible: true },
    { path: '/system-tasks', title: '系统任务', icon: 'fa-cogs', permission: 'system_tasks', visible: true },
    { path: '/tickets', title: '工单管理', icon: 'fa-ticket', permission: 'tickets', visible: true },
    { path: '/ticket-analytics', title: '工单统计', icon: 'fa-chart-bar', permission: 'ticket_analytics', visible: true },
    { path: '/system-map', title: '系统地图', icon: 'fa-sitemap', permission: 'system_map', visible: true },
  ]},
]

// 路由路径 → 权限 key 映射（供路由守卫使用）
export const menuRouteMap = ALL_MENU_ITEMS.reduce((acc, item) => {
  acc[item.path] = item.permission
  return acc
}, {})

// 扁平化所有菜单项（用于路由守卫查找首个可访问菜单）
export const flatMenuItems = ALL_MENU_ITEMS.map(item => ({ path: item.path, menu: item.permission }))

// 路由路径 → 标题映射
export const titleMap = ALL_MENU_ITEMS.reduce((acc, item) => {
  acc[item.path] = item.title
  return acc
}, {})
