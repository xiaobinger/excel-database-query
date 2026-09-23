<template>
  <div class="creature panda" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 92" aria-hidden="true">
      <defs>
        <radialGradient id="pandaFur" cx="35%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="55%" stop-color="#f6f7f9" />
          <stop offset="100%" stop-color="#e4e8ee" />
        </radialGradient>
        <radialGradient id="pandaDark" cx="40%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#565d65" />
          <stop offset="100%" stop-color="#32373c" />
        </radialGradient>
        <radialGradient id="pandaBelly" cx="50%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#fafbfc" />
          <stop offset="100%" stop-color="#e9edf1" />
        </radialGradient>
      </defs>

      <!-- 黑耳朵（闲时轻抖） -->
      <g class="panda-ear ear-l"><circle cx="13" cy="23" r="8.5" fill="url(#pandaDark)" /></g>
      <g class="panda-ear ear-r"><circle cx="51" cy="23" r="8.5" fill="url(#pandaDark)" /></g>

      <!-- 黑手臂 -->
      <ellipse cx="14" cy="73" rx="5" ry="8" fill="url(#pandaDark)" transform="rotate(12 14 73)" />
      <ellipse cx="50" cy="73" rx="5" ry="8" fill="url(#pandaDark)" transform="rotate(-12 50 73)" />

      <!-- 黑身体 + 白肚皮 + 黑脚 -->
      <ellipse cx="32" cy="76" rx="17" ry="14" fill="url(#pandaDark)" />
      <ellipse cx="32" cy="80" rx="11" ry="9.5" fill="url(#pandaBelly)" />
      <ellipse cx="23" cy="87" rx="5" ry="3" fill="#32373c" />
      <ellipse cx="41" cy="87" rx="5" ry="3" fill="#32373c" />

      <!-- 白头（黑眼圈/眼由 DOM 表情层绘制，保持 working/mood 兼容） -->
      <ellipse cx="32" cy="46" rx="27" ry="24" fill="url(#pandaFur)" />

      <!-- 鼻 + 人中 -->
      <rect x="28" y="46" width="8" height="6" rx="3" fill="#3a3f45" />
      <ellipse cx="30" cy="47.6" rx="1.2" ry="0.7" fill="#ffffff" opacity="0.5" />
      <path d="M32 52 v2" stroke="#3a3f45" stroke-width="1.2" stroke-linecap="round" />

      <!-- 顶光 -->
      <ellipse cx="20" cy="32" rx="8" ry="4" fill="#ffffff" opacity="0.5" transform="rotate(-18 20 32)" />
    </svg>

    <div class="panda-head">
      <span class="eye-patch patch-l"><i class="eye"></i></span>
      <span class="eye-patch patch-r"><i class="eye"></i></span>
      <span class="panda-mouth"></span>
    </div>
  </div>
</template>

<script setup>
defineProps({ working: Boolean, mood: { type: String, default: 'normal' } })
</script>

<style scoped>
.creature {
  position: relative;
  width: 64px;
  height: 92px;
}

.pet-art {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  overflow: visible;
  pointer-events: none;
}

.panda-head {
  position: absolute;
  top: 22px;
  left: 5px;
  width: 54px;
  height: 48px;
  z-index: 2;
}

/* 黑眼圈（保留 DOM，working 时眼白变金星色） */
.eye-patch {
  position: absolute;
  top: 13px;
  width: 16px;
  height: 12px;
  background: #3a3f45;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.patch-l { left: 7px; transform: rotate(14deg); }
.patch-r { right: 7px; transform: rotate(-14deg); }

.eye-patch .eye {
  width: 5px;
  height: 5px;
  background: #ffffff;
  border-radius: 50%;
  animation: pet-blink 4.8s infinite;
}

.panda-mouth {
  position: absolute;
  top: 33px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 5px;
  border-bottom: 2px solid #3a3f45;
  border-radius: 0 0 10px 10px;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 闲时耳朵轻抖 */
.creature:not(.working) .panda-ear.ear-l {
  transform-box: fill-box;
  transform-origin: center;
  animation: ear-bob 3.6s ease-in-out infinite;
}
.creature:not(.working) .panda-ear.ear-r {
  transform-box: fill-box;
  transform-origin: center;
  animation: ear-bob 3.6s ease-in-out 0.4s infinite;
}

@keyframes ear-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-1.5px); }
}

/* 工作中：眼白变星星亮色 + 耳朵快速小幅摆动 */
.creature.working .eye-patch .eye {
  background: #ffd34d;
  box-shadow: 0 0 5px rgba(255, 211, 77, 0.9);
  animation: none;
}

.creature.working .panda-ear {
  transform-box: fill-box;
  transform-origin: center;
  animation: ear-bob 0.8s ease-in-out infinite;
}
</style>
