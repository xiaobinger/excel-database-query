import ClockWidget from '../components/widgets/ClockWidget.vue'
import AlmanacWidget from '../components/widgets/AlmanacWidget.vue'
import WeatherWidget from '../components/widgets/WeatherWidget.vue'
import NewsWidget from '../components/widgets/NewsWidget.vue'
import TodoWidget from '../components/widgets/TodoWidget.vue'
import StickerWidget from '../components/widgets/StickerWidget.vue'
import StocksWidget from '../components/widgets/StocksWidget.vue'

/** 插件 key → 组件映射（key 与后端 widget_service.WIDGETS 保持一致） */
export const WIDGET_COMPONENTS = {
  clock: ClockWidget,
  almanac: AlmanacWidget,
  weather: WeatherWidget,
  news: NewsWidget,
  todo: TodoWidget,
  sticker: StickerWidget,
  stocks: StocksWidget,
}

/** 角色授权勾选项（仅用于展示，实际可用性以后端返回为准） */
export const WIDGET_OPTIONS = [
  { value: 'clock', label: '时钟' },
  { value: 'almanac', label: '黄历' },
  { value: 'weather', label: '天气' },
  { value: 'news', label: '支付圈新闻' },
  { value: 'todo', label: '系统待办' },
  { value: 'sticker', label: '自定义贴图' },
  { value: 'stocks', label: '自选股行情' },
]

export function widgetComponent(key) {
  return WIDGET_COMPONENTS[key] || null
}
