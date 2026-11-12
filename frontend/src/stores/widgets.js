import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../api'

function normalizeConfig(raw) {
  const data = raw && typeof raw === 'object' ? raw : {}
  return {
    enabled: Array.isArray(data.enabled) ? [...data.enabled] : [],
    order: Array.isArray(data.order) ? [...data.order] : [],
    settings: data.settings && typeof data.settings === 'object' ? JSON.parse(JSON.stringify(data.settings)) : {},
    collapsed: !!data.collapsed,
  }
}

export const useWidgetsStore = defineStore('widgets', () => {
  const definitions = ref([])
  const config = ref(normalizeConfig({}))
  const loading = ref(false)
  const loaded = ref(false)

  /** 已启用且按用户排序的插件 key */
  const enabledKeys = computed(() => config.value.order.filter((key) => config.value.enabled.includes(key)))
  const hasWidgets = computed(() => enabledKeys.value.length > 0)

  function definitionFor(key) {
    return definitions.value.find((item) => item.key === key) || null
  }

  async function load(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    try {
      const res = await api.widgets.get()
      const data = res.data || res || {}
      definitions.value = data.definitions || []
      config.value = normalizeConfig(data.config)
      loaded.value = true
    } catch {
      definitions.value = []
    } finally {
      loading.value = false
    }
  }

  /** 保存完整配置（个人中心点保存时调用） */
  async function persist(patch = {}) {
    const payload = {
      enabled: config.value.enabled,
      order: config.value.order,
      settings: config.value.settings,
      collapsed: config.value.collapsed,
      ...patch,
    }
    const res = await api.widgets.saveConfig(payload)
    const data = res.data || res || {}
    config.value = normalizeConfig(data.config || payload)
    return config.value
  }

  /** 折叠状态即时保存（失败不打断交互） */
  function setCollapsed(collapsed) {
    config.value.collapsed = collapsed
    persist({ collapsed }).catch(() => {})
  }

  function applyConfig(next) {
    config.value = normalizeConfig(next)
  }

  return {
    definitions,
    config,
    loading,
    loaded,
    enabledKeys,
    hasWidgets,
    definitionFor,
    load,
    persist,
    setCollapsed,
    applyConfig,
  }
})
