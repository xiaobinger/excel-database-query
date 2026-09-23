<template>
  <div class="creature bear" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 92" aria-hidden="true">
      <defs>
        <radialGradient id="bearFur" cx="35%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#d8a76e" />
          <stop offset="55%" stop-color="#bf8c53" />
          <stop offset="100%" stop-color="#a3733f" />
        </radialGradient>
        <radialGradient id="bearTan" cx="50%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#f4e2c4" />
          <stop offset="100%" stop-color="#e6cda6" />
        </radialGradient>
      </defs>

      <!-- 耳朵（圆耳 + 浅色内耳，闲时轻抖） -->
      <g class="bear-ear ear-l">
        <circle cx="12" cy="24" r="8" fill="url(#bearFur)" />
        <circle cx="12" cy="24" r="4" fill="url(#bearTan)" />
      </g>
      <g class="bear-ear ear-r">
        <circle cx="52" cy="24" r="8" fill="url(#bearFur)" />
        <circle cx="52" cy="24" r="4" fill="url(#bearTan)" />
      </g>

      <!-- 手臂（身体两侧，微张） -->
      <ellipse cx="14" cy="73" rx="5" ry="8" fill="url(#bearFur)" transform="rotate(12 14 73)" />
      <ellipse cx="50" cy="73" rx="5" ry="8" fill="url(#bearFur)" transform="rotate(-12 50 73)" />

      <!-- 身体 + 肚皮 + 脚 -->
      <ellipse cx="32" cy="76" rx="17" ry="14" fill="url(#bearFur)" />
      <ellipse cx="32" cy="80" rx="10.5" ry="9.5" fill="url(#bearTan)" />
      <ellipse cx="23" cy="87" rx="5" ry="3" fill="#a3733f" />
      <ellipse cx="41" cy="87" rx="5" ry="3" fill="#a3733f" />

      <!-- 头 + 吻部 + 鼻 + 人中 -->
      <ellipse cx="32" cy="46" rx="26" ry="23" fill="url(#bearFur)" />
      <ellipse cx="32" cy="54" rx="13" ry="10" fill="url(#bearTan)" />
      <rect x="28.5" y="47" width="7" height="5.5" rx="2.6" fill="#6b4a2e" />
      <ellipse cx="30.2" cy="48.5" rx="1.1" ry="0.7" fill="#ffffff" opacity="0.65" />
      <path d="M32 52.5 v2" stroke="#8a6a4c" stroke-width="1.2" stroke-linecap="round" />

      <!-- 顶光 -->
      <ellipse cx="21" cy="33" rx="8" ry="4" fill="#ffffff" opacity="0.28" transform="rotate(-18 21 33)" />
    </svg>

    <div class="bear-head">
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="bear-mouth"></span>
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

.bear-head {
  position: absolute;
  top: 22px;
  left: 6px;
  width: 52px;
  height: 46px;
  z-index: 2;
}

.eye {
  position: absolute;
  top: 14px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.5s infinite;
}

.eye-l { left: 10px; }
.eye-r { right: 10px; }

.bear-mouth {
  position: absolute;
  top: 33px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 5px;
  border-bottom: 2px solid #8a6a4c;
  border-radius: 0 0 10px 10px;
}

.blush {
  position: absolute;
  top: 24px;
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

/* 闲时耳朵轻抖 */
.creature:not(.working) .bear-ear.ear-l {
  transform-box: fill-box;
  transform-origin: center;
  animation: ear-bob 3.6s ease-in-out infinite;
}
.creature:not(.working) .bear-ear.ear-r {
  transform-box: fill-box;
  transform-origin: center;
  animation: ear-bob 3.6s ease-in-out 0.4s infinite;
}

@keyframes ear-bob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-1.5px); }
}

/* 工作中：眼睛变开心弧线 + 耳朵快速抖 */
.creature.working .eye {
  width: 9px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 16px;
}

.creature.working .bear-ear {
  transform-box: fill-box;
  transform-origin: center;
  animation: ear-bob 0.8s ease-in-out infinite;
}
</style>
