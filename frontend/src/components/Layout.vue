<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="layout-aside">
      <div class="logo-area">
        <i class="fas fa-database logo-icon"></i>
        <span v-show="!isCollapsed" class="logo-text">综合运营管理系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="false"
        :unique-opened="true"
        router
        class="sidebar-menu"
        :background-color="sidebarBg"
        :text-color="sidebarText"
        :active-text-color="sidebarActive"
      >
        <template v-for="item in visibleMenu" :key="item.path || item.title">
          <!-- 单独一级菜单 -->
          <el-menu-item
            v-if="item.type === 'item' && store.hasMenuPermission(item.permission)"
            :index="item.path"
          >
            <i class="fas" :class="item.icon"></i>
            <template #title>{{ item.title }}</template>
          </el-menu-item>

          <!-- 分组菜单（二级） -->
          <el-sub-menu
            v-else-if="item.type === 'group' && hasVisibleChildren(item)"
            :index="item.title"
          >
            <template #title>
              <i class="fas" :class="item.icon"></i>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item
              v-for="child in item.children"
              v-show="child.visible !== false && store.hasMenuPermission(child.permission)"
              :key="child.path"
              :index="child.path"
            >
              <i class="fas" :class="child.icon"></i>
              <template #title>{{ child.title }}</template>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <button
            class="collapse-toggle"
            :class="{ 'is-collapsed': isCollapsed }"
            :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="toggleCollapse"
          >
            <i class="fas fa-angles-left"></i>
          </button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag :type="serverOnline ? 'success' : 'danger'" effect="dark" size="small">
            <i class="fas fa-circle" style="font-size: 8px; margin-right: 4px"></i>
            {{ serverOnline ? '服务正常' : '服务异常' }}
          </el-tag>
          <ThemeSwitch />
          <TaskBadge />
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-info">
              <el-avatar :size="30" class="user-avatar">
                <i class="fas fa-user"></i>
              </el-avatar>
              <span class="user-name">{{ displayName }}</span>
              <i class="fas fa-chevron-down user-arrow"></i>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="changePassword">
                  <i class="fas fa-key"></i> 修改密码
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <i class="fas fa-sign-out-alt"></i> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <TagsView />
      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>

    <el-dialog
      v-model="passwordDialogVisible"
      title="修改密码"
      width="460px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
        label-position="right"
      >
        <el-form-item label="当前密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSubmitting" @click="handleChangePassword">确定</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useAppStore } from '../stores'
import { useTaskMonitorStore } from '../stores/taskMonitor'
import { ElMessage } from 'element-plus'
import ThemeSwitch from './ThemeSwitch.vue'
import TagsView from './TagsView.vue'
import TaskBadge from './TaskBadge.vue'
import { titleMap } from '../config/menuConfig'

const route = useRoute()
const store = useAppStore()
const monitor = useTaskMonitorStore()
const isCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')
const serverOnline = ref(false)
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordFormRef = ref(null)

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('sidebar_collapsed', String(isCollapsed.value))
}

const activeMenu = computed(() => route.path)

const displayName = computed(() => {
  return store.user?.display_name || store.user?.username || ''
})

const currentTitle = computed(() => route.meta?.title || titleMap[route.path] || '仪表盘')

/** 仅展示 visible !== false 的顶层菜单项/分组 */
const visibleMenu = computed(() => {
  const cfg = store.menuConfig && store.menuConfig.length ? store.menuConfig : []
  return cfg.filter(item => item.visible !== false)
})

/** 检查分组中是否有有权限且可见的子菜单 */
function hasVisibleChildren(group) {
  if (!group.children) return false
  return group.children.some(child => child.visible !== false && store.hasMenuPermission(child.permission))
}

const sidebarBg = ref('#1d1e1f')
const sidebarText = ref('#bfcbd9')
const sidebarActive = ref('#409eff')

function updateSidebarColors() {
  const style = getComputedStyle(document.documentElement)
  sidebarBg.value = style.getPropertyValue('--sidebar-bg').trim() || '#1d1e1f'
  sidebarText.value = style.getPropertyValue('--sidebar-text').trim() || '#bfcbd9'
  sidebarActive.value = style.getPropertyValue('--sidebar-active').trim() || '#409eff'
}

watch(() => store.theme, () => {
  setTimeout(updateSidebarColors, 50)
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

function handleUserCommand(command) {
  if (command === 'changePassword') {
    Object.assign(passwordForm, { old_password: '', new_password: '', confirm_password: '' })
    passwordDialogVisible.value = true
  } else if (command === 'logout') {
    store.logout()
  }
}

async function handleChangePassword() {
  if (!passwordFormRef.value) return
  await passwordFormRef.value.validate()
  passwordSubmitting.value = true
  try {
    await api.auth.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })
    ElMessage.success('密码修改成功')
    passwordDialogVisible.value = false
  } catch {
  } finally {
    passwordSubmitting.value = false
  }
}

async function checkServer() {
  try {
    await api.query.dashboard()
    serverOnline.value = true
  } catch {
    serverOnline.value = false
  }
}

let serverTimer = null

onMounted(() => {
  store.initTheme()
  updateSidebarColors()
  checkServer()
  serverTimer = setInterval(checkServer, 30000)
  // 启动任务监控轮询
  monitor.start()
})

onUnmounted(() => {
  if (serverTimer) { clearInterval(serverTimer); serverTimer = null }
  monitor.stop()
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-aside {
  background-color: var(--sidebar-bg);
  overflow: hidden;
  transition: width 0.3s;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-icon {
  font-size: 24px;
  color: var(--logo-icon-color);
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  margin-left: 10px;
  white-space: nowrap;
}

.sidebar-menu {
  border-right: none;
  overflow-y: auto;
  overflow-x: hidden;
  height: calc(100vh - 60px);
}

.sidebar-menu .el-menu-item {
  height: 50px;
  line-height: 50px;
}

.sidebar-menu .el-menu-item i,
.sidebar-menu .el-sub-menu__title i {
  margin-right: 10px;
  font-size: 16px;
  width: 20px;
  text-align: center;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
  background: var(--header-bg);
  padding: 0 20px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  padding: 0;
  border: none;
  border-radius: 11px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 15px;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.collapse-toggle::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: var(--primary-color);
  opacity: 0;
  transform: scale(0.7);
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

.collapse-toggle > i {
  position: relative;
  z-index: 1;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.2s ease;
}

.collapse-toggle:hover {
  color: var(--primary-color);
  transform: translateY(-1px);
}

.collapse-toggle:hover::before {
  opacity: 0.1;
  transform: scale(1);
}

.collapse-toggle:active {
  transform: translateY(0) scale(0.94);
}

/* 折叠态：双箭头翻转朝右 + 主色柔光背景提示"菜单已隐藏" */
.collapse-toggle.is-collapsed {
  color: #fff;
}

.collapse-toggle.is-collapsed::before {
  opacity: 1;
  transform: scale(1);
}

.collapse-toggle.is-collapsed > i {
  transform: rotate(180deg);
}

.collapse-toggle.is-collapsed:hover {
  color: #fff;
  filter: brightness(1.08);
}

.collapse-toggle.is-collapsed:hover::before {
  opacity: 0.85;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
}

.user-info:hover {
  background: var(--primary-light);
}

.user-avatar {
  background: var(--user-avatar-bg);
  font-size: 14px;
}

.user-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.user-arrow {
  font-size: 12px;
  color: var(--text-muted);
}

.layout-main {
  background-color: var(--main-bg);
  padding: 20px;
  overflow-y: auto;
}
</style>
