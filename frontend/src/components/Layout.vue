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
          <el-tooltip v-if="myTokens" effect="dark" placement="bottom">
            <template #content>
              <div class="token-tip">
                <div class="token-tip-title">我的Token消耗</div>
                <div>总消耗：{{ fmtNum(myTokens.total_tokens) }}</div>
                <div>AI对话：{{ fmtNum(myTokens.ai_chat_tokens) }}</div>
                <div>工单：{{ fmtNum(myTokens.ticket_tokens) }}</div>
                <div>今日：{{ fmtNum(myTokens.today_tokens) }}</div>
                <div>近30天：{{ fmtNum(myTokens.last_30d_tokens) }}</div>
              </div>
            </template>
            <el-tag
              :type="myTokens.total_tokens > 0 ? 'warning' : 'info'"
              effect="plain"
              size="small"
              class="token-tag"
              title="我的Token消耗"
              @click="goTokenStats"
            >
              <i class="fas fa-coins" style="font-size: 10px; margin-right: 4px"></i>
              {{ fmtCompact(myTokens.total_tokens) }}
            </el-tag>
          </el-tooltip>
          <ThemeSwitch />
          <TaskBadge />
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-info">
              <el-avatar :size="30" class="user-avatar" :src="avatarUrl" :fit="cover">
                <i class="fas fa-user"></i>
              </el-avatar>
              <span class="user-name">{{ displayName }}</span>
              <i class="fas fa-chevron-down user-arrow"></i>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <i class="fas fa-user-circle"></i> 个人中心
                </el-dropdown-item>
                <el-dropdown-item command="changePassword" divided>
                  <i class="fas fa-key"></i> 修改密码
                </el-dropdown-item>
                <el-dropdown-item command="logout">
                  <i class="fas fa-sign-out-alt"></i> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <TagsView />
      <el-container class="layout-body">
        <el-main class="layout-main">
          <router-view v-slot="{ Component }">
            <keep-alive>
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </el-main>
        <WidgetDock />
      </el-container>
      <el-footer class="layout-footer">
        <span>Copyright © 2026-{{ currentYear }} Power By XiaoBinger</span>
        <span class="footer-divider">|</span>
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">粤ICP备2026000000号</a>
      </el-footer>
    </el-container>

    <!-- AI宠物助手（个人中心可开关/换造型，默认开启）：点击弹出对话窗，可拖动 -->
    <AiPet v-if="petEnabled" :pet-style="petStyle" />

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

    <el-dialog
      v-model="profileDialogVisible"
      title="个人中心"
      width="560px"
      destroy-on-close
      :close-on-click-modal="false"
    >
      <el-form :model="profileForm" label-width="80px" label-position="right">
        <div v-if="myTokens" class="token-summary">
          <div class="token-summary-title"><i class="fas fa-coins"></i> Token消耗统计</div>
          <div class="token-summary-grid">
            <div class="token-summary-item">
              <div class="ts-label">总消耗</div>
              <div class="ts-value">{{ fmtCompact(myTokens.total_tokens) }}</div>
            </div>
            <div class="token-summary-item">
              <div class="ts-label">AI对话</div>
              <div class="ts-value chat">{{ fmtCompact(myTokens.ai_chat_tokens) }}</div>
            </div>
            <div class="token-summary-item">
              <div class="ts-label">工单</div>
              <div class="ts-value ticket">{{ fmtCompact(myTokens.ticket_tokens) }}</div>
            </div>
            <div class="token-summary-item">
              <div class="ts-label">近30天</div>
              <div class="ts-value recent">{{ fmtCompact(myTokens.last_30d_tokens) }}</div>
            </div>
          </div>
          <div class="token-summary-sub">
            今日 {{ fmtNum(myTokens.today_tokens) }} · 对话消息 {{ fmtNum(myTokens.chat_message_count) }} 条 · AI工单 {{ fmtNum(myTokens.ticket_count) }} 个
          </div>
        </div>
        <el-form-item label="头像">
          <div class="avatar-uploader">
            <el-avatar :size="80" :src="profileForm.avatarUrl" :fit="cover" class="profile-avatar">
              <i class="fas fa-user" style="font-size: 32px"></i>
            </el-avatar>
            <div class="avatar-actions">
              <el-upload
                :show-file-list="false"
                :before-upload="beforeAvatarUpload"
                :http-request="handleAvatarUpload"
                accept="image/*"
              >
                <el-button type="primary" size="small" :loading="avatarUploading">
                  <i class="fas fa-upload"></i> 上传头像
                </el-button>
              </el-upload>
              <el-button v-if="profileForm.avatarUrl" type="danger" size="small" text @click="handleDeleteAvatar">
                <i class="fas fa-trash"></i> 删除
              </el-button>
              <div class="avatar-tip">支持 JPG/PNG/GIF/WEBP，≤2MB</div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input :value="profileForm.username" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="profileForm.display_name" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="profileForm.gender">
            <el-radio value="male">男</el-radio>
            <el-radio value="female">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="profileForm.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="AI宠物">
          <div class="pet-setting">
            <el-switch v-model="profileForm.pet_enabled" active-text="开启" inactive-text="关闭" />
            <div class="pet-setting-tip">开启后右下角常驻可爱宠物：点击可弹出对话窗，并自动播报你提交给 AI 的工单处理进度</div>
            <div v-if="profileForm.pet_enabled" class="pet-style-picker">
              <div class="pet-style-label">选择造型</div>
              <div class="pet-style-grid">
                <button
                  v-for="opt in PET_OPTIONS"
                  :key="opt.key"
                  type="button"
                  class="pet-style-card"
                  :class="{ active: profileForm.pet_style === opt.key }"
                  :title="opt.name"
                  @click="profileForm.pet_style = opt.key"
                >
                  <div class="pet-style-preview">
                    <component :is="opt.component" />
                  </div>
                  <span class="pet-style-name">{{ opt.name }}</span>
                </button>
              </div>
            </div>
          </div>
        </el-form-item>

        <el-divider content-position="left">个性插件</el-divider>
        <el-form-item label="右侧插件栏">
          <div class="widget-setting">
            <div class="widget-setting-tip">管理员在「角色管理」授权后，可在这里勾选并排序右侧插件坞展示的插件</div>
            <div v-if="!widgetStore.definitions.length" class="widget-no-auth">
              <i class="fas fa-lock"></i> 暂无可用的个性插件，请联系管理员授权
            </div>
            <div v-else class="widget-config-list">
              <div v-for="(key, idx) in widgetForm.order" :key="key" class="widget-config-item">
                <div class="widget-config-head">
                  <span class="widget-config-name">
                    <i class="fas" :class="widgetIcon(key)"></i>
                    {{ widgetName(key) }}
                  </span>
                  <div class="widget-config-actions">
                    <el-button text size="small" :disabled="idx === 0" title="上移" @click="moveWidget(idx, -1)">
                      <i class="fas fa-arrow-up"></i>
                    </el-button>
                    <el-button text size="small" :disabled="idx === widgetForm.order.length - 1" title="下移" @click="moveWidget(idx, 1)">
                      <i class="fas fa-arrow-down"></i>
                    </el-button>
                    <el-switch
                      :model-value="isWidgetEnabled(key)"
                      size="small"
                      @change="(val) => toggleWidget(key, val)"
                    />
                  </div>
                </div>
                <div v-if="isWidgetEnabled(key)" class="widget-config-settings">
                  <template v-if="key === 'weather'">
                    <span class="widget-field-label">城市</span>
                    <el-input v-model="widgetForm.settings.weather.city" size="small" placeholder="如：深圳" style="max-width: 200px" />
                  </template>
                  <template v-else-if="key === 'news'">
                    <span class="widget-field-label">RSS 源</span>
                    <el-input v-model="widgetForm.settings.news.feed_url" size="small" placeholder="https://www.36kr.com/feed" />
                  </template>
                  <template v-else-if="key === 'stocks'">
                    <span class="widget-field-label">股票代码</span>
                    <el-input v-model="widgetForm.settings.stocks.symbols" size="small" placeholder="sh000001,sz399001" />
                  </template>
                  <template v-else-if="key === 'todo'">
                    <span class="widget-field-label">显示条数</span>
                    <el-input-number v-model="widgetForm.settings.todo.limit" size="small" :min="1" :max="20" />
                  </template>
                  <template v-else-if="key === 'sticker'">
                    <div class="widget-sticker-editor">
                      <el-input
                        v-model="widgetForm.settings.sticker.text"
                        type="textarea"
                        :rows="2"
                        placeholder="写一张便签，例如：今天要核对渠道对账"
                      />
                      <div class="widget-sticker-tools">
                        <el-color-picker v-model="widgetForm.settings.sticker.color" size="small" />
                        <el-upload
                          :show-file-list="false"
                          :before-upload="beforeStickerUpload"
                          :http-request="handleStickerUpload"
                          accept="image/*"
                        >
                          <el-button size="small" :loading="stickerUploading">
                            <i class="fas fa-upload"></i> 上传贴图
                          </el-button>
                        </el-upload>
                        <el-button
                          v-if="widgetForm.settings.sticker.image"
                          size="small"
                          text
                          type="danger"
                          @click="handleStickerDelete"
                        >删除贴图</el-button>
                      </div>
                      <img
                        v-if="widgetForm.settings.sticker.image"
                        :src="widgetForm.settings.sticker.image"
                        class="widget-sticker-preview"
                        alt="贴图预览"
                      />
                    </div>
                  </template>
                  <span v-else class="widget-field-hint">无需额外设置</span>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="profileSubmitting" @click="handleSaveProfile">保存</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useAppStore } from '../stores'
import { useTaskMonitorStore } from '../stores/taskMonitor'
import { ElMessage } from 'element-plus'
import ThemeSwitch from './ThemeSwitch.vue'
import TagsView from './TagsView.vue'
import TaskBadge from './TaskBadge.vue'
import AiPet from './AiPet.vue'
import WidgetDock from './widgets/WidgetDock.vue'
import { useWidgetsStore } from '../stores/widgets'
import RobotPet from './pets/RobotPet.vue'
import CatPet from './pets/CatPet.vue'
import BunnyPet from './pets/BunnyPet.vue'
import PandaPet from './pets/PandaPet.vue'
import BearPet from './pets/BearPet.vue'
import FoxPet from './pets/FoxPet.vue'
import PigPet from './pets/PigPet.vue'
import FrogPet from './pets/FrogPet.vue'
import KoalaPet from './pets/KoalaPet.vue'
import ChickPet from './pets/ChickPet.vue'
import { titleMap } from '../config/menuConfig'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const monitor = useTaskMonitorStore()
const widgetStore = useWidgetsStore()
const isCollapsed = ref(localStorage.getItem('sidebar_collapsed') === 'true')
const serverOnline = ref(false)
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordFormRef = ref(null)

const profileDialogVisible = ref(false)
const profileSubmitting = ref(false)
const avatarUploading = ref(false)
const stickerUploading = ref(false)
const profileForm = reactive({
  username: '',
  display_name: '',
  gender: 'male',
  phone: '',
  avatarUrl: '',
  pet_enabled: true,
  pet_style: 'robot',
})

/** 个人中心里的插件配置草稿（点保存后写回后端） */
const widgetForm = reactive({
  enabled: [],
  order: [],
  settings: {},
})

function resetWidgetForm() {
  const cfg = widgetStore.config
  widgetForm.enabled = [...cfg.enabled]
  widgetForm.order = [...cfg.order]
  widgetForm.settings = JSON.parse(JSON.stringify(cfg.settings || {}))
}

function widgetDefinition(key) {
  return widgetStore.definitionFor(key)
}

function widgetName(key) {
  return widgetDefinition(key)?.name || key
}

function widgetIcon(key) {
  return widgetDefinition(key)?.icon || 'fa-puzzle-piece'
}

function isWidgetEnabled(key) {
  return widgetForm.enabled.includes(key)
}

function toggleWidget(key, value) {
  if (value) {
    if (!widgetForm.enabled.includes(key)) widgetForm.enabled.push(key)
  } else {
    widgetForm.enabled = widgetForm.enabled.filter((item) => item !== key)
  }
}

function moveWidget(index, offset) {
  const target = index + offset
  if (target < 0 || target >= widgetForm.order.length) return
  const list = [...widgetForm.order]
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  widgetForm.order = list
}

function beforeStickerUpload(file) {
  const isImage = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'].includes(file.type)
  if (!isImage) {
    ElMessage.error('贴图仅支持 JPG/PNG/GIF/WEBP/BMP 格式')
    return false
  }
  if (file.size / 1024 / 1024 > 2) {
    ElMessage.error('贴图大小不能超过 2MB')
    return false
  }
  return true
}

async function handleStickerUpload({ file }) {
  stickerUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.widgets.uploadSticker(formData)
    const data = res.data || res || {}
    if (data.url) {
      widgetForm.settings.sticker = { ...(widgetForm.settings.sticker || {}), image: data.url }
      widgetStore.config.settings.sticker = { ...(widgetStore.config.settings.sticker || {}), image: data.url }
    }
    ElMessage.success('贴图已上传')
  } catch {
  } finally {
    stickerUploading.value = false
  }
}

async function handleStickerDelete() {
  try {
    const res = await api.widgets.deleteSticker()
    const data = res.data || res || {}
    widgetForm.settings.sticker = { ...(widgetForm.settings.sticker || {}), image: '' }
    if (data.config) {
      widgetStore.applyConfig(data.config)
      widgetForm.settings = JSON.parse(JSON.stringify(widgetStore.config.settings || {}))
    }
    ElMessage.success('贴图已删除')
  } catch {
  }
}

/** AI宠物可选造型（key 与后端 PET_STYLES 白名单一致） */
const PET_OPTIONS = [
  { key: 'robot', name: '小机器人', component: RobotPet },
  { key: 'cat', name: '喵喵', component: CatPet },
  { key: 'bunny', name: '兔兔', component: BunnyPet },
  { key: 'panda', name: '团团', component: PandaPet },
  { key: 'bear', name: '棕熊', component: BearPet },
  { key: 'fox', name: '狐狐', component: FoxPet },
  { key: 'pig', name: '猪猪', component: PigPet },
  { key: 'frog', name: '呱呱', component: FrogPet },
  { key: 'koala', name: '考拉', component: KoalaPet },
  { key: 'chick', name: '小鸡', component: ChickPet },
]

/** AI宠物是否展示（默认开启，个人中心可关闭） */
const petEnabled = computed(() => store.user?.pet_enabled !== false)

/** AI宠物当前造型（默认 robot） */
const petStyle = computed(() => store.user?.pet_style || 'robot')

/** 我的Token消耗指标（顶栏与个人中心展示） */
const myTokens = ref(null)

async function loadMyTokens() {
  try {
    const res = await api.tokenStats.my()
    myTokens.value = res.data || res
  } catch {
  }
}

function fmtNum(n) {
  return (n ?? 0).toLocaleString('zh-CN')
}

function fmtCompact(n) {
  n = n || 0
  if (n >= 100000000) return (n / 100000000).toFixed(2) + '亿'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString('zh-CN')
}

function goTokenStats() {
  if (store.hasMenuPermission('token_stats')) {
    router.push('/token-stats')
  }
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
  localStorage.setItem('sidebar_collapsed', String(isCollapsed.value))
}

const activeMenu = computed(() => route.path)
const currentYear = new Date().getFullYear()

const displayName = computed(() => {
  return store.user?.display_name || store.user?.username || ''
})

const avatarUrl = computed(() => {
  if (store.user?.avatar) {
    return `/api/auth/avatar/${store.user.avatar}`
  }
  return ''
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
  } else if (command === 'profile') {
    openProfileDialog()
  } else if (command === 'logout') {
    store.logout()
  }
}

async function openProfileDialog() {
  loadMyTokens()
  const u = store.user || {}
  Object.assign(profileForm, {
    username: u.username || '',
    display_name: u.display_name || '',
    gender: u.gender || 'male',
    phone: u.phone || '',
    avatarUrl: u.avatar ? `/api/auth/avatar/${u.avatar}` : '',
    pet_enabled: u.pet_enabled !== false,
    pet_style: u.pet_style || 'robot',
  })
  profileDialogVisible.value = true
  try {
    await widgetStore.load(true)
  } catch {
  }
  resetWidgetForm()
}

async function handleSaveProfile() {
  profileSubmitting.value = true
  try {
    const res = await api.auth.updateProfile({
      display_name: profileForm.display_name,
      gender: profileForm.gender,
      phone: profileForm.phone,
      pet_enabled: profileForm.pet_enabled,
      pet_style: profileForm.pet_style,
    })
    if (res.data) {
      store.user = { ...store.user, ...res.data }
    }
    if (widgetStore.definitions.length) {
      await widgetStore.persist({
        enabled: widgetForm.enabled,
        order: widgetForm.order,
        settings: widgetForm.settings,
      })
    }
    ElMessage.success('资料已更新')
    profileDialogVisible.value = false
  } catch {
  } finally {
    profileSubmitting.value = false
  }
}

function beforeAvatarUpload(file) {
  const isImage = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'].includes(file.type)
  const isLt2M = file.size / 1024 / 1024 < 2
  if (!isImage) {
    ElMessage.error('仅支持 JPG/PNG/GIF/WEBP/BMP 格式')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB')
    return false
  }
  return true
}

async function handleAvatarUpload({ file }) {
  avatarUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.auth.uploadAvatar(formData)
    if (res.data?.avatar) {
      const newUrl = `/api/auth/avatar/${res.data.avatar}?t=${Date.now()}`
      profileForm.avatarUrl = newUrl
      store.user = { ...store.user, avatar: res.data.avatar }
    }
    ElMessage.success('头像上传成功')
  } catch {
  } finally {
    avatarUploading.value = false
  }
}

async function handleDeleteAvatar() {
  try {
    await api.auth.deleteAvatar()
    profileForm.avatarUrl = ''
    if (store.user) {
      store.user = { ...store.user, avatar: null }
    }
    ElMessage.success('头像已删除')
  } catch {
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
  // 加载我的Token消耗指标
  loadMyTokens()
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

.token-tag {
  cursor: pointer;
}

.token-tag:hover {
  opacity: 0.85;
}

.token-tip {
  line-height: 1.8;
  font-size: 12px;
}

.token-tip-title {
  font-weight: 600;
  margin-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding-bottom: 4px;
}

.token-summary {
  margin-bottom: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--main-bg, #f5f7fa);
  border: 1px dashed var(--border-color, #e4e7ed);
}

.token-summary-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
  margin-bottom: 10px;
}

.token-summary-title i {
  color: #e6a23c;
  margin-right: 4px;
}

.token-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.token-summary-item {
  background: var(--card-bg, #fff);
  border-radius: 8px;
  padding: 10px 8px;
  text-align: center;
}

.ts-label {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}

.ts-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary, #303133);
  margin-top: 2px;
}

.ts-value.chat { color: #409eff; }
.ts-value.ticket { color: #67c23a; }
.ts-value.recent { color: #e6a23c; }

.token-summary-sub {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-muted, #c0c4cc);
  text-align: center;
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
  min-width: 0;
}

.layout-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.layout-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 36px;
  background-color: var(--header-bg, #fff);
  border-top: 1px solid var(--border-color, #e4e7ed);
  font-size: 12px;
  color: #909399;
  padding: 0 20px;
}

.layout-footer a {
  color: #909399;
  text-decoration: none;
  transition: color 0.2s;
}

.layout-footer a:hover {
  color: #409eff;
}

.footer-divider {
  color: #c0c4cc;
}

.avatar-uploader {
  display: flex;
  align-items: center;
  gap: 16px;
}

.profile-avatar {
  background: var(--user-avatar-bg);
  flex-shrink: 0;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.avatar-tip {
  color: #909399;
  font-size: 12px;
}

.pet-setting {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pet-setting-tip {
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
  max-width: 320px;
}

.pet-style-picker {
  margin-top: 10px;
}

.pet-style-label {
  color: #909399;
  font-size: 12px;
  margin-bottom: 8px;
}

.pet-style-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  max-width: 360px;
}

.pet-style-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 2px 5px;
  border: 1.5px solid var(--border-color, #e4e7ed);
  border-radius: 10px;
  background: var(--main-bg, #fff);
  cursor: pointer;
  transition: all 0.2s;
}

.pet-style-card:hover {
  border-color: #a8c8f8;
  transform: translateY(-1px);
}

.pet-style-card.active {
  border-color: #7ea6ee;
  background: rgba(126, 166, 238, 0.06);
  box-shadow: 0 0 0 2px rgba(126, 166, 238, 0.18);
}

.pet-style-card.active::after {
  content: '✓';
  position: absolute;
  top: -6px;
  right: -6px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #7ea6ee;
  color: #fff;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
}

.pet-style-preview {
  height: 60px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: hidden;
}

.pet-style-preview :deep(.creature) {
  transform: scale(0.6);
  transform-origin: bottom center;
}

.pet-style-name {
  font-size: 11px;
  color: var(--text-primary, #606266);
  white-space: nowrap;
}

.widget-setting {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.widget-setting-tip {
  color: var(--text-muted, #909399);
  font-size: 12px;
  line-height: 1.5;
}

.widget-no-auth {
  padding: 12px 14px;
  border: 1px dashed var(--border-color, #e4e7ed);
  border-radius: 8px;
  color: var(--text-muted, #909399);
  font-size: 12px;
}

.widget-config-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 4px;
}

.widget-config-item {
  border: 1px solid var(--border-color, #e4e7ed);
  border-radius: 10px;
  padding: 8px 10px;
  background: var(--main-bg, #f8fafc);
}

.widget-config-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.widget-config-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}

.widget-config-name i {
  width: 14px;
  text-align: center;
  color: var(--primary-color, #409eff);
}

.widget-config-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.widget-config-actions :deep(.el-button) {
  margin-left: 0;
  padding: 2px 4px;
}

.widget-config-settings {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color, #e4e7ed);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.widget-field-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-secondary, #606266);
}

.widget-field-hint {
  font-size: 12px;
  color: var(--text-muted, #909399);
}

.widget-sticker-editor {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.widget-sticker-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.widget-sticker-preview {
  max-width: 120px;
  max-height: 80px;
  border-radius: 6px;
  object-fit: contain;
  border: 1px solid var(--border-color, #e4e7ed);
}
</style>
