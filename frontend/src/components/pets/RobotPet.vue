<template>
  <div class="creature robot" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <div class="antenna">
      <span class="antenna-line"></span>
      <span class="antenna-dot"></span>
    </div>
    <div class="pet-head">
      <span class="ear ear-left"></span>
      <div class="face">
        <span class="eye eye-left"></span>
        <span class="eye eye-right"></span>
        <span class="blush blush-left"></span>
        <span class="blush blush-right"></span>
        <span class="mouth"></span>
      </div>
      <span class="ear ear-right"></span>
    </div>
    <div class="pet-torso">
      <span class="hand hand-left"></span>
      <span class="chest"></span>
      <span class="hand hand-right"></span>
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
  display: flex;
  flex-direction: column;
  align-items: center;
}

.antenna {
  position: relative;
  width: 14px;
  height: 14px;
  margin-bottom: -2px;
  flex-shrink: 0;
}

.antenna-line {
  position: absolute;
  left: 50%;
  bottom: 4px;
  transform: translateX(-50%);
  width: 3px;
  height: 10px;
  border-radius: 2px;
  background: linear-gradient(#b3c6e6, #8ba3c9);
}

.antenna-dot {
  position: absolute;
  left: 50%;
  top: -2px;
  transform: translateX(-50%);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #67c23a;
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.8);
}

.pet-head {
  position: relative;
  width: 64px;
  height: 50px;
  background: linear-gradient(160deg, #ffffff 0%, #eef3fb 100%);
  border: 2px solid #c3d2e8;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 -3px 0 rgba(139, 163, 201, 0.25), 0 3px 8px rgba(139, 163, 201, 0.3);
  z-index: 2;
}

.ear {
  position: absolute;
  top: 14px;
  width: 7px;
  height: 18px;
  background: linear-gradient(#a9c0e2, #8ba3c9);
  border-radius: 4px;
}

.ear-left { left: -8px; }
.ear-right { right: -8px; }

.face {
  position: relative;
  width: 46px;
  height: 34px;
}

.eye {
  position: absolute;
  top: 9px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #2c3e50;
  animation: pet-blink 4.2s infinite;
}

.eye-left { left: 7px; }
.eye-right { right: 7px; }

.blush {
  position: absolute;
  top: 18px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.55);
}

.blush-left { left: 1px; }
.blush-right { right: 1px; }

.mouth {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 3px;
  border-radius: 0 0 6px 6px;
  background: #2c3e50;
}

.pet-torso {
  position: relative;
  margin-top: -6px;
  width: 44px;
  height: 32px;
  background: linear-gradient(165deg, #dcebff 0%, #bcd4f5 100%);
  border: 2px solid #a9c0e2;
  border-radius: 12px 12px 10px 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  box-shadow: 0 3px 8px rgba(139, 163, 201, 0.35);
}

.hand {
  position: absolute;
  top: 8px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #a9c0e2;
  border: 2px solid #93aecd;
}

.hand-left { left: -9px; }
.hand-right { right: -9px; }

.chest {
  width: 18px;
  height: 14px;
  border-radius: 5px;
  background: #2c3e50;
  position: relative;
  overflow: hidden;
  box-shadow: inset 0 0 3px rgba(0, 0, 0, 0.6);
}

.chest::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  right: 3px;
  height: 2px;
  border-radius: 1px;
  background: #56e39f;
  animation: chest-scan 1.6s ease-in-out infinite;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

@keyframes chest-scan {
  0% { top: 3px; opacity: 0.4; }
  50% { top: 8px; opacity: 1; }
  100% { top: 3px; opacity: 0.4; }
}

@keyframes antenna-busy {
  0%, 100% { box-shadow: 0 0 4px rgba(230, 162, 60, 0.7); background: #e6a23c; }
  50% { box-shadow: 0 0 10px rgba(245, 108, 108, 0.9); background: #f56c6c; }
}

/* 工作中：眼睛变开心弧线 + 天线橙红快闪 */
.creature.working .eye {
  width: 10px;
  height: 5px;
  background: transparent;
  border: 2px solid #2c3e50;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 11px;
}

.creature.working .antenna-dot {
  background: #e6a23c;
  animation: antenna-busy 0.8s ease-in-out infinite;
}
</style>
