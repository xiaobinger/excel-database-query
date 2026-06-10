<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="layout-aside">
      <div class="logo-area">
        <i class="fas fa-database logo-icon"></i>
        <span v-show="!isCollapsed" class="logo-text">Excel查询工具</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu"
        :background-color="sidebarBg"
        :text-color="sidebarText"
        :active-text-color="sidebarActive"
      >
        <el-menu-item v-if="store.hasMenuPermission('dashboard')" index="/">
          <i class="fas fa-tachometer-alt"></i>
          <template #title>仪表盘</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('databases')" index="/databases">
          <i class="fas fa-database"></i>
          <template #title>数据库管理</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('scripts')" index="/scripts">
          <i class="fas fa-clipboard-list"></i>
          <template #title>查询选项</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('query')" index="/query">
          <i class="fas fa-play-circle"></i>
          <template #title>查询执行</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('exports')" index="/exports">
          <i class="fas fa-file-export"></i>
          <template #title>导出选项</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('export_exec')" index="/export-exec">
          <i class="fas fa-download"></i>
          <template #title>导出任务</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('auto_export')" index="/auto-export">
          <i class="fas fa-clock"></i>
          <template #title>自动导出</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('system')" index="/system">
          <i class="fas fa-cog"></i>
          <template #title>系统配置</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('history')" index="/history">
          <i class="fas fa-history"></i>
          <template #title>执行历史</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('users')" index="/users">
          <i class="fas fa-users"></i>
          <template #title>用户管理</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('roles')" index="/roles">
          <i class="fas fa-user-shield"></i>
          <template #title>角色管理</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('ai_chat')" index="/ai-chat">
          <i class="fas fa-robot"></i>
          <template #title>AI 助手</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('ai_sessions')" index="/ai-sessions">
          <i class="fas fa-comments"></i>
          <template #title>AI会话管理</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('skills')" index="/skills">
          <i class="fas fa-brain"></i>
          <template #title>Skills</template>
        </el-menu-item>
        <el-menu-item v-if="store.hasMenuPermission('business_systems')" index="/business">
          <i class="fas fa-th-large"></i>
          <template #title>业务系统</template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-button
            :icon="isCollapsed ? 'Expand' : 'Fold'"
            text
            @click="isCollapsed = !isCollapsed"
          />
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
      <el-main class="layout-main">
        <router-view />
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
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useAppStore } from '../stores'
import { ElMessage } from 'element-plus'
import ThemeSwitch from './ThemeSwitch.vue'

const route = useRoute()
const store = useAppStore()
const isCollapsed = ref(false)
const serverOnline = ref(false)
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordFormRef = ref(null)

const activeMenu = computed(() => route.path)

const displayName = computed(() => {
  return store.user?.display_name || store.user?.username || ''
})

const titleMap = {
  '/': '仪表盘',
  '/databases': '数据库管理',
  '/scripts': '查询选项',
  '/query': '查询执行',
  '/exports': '导出选项',
  '/export-exec': '导出任务',
  '/auto-export': '自动导出',
  '/system': '系统配置',
  '/history': '执行历史',
  '/users': '用户管理',
  '/roles': '角色管理',
  '/ai-chat': 'AI 助手',
  '/ai-sessions': 'AI会话管理',
  '/skills': 'Skills',
  '/business': '业务系统'
}

const currentTitle = computed(() => titleMap[route.path] || '仪表盘')

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

onMounted(() => {
  store.initTheme()
  updateSidebarColors()
  checkServer()
  setInterval(checkServer, 30000)
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
}

.sidebar-menu .el-menu-item {
  height: 50px;
  line-height: 50px;
}

.sidebar-menu .el-menu-item i {
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
