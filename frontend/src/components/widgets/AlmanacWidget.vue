<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-calendar-day"></i>黄历</span>
      <span class="widget-muted">传统参考</span>
    </div>
    <div class="widget-body almanac-body">
      <div class="almanac-main">
        <div class="almanac-day">{{ lunar.dayText }}</div>
        <div class="almanac-month">{{ lunar.monthText }}</div>
      </div>
      <div class="almanac-row">
        <span class="almanac-label">干支</span>
        <span>{{ lunar.yearGanZhi }}年 · {{ lunar.monthGanZhi }}月 · {{ lunar.dayGanZhi }}日</span>
      </div>
      <div class="almanac-row">
        <span class="almanac-label">生肖</span>
        <span>{{ lunar.zodiac }} · {{ lunar.jianChu }}日</span>
      </div>
      <div class="almanac-yiji">
        <div class="yiji-block yi">
          <span class="yiji-tag">宜</span>
          <span class="yiji-text">{{ lunar.yi.join(' · ') }}</span>
        </div>
        <div class="yiji-block ji">
          <span class="yiji-tag">忌</span>
          <span class="yiji-text">{{ lunar.ji.join(' · ') }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { solarToLunar } from '../../utils/lunar'

const lunar = ref(solarToLunar(new Date()))
let timer = null

function refresh() {
  lunar.value = solarToLunar(new Date())
}

onMounted(() => {
  // 每分钟刷新一次，跨天自动更新
  timer = setInterval(refresh, 60 * 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.almanac-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.almanac-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.almanac-day {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary, #303133);
}

.almanac-month {
  font-size: 13px;
  color: var(--text-secondary, #606266);
}

.almanac-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary, #606266);
  line-height: 1.6;
}

.almanac-label {
  flex-shrink: 0;
  color: var(--text-muted, #909399);
}

.almanac-yiji {
  margin-top: 2px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.yiji-block {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.yiji-tag {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 5px;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  color: #fff;
  margin-top: 1px;
}

.yiji-block.yi .yiji-tag {
  background: #67c23a;
}

.yiji-block.ji .yiji-tag {
  background: #f56c6c;
}

.yiji-text {
  font-size: 12px;
  color: var(--text-secondary, #606266);
  line-height: 1.6;
}
</style>
