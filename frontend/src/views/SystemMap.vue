<template>
  <div class="system-map">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-sitemap"></i> 系统地图</span>
          <div class="header-actions">
            <el-button @click="handleReset" :disabled="saving">
              <i class="fas fa-undo"></i> 恢复默认
            </el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">
              <i class="fas fa-save"></i> 保存配置
            </el-button>
          </div>
        </div>
      </template>

      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
        <template #title>
          拖拽菜单项可在分组间移动或调整顺序；拖拽分组可调整一级顺序；切换"可见"控制是否在侧边栏展示；新建/编辑分组时可选择图标。
        </template>
      </el-alert>

      <!-- 顶层结构 -->
      <div
        class="top-list"
        :class="{ 'is-dragging': !!dragPayload }"
        @dragover.prevent="onDragOverTopEnd"
        @drop="onDropTopEnd"
      >
        <div
          v-for="(node, idx) in editingConfig"
          :key="nodeKey(node, idx)"
          class="top-node"
          :class="{
            'drag-over': dragOverKey === 'top-' + idx,
            'is-group': node.type === 'group',
            'is-hidden': node.visible === false
          }"
          draggable="true"
          @dragstart="onDragStart($event, node.type === 'group' ? { kind: 'group', groupIndex: idx } : { kind: 'top', path: node.path })"
          @dragend="onDragEnd"
          @dragover.prevent="onDragOver('top-' + idx)"
          @dragleave="onDragLeave('top-' + idx)"
          @drop.stop="onDropTop(idx, $event)"
        >
          <!-- 顶层独立菜单项 -->
          <div v-if="node.type === 'item'" class="node-row">
            <i class="fas fa-grip-vertical drag-handle"></i>
            <i class="fas menu-icon" :class="node.icon"></i>
            <span class="node-title">{{ node.title }}</span>
            <el-tag size="small" type="info" effect="plain">一级菜单</el-tag>
            <div class="row-actions">
              <span class="vis-label">可见</span>
              <el-switch v-model="node.visible" size="small" />
              <el-button text size="small" @click="moveTopToUnplaced(idx)">
                <i class="fas fa-arrow-down"></i> 移出
              </el-button>
            </div>
          </div>

          <!-- 分组 -->
          <div v-else class="group-block">
            <div class="group-header">
              <i class="fas fa-grip-vertical drag-handle"></i>
              <i class="fas menu-icon" :class="node.icon"></i>
              <span class="node-title">{{ node.title }}</span>
              <el-tag size="small" type="warning" effect="plain">分组</el-tag>
              <div class="row-actions">
                <span class="vis-label">可见</span>
                <el-switch v-model="node.visible" size="small" />
                <el-button text size="small" @click="editGroup(idx)">
                  <i class="fas fa-pen"></i> 编辑
                </el-button>
                <el-button text size="small" type="danger" @click="deleteGroup(idx)">
                  <i class="fas fa-trash"></i> 删除分组
                </el-button>
              </div>
            </div>
            <div class="group-children">
              <div
                v-for="(child, cIdx) in node.children"
                :key="child.path"
                class="node-row child"
                :class="{
                  'drag-over': dragOverKey === 'child-' + idx + '-' + cIdx,
                  'is-hidden': child.visible === false
                }"
                draggable="true"
                @dragstart.stop="onDragStart($event, { kind: 'group-child', path: child.path, groupIndex: idx })"
                @dragend="onDragEnd"
                @dragover.prevent.stop="onDragOver('child-' + idx + '-' + cIdx)"
                @dragleave="onDragLeave('child-' + idx + '-' + cIdx)"
                @drop.stop="onDropChild(idx, cIdx, $event)"
              >
                <i class="fas fa-grip-vertical drag-handle"></i>
                <i class="fas menu-icon" :class="child.icon"></i>
                <span class="node-title">{{ child.title }}</span>
                <div class="row-actions">
                  <span class="vis-label">可见</span>
                  <el-switch v-model="child.visible" size="small" />
                  <el-button text size="small" @click="moveChildToUnplaced(idx, cIdx)">
                    <i class="fas fa-arrow-down"></i> 移出
                  </el-button>
                </div>
              </div>
              <div
                v-if="!node.children || node.children.length === 0"
                class="empty-children"
                @dragover.prevent.stop="onDragOver('child-end-' + idx)"
                @dragleave="onDragLeave('child-end-' + idx)"
                @drop.stop="onDropChildEnd(idx, $event)"
              >
                拖拽菜单项到此处放入分组
              </div>
              <div
                v-else
                class="dropzone-end"
                :class="{ 'drag-over': dragOverKey === 'child-end-' + idx }"
                @dragover.prevent.stop="onDragOver('child-end-' + idx)"
                @dragleave="onDragLeave('child-end-' + idx)"
                @drop.stop="onDropChildEnd(idx, $event)"
              >
                + 放到末尾
              </div>
            </div>
          </div>
        </div>

        <div
          class="dropzone-top-end"
          :class="{ 'drag-over': dragOverKey === 'top-end' }"
          @dragover.prevent="onDragOver('top-end')"
          @dragleave="onDragLeave('top-end')"
          @drop.stop="onDropTopEnd"
        >
          <el-button text @click="addGroup">
            <i class="fas fa-plus"></i> 新建分组
          </el-button>
        </div>
      </div>

      <!-- 未放置菜单池 -->
      <el-divider content-position="left">
        <i class="fas fa-inbox"></i> 未放置菜单（不显示在侧边栏）
      </el-divider>
      <div
        class="unplaced-list"
        :class="{
          'drag-over': dragOverKey === 'unplaced',
          'is-empty': unplacedItems.length === 0
        }"
        @dragover.prevent="onDragOver('unplaced')"
        @dragleave="onDragLeave('unplaced')"
        @drop.stop="onDropUnplaced"
      >
        <div
          v-for="item in unplacedItems"
          :key="item.path"
          class="node-row unplaced"
          draggable="true"
          @dragstart="onDragStart($event, { kind: 'unplaced', path: item.path })"
          @dragend="onDragEnd"
        >
          <i class="fas fa-grip-vertical drag-handle"></i>
          <i class="fas menu-icon" :class="item.icon"></i>
          <span class="node-title">{{ item.title }}</span>
          <el-tag size="small" type="info">未放置</el-tag>
        </div>
        <div v-if="unplacedItems.length === 0" class="empty-unplaced">
          所有菜单均已放置
        </div>
      </div>
    </el-card>

    <!-- 新建/编辑分组对话框 -->
    <el-dialog
      v-model="groupDialog.visible"
      :title="groupDialog.mode === 'create' ? '新建分组' : '编辑分组'"
      width="500px"
      append-to-body
    >
      <el-form label-width="80px" @submit.prevent>
        <el-form-item label="分组名称">
          <el-input v-model="groupDialog.title" placeholder="请输入分组名称" maxlength="20" />
        </el-form-item>
        <el-form-item label="分组图标">
          <div class="icon-grid">
            <button
              v-for="ic in GROUP_ICONS"
              :key="ic"
              type="button"
              class="icon-cell"
              :class="{ active: groupDialog.icon === ic }"
              :title="ic"
              @click="groupDialog.icon = ic"
            >
              <i class="fas" :class="ic"></i>
            </button>
          </div>
        </el-form-item>
        <el-form-item label="预览">
          <span class="group-preview">
            <i class="fas" :class="groupDialog.icon"></i>
            {{ groupDialog.title || '分组名称' }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="confirmGroupDialog">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useAppStore } from '../stores'
import { ALL_MENU_ITEMS, DEFAULT_MENU_CONFIG } from '../config/menuConfig'

const store = useAppStore()

/** 深拷贝一份进行编辑，保存时再提交 */
const editingConfig = ref([])
const unplacedItems = ref([])
const saving = ref(false)

/** 当前拖拽负载 */
const dragPayload = ref(null)
const dragOverKey = ref('')

function nodeKey(node, idx) {
  return node.type === 'group' ? 'g-' + idx + '-' + node.title : 'i-' + node.path
}

function findItemMeta(path) {
  return ALL_MENU_ITEMS.find(m => m.path === path)
}

function cloneDefault() {
  return JSON.parse(JSON.stringify(DEFAULT_MENU_CONFIG))
}

/** 计算未放置菜单 */
function recomputeUnplaced() {
  const placed = new Set()
  editingConfig.value.forEach(n => {
    if (n.type === 'item') placed.add(n.path)
    else if (n.type === 'group' && Array.isArray(n.children)) n.children.forEach(c => placed.add(c.path))
  })
  unplacedItems.value = ALL_MENU_ITEMS.filter(m => !placed.has(m.path)).map(m => ({ ...m }))
}

/** 加载远程配置 */
async function loadConfig() {
  try {
    const res = await api.system.getMenuConfig()
    const cfg = res.data || res || []
    editingConfig.value = (cfg && cfg.length) ? JSON.parse(JSON.stringify(cfg)) : cloneDefault()
    // 规整 visible 字段（兼容旧数据）
    editingConfig.value.forEach(n => {
      if (n.visible === undefined) n.visible = true
      if (n.type === 'group' && Array.isArray(n.children)) {
        n.children.forEach(c => { if (c.visible === undefined) c.visible = true })
      }
    })
    recomputeUnplaced()
  } catch {
    editingConfig.value = cloneDefault()
    recomputeUnplaced()
  }
}

// ── 拖拽事件 ─────────────────────────────────────────────

function onDragStart(e, payload) {
  dragPayload.value = payload
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', JSON.stringify(payload)) } catch (_) {}
  }
}

function onDragEnd() {
  dragPayload.value = null
  dragOverKey.value = ''
}

function onDragOver(key) {
  dragOverKey.value = key
}

function onDragLeave(key) {
  if (dragOverKey.value === key) dragOverKey.value = ''
}

function onDragOverTopEnd(e) {
  // 顶层末尾区由具体子元素处理，这里仅防止默认
  if (dragOverKey.value === '') dragOverKey.value = 'top-end'
}

/** 从原位置弹出，返回原节点对象（保留 visible 状态） */
function popItem(payload) {
  if (payload.kind === 'top') {
    const idx = editingConfig.value.findIndex(n => n.type === 'item' && n.path === payload.path)
    if (idx >= 0) return editingConfig.value.splice(idx, 1)[0]
  } else if (payload.kind === 'group-child') {
    const g = editingConfig.value[payload.groupIndex]
    if (g && Array.isArray(g.children)) {
      const idx = g.children.findIndex(c => c.path === payload.path)
      if (idx >= 0) return g.children.splice(idx, 1)[0]
    }
  } else if (payload.kind === 'unplaced') {
    const idx = unplacedItems.value.findIndex(i => i.path === payload.path)
    if (idx >= 0) return unplacedItems.value.splice(idx, 1)[0]
  }
  return null
}

function normalizeAsTop(popped, path) {
  const meta = findItemMeta(path) || {}
  return {
    type: 'item',
    path: popped.path || meta.path,
    title: popped.title || meta.title,
    icon: popped.icon || meta.icon,
    permission: popped.permission || meta.permission,
    visible: popped.visible !== undefined ? popped.visible : true
  }
}

function normalizeAsChild(popped, path) {
  const meta = findItemMeta(path) || {}
  return {
    path: popped.path || meta.path,
    title: popped.title || meta.title,
    icon: popped.icon || meta.icon,
    permission: popped.permission || meta.permission,
    visible: popped.visible !== undefined ? popped.visible : true
  }
}

/** 顶层位置放置（插入到 idx 之前） */
function onDropTop(idx, e) {
  e.preventDefault()
  const p = dragPayload.value
  dragOverKey.value = ''
  if (!p) return

  if (p.kind === 'group') {
    const fromIdx = p.groupIndex
    if (fromIdx === idx) return
    const [grp] = editingConfig.value.splice(fromIdx, 1)
    const adjusted = fromIdx < idx ? idx - 1 : idx
    editingConfig.value.splice(adjusted, 0, grp)
    dragPayload.value = null
    return
  }

  const fromTopIdx = p.kind === 'top'
    ? editingConfig.value.findIndex(n => n.type === 'item' && n.path === p.path)
    : -1
  const popped = popItem(p)
  if (!popped) { dragPayload.value = null; return }
  const newItem = normalizeAsTop(popped, p.path)
  let adjusted = idx
  if (fromTopIdx >= 0 && fromTopIdx < idx) adjusted = idx - 1
  editingConfig.value.splice(adjusted, 0, newItem)
  recomputeUnplaced()
  dragPayload.value = null
}

/** 顶层末尾放置 */
function onDropTopEnd(e) {
  e.preventDefault()
  const p = dragPayload.value
  dragOverKey.value = ''
  if (!p) return
  if (p.kind === 'group') {
    const fromIdx = p.groupIndex
    const [grp] = editingConfig.value.splice(fromIdx, 1)
    editingConfig.value.push(grp)
    dragPayload.value = null
    return
  }
  const popped = popItem(p)
  if (!popped) { dragPayload.value = null; return }
  const newItem = normalizeAsTop(popped, p.path)
  editingConfig.value.push(newItem)
  recomputeUnplaced()
  dragPayload.value = null
}

/** 分组内子项位置放置（插入到 cIdx 之前） */
function onDropChild(groupIdx, cIdx, e) {
  e.preventDefault()
  const p = dragPayload.value
  dragOverKey.value = ''
  if (!p || p.kind === 'group') return

  const fromGroupIdx = p.kind === 'group-child' ? p.groupIndex : -1
  const fromChildIdx = p.kind === 'group-child'
    ? (editingConfig.value[p.groupIndex]?.children?.findIndex(c => c.path === p.path) ?? -1)
    : -1
  const popped = popItem(p)
  if (!popped) { dragPayload.value = null; return }
  const newChild = normalizeAsChild(popped, p.path)
  let target = cIdx
  if (fromGroupIdx === groupIdx && fromChildIdx >= 0 && fromChildIdx < cIdx) target = cIdx - 1
  const grp = editingConfig.value[groupIdx]
  if (!grp) { dragPayload.value = null; return }
  if (!Array.isArray(grp.children)) grp.children = []
  grp.children.splice(target, 0, newChild)
  recomputeUnplaced()
  dragPayload.value = null
}

/** 分组末尾放置 */
function onDropChildEnd(groupIdx, e) {
  e.preventDefault()
  const p = dragPayload.value
  dragOverKey.value = ''
  if (!p || p.kind === 'group') return
  const popped = popItem(p)
  if (!popped) { dragPayload.value = null; return }
  const newChild = normalizeAsChild(popped, p.path)
  const grp = editingConfig.value[groupIdx]
  if (!grp) { dragPayload.value = null; return }
  if (!Array.isArray(grp.children)) grp.children = []
  grp.children.push(newChild)
  recomputeUnplaced()
  dragPayload.value = null
}

/** 未放置区放置 */
function onDropUnplaced(e) {
  e.preventDefault()
  const p = dragPayload.value
  dragOverKey.value = ''
  if (!p || p.kind === 'group') return
  popItem(p)
  recomputeUnplaced()
  dragPayload.value = null
}

// ── 操作按钮 ─────────────────────────────────────────────

// 常用分组图标（Font Awesome 6 Free Solid）
const GROUP_ICONS = [
  'fa-folder', 'fa-folder-open', 'fa-folder-tree', 'fa-layer-group', 'fa-sitemap', 'fa-cubes', 'fa-box', 'fa-boxes-stacked',
  'fa-tags', 'fa-star', 'fa-bookmark', 'fa-book', 'fa-graduation-cap', 'fa-briefcase', 'fa-building', 'fa-industry',
  'fa-house', 'fa-city', 'fa-shop', 'fa-cart-shopping', 'fa-truck', 'fa-wallet', 'fa-money-bill-wave', 'fa-credit-card',
  'fa-coins', 'fa-chart-line', 'fa-chart-bar', 'fa-chart-pie', 'fa-gauge', 'fa-list-check', 'fa-clipboard-list', 'fa-file-lines',
  'fa-database', 'fa-server', 'fa-cloud', 'fa-terminal', 'fa-code', 'fa-bug', 'fa-wrench', 'fa-screwdriver-wrench',
  'fa-gears', 'fa-plug', 'fa-key', 'fa-shield-halved', 'fa-users', 'fa-user-gear', 'fa-robot', 'fa-brain',
  'fa-comments', 'fa-envelope', 'fa-bell', 'fa-calendar', 'fa-clock', 'fa-history', 'fa-search', 'fa-route',
  'fa-compass', 'fa-globe', 'fa-tower-broadcast', 'fa-inbox', 'fa-lightbulb', 'fa-bolt', 'fa-headset', 'fa-handshake',
]

// 新建/编辑分组对话框
const groupDialog = reactive({
  visible: false,
  mode: 'create', // create | edit
  editIndex: -1,
  title: '',
  icon: 'fa-folder',
})

function addGroup() {
  groupDialog.mode = 'create'
  groupDialog.editIndex = -1
  groupDialog.title = ''
  groupDialog.icon = 'fa-folder'
  groupDialog.visible = true
}

function editGroup(idx) {
  const grp = editingConfig.value[idx]
  if (!grp) return
  groupDialog.mode = 'edit'
  groupDialog.editIndex = idx
  groupDialog.title = grp.title
  groupDialog.icon = grp.icon || 'fa-folder'
  groupDialog.visible = true
}

function confirmGroupDialog() {
  const title = groupDialog.title.trim()
  if (!title) {
    ElMessage.warning('分组名称不能为空')
    return
  }
  if (groupDialog.mode === 'create') {
    editingConfig.value.push({
      type: 'group',
      title,
      icon: groupDialog.icon,
      visible: true,
      children: []
    })
    ElMessage.success('分组已添加，记得拖拽菜单项进入并保存')
  } else {
    const grp = editingConfig.value[groupDialog.editIndex]
    if (grp) {
      grp.title = title
      grp.icon = groupDialog.icon
    }
  }
  groupDialog.visible = false
}

function deleteGroup(idx) {
  ElMessageBox.confirm('删除分组后，组内菜单将移至"未放置"。确认删除？', '提示', {
    type: 'warning'
  }).then(() => {
    const grp = editingConfig.value[idx]
    if (grp && Array.isArray(grp.children)) {
      // children 移到未放置
      grp.children.forEach(c => unplacedItems.value.push({ ...c }))
    }
    editingConfig.value.splice(idx, 1)
    recomputeUnplaced()
  }).catch(() => {})
}

function moveTopToUnplaced(idx) {
  const node = editingConfig.value[idx]
  if (!node) return
  editingConfig.value.splice(idx, 1)
  recomputeUnplaced()
}

function moveChildToUnplaced(groupIdx, childIdx) {
  const grp = editingConfig.value[groupIdx]
  if (!grp || !grp.children) return
  grp.children.splice(childIdx, 1)
  recomputeUnplaced()
}

function handleReset() {
  ElMessageBox.confirm('恢复为默认菜单配置？未保存的修改将丢失。', '提示', {
    type: 'warning'
  }).then(() => {
    editingConfig.value = cloneDefault()
    recomputeUnplaced()
    ElMessage.success('已恢复默认配置（未保存）')
  }).catch(() => {})
}

async function handleSave() {
  // 校验：确保所有 ALL_MENU_ITEMS 都在配置中
  const placed = new Set()
  editingConfig.value.forEach(n => {
    if (n.type === 'item') placed.add(n.path)
    else if (n.type === 'group' && Array.isArray(n.children)) n.children.forEach(c => placed.add(c.path))
  })
  const missing = ALL_MENU_ITEMS.filter(m => !placed.has(m.path) && !unplacedItems.value.find(u => u.path === m.path))
  if (missing.length) {
    ElMessage.warning(`存在菜单项未处理: ${missing.map(m => m.title).join('、')}，请放入未放置区或某分组`)
    return
  }

  saving.value = true
  try {
    // 提交前过滤空分组（无 children 的分组保留以保留结构）
    const payload = editingConfig.value.map(n => {
      if (n.type === 'group') {
        return {
          type: 'group',
          title: n.title,
          icon: n.icon || 'fa-folder',
          visible: n.visible !== false,
          children: (n.children || []).map(c => ({
            path: c.path,
            title: c.title,
            icon: c.icon,
            permission: c.permission,
            visible: c.visible !== false
          }))
        }
      }
      return {
        type: 'item',
        path: n.path,
        title: n.title,
        icon: n.icon,
        permission: n.permission,
        affix: n.affix || false,
        visible: n.visible !== false
      }
    })
    await api.system.saveMenuConfig(payload)
    // 同步刷新 store（从后端重新拉取，确保所有页面一致）
    await store.fetchMenuConfig()
    ElMessage.success('菜单配置已保存')
  } catch (e) {
    // 拦截器已弹错误提示
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.system-map {
  max-width: 1000px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.top-list {
  border: 1px dashed var(--border-color);
  border-radius: 6px;
  padding: 8px;
  min-height: 80px;
  background: var(--card-bg, #fff);
  transition: background 0.2s;
}

.top-list.is-dragging {
  background: var(--primary-light, rgba(64, 158, 255, 0.05));
}

.top-node {
  border: 1px solid var(--border-color);
  border-radius: 6px;
  margin-bottom: 8px;
  background: var(--bg-color, #fff);
  transition: all 0.2s;
}

.top-node.drag-over {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.25);
}

.top-node.is-group {
  background: var(--fill-color-light, #fafafa);
}

.top-node.is-hidden {
  opacity: 0.55;
}

.node-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: move;
  border-radius: 4px;
}

.node-row.child {
  padding-left: 36px;
  border: 1px dashed transparent;
  margin: 2px 8px;
}

.node-row.child:hover {
  background: var(--primary-light, rgba(64, 158, 255, 0.06));
}

.node-row.child.drag-over {
  border-color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.08);
}

.node-row.unplaced {
  cursor: grab;
}

.drag-handle {
  color: var(--text-muted, #999);
  font-size: 14px;
}

.menu-icon {
  color: var(--el-color-primary);
  width: 18px;
  text-align: center;
}

.node-title {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vis-label {
  font-size: 12px;
  color: var(--text-muted, #999);
}

.group-block {
  padding: 4px 0;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
  cursor: move;
}

.group-children {
  padding: 6px 0;
}

.empty-children {
  padding: 14px;
  margin: 4px 8px;
  text-align: center;
  color: var(--text-muted, #999);
  font-size: 12px;
  border: 1px dashed var(--border-color);
  border-radius: 4px;
}

.dropzone-end {
  margin: 4px 8px;
  padding: 4px 10px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted, #999);
  border: 1px dashed transparent;
  border-radius: 4px;
  transition: all 0.2s;
}

.dropzone-end.drag-over {
  border-color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.08);
  color: var(--el-color-primary);
}

.dropzone-top-end {
  margin-top: 4px;
  padding: 6px;
  text-align: center;
  border: 1px dashed var(--border-color);
  border-radius: 4px;
  transition: all 0.2s;
}

.dropzone-top-end.drag-over {
  border-color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.08);
}

.unplaced-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px;
  border: 1px dashed var(--border-color);
  border-radius: 6px;
  min-height: 60px;
  transition: all 0.2s;
}

.unplaced-list.drag-over {
  border-color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.06);
}

.unplaced-list.is-empty {
  align-items: center;
  justify-content: center;
}

.unplaced-list .node-row {
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-color, #fff);
  flex: 0 0 auto;
}

.empty-unplaced {
  color: var(--text-muted, #999);
  font-size: 12px;
}

/* 分组图标选择器 */
.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 6px;
  width: 100%;
  max-height: 220px;
  overflow-y: auto;
  padding: 2px;
}

.icon-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 34px;
  padding: 0;
  font-size: 15px;
  color: var(--text-color, #606266);
  background: var(--bg-color, #fff);
  border: 1px solid var(--border-color, #dcdfe6);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.icon-cell:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.icon-cell.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary);
  color: #fff;
}

.group-preview {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-color, #606266);
}
</style>
