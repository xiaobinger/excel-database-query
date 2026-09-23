<template>
  <div class="creature koala" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 92" aria-hidden="true">
      <defs>
        <radialGradient id="koalaFur" cx="35%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#cdd5de" />
          <stop offset="55%" stop-color="#b0bbc7" />
          <stop offset="100%" stop-color="#96a3b1" />
        </radialGradient>
        <radialGradient id="koalaFluff" cx="50%" cy="40%" r="70%">
          <stop offset="0%" stop-color="#e6ebf0" />
          <stop offset="100%" stop-color="#cdd5de" />
        </radialGradient>
      </defs>

      <!-- 大绒耳（外灰 + 内浅绒毛圈 + 白绒点，闲时轻扇） -->
      <g class="koala-ear ear-l">
        <circle cx="7" cy="24" r="13" fill="url(#koalaFur)" />
        <circle cx="7" cy="24" r="8.5" fill="url(#koalaFluff)" />
        <circle cx="4" cy="20" r="2.2" fill="#ffffff" opacity="0.7" />
        <circle cx="9" cy="28" r="1.8" fill="#ffffff" opacity="0.5" />
      </g>
      <g class="koala-ear ear-r">
        <circle cx="57" cy="24" r="13" fill="url(#koalaFur)" />
        <circle cx="57" cy="24" r="8.5" fill="url(#koalaFluff)" />
        <circle cx="60" cy="20" r="2.2" fill="#ffffff" opacity="0.7" />
        <circle cx="55" cy="28" r="1.8" fill="#ffffff" opacity="0.5" />
      </g>

      <!-- 手臂 + 身体 + 肚皮 + 脚 -->
      <ellipse cx="17" cy="72" rx="4.5" ry="7" fill="url(#koalaFur)" transform="rotate(10 17 72)" />
      <ellipse cx="47" cy="72" rx="4.5" ry="7" fill="url(#koalaFur)" transform="rotate(-10 47 72)" />
      <ellipse cx="32" cy="76" rx="16" ry="13" fill="url(#koalaFur)" />
      <ellipse cx="32" cy="80" rx="10" ry="8.5" fill="url(#koalaFluff)" />
      <ellipse cx="24" cy="87" rx="4.5" ry="3" fill="#8d99a8" />
      <ellipse cx="40" cy="87" rx="4.5" ry="3" fill="#8d99a8" />

      <!-- 头（大鼻子由 DOM 保留） -->
      <ellipse cx="32" cy="46" rx="24" ry="22" fill="url(#koalaFur)" />

      <!-- 顶光 -->
      <ellipse cx="21" cy="33" rx="8" ry="4" fill="#ffffff" opacity="0.4" transform="rotate(-18 21 33)" />
    </svg>

    <div class="koala-head">
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="koala-nose"></span>
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

.koala-head {
  position: absolute;
  top: 24px;
  left: 8px;
  width: 48px;
  height: 44px;
  z-index: 2;
}

.eye {
  position: absolute;
  top: 15px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #33393f;
  animation: pet-blink 4.6s infinite;
}

.eye-l { left: 8px; }
.eye-r { right: 8px; }

.koala-nose {
  position: absolute;
  top: 17px;
  left: 50%;
  transform: translateX(-50%);
  width: 12px;
  height: 17px;
  background: linear-gradient(#66737f, #5d6b7a);
  border-radius: 7px;
  box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.15), inset 0 2px 2px rgba(255, 255, 255, 0.25);
}

.blush {
  position: absolute;
  top: 27px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.4);
}

.b-l { left: 2px; }
.b-r { right: 2px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 闲时耳朵轻扇 */
.creature:not(.working) .koala-ear.ear-l {
  transform-box: fill-box;
  transform-origin: right center;
  animation: ear-fan-l 3.8s ease-in-out infinite;
}
.creature:not(.working) .koala-ear.ear-r {
  transform-box: fill-box;
  transform-origin: left center;
  animation: ear-fan-r 3.8s ease-in-out 0.3s infinite;
}

@keyframes ear-fan-l {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-5deg); }
}
@keyframes ear-fan-r {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(5deg); }
}

/* 工作中：眼睛变开心弧线 + 大耳朵快速扑扇 */
.creature.working .eye {
  width: 8px;
  height: 4px;
  background: transparent;
  border: 2px solid #33393f;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  animation: none;
  top: 17px;
}

.creature.working .koala-ear.ear-l {
  transform-box: fill-box;
  transform-origin: right center;
  animation: ear-fan-l 0.85s ease-in-out infinite;
}
.creature.working .koala-ear.ear-r {
  transform-box: fill-box;
  transform-origin: left center;
  animation: ear-fan-r 0.85s ease-in-out infinite;
}
</style>
