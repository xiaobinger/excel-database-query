<template>
  <div class="creature" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <span class="bunny-tail"></span>
    <div class="bunny-body">
      <span class="bunny-paw paw-l"></span>
      <span class="bunny-paw paw-r"></span>
    </div>
    <div class="bunny-head">
      <span class="bunny-ear ear-l"><i class="inner"></i></span>
      <span class="bunny-ear ear-r"><i class="inner"></i></span>
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="bunny-nose"></span>
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

.bunny-ear {
  position: absolute;
  top: 0;
  width: 13px;
  height: 36px;
  background: linear-gradient(#ffffff, #f4f0ea);
  border: 2px solid #e3ded6;
  border-radius: 8px;
  z-index: 1;
}

.ear-l { left: 15px; transform: rotate(-7deg); }
.ear-r { right: 15px; transform: rotate(7deg); }

.bunny-ear .inner {
  position: absolute;
  top: 4px;
  left: 50%;
  transform: translateX(-50%);
  width: 6px;
  height: 24px;
  background: #f9cdd6;
  border-radius: 4px;
}

.bunny-head {
  position: absolute;
  top: 32px;
  left: 8px;
  width: 48px;
  height: 42px;
  background: linear-gradient(170deg, #ffffff 0%, #f4f0ea 100%);
  border: 2px solid #e3ded6;
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 8px rgba(180, 170, 158, 0.3);
  z-index: 2;
}

.eye {
  position: absolute;
  top: 14px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.4s infinite;
}

.eye-l { left: 11px; }
.eye-r { right: 11px; }

.bunny-nose {
  position: absolute;
  top: 23px;
  left: 50%;
  transform: translateX(-50%);
  width: 7px;
  height: 5px;
  background: #e87c94;
  border-radius: 50% 50% 60% 60%;
}

.bunny-mouth {
  position: absolute;
  top: 29px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 5px;
  border-bottom: 2px solid #a58d7a;
  border-radius: 0 0 10px 10px;
}

.blush {
  position: absolute;
  top: 22px;
  width: 8px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.5);
}

.b-l { left: 3px; }
.b-r { right: 3px; }

.bunny-body {
  position: absolute;
  top: 72px;
  left: 14px;
  width: 36px;
  height: 26px;
  background: linear-gradient(175deg, #ffffff 0%, #f0ebe4 100%);
  border: 2px solid #e3ded6;
  border-radius: 13px 13px 11px 11px;
  box-shadow: 0 3px 8px rgba(180, 170, 158, 0.3);
  z-index: 1;
}

.bunny-paw {
  position: absolute;
  bottom: -3px;
  width: 11px;
  height: 9px;
  background: #ffffff;
  border: 2px solid #e3ded6;
  border-radius: 50%;
}

.paw-l { left: 3px; }
.paw-r { right: 3px; }

.bunny-tail {
  position: absolute;
  top: 78px;
  right: 3px;
  width: 13px;
  height: 13px;
  background: radial-gradient(circle at 35% 35%, #ffffff, #ece7df);
  border: 2px solid #e3ded6;
  border-radius: 50%;
  z-index: 0;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：眼睛变开心弧线 + 耳朵竖动 */
.creature.working .eye {
  width: 10px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 16px;
}

.creature.working .ear-l { animation: ear-l-wag 0.9s ease-in-out infinite; }
.creature.working .ear-r { animation: ear-r-wag 0.9s ease-in-out infinite; }

@keyframes ear-l-wag {
  0%, 100% { transform: rotate(-7deg); }
  50% { transform: rotate(-13deg); }
}

@keyframes ear-r-wag {
  0%, 100% { transform: rotate(7deg); }
  50% { transform: rotate(13deg); }
}
</style>
