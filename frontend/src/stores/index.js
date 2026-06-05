import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'
import router from '../router'

export const useAppStore = defineStore('app', () => {
  const databases = ref([])
  const scripts = ref([])
  const loading = ref(false)

  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  const theme = ref(localStorage.getItem('theme') || 'default')
  const themeUserSet = ref(localStorage.getItem('theme_user_set') === 'true')
  const taskVersion = ref(0)

  const isAuthenticated = computed(() => !!token.value)

  const isAdmin = computed(() => {
    if (!user.value) return false
    if (user.value.role?.is_admin) return true
    if (user.value.role?.button_permissions?.includes('all')) return true
    return false
  })

  function hasMenuPermission(menu) {
    if (!user.value) return false
    if (isAdmin.value) return true
    const perms = user.value.role?.menu_permissions || []
    return perms.includes(menu)
  }

  function hasButtonPermission(button) {
    if (!user.value) return false
    if (isAdmin.value) return true
    const perms = user.value.role?.button_permissions || []
    return perms.includes(button)
  }

  function getUserScriptIds() {
    if (!user.value) return []
    if (isAdmin.value) return []
    return user.value.script_ids || []
  }

  async function login(username, password) {
    const res = await api.auth.login({ username, password })
    if (res.success && res.data?.token) {
      token.value = res.data.token
      localStorage.setItem('token', res.data.token)
      if (res.data.user) {
        user.value = res.data.user
        applyGenderTheme(res.data.user.gender)
      } else {
        await fetchCurrentUser()
      }
      return true
    }
    return false
  }

  function logout() {
    token.value = ''
    user.value = null
    themeUserSet.value = false
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    localStorage.removeItem('theme_user_set')
    router.push('/login')
  }

  async function fetchCurrentUser() {
    try {
      const res = await api.auth.me()
      const data = res.data || res
      user.value = data
      applyGenderTheme(data.gender)
      return data
    } catch {
      logout()
      return null
    }
  }

  async function fetchDatabases() {
    loading.value = true
    try {
      const res = await api.databases.list()
      databases.value = res.data || res || []
    } catch {
      databases.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchScripts() {
    loading.value = true
    try {
      const res = await api.scripts.list()
      scripts.value = res.data || res || []
    } catch {
      scripts.value = []
    } finally {
      loading.value = false
    }
  }

  function setTheme(t) {
    theme.value = t
    themeUserSet.value = true
    localStorage.setItem('theme', t)
    localStorage.setItem('theme_user_set', 'true')
    document.documentElement.setAttribute('data-theme', t)
  }

  function applyGenderTheme(gender) {
    if (themeUserSet.value) return
    let defaultTheme = 'default'
    if (gender === 'female') {
      defaultTheme = 'pink'
    } else if (gender === 'male') {
      defaultTheme = 'orange'
    }
    theme.value = defaultTheme
    localStorage.setItem('theme', defaultTheme)
    document.documentElement.setAttribute('data-theme', defaultTheme)
  }

  function initTheme() {
    const saved = localStorage.getItem('theme') || 'default'
    theme.value = saved
    document.documentElement.setAttribute('data-theme', saved)
  }

  function notifyTaskChanged() {
    taskVersion.value++
  }

  function toastSuccess(msg) {
    ElMessage.success(msg)
  }

  function toastError(msg) {
    ElMessage.error(msg)
  }

  function toastWarning(msg) {
    ElMessage.warning(msg)
  }

  return {
    databases,
    scripts,
    loading,
    token,
    user,
    theme,
    taskVersion,
    isAuthenticated,
    isAdmin,
    hasMenuPermission,
    hasButtonPermission,
    getUserScriptIds,
    login,
    logout,
    fetchCurrentUser,
    fetchDatabases,
    fetchScripts,
    setTheme,
    initTheme,
    notifyTaskChanged,
    toastSuccess,
    toastError,
    toastWarning
  }
})
