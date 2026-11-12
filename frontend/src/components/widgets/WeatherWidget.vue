<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-cloud-sun"></i>天气</span>
      <button class="widget-refresh" title="刷新天气" @click="load">
        <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
      </button>
    </div>
    <div class="widget-body">
      <div v-if="error" class="widget-error">{{ error }}</div>
      <div v-else-if="!data" class="widget-empty">加载中…</div>
      <template v-else>
        <div class="weather-main">
          <i class="fas weather-icon" :class="weatherIcon"></i>
          <div>
            <div class="weather-temp">{{ fmt(data.temperature) }}<span class="weather-unit">°C</span></div>
            <div class="weather-desc">{{ weatherText }}</div>
          </div>
        </div>
        <div class="weather-city">
          <i class="fas fa-location-dot"></i> {{ data.city }}<span v-if="data.region"> · {{ data.region }}</span>
        </div>
        <div class="weather-meta">
          <span>最高 {{ fmt(data.high) }}°</span>
          <span>最低 {{ fmt(data.low) }}°</span>
          <span>湿度 {{ fmt(data.humidity) }}%</span>
          <span>风速 {{ fmt(data.wind_speed) }} km/h</span>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import api from '../../api'

const props = defineProps({
  settings: { type: Object, default: () => ({}) },
})

const data = ref(null)
const error = ref('')
const loading = ref(false)
let timer = null

const WEATHER_MAP = {
  0: ['晴', 'fa-sun'],
  1: ['大部晴朗', 'fa-sun'],
  2: ['多云', 'fa-cloud-sun'],
  3: ['阴', 'fa-cloud'],
  45: ['有雾', 'fa-smog'],
  48: ['雾凇', 'fa-smog'],
  51: ['毛毛雨', 'fa-cloud-rain'],
  53: ['毛毛雨', 'fa-cloud-rain'],
  55: ['毛毛雨', 'fa-cloud-rain'],
  56: ['冻毛毛雨', 'fa-cloud-rain'],
  57: ['冻毛毛雨', 'fa-cloud-rain'],
  61: ['小雨', 'fa-cloud-rain'],
  63: ['中雨', 'fa-cloud-rain'],
  65: ['大雨', 'fa-cloud-rain'],
  66: ['冻雨', 'fa-cloud-rain'],
  67: ['冻雨', 'fa-cloud-rain'],
  71: ['小雪', 'fa-snowflake'],
  73: ['中雪', 'fa-snowflake'],
  75: ['大雪', 'fa-snowflake'],
  77: ['雪粒', 'fa-snowflake'],
  80: ['阵雨', 'fa-cloud-rain'],
  81: ['阵雨', 'fa-cloud-rain'],
  82: ['强阵雨', 'fa-cloud-rain'],
  85: ['阵雪', 'fa-snowflake'],
  86: ['阵雪', 'fa-snowflake'],
  95: ['雷阵雨', 'fa-cloud-bolt'],
  96: ['雷暴冰雹', 'fa-cloud-bolt'],
  99: ['雷暴冰雹', 'fa-cloud-bolt'],
}

const weatherInfo = computed(() => WEATHER_MAP[data.value?.weather_code] || ['未知', 'fa-cloud'])
const weatherText = computed(() => weatherInfo.value[0])
const weatherIcon = computed(() => weatherInfo.value[1])

function fmt(value) {
  return value === null || value === undefined ? '-' : Math.round(Number(value))
}

async function load() {
  if (!props.settings?.city) {
    error.value = '请在个人中心设置天气城市'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await api.widgets.weather({ city: props.settings.city })
    if (res.success === false) {
      error.value = res.message || '天气获取失败'
      return
    }
    data.value = res.data || res
  } catch {
    error.value = '天气获取失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.settings?.city, load)

onMounted(() => {
  load()
  timer = setInterval(load, 30 * 60 * 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.weather-main {
  display: flex;
  align-items: center;
  gap: 12px;
}

.weather-icon {
  font-size: 38px;
  color: var(--primary-color, #409eff);
}

.weather-temp {
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary, #303133);
  line-height: 1.1;
}

.weather-unit {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary, #606266);
  margin-left: 2px;
}

.weather-desc {
  font-size: 13px;
  color: var(--text-secondary, #606266);
  margin-top: 2px;
}

.weather-city {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary, #606266);
}

.weather-city i {
  color: var(--primary-color, #409eff);
  margin-right: 2px;
}

.weather-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
  color: var(--text-muted, #909399);
}
</style>
