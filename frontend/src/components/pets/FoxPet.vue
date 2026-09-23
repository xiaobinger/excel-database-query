<template>
  <div class="creature fox" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 92" aria-hidden="true">
      <defs>
        <radialGradient id="foxFur" cx="35%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#f8ac63" />
          <stop offset="55%" stop-color="#ef8b3f" />
          <stop offset="100%" stop-color="#dd7223" />
        </radialGradient>
        <radialGradient id="foxCream" cx="50%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#fffdf8" />
          <stop offset="100%" stop-color="#ffeedd" />
        </radialGradient>
      </defs>

      <!-- 大蓬尾（橙色 + 白尾尖，轻摆） -->
      <g class="fox-tail">
        <path d="M43 82 C57 80 63 68 59.5 56.5 C58 51 53 49.5 49.5 51.5"
          fill="none" stroke="#ef8b3f" stroke-width="9.5" stroke-linecap="round" />
        <path d="M43 82 C56 80 61.5 70 59 59" fill="none" stroke="#f8ac63" stroke-width="4" stroke-linecap="round" />
        <path d="M59.5 56.5 C58 51 53 49.5 49.5 51.5" fill="none" stroke="#fff7ef" stroke-width="9.5" stroke-linecap="round" />
      </g>

      <!-- 身体 + 白胸 + 深色袜爪 -->
      <ellipse cx="30" cy="76" rx="16" ry="14" fill="url(#foxFur)" />
      <ellipse cx="30" cy="79.5" rx="10" ry="9" fill="url(#foxCream)" />
      <ellipse cx="22" cy="86.5" rx="4.6" ry="3.2" fill="#5d4633" />
      <ellipse cx="36" cy="86.5" rx="4.6" ry="3.2" fill="#5d4633" />

      <!-- 尖耳（深色耳尖 + 奶油内耳） -->
      <g class="fox-ear ear-l">
        <path d="M13 30 C11 20 10 10 13.5 4 C19 8 24 15 26.5 20.5 C21.5 22.5 16.5 25.5 13 30 Z" fill="url(#foxFur)" />
        <path d="M13.5 4 C15.5 6.5 17.5 9.5 19.2 12.5 L14 16.5 C12.3 12 12 8 13.5 4 Z" fill="#5d4633" />
        <path d="M15.5 24.5 C14.5 18.5 14.5 13.5 16 9.5 C18.5 12.5 21 16 22.3 18.5 C19.5 19.5 17.3 21.8 15.5 24.5 Z" fill="#fbe3cf" />
      </g>
      <g class="fox-ear ear-r">
        <path d="M51 30 C53 20 54 10 50.5 4 C45 8 40 15 37.5 20.5 C42.5 22.5 47.5 25.5 51 30 Z" fill="url(#foxFur)" />
        <path d="M50.5 4 C48.5 6.5 46.5 9.5 44.8 12.5 L50 16.5 C51.7 12 52 8 50.5 4 Z" fill="#5d4633" />
        <path d="M48.5 24.5 C49.5 18.5 49.5 13.5 48 9.5 C45.5 12.5 43 16 41.7 18.5 C44.5 19.5 46.7 21.8 48.5 24.5 Z" fill="#fbe3cf" />
      </g>

      <!-- 头 + 白脸颊 + 白吻部 + 鼻 + 嘴线 -->
      <ellipse cx="32" cy="47" rx="26" ry="21" fill="url(#foxFur)" />
      <path d="M11 52 Q6 57 8.5 62 Q14 60 16.5 55 Z" fill="url(#foxCream)" />
      <path d="M53 52 Q58 57 55.5 62 Q50 60 47.5 55 Z" fill="url(#foxCream)" />
      <ellipse cx="32" cy="57" rx="13" ry="9" fill="url(#foxCream)" />
      <path d="M28.8 52 Q32 50.8 35.2 52 Q34 56.2 32 56.6 Q30 56.2 28.8 52 Z" fill="#3b2f2a" />
      <ellipse cx="30.6" cy="52.5" rx="1" ry="0.6" fill="#ffffff" opacity="0.6" />
      <path d="M32 56.6 v1.6 M32 58.2 Q29 60.2 27 58.6 M32 58.2 Q35 60.2 37 58.6" stroke="#8a6a4c" stroke-width="1.1" stroke-linecap="round" fill="none" />

      <!-- 顶光 -->
      <ellipse cx="21" cy="35" rx="8" ry="4" fill="#ffffff" opacity="0.32" transform="rotate(-18 21 35)" />
    </svg>

    <div class="fox-head">
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="blush b-l"></span>
      <span class="blush b-r"></span>
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

.fox-head {
  position: absolute;
  top: 24px;
  left: 6px;
  width: 52px;
  height: 44px;
  z-index: 2;
}

.eye {
  position: absolute;
  top: 13px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.3s infinite;
}

.eye-l { left: 10px; }
.eye-r { right: 10px; }

.blush {
  position: absolute;
  top: 22px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.45);
}

.b-l { left: 3px; }
.b-r { right: 3px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 尾巴轻摆 */
.creature:not(.working) .fox-tail {
  transform-box: fill-box;
  transform-origin: left bottom;
  animation: tail-sway 2.2s ease-in-out infinite;
}

@keyframes tail-sway {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-7deg); }
}

/* 工作中：眼睛变开心弧线 + 尾巴加速摇 */
.creature.working .eye {
  width: 9px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 15px;
}

.creature.working .fox-tail {
  transform-box: fill-box;
  transform-origin: left bottom;
  animation: tail-sway 0.7s ease-in-out infinite;
}
</style>
