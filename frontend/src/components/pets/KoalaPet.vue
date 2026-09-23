<template>
  <div class="creature koala" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <div class="koala-body">
      <span class="koala-belly"></span>
    </div>
    <div class="koala-head">
      <span class="koala-ear ear-l"><i class="fluff"></i></span>
      <span class="koala-ear ear-r"><i class="fluff"></i></span>
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

.koala-head {
  position: absolute;
  top: 24px;
  left: 8px;
  width: 48px;
  height: 44px;
  background: linear-gradient(170deg, #b8c2cd 0%, #a8b4c2 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 8px rgba(138, 152, 168, 0.4);
  z-index: 2;
}

.koala-ear {
  position: absolute;
  top: -8px;
  width: 26px;
  height: 26px;
  background: #9aa7b5;
  border: 2px solid #8d99a8;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ear-l { left: -14px; }
.ear-r { right: -14px; }

.koala-ear .fluff {
  width: 16px;
  height: 16px;
  background: #d6dde4;
  border-radius: 50%;
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
  box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.15);
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

.koala-body {
  position: absolute;
  top: 66px;
  left: 13px;
  width: 38px;
  height: 26px;
  background: linear-gradient(175deg, #b8c2cd 0%, #a0adb9 100%);
  border-radius: 14px 14px 11px 11px;
  box-shadow: 0 3px 8px rgba(138, 152, 168, 0.4);
  z-index: 1;
  overflow: hidden;
}

.koala-belly {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 22px;
  height: 16px;
  background: #d6dde4;
  border-radius: 50%;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：大耳朵扑扇 */
.creature.working .koala-ear {
  animation: ear-flap 0.85s ease-in-out infinite;
}

.creature.working .ear-l { animation-name: ear-flap-l; }
.creature.working .ear-r { animation-name: ear-flap-r; }

@keyframes ear-flap-l {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(-9deg); }
}

@keyframes ear-flap-r {
  0%, 100% { transform: rotate(0deg); }
  50% { transform: rotate(9deg); }
}
</style>
