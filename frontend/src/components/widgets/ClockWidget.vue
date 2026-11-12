<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-clock"></i>时钟</span>
      <span class="widget-muted">{{ weekday }}</span>
    </div>
    <div class="widget-body clock-body">
      <div class="clock-time">{{ timeText }}</div>
      <div class="clock-date">{{ dateText }}</div>
      <div class="clock-greet">{{ greeting }}</div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const now = ref(new Date())
let timer = null

const pad = (n) => String(n).padStart(2, '0')
const timeText = computed(() => `${pad(now.value.getHours())}:${pad(now.value.getMinutes())}:${pad(now.value.getSeconds())}`)
const dateText = computed(() => `${now.value.getFullYear()}年${now.value.getMonth() + 1}月${now.value.getDate()}日`)
const weekday = computed(() => ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][now.value.getDay()])
const greeting = computed(() => {
  const hour = now.value.getHours()
  if (hour < 6) return '夜深了，注意休息'
  if (hour < 9) return '早上好，新的一天'
  if (hour < 12) return '上午好，专注当下'
  if (hour < 14) return '中午好，记得午休'
  if (hour < 18) return '下午好，继续加油'
  return '晚上好，辛苦一天了'
})

onMounted(() => {
  timer = setInterval(() => { now.value = new Date() }, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.clock-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.clock-time {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 1px;
  color: var(--text-primary, #303133);
  font-variant-numeric: tabular-nums;
}

.clock-date {
  font-size: 13px;
  color: var(--text-secondary, #606266);
}

.clock-greet {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted, #909399);
}
</style>
