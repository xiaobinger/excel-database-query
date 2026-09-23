<template>
  <div class="creature" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <span class="fox-tail"></span>
    <div class="fox-body">
      <span class="fox-chest"></span>
    </div>
    <div class="fox-head">
      <span class="fox-ear ear-l"><i class="inner"></i></span>
      <span class="fox-ear ear-r"><i class="inner"></i></span>
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="fox-muzzle"></span>
      <span class="fox-nose"></span>
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

.fox-head {
  position: absolute;
  top: 24px;
  left: 6px;
  width: 52px;
  height: 44px;
  background: linear-gradient(170deg, #f49a4e 0%, #ef8b3f 100%);
  border-radius: 50% 50% 44% 44%;
  box-shadow: 0 3px 8px rgba(206, 116, 44, 0.35);
  z-index: 2;
}

.fox-ear {
  position: absolute;
  top: -15px;
  width: 0;
  height: 0;
  border-left: 11px solid transparent;
  border-right: 11px solid transparent;
  border-bottom: 20px solid #ef8b3f;
}

.ear-l { left: -1px; }
.ear-r { right: -1px; }

.fox-ear .inner {
  position: absolute;
  left: -5px;
  top: 6px;
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-bottom: 11px solid #5d4633;
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

.fox-muzzle {
  position: absolute;
  bottom: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 30px;
  height: 19px;
  background: #fff7ef;
  border-radius: 50% 50% 45% 45%;
}

.fox-nose {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  width: 7px;
  height: 6px;
  background: #3b2f2a;
  border-radius: 50%;
  z-index: 1;
}

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

.fox-body {
  position: absolute;
  top: 66px;
  left: 13px;
  width: 38px;
  height: 26px;
  background: linear-gradient(175deg, #f49a4e 0%, #e57e30 100%);
  border-radius: 14px 14px 11px 11px;
  box-shadow: 0 3px 8px rgba(206, 116, 44, 0.35);
  z-index: 1;
  overflow: hidden;
}

.fox-chest {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 20px;
  height: 16px;
  background: #fff7ef;
  border-radius: 50%;
}

.fox-tail {
  position: absolute;
  top: 68px;
  right: -8px;
  width: 15px;
  height: 30px;
  background: #ef8b3f;
  border-radius: 10px;
  transform-origin: top center;
  transform: rotate(-22deg);
  animation: tail-sway 2.2s ease-in-out infinite;
  z-index: 0;
}

.fox-tail::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 15px;
  height: 13px;
  background: #fff7ef;
  border-radius: 0 0 10px 10px;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

@keyframes tail-sway {
  0%, 100% { transform: rotate(-22deg); }
  50% { transform: rotate(-40deg); }
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
  animation: tail-sway 0.7s ease-in-out infinite;
}
</style>
