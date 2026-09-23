<template>
  <div class="creature" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <span class="pig-tail"></span>
    <div class="pig-body"></div>
    <div class="pig-head">
      <span class="pig-ear ear-l"></span>
      <span class="pig-ear ear-r"></span>
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

.pig-head {
  position: absolute;
  top: 22px;
  left: 6px;
  width: 52px;
  height: 46px;
  background: linear-gradient(170deg, #fbcdd6 0%, #f7b8c4 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 8px rgba(226, 137, 158, 0.35);
  z-index: 2;
}

.pig-ear {
  position: absolute;
  top: -6px;
  width: 17px;
  height: 15px;
  background: #ef9db0;
  border-radius: 58% 42% 55% 45%;
}

.ear-l { left: -2px; transform: rotate(-22deg); }
.ear-r { right: -2px; transform: rotate(22deg); }

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
  background: #ef9db0;
  border-radius: 50%;
  box-shadow: inset 0 -2px 0 rgba(217, 136, 158, 0.4);
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

.pig-body {
  position: absolute;
  top: 66px;
  left: 13px;
  width: 38px;
  height: 24px;
  background: linear-gradient(175deg, #fbcdd6 0%, #f2aebc 100%);
  border-radius: 13px 13px 11px 11px;
  box-shadow: 0 3px 8px rgba(226, 137, 158, 0.35);
  z-index: 1;
}

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
  z-index: 0;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

@keyframes tail-curl {
  0%, 100% { transform: rotate(38deg) scale(1); }
  50% { transform: rotate(65deg) scale(1.08); }
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
