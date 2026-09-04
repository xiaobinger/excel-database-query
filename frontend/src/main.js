import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import App from './App.vue'
import router from './router'
import { useAppStore } from './stores'
import './styles/themes.css'
import './styles/global.css'
import 'highlight.js/styles/github-dark.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 全局错误兜底：单个页面组件渲染出错时仅记录日志并拦截冒泡，
// 避免未捕获的渲染异常破坏整个组件树、导致后续路由切换全站白屏
app.config.errorHandler = (err, instance, info) => {
  console.error('[GlobalErrorHandler]', info, err)
}

app.directive('hasPermi', {
  mounted(el, binding) {
    const store = useAppStore()
    const permissions = binding.value
    if (!permissions || permissions.length === 0) return
    const hasPermission = permissions.some(perm => store.hasButtonPermission(perm))
    if (!hasPermission) {
      el.parentNode && el.parentNode.removeChild(el)
    }
  }
})

app.mount('#app')

const savedTheme = localStorage.getItem('theme') || 'default'
document.documentElement.setAttribute('data-theme', savedTheme)
