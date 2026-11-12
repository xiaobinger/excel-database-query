<template>
  <section class="widget-card">
    <div class="widget-card-head">
      <span class="widget-title"><i class="fas fa-note-sticky"></i>自定义贴图</span>
      <span class="widget-muted">个人中心可更换</span>
    </div>
    <div class="widget-body sticker-body">
      <img v-if="settings?.image" :src="settings.image" class="sticker-image" alt="自定义贴图" />
      <div
        v-else-if="settings?.text"
        class="sticker-note"
        :style="{ background: settings.color || '#fff7e6' }"
      >{{ settings.text }}</div>
      <div v-else class="widget-empty">在个人中心上传贴图或写一张便签</div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  settings: { type: Object, default: () => ({}) },
})
</script>

<style scoped>
.sticker-body {
  display: flex;
  justify-content: center;
}

.sticker-image {
  display: block;
  max-width: 100%;
  max-height: 220px;
  border-radius: 8px;
  object-fit: contain;
}

.sticker-note {
  width: 100%;
  min-height: 80px;
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #6b4f1d;
  white-space: pre-wrap;
  word-break: break-word;
  box-sizing: border-box;
}
</style>
