<template>
  <div class="creature chick" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 88" aria-hidden="true">
      <defs>
        <radialGradient id="chickDown" cx="38%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#fff0a0" />
          <stop offset="50%" stop-color="#ffe079" />
          <stop offset="100%" stop-color="#f6c83a" />
        </radialGradient>
        <radialGradient id="chickWing" cx="40%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#ffdd6a" />
          <stop offset="100%" stop-color="#edbc2c" />
        </radialGradient>
      </defs>

      <!-- 翅膀（身体两侧，工作时扑扇） -->
      <ellipse class="chick-wing wing-l" cx="6.5" cy="50" rx="5" ry="9" fill="url(#chickWing)" transform="rotate(15 6.5 50)" />
      <ellipse class="chick-wing wing-r" cx="57.5" cy="50" rx="5" ry="9" fill="url(#chickWing)" transform="rotate(-15 57.5 50)" />

      <!-- 梨形绒身 -->
      <path d="M32 18 C46 18 57 32 57 50 C57 66 46 80 32 80 C18 80 7 66 7 50 C7 32 18 18 32 18 Z" fill="url(#chickDown)" />
      <!-- 胸前浅色绒区 -->
      <ellipse cx="32" cy="64" rx="13" ry="12" fill="#ffeeb0" opacity="0.7" />

      <!-- 三趾小脚 -->
      <path d="M25 81 l-2.5 5 M25 81 v6 M25 81 l2.5 5" stroke="#ff9d3b" stroke-width="1.8" stroke-linecap="round" fill="none" />
      <path d="M39 81 l-2.5 5 M39 81 v6 M39 81 l2.5 5" stroke="#ff9d3b" stroke-width="1.8" stroke-linecap="round" fill="none" />

      <!-- 顶光 -->
      <ellipse cx="21" cy="30" rx="8" ry="4" fill="#ffffff" opacity="0.45" transform="rotate(-18 21 30)" />
    </svg>

    <div class="chick-blob">
      <span class="chick-ahoge"></span>
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="chick-beak"></span>
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

/* 透明表情层：保持旧版 blob 位姿 */
.chick-blob {
  position: absolute;
  top: 18px;
  left: 5px;
  width: 54px;
  height: 62px;
  z-index: 2;
}

.chick-ahoge {
  position: absolute;
  top: -5px;
  left: 50%;
  width: 10px;
  height: 9px;
  border-top: 2.5px solid #f0b429;
  border-radius: 50%;
  transform: translateX(-50%) rotate(-24deg);
}

.eye {
  position: absolute;
  top: 18px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.2s infinite;
}

.eye-l { left: 13px; }
.eye-r { right: 13px; }

.chick-beak {
  position: absolute;
  top: 27px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid #ff9d3b;
}

.blush {
  position: absolute;
  top: 28px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 130, 130, 0.55);
}

.b-l { left: 5px; }
.b-r { right: 5px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：翅膀扑扇（SVG 元素，transform-box 以自身为基准） */
.creature.working .chick-wing.wing-l {
  transform-box: fill-box;
  transform-origin: right center;
  animation: wing-flap-l 0.5s ease-in-out infinite;
}
.creature.working .chick-wing.wing-r {
  transform-box: fill-box;
  transform-origin: left center;
  animation: wing-flap-r 0.5s ease-in-out infinite;
}

@keyframes wing-flap-l {
  0%, 100% { transform: rotate(15deg); }
  50% { transform: rotate(38deg); }
}
@keyframes wing-flap-r {
  0%, 100% { transform: rotate(-15deg); }
  50% { transform: rotate(-38deg); }
}
</style>
