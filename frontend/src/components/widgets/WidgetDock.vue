<template>
  <aside v-if="store.hasWidgets" class="widget-dock" :class="{ collapsed: collapsed }">
    <div class="dock-head">
      <span v-if="!collapsed" class="dock-title">
        <i class="fas fa-wand-magic-sparkles"></i>
        个性插件
      </span>
      <button class="dock-toggle" :title="collapsed ? '展开插件栏' : '收起插件栏'" @click="toggle">
        <i class="fas" :class="collapsed ? 'fa-angles-left' : 'fa-angles-right'"></i>
      </button>
    </div>

    <div v-if="!collapsed" class="dock-body">
      <component
        :is="componentFor(key)"
        v-for="key in store.enabledKeys"
        :key="key"
        :settings="settingsFor(key)"
      />
    </div>

    <div v-else class="dock-icons">
      <button
        v-for="key in store.enabledKeys"
        :key="key"
        class="dock-icon"
        :title="nameFor(key)"
        @click="toggle"
      >
        <i class="fas" :class="iconFor(key)"></i>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useWidgetsStore } from '../../stores/widgets'
import { widgetComponent } from '../../config/widgetRegistry'

const store = useWidgetsStore()
const collapsed = computed(() => store.config.collapsed)

function componentFor(key) {
  return widgetComponent(key)
}

function settingsFor(key) {
  return store.config.settings[key] || {}
}

function nameFor(key) {
  return store.definitionFor(key)?.name || key
}

function iconFor(key) {
  return store.definitionFor(key)?.icon || 'fa-puzzle-piece'
}

function toggle() {
  store.setCollapsed(!collapsed.value)
}

onMounted(() => {
  // 每次进入主框架都重新拉取，确保权限变更或切换账号后不会展示未授权插件
  store.load(true)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

function handleVisibilityChange() {
  // 从其他标签页/窗口切回时重新校验权限，管理员撤销授权后无需刷新页面
  if (document.visibilityState === 'visible') {
    store.load(true)
  }
}
</script>

<style scoped>
.widget-dock {
  width: 300px;
  flex-shrink: 0;
  height: 100%;
  padding: 20px 16px 20px 0;
  box-sizing: border-box;
  overflow-y: auto;
  transition: width 0.25s;
}

.widget-dock.collapsed {
  width: 52px;
  padding-right: 8px;
}

.dock-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 12px;
  padding-left: 2px;
}

.widget-dock.collapsed .dock-head {
  justify-content: center;
  padding-left: 0;
}

.dock-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #606266);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.dock-title i {
  color: var(--primary-color, #409eff);
}

.dock-toggle {
  border: none;
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e4e7ed);
  color: var(--text-muted, #909399);
  width: 26px;
  height: 26px;
  border-radius: 8px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
  font-size: 11px;
}

.dock-toggle:hover {
  color: var(--primary-color, #409eff);
  border-color: var(--primary-color, #409eff);
}

.dock-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dock-icons {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.dock-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid var(--border-color, #e4e7ed);
  background: var(--card-bg, #fff);
  color: var(--text-secondary, #606266);
  cursor: pointer;
  transition: all 0.2s;
}

.dock-icon:hover {
  color: var(--primary-color, #409eff);
  border-color: var(--primary-color, #409eff);
}

@media (max-width: 1180px) {
  .widget-dock {
    display: none;
  }
}
</style>
