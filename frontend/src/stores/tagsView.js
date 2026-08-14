import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTagsViewStore = defineStore('tagsView', () => {
  // 已打开的标签列表: [{ path, title, name }]
  const visitedViews = ref([])

  /**
   * 添加标签（去重）
   */
  function addView(view) {
    if (!view || !view.path) return
    if (visitedViews.value.some(v => v.path === view.path)) return
    visitedViews.value.push({
      path: view.path,
      title: view.title || '未命名',
      name: view.name || '',
      affix: view.affix || false
    })
  }

  /**
   * 关闭指定标签，返回应跳转的目标路径（如果关闭的是当前激活标签）
   */
  function removeView(path) {
    const idx = visitedViews.value.findIndex(v => v.path === path)
    if (idx === -1) return null
    if (visitedViews.value[idx].affix) return null // 固定标签不可关闭

    visitedViews.value.splice(idx, 1)

    // 返回相邻标签路径
    if (visitedViews.value.length === 0) return '/'
    if (idx >= visitedViews.value.length) {
      return visitedViews.value[visitedViews.value.length - 1].path
    }
    return visitedViews.value[idx].path
  }

  /**
   * 关闭其他标签（保留固定标签和指定标签）
   */
  function removeOtherViews(path) {
    visitedViews.value = visitedViews.value.filter(
      v => v.affix || v.path === path
    )
  }

  /**
   * 关闭左侧标签（保留固定标签）
   */
  function removeLeftViews(path) {
    const idx = visitedViews.value.findIndex(v => v.path === path)
    if (idx === -1) return
    visitedViews.value = visitedViews.value.filter(
      (v, i) => v.affix || i >= idx
    )
  }

  /**
   * 关闭右侧标签（保留固定标签）
   */
  function removeRightViews(path) {
    const idx = visitedViews.value.findIndex(v => v.path === path)
    if (idx === -1) return
    visitedViews.value = visitedViews.value.filter(
      (v, i) => v.affix || i <= idx
    )
  }

  /**
   * 关闭全部标签（仅保留固定标签）
   */
  function removeAllViews() {
    const affixView = visitedViews.value.find(v => v.affix)
    visitedViews.value = affixView ? [affixView] : []
    return affixView ? affixView.path : '/'
  }

  return {
    visitedViews,
    addView,
    removeView,
    removeOtherViews,
    removeLeftViews,
    removeRightViews,
    removeAllViews
  }
})
