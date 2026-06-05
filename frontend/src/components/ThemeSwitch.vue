<template>
  <el-dropdown trigger="click" @command="handleSelect">
    <div class="theme-switch" title="切换主题">
      <i class="fas fa-palette"></i>
    </div>
    <template #dropdown>
      <el-dropdown-menu class="theme-dropdown-menu">
        <div class="theme-group-label">色彩系</div>
        <el-dropdown-item
          v-for="t in colorThemes"
          :key="t.value"
          :command="t.value"
          :class="{ 'is-active': currentTheme === t.value }"
        >
          <span class="theme-option">
            <span class="theme-dot" :style="{ background: t.color }"></span>
            <span class="theme-label">{{ t.label }}</span>
            <i v-if="currentTheme === t.value" class="fas fa-check theme-check"></i>
          </span>
        </el-dropdown-item>
        <div class="theme-group-label">场景系</div>
        <el-dropdown-item
          v-for="t in sceneThemes"
          :key="t.value"
          :command="t.value"
          :class="{ 'is-active': currentTheme === t.value }"
        >
          <span class="theme-option">
            <span class="theme-dot" :style="{ background: t.color }"></span>
            <span class="theme-label">{{ t.label }}</span>
            <i v-if="currentTheme === t.value" class="fas fa-check theme-check"></i>
          </span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores'

const store = useAppStore()

const colorThemes = [
  { value: 'default', label: '默认蓝', color: '#409eff' },
  { value: 'pink', label: '粉色甜美', color: '#f472b6' },
  { value: 'orange', label: '阳光橙色', color: '#f97316' },
  { value: 'dark', label: '暗黑模式', color: '#818cf8' },
  { value: 'green', label: '豆绿养眼', color: '#22c55e' }
]

const sceneThemes = [
  { value: 'academy', label: '学院系', color: '#1d4ed8' },
  { value: 'nature', label: '户外风景系', color: '#0ea5e9' },
  { value: 'cyber', label: '赛博科技系', color: '#a855f7' },
  { value: 'office', label: '办公室系', color: '#475569' },
  { value: 'bedroom', label: '卧室系', color: '#d97706' },
  { value: 'study', label: '书房系', color: '#6b7280' }
]

const currentTheme = computed(() => store.theme)

function handleSelect(theme) {
  store.setTheme(theme)
}
</script>

<style scoped>
.theme-switch {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
  color: var(--text-secondary);
}

.theme-switch:hover {
  background: var(--primary-light);
  color: var(--primary-color);
}

.theme-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.theme-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
  border: 2px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.1);
}

.theme-label {
  flex: 1;
  font-size: 13px;
}

.theme-check {
  color: var(--primary-color);
  font-size: 12px;
}
</style>

<style>
.theme-group-label {
  padding: 6px 16px 2px;
  font-size: 11px;
  color: #909399;
  font-weight: 600;
  letter-spacing: 1px;
  user-select: none;
}
.theme-group-label:not(:first-child) {
  margin-top: 4px;
  border-top: 1px solid #ebeef5;
  padding-top: 8px;
}
</style>
