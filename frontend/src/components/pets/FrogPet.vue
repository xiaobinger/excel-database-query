<template>
  <div class="creature frog" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 88" aria-hidden="true">
      <defs>
        <radialGradient id="frogSkin" cx="32%" cy="24%" r="80%">
          <stop offset="0%" stop-color="#b6eaa4" />
          <stop offset="50%" stop-color="#8fd67e" />
          <stop offset="100%" stop-color="#6fbb5d" />
        </radialGradient>
        <radialGradient id="frogBelly" cx="50%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#ecf7dd" />
          <stop offset="100%" stop-color="#cfeab8" />
        </radialGradient>
      </defs>

      <!-- 身体 + 白肚皮 + 带蹼的脚 -->
      <ellipse cx="32" cy="74" rx="18" ry="12" fill="url(#frogSkin)" />
      <ellipse cx="32" cy="78" rx="11" ry="8" fill="url(#frogBelly)" />
      <ellipse cx="14.5" cy="84.5" rx="7" ry="3.4" fill="#6db85e" />
      <ellipse cx="49.5" cy="84.5" rx="7" ry="3.4" fill="#6db85e" />
      <circle cx="9.5" cy="83.4" r="1.6" fill="#6db85e" />
      <circle cx="54.5" cy="83.4" r="1.6" fill="#6db85e" />

      <!-- 头（宽扁，蛙形；眼睛鼓包由 DOM 保留） -->
      <ellipse cx="32" cy="47" rx="28" ry="21" fill="url(#frogSkin)" />
      <!-- 咽喉白区 -->
      <ellipse cx="32" cy="62" rx="13" ry="6.5" fill="url(#frogBelly)" opacity="0.85" />
      <!-- 釉面高光 -->
      <ellipse cx="18" cy="35" rx="9" ry="4.5" fill="#ffffff" opacity="0.45" transform="rotate(-20 18 35)" />
    </svg>

    <div class="frog-head">
      <span class="eye-bump bump-l"><i class="eye"><i class="pupil"></i></i></span>
      <span class="eye-bump bump-r"><i class="eye"><i class="pupil"></i></i></span>
      <span class="frog-mouth"></span>
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
  height: 88px;
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

.frog-head {
  position: absolute;
  top: 26px;
  left: 4px;
  width: 56px;
  height: 44px;
  z-index: 2;
}

/* 眼睛鼓包（保留 DOM：绿包 + 白眼 + 瞳孔，mood 系统直接操作 .eye/.pupil） */
.eye-bump {
  position: absolute;
  top: -9px;
  width: 18px;
  height: 18px;
  background: radial-gradient(circle at 40% 30%, #9fdc8f, #6fb95e 75%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 5px rgba(98, 168, 82, 0.3);
}

.bump-l { left: 5px; }
.bump-r { right: 5px; }

.eye-bump .eye {
  width: 11px;
  height: 11px;
  background: #ffffff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pet-blink 4.4s infinite;
}

.eye-bump .pupil {
  width: 5px;
  height: 5px;
  background: #2c3e50;
  border-radius: 50%;
}

.frog-mouth {
  position: absolute;
  top: 27px;
  left: 50%;
  transform: translateX(-50%);
  width: 26px;
  height: 11px;
  border-bottom: 2.5px solid #4e9440;
  border-radius: 0 0 26px 26px;
}

.blush {
  position: absolute;
  top: 22px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 130, 160, 0.5);
}

.b-l { left: 5px; }
.b-r { right: 5px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：腮红闪烁 + 嘴巴变大微笑 */
.creature.working .blush {
  animation: blush-pulse 0.9s ease-in-out infinite;
}

.creature.working .frog-mouth {
  width: 32px;
  height: 14px;
}

@keyframes blush-pulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.25); }
}
</style>
