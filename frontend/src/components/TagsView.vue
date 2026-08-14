<template>
  <div class="tags-view-container">
    <div class="tags-view-wrapper" ref="scrollContainer" @wheel.prevent="handleScroll">
      <div
        v-for="tag in tagsStore.visitedViews"
        :key="tag.path"
        class="tags-view-item"
        :class="{ active: isActive(tag) }"
        @click="clickTag(tag)"
        @contextmenu.prevent="openContextMenu($event, tag)"
      >
        <span class="tag-dot" v-if="isActive(tag)"></span>
        <span class="tag-title">{{ tag.title }}</span>
        <i
          v-if="!tag.affix"
          class="fas fa-times tag-close"
          @click.stop="closeTag(tag)"
        ></i>
      </div>
    </div>

    <!-- 右键菜单 -->
    <ul
      v-show="contextMenu.visible"
      class="context-menu"
      :style="{ left: contextMenu.left + 'px', top: contextMenu.top + 'px' }"
    >
      <li v-if="!contextMenu.tag?.affix" @click="closeTag(contextMenu.tag)">
        <i class="fas fa-times"></i> 关闭
      </li>
      <li @click="closeOthers">
        <i class="fas fa-window-restore"></i> 关闭其他
      </li>
      <li @click="closeLeft">
        <i class="fas fa-angle-left"></i> 关闭左侧
      </li>
      <li @click="closeRight">
        <i class="fas fa-angle-right"></i> 关闭右侧
      </li>
      <li @click="closeAll">
        <i class="fas fa-window-close"></i> 关闭全部
      </li>
    </ul>
  </div>
</template>

<script setup>
import { reactive, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTagsViewStore } from '../stores/tagsView'

const route = useRoute()
const router = useRouter()
const tagsStore = useTagsViewStore()

const scrollContainer = ref(null)

const contextMenu = reactive({
  visible: false,
  left: 0,
  top: 0,
  tag: null
})

function isActive(tag) {
  return tag.path === route.path
}

function addCurrentView() {
  tagsStore.addView({
    path: route.path,
    title: route.meta?.title || route.name || '未命名',
    name: route.name,
    affix: route.path === '/'
  })
}

function clickTag(tag) {
  if (tag.path !== route.path) {
    router.push(tag.path)
  }
}

function closeTag(tag) {
  if (!tag || tag.affix) return
  const wasActive = isActive(tag)
  tagsStore.removeView(tag.path)
  if (wasActive) {
    // 关闭的是当前激活标签，跳转到相邻标签
    const last = tagsStore.visitedViews[tagsStore.visitedViews.length - 1]
    router.push(last ? last.path : '/')
  }
  closeContextMenu()
}

function closeOthers() {
  tagsStore.removeOtherViews(contextMenu.tag?.path || route.path)
  if (contextMenu.tag && contextMenu.tag.path !== route.path) {
    router.push(contextMenu.tag.path)
  }
  closeContextMenu()
}

function closeLeft() {
  tagsStore.removeLeftViews(contextMenu.tag?.path || route.path)
  closeContextMenu()
}

function closeRight() {
  const targetPath = contextMenu.tag?.path || route.path
  tagsStore.removeRightViews(targetPath)
  // 如果当前标签在右侧被关闭了，跳转到目标标签
  const stillExists = tagsStore.visitedViews.some(v => v.path === route.path)
  if (!stillExists) {
    router.push(targetPath)
  }
  closeContextMenu()
}

function closeAll() {
  const target = tagsStore.removeAllViews()
  router.push(target)
  closeContextMenu()
}

function openContextMenu(e, tag) {
  contextMenu.visible = true
  contextMenu.left = e.clientX
  contextMenu.top = e.clientY
  contextMenu.tag = tag
}

function closeContextMenu() {
  contextMenu.visible = false
  contextMenu.tag = null
}

function handleClickOutside() {
  closeContextMenu()
}

function handleScroll(e) {
  const wrapper = scrollContainer.value
  if (!wrapper) return
  wrapper.scrollLeft += e.deltaY
}

/**
 * 滚动到当前激活标签，确保可见
 */
function scrollToActiveTag() {
  nextTick(() => {
    const wrapper = scrollContainer.value
    if (!wrapper) return
    const activeEl = wrapper.querySelector('.tags-view-item.active')
    if (!activeEl) return
    const wrapperRect = wrapper.getBoundingClientRect()
    const activeRect = activeEl.getBoundingClientRect()
    if (activeRect.left < wrapperRect.left) {
      wrapper.scrollLeft -= wrapperRect.left - activeRect.left + 4
    } else if (activeRect.right > wrapperRect.right) {
      wrapper.scrollLeft += activeRect.right - wrapperRect.right + 4
    }
  })
}

watch(() => route.path, () => {
  addCurrentView()
  scrollToActiveTag()
})

onMounted(() => {
  addCurrentView()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.tags-view-container {
  position: relative;
  background: var(--header-bg);
  border-bottom: 1px solid var(--border-color);
  height: 38px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  user-select: none;
}

.tags-view-wrapper {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  scroll-behavior: smooth;
  flex: 1;
}

.tags-view-wrapper::-webkit-scrollbar {
  height: 0;
}

.tags-view-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--card-bg);
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.tags-view-item:hover {
  color: var(--primary-color);
  border-color: var(--primary-color);
}

.tags-view-item.active {
  color: #fff;
  background: var(--primary-color);
  border-color: var(--primary-color);
}

.tag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
  display: inline-block;
}

.tag-title {
  line-height: 1;
}

.tag-close {
  font-size: 10px;
  margin-left: 2px;
  padding: 2px;
  border-radius: 50%;
  transition: all 0.15s;
}

.tag-close:hover {
  background: rgba(0, 0, 0, 0.25);
  color: #fff;
}

.context-menu {
  position: fixed;
  z-index: 9999;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  margin: 0;
  list-style: none;
  min-width: 140px;
}

.context-menu li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.15s;
}

.context-menu li:hover {
  background: var(--primary-light);
  color: var(--primary-color);
}

.context-menu li i {
  font-size: 12px;
  width: 14px;
  text-align: center;
}
</style>
