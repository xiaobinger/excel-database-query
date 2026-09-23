<template>
  <div class="creature" :class="{ working }">
    <div class="frog-body">
      <span class="frog-belly"></span>
      <span class="frog-foot foot-l"></span>
      <span class="frog-foot foot-r"></span>
    </div>
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
defineProps({ working: Boolean })
</script>

<style scoped>
.creature {
  position: relative;
  width: 64px;
  height: 88px;
}

.frog-head {
  position: absolute;
  top: 26px;
  left: 4px;
  width: 56px;
  height: 44px;
  background: linear-gradient(170deg, #8fd67e 0%, #82cc72 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 8px rgba(98, 168, 82, 0.35);
  z-index: 2;
}

.eye-bump {
  position: absolute;
  top: -9px;
  width: 18px;
  height: 18px;
  background: #82cc72;
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

.frog-body {
  position: absolute;
  top: 66px;
  left: 12px;
  width: 40px;
  height: 20px;
  background: linear-gradient(175deg, #8fd67e 0%, #74bf64 100%);
  border-radius: 12px 12px 16px 16px;
  box-shadow: 0 3px 8px rgba(98, 168, 82, 0.35);
  z-index: 1;
  overflow: visible;
}

.frog-belly {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 26px;
  height: 14px;
  background: #d6efc8;
  border-radius: 50%;
}

.frog-foot {
  position: absolute;
  bottom: -4px;
  width: 14px;
  height: 8px;
  background: #6db85e;
  border-radius: 8px;
}

.foot-l { left: 0; }
.foot-r { right: 0; }

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
