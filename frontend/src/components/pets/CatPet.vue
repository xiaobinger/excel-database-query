<template>
  <div class="creature cat" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <!-- SVG 手绘身体：耳朵/头/斑纹/口鼻/身体/尾巴/爪（DOM 只保留眼/嘴/腮红，供表情系统接管） -->
    <svg class="pet-art" viewBox="0 0 64 92" aria-hidden="true">
      <defs>
        <radialGradient id="catFur" cx="35%" cy="26%" r="80%">
          <stop offset="0%" stop-color="#fcdaa8" />
          <stop offset="55%" stop-color="#f2b774" />
          <stop offset="100%" stop-color="#e79a50" />
        </radialGradient>
        <radialGradient id="catBelly" cx="50%" cy="30%" r="80%">
          <stop offset="0%" stop-color="#fdf0dc" />
          <stop offset="100%" stop-color="#f3dab5" />
        </radialGradient>
      </defs>

      <!-- 尾巴（带虎斑环纹，轻摆） -->
      <g class="cat-tail">
        <path d="M44 80 C57 78 62 67 58.5 55.5 C57.5 52 54.5 50.5 52 51.5"
          fill="none" stroke="#e79a50" stroke-width="8" stroke-linecap="round" />
        <path d="M44 80 C56 78 60.5 68.5 58 57.5" fill="none" stroke="#f2b774" stroke-width="3.5" stroke-linecap="round" />
        <path d="M60.5 62.5 L54 63.5 M59 56.5 L53.5 55" stroke="#d9883c" stroke-width="2" stroke-linecap="round" fill="none" />
      </g>

      <!-- 身体 + 肚皮 + 前爪 -->
      <ellipse cx="30" cy="76" rx="17" ry="14" fill="url(#catFur)" />
      <ellipse cx="30" cy="79.5" rx="10" ry="9" fill="url(#catBelly)" />
      <ellipse cx="22" cy="86.5" rx="4.6" ry="3.2" fill="#e79a50" />
      <ellipse cx="36" cy="86.5" rx="4.6" ry="3.2" fill="#e79a50" />
      <path d="M21 85 v3 M23.4 85 v3 M35 85 v3 M37.4 85 v3" stroke="#d9883c" stroke-width="0.9" stroke-linecap="round" fill="none" />

      <!-- 耳朵（圆润三角 + 粉色内耳，头顶后方） -->
      <path d="M13 33 C11 23 10 14 13 8 C19 12 24 17 27 22 C22 24 16 27 13 33 Z" fill="url(#catFur)" />
      <path d="M15 28 C14 21 14 15 15.5 11 C19 14 22 17 24 20 C21 21 17 24 15 28 Z" fill="#f7b8c4" />
      <path d="M51 33 C53 23 54 14 51 8 C45 12 40 17 37 22 C42 24 48 27 51 33 Z" fill="url(#catFur)" />
      <path d="M49 28 C50 21 50 15 48.5 11 C45 14 42 17 40 20 C43 21 47 24 49 28 Z" fill="#f7b8c4" />

      <!-- 头（带脸颊毛簇） -->
      <path d="M32 25 C45 25 55 33 55 45 C55 52 52 58 47 61.5 C42 64.5 37 66 32 66
               C27 66 22 64.5 17 61.5 C12 58 9 52 9 45 C9 33 19 25 32 25 Z" fill="url(#catFur)" />
      <path d="M10.5 49 L5 53.5 L11 54.5 Z" fill="#e79a50" />
      <path d="M53.5 49 L59 53.5 L53 54.5 Z" fill="#e79a50" />

      <!-- 虎斑：额头 M 纹 + 脸颊纹 -->
      <path d="M28.5 28.5 v4.5 M32 28 v5.5 M35.5 28.5 v4.5" stroke="#d9883c" stroke-width="1.6" stroke-linecap="round" fill="none" />
      <path d="M12.5 43 L7 41.8 M13 48 L7.5 49.5 M51.5 43 L57 41.8 M51 48 L56.5 49.5" stroke="#d9883c" stroke-width="1.4" stroke-linecap="round" fill="none" />

      <!-- 白色吻部 + 鼻 + 人中 + 嘴线 + 胡须 -->
      <ellipse cx="32" cy="55" rx="11" ry="8" fill="url(#catBelly)" />
      <path d="M28.8 49.5 Q32 48.4 35.2 49.5 Q34 53 32 53.3 Q30 53 28.8 49.5 Z" fill="#e87c94" />
      <ellipse cx="30.6" cy="50" rx="1" ry="0.6" fill="#ffffff" opacity="0.7" />
      <path d="M32 53.3 v2.2 M32 55.5 Q28.5 58 26.2 56.6 M32 55.5 Q35.5 58 37.8 56.6" stroke="#b06a3f" stroke-width="1.2" stroke-linecap="round" fill="none" />
      <path d="M15 50 L4 47.2 M15 54 L3.6 54 M15 58 L5 61 M49 50 L60 47.2 M49 54 L60.4 54 M49 58 L59 61"
        stroke="rgba(122,92,72,0.55)" stroke-width="1" stroke-linecap="round" fill="none" />

      <!-- 顶光 -->
      <ellipse cx="21" cy="33" rx="8" ry="4" fill="#ffffff" opacity="0.3" transform="rotate(-18 21 33)" />
    </svg>

    <!-- DOM 表情层：眼/嘴/腮红（坐标与旧版一致，表情系统 mood-* 与 working 不受影响） -->
    <div class="cat-head">
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="cat-mouth"></span>
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

/* 透明表情层：保持旧版头部位姿，供 mood 系列/working 表情规则定位 */
.cat-head {
  position: absolute;
  top: 26px;
  left: 6px;
  width: 52px;
  height: 44px;
  z-index: 2;
}

.eye {
  position: absolute;
  top: 19px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.6s infinite;
}

.eye-l { left: 14px; }
.eye-r { right: 14px; }

.cat-mouth {
  position: absolute;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  width: 12px;
  height: 6px;
  border-bottom: 2px solid #7a5c48;
  border-radius: 0 0 12px 12px;
}

.blush {
  position: absolute;
  top: 27px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.5);
}

.b-l { left: 3px; }
.b-r { right: 3px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 尾巴轻摆（SVG 内部，闲时） */
.creature:not(.working) .cat-tail {
  transform-box: fill-box;
  transform-origin: left bottom;
  animation: tail-sway 2.4s ease-in-out infinite;
}

@keyframes tail-sway {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-6deg); }
}

/* 工作中：眼睛变开心弧线 + 尾巴加速 */
.creature.working .eye {
  width: 10px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 21px;
}

.creature.working .cat-tail {
  transform-box: fill-box;
  transform-origin: left bottom;
  animation: tail-sway 0.8s ease-in-out infinite;
}
</style>
