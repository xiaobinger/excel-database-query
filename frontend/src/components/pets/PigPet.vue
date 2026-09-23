<template>
  <div class="creature pig" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 90" aria-hidden="true">
      <defs>
        <radialGradient id="pigSkin" cx="35%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#ffdbe3" />
          <stop offset="55%" stop-color="#f8bcc9" />
          <stop offset="100%" stop-color="#eda3b2" />
        </radialGradient>
        <radialGradient id="pigEarIn" cx="50%" cy="40%" r="70%">
          <stop offset="0%" stop-color="#f3aab8" />
          <stop offset="100%" stop-color="#e78ba0" />
        </radialGradient>
      </defs>

      <!-- 耷拉折耳（向前下垂盖住部分额头，真小猪耳型） -->
      <g class="pig-ear ear-l">
        <path d="M10 26 C6 20 7 11 13 6 C19 9 24 15 25 21 C25.5 26 22 29 18 29 C14 29 11.5 28 10 26 Z" fill="url(#pigSkin)" />
        <path d="M13 23 C11 18.5 12 13 15 10 C18.5 12.5 21.5 16.5 22.5 20 C22.8 23.5 20.5 25.5 17.5 25.5 C15.5 25.5 13.8 24.5 13 23 Z" fill="url(#pigEarIn)" />
      </g>
      <g class="pig-ear ear-r">
        <path d="M54 26 C58 20 57 11 51 6 C45 9 40 15 39 21 C38.5 26 42 29 46 29 C50 29 52.5 28 54 26 Z" fill="url(#pigSkin)" />
        <path d="M51 23 C53 18.5 52 13 49 10 C45.5 12.5 42.5 16.5 41.5 20 C41.2 23.5 43.5 25.5 46.5 25.5 C48.5 25.5 50.2 24.5 51 23 Z" fill="url(#pigEarIn)" />
      </g>

      <!-- 身体 + 深色蹄子 -->
      <ellipse cx="30" cy="76" rx="16" ry="13" fill="url(#pigSkin)" />
      <ellipse cx="23" cy="86.5" rx="4.6" ry="3.2" fill="#d9889e" />
      <ellipse cx="37" cy="86.5" rx="4.6" ry="3.2" fill="#d9889e" />

      <!-- 头（猪鼻由 DOM 保留，带鼻孔细节） -->
      <ellipse cx="32" cy="45" rx="26" ry="23" fill="url(#pigSkin)" />

      <!-- 顶光 -->
      <ellipse cx="21" cy="32" rx="8" ry="4" fill="#ffffff" opacity="0.4" transform="rotate(-18 21 32)" />
    </svg>

    <!-- 卷尾（DOM 保留，原本就有卷曲动画） -->
    <span class="pig-tail"></span>

    <div class="pig-head">
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="pig-snout">
        <i class="nostril n-l"></i>
        <i class="nostril n-r"></i>
      </span>
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
  height: 90px;
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

.pig-head {
  position: absolute;
  top: 22px;
  left: 6px;
  width: 52px;
  height: 46px;
  z-index: 2;
}

.eye {
  position: absolute;
  top: 13px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #4a3b3b;
  animation: pet-blink 4.7s infinite;
}

.eye-l { left: 10px; }
.eye-r { right: 10px; }

.pig-snout {
  position: absolute;
  top: 23px;
  left: 50%;
  transform: translateX(-50%);
  width: 22px;
  height: 15px;
  background: radial-gradient(circle at 50% 25%, #f3aab8, #e78ba0);
  border-radius: 50%;
  box-shadow: inset 0 -2px 0 rgba(214, 120, 142, 0.5), inset 0 1px 2px rgba(255, 255, 255, 0.5);
}

.nostril {
  position: absolute;
  top: 5px;
  width: 4px;
  height: 6px;
  background: #d9889e;
  border-radius: 3px;
}

.n-l { left: 4px; }
.n-r { right: 4px; }

.blush {
  position: absolute;
  top: 24px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(240, 110, 140, 0.45);
}

.b-l { left: 2px; }
.b-r { right: 2px; }

.pig-tail {
  position: absolute;
  top: 70px;
  right: 0;
  width: 11px;
  height: 11px;
  border: 3px solid #ef9db0;
  border-radius: 50%;
  border-top-color: transparent;
  border-left-color: transparent;
  transform: rotate(38deg);
  animation: tail-curl 2.6s ease-in-out infinite;
  z-index: 1;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

@keyframes tail-curl {
  0%, 100% { transform: rotate(38deg) scale(1); }
  50% { transform: rotate(65deg) scale(1.08); }
}

/* 闲时耳朵轻扇 */
.creature:not(.working) .pig-ear.ear-l {
  transform-box: fill-box;
  transform-origin: right bottom;
  animation: ear-flop-l 3.8s ease-in-out infinite;
}
.creature:not(.working) .pig-ear.ear-r {
  transform-box: fill-box;
  transform-origin: left bottom;
  animation: ear-flop-r 3.8s ease-in-out infinite;
}

@keyframes ear-flop-l {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-5deg); }
}
@keyframes ear-flop-r {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(5deg); }
}

/* 工作中：眼睛变开心弧线 + 卷尾加速转 */
.creature.working .eye {
  width: 9px;
  height: 5px;
  background: transparent;
  border: 2px solid #4a3b3b;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 15px;
}

.creature.working .pig-tail {
  animation: tail-curl 0.8s ease-in-out infinite;
}
</style>
