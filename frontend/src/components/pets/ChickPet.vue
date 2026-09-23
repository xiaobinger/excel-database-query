<template>
  <div class="creature" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <span class="chick-ahoge"></span>
    <div class="chick-blob">
      <span class="chick-wing wing-l"></span>
      <span class="chick-wing wing-r"></span>
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

.chick-ahoge {
  position: absolute;
  top: 13px;
  left: 50%;
  width: 10px;
  height: 9px;
  border-top: 2.5px solid #f0b429;
  border-radius: 50%;
  transform: translateX(-50%) rotate(-24deg);
  z-index: 1;
}

.chick-blob {
  position: absolute;
  top: 18px;
  left: 5px;
  width: 54px;
  height: 62px;
  background: radial-gradient(circle at 38% 30%, #ffe487 0%, #ffd75e 55%, #f8c93f 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 10px rgba(226, 178, 38, 0.4);
  z-index: 2;
}

.chick-wing {
  position: absolute;
  top: 30px;
  width: 12px;
  height: 19px;
  background: #f5c93f;
  border-radius: 50%;
  z-index: 0;
}

.wing-l { left: -4px; transform: rotate(18deg); }
.wing-r { right: -4px; transform: rotate(-18deg); }

.eye {
  position: absolute;
  top: 18px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.2s infinite;
  z-index: 1;
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
  z-index: 1;
}

.blush {
  position: absolute;
  top: 28px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 130, 130, 0.55);
  z-index: 1;
}

.b-l { left: 5px; }
.b-r { right: 5px; }

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：翅膀扑扇 */
.creature.working .chick-wing {
  animation: wing-flap 0.5s ease-in-out infinite;
}

.creature.working .wing-l { animation-name: wing-flap-l; }
.creature.working .wing-r { animation-name: wing-flap-r; }

@keyframes wing-flap-l {
  0%, 100% { transform: rotate(18deg); }
  50% { transform: rotate(42deg); }
}

@keyframes wing-flap-r {
  0%, 100% { transform: rotate(-18deg); }
  50% { transform: rotate(-42deg); }
}
</style>
