<template>
  <div class="creature bunny" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <svg class="pet-art" viewBox="0 0 64 100" aria-hidden="true">
      <defs>
        <radialGradient id="bunnyFur" cx="35%" cy="24%" r="80%">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="55%" stop-color="#f8f4ee" />
          <stop offset="100%" stop-color="#e9e2d8" />
        </radialGradient>
        <linearGradient id="bunnyEarIn" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#fbdce2" />
          <stop offset="100%" stop-color="#f4aebf" />
        </linearGradient>
      </defs>

      <!-- 绒球尾（身体侧后） -->
      <circle cx="50.5" cy="85" r="5" fill="url(#bunnyFur)" stroke="#e3ded6" stroke-width="1" />

      <!-- 耳朵：饱满粗椭圆 + 粉内耳，微外撇 -->
      <g class="bunny-ear ear-l">
        <ellipse cx="20.5" cy="18" rx="6.5" ry="16" transform="rotate(-8 20.5 18)"
          fill="url(#bunnyFur)" stroke="#e3ded6" stroke-width="1" />
        <ellipse cx="21" cy="19.5" rx="3.4" ry="11.5" transform="rotate(-8 21 19.5)" fill="url(#bunnyEarIn)" />
      </g>
      <g class="bunny-ear ear-r">
        <ellipse cx="43.5" cy="18" rx="6.5" ry="16" transform="rotate(8 43.5 18)"
          fill="url(#bunnyFur)" stroke="#e3ded6" stroke-width="1" />
        <ellipse cx="43" cy="19.5" rx="3.4" ry="11.5" transform="rotate(8 43 19.5)" fill="url(#bunnyEarIn)" />
      </g>

      <!-- 身体 + 大脚板 + 前爪 -->
      <ellipse cx="32" cy="86" rx="14" ry="12" fill="url(#bunnyFur)" stroke="#e3ded6" stroke-width="1" />
      <ellipse cx="21.5" cy="95.5" rx="7" ry="3.2" fill="#f4f0ea" stroke="#e3ded6" stroke-width="0.8" />
      <ellipse cx="42.5" cy="95.5" rx="7" ry="3.2" fill="#f4f0ea" stroke="#e3ded6" stroke-width="0.8" />
      <ellipse cx="26.5" cy="88.5" rx="3.2" ry="2.6" fill="#f7f3ec" stroke="#e3ded6" stroke-width="0.6" />
      <ellipse cx="37.5" cy="88.5" rx="3.2" ry="2.6" fill="#f7f3ec" stroke="#e3ded6" stroke-width="0.6" />

      <!-- 头 -->
      <ellipse cx="32" cy="53" rx="21.5" ry="20" fill="url(#bunnyFur)" stroke="#e3ded6" stroke-width="1" />

      <!-- 双球吻部（兔子标志性的腮帮鼻吻区） -->
      <circle cx="26" cy="61" r="7" fill="#fdfaf5" />
      <circle cx="38" cy="61" r="7" fill="#fdfaf5" />

      <!-- 鼻 + 人中（嘴弧线由 DOM 表情层绘制，门牙挂在 DOM 嘴 ::after 上随表情走） -->
      <path d="M29 55 Q32 53.6 35 55 Q34.2 58.6 32 59 Q29.8 58.6 29 55 Z" fill="#e87c94" />
      <ellipse cx="30.7" cy="55.4" rx="0.9" ry="0.55" fill="#ffffff" opacity="0.7" />
      <path d="M32 59 v2.6" stroke="#b0907e" stroke-width="1.1" stroke-linecap="round" />

      <!-- 胡须 -->
      <path d="M15.5 55 L5 52.5 M15.5 59 L4.5 60 M48.5 55 L59 52.5 M48.5 59 L59.5 60"
        stroke="rgba(140,125,110,0.5)" stroke-width="0.9" stroke-linecap="round" fill="none" />

      <!-- 顶光 -->
      <ellipse cx="22" cy="40" rx="7" ry="3.5" fill="#ffffff" opacity="0.55" transform="rotate(-18 22 40)" />
    </svg>

    <div class="bunny-head">
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="bunny-mouth"></span>
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
  height: 100px;
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

/* 透明表情层：眼/嘴/腮红（top 以 mood-happy 的 12px 为基准，避免表情切换时跳位） */
.bunny-head {
  position: absolute;
  top: 32px;
  left: 8px;
  width: 48px;
  height: 42px;
  z-index: 2;
}

.eye {
  position: absolute;
  top: 12.5px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.4s infinite;
}

.eye-l { left: 11.5px; }
.eye-r { right: 11.5px; }

.bunny-mouth {
  position: absolute;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 5px;
  border-bottom: 2px solid #a58d7a;
  border-radius: 0 0 10px 10px;
}

/* 门牙：挂在嘴元素 ::after 上，随表情嘴型联动（双牙分缝用渐变线模拟） */
.bunny-mouth::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translate(-50%, -1px);
  width: 5px;
  height: 4.5px;
  border: 0.7px solid #e0d9cf;
  border-top: none;
  border-radius: 0 0 2px 2px;
  background:
    linear-gradient(to right, transparent calc(50% - 0.4px), #dcd6cc calc(50% - 0.4px), #dcd6cc calc(50% + 0.4px), transparent calc(50% + 0.4px)),
    #ffffff;
}

/* happy 张嘴笑：牙收进嘴里（贴口腔上部，上牙垂下） */
.creature.mood-happy .bunny-mouth::after {
  top: 0;
  transform: translateX(-50%);
  width: 60%;
  height: 46%;
  border: none;
  border-radius: 0 0 1.5px 1.5px;
}

/* 深色小嘴型/自带白牙的表情：藏起门牙（proud 嘴自带 box-shadow 白牙） */
.creature.mood-curious .bunny-mouth::after,
.creature.mood-sneaky .bunny-mouth::after,
.creature.mood-proud .bunny-mouth::after,
.creature.mood-excited .bunny-mouth::after,
.creature.mood-dizzy .bunny-mouth::after {
  display: none;
}

.blush {
  position: absolute;
  top: 23px;
  width: 8px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.5);
}

.b-l { left: 2.5px; }
.b-r { right: 2.5px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 耳朵轻摆（SVG 组，transform-box 以自身为基准） */
.creature:not(.working) .bunny-ear.ear-l {
  transform-box: fill-box;
  transform-origin: 50% 100%;
  animation: ear-sway-l 3.4s ease-in-out infinite;
}
.creature:not(.working) .bunny-ear.ear-r {
  transform-box: fill-box;
  transform-origin: 50% 100%;
  animation: ear-sway-r 3.4s ease-in-out infinite;
}

@keyframes ear-sway-l {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-4deg); }
}
@keyframes ear-sway-r {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(4deg); }
}

/* 工作中：眼睛变开心弧线 + 耳朵快速摆 */
.creature.working .eye {
  width: 10px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 14.5px;
}

.creature.working .bunny-ear.ear-l {
  transform-box: fill-box;
  transform-origin: 50% 100%;
  animation: ear-sway-l 0.9s ease-in-out infinite;
}
.creature.working .bunny-ear.ear-r {
  transform-box: fill-box;
  transform-origin: 50% 100%;
  animation: ear-sway-r 0.9s ease-in-out infinite;
}
</style>
