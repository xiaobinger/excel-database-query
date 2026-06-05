<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <i class="fas fa-database login-logo"></i>
          <h1 class="login-title">Excel查询工具</h1>
          <p class="login-subtitle">请登录您的账号</p>
        </div>
        <el-form ref="formRef" :model="form" :rules="rules" @keyup.enter="handleLogin">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="用户名"
              size="large"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              size="large"
              show-password
              :prefix-icon="Lock"
            />
          </el-form-item>
          <el-form-item>
            <div class="captcha-wrapper">
              <div class="captcha-track" ref="captchaTrackRef">
                <div class="captcha-progress" :style="{ width: captchaOffset + 'px' }"></div>
                <div class="captcha-text" v-if="!captchaVerified && captchaOffset === 0">拖动滑块完成验证</div>
                <div class="captcha-text" v-else-if="captchaVerified" style="color: #67c23a">
                  <i class="fas fa-check-circle"></i> 验证通过
                </div>
                <div
                  v-if="!captchaVerified"
                  class="captcha-slider"
                  :class="{ dragging: isDragging }"
                  :style="{ left: captchaOffset + 'px' }"
                  @mousedown="onDragStart"
                  @touchstart.prevent="onDragStart"
                >
                  <i class="fas fa-angle-double-right" v-if="captchaOffset === 0"></i>
                  <i class="fas fa-arrow-right" v-else></i>
                </div>
              </div>
            </div>
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              :disabled="!captchaVerified"
              class="login-btn"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const store = useAppStore()
const formRef = ref(null)
const loading = ref(false)
const captchaTrackRef = ref(null)
const captchaOffset = ref(0)
const captchaVerified = ref(false)
const isDragging = ref(false)
const dragStartX = ref(0)
const maxOffset = ref(0)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

function onDragStart(e) {
  if (captchaVerified.value) return
  isDragging.value = true
  const clientX = e.touches ? e.touches[0].clientX : e.clientX
  dragStartX.value = clientX - captchaOffset.value
  if (captchaTrackRef.value) {
    maxOffset.value = captchaTrackRef.value.offsetWidth - 44
  }
}

function onDragMove(e) {
  if (!isDragging.value || captchaVerified.value) return
  const clientX = e.touches ? e.touches[0].clientX : e.clientX
  let offset = clientX - dragStartX.value
  offset = Math.max(0, Math.min(offset, maxOffset.value))
  captchaOffset.value = offset
}

function onDragEnd() {
  if (!isDragging.value || captchaVerified.value) return
  isDragging.value = false
  if (captchaOffset.value >= maxOffset.value - 5) {
    captchaOffset.value = maxOffset.value
    captchaVerified.value = true
  } else {
    captchaOffset.value = 0
  }
}

async function handleLogin() {
  if (!formRef.value) return
  await formRef.value.validate()
  if (!captchaVerified.value) {
    ElMessage.warning('请先完成滑块验证')
    return
  }
  loading.value = true
  try {
    const success = await store.login(form.username, form.password)
    if (success) {
      ElMessage.success('登录成功')
      if (store.hasMenuPermission('dashboard')) {
        router.push('/')
      } else {
        const firstMenu = ['query', 'history', 'scripts', 'databases', 'users', 'roles']
          .find(m => store.hasMenuPermission(m))
        router.push(firstMenu ? `/${firstMenu}` : '/')
      }
    } else {
      ElMessage.error('登录失败，请检查用户名和密码')
      resetCaptcha()
    }
  } catch {
    ElMessage.error('登录失败，请检查用户名和密码')
    resetCaptcha()
  } finally {
    loading.value = false
  }
}

function resetCaptcha() {
  captchaVerified.value = false
  captchaOffset.value = 0
}

onMounted(() => {
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  document.addEventListener('touchmove', onDragMove, { passive: false })
  document.addEventListener('touchend', onDragEnd)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.removeEventListener('touchmove', onDragMove)
  document.removeEventListener('touchend', onDragEnd)
})
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--sidebar-bg, #1d1e1f) 0%, #2d3a4a 50%, #1a2332 100%);
  position: relative;
  overflow: hidden;
}

.login-page::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at 30% 50%, rgba(64, 158, 255, 0.08) 0%, transparent 50%),
              radial-gradient(circle at 70% 80%, rgba(103, 194, 58, 0.05) 0%, transparent 40%);
  animation: bgShift 20s ease-in-out infinite alternate;
}

@keyframes bgShift {
  0% { transform: translate(0, 0); }
  100% { transform: translate(-5%, -3%); }
}

.login-container {
  position: relative;
  z-index: 1;
}

.login-card {
  width: 420px;
  padding: 48px 40px 36px;
  background: var(--card-bg, #fff);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.login-logo {
  font-size: 48px;
  color: var(--primary-color, #409eff);
  margin-bottom: 16px;
}

.login-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary, #303133);
  margin: 0 0 8px;
}

.login-subtitle {
  font-size: 14px;
  color: var(--text-muted, #909399);
  margin: 0;
}

.login-btn {
  width: 100%;
  font-size: 16px;
  letter-spacing: 4px;
}

.login-card :deep(.el-form-item) {
  margin-bottom: 22px;
}

.login-card :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.captcha-wrapper {
  width: 100%;
}

.captcha-track {
  position: relative;
  width: 100%;
  height: 44px;
  background: #e8e8e8;
  border-radius: 22px;
  overflow: hidden;
  user-select: none;
}

.captcha-progress {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color, #409eff), #67c23a);
  border-radius: 22px;
  opacity: 0.3;
  transition: opacity 0.3s;
}

.captcha-text {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #909399;
  letter-spacing: 2px;
  pointer-events: none;
}

.captcha-slider {
  position: absolute;
  top: 2px;
  width: 40px;
  height: 40px;
  background: var(--card-bg, #fff);
  border-radius: 50%;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  color: var(--primary-color, #409eff);
  font-size: 16px;
  transition: box-shadow 0.2s;
  z-index: 2;
}

.captcha-slider:hover {
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.4);
}

.captcha-slider.dragging {
  cursor: grabbing;
  box-shadow: 0 2px 16px rgba(64, 158, 255, 0.5);
}
</style>
