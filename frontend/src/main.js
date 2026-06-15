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
