<template>
  <div class="creature" :class="{ working }">
    <span class="cat-tail"></span>
    <div class="cat-body">
      <span class="cat-belly"></span>
    </div>
    <div class="cat-head">
      <span class="cat-ear ear-left"><i class="inner"></i></span>
      <span class="cat-ear ear-right"><i class="inner"></i></span>
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="cat-nose"></span>
      <span class="cat-mouth"></span>
      <span class="whisker w-l1"></span>
      <span class="whisker w-l2"></span>
      <span class="whisker w-r1"></span>
      <span class="whisker w-r2"></span>
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
  height: 92px;
}

.cat-head {
  position: absolute;
  top: 26px;
  left: 6px;
  width: 52px;
  height: 44px;
  background: linear-gradient(170deg, #f8cf9a 0%, #f0b269 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 8px rgba(222, 158, 88, 0.35);
  z-index: 2;
}

.cat-ear {
  position: absolute;
  top: -13px;
  width: 0;
  height: 0;
  border-left: 11px solid transparent;
  border-right: 11px solid transparent;
  border-bottom: 17px solid #eda45f;
}

.ear-left { left: -1px; }
.ear-right { right: -1px; }

.cat-ear .inner {
  position: absolute;
  left: -6px;
  top: 5px;
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 10px solid #f7b8c4;
}

.eye {
  position: absolute;
  top: 15px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.6s infinite;
}

.eye-l { left: 12px; }
.eye-r { right: 12px; }

.cat-nose {
  position: absolute;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 5px solid #e87c94;
}

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

.whisker {
  position: absolute;
  width: 12px;
  height: 2px;
  border-radius: 2px;
  background: rgba(122, 92, 72, 0.45);
}

.w-l1 { top: 21px; left: -9px; transform: rotate(9deg); }
.w-l2 { top: 27px; left: -8px; transform: rotate(-8deg); }
.w-r1 { top: 21px; right: -9px; transform: rotate(-9deg); }
.w-r2 { top: 27px; right: -8px; transform: rotate(8deg); }

.blush {
  position: absolute;
  top: 25px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.5);
}

.b-l { left: 4px; }
.b-r { right: 4px; }

.cat-body {
  position: absolute;
  top: 66px;
  left: 14px;
  width: 38px;
  height: 26px;
  background: linear-gradient(175deg, #f5c288 0%, #eda45f 100%);
  border-radius: 14px 14px 11px 11px;
  box-shadow: 0 3px 8px rgba(222, 158, 88, 0.35);
  z-index: 1;
  overflow: hidden;
}

.cat-belly {
  position: absolute;
  bottom: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 22px;
  height: 16px;
  background: #fbe8cc;
  border-radius: 50%;
}

.cat-tail {
  position: absolute;
  top: 72px;
  right: -4px;
  width: 26px;
  height: 10px;
  background: #eda45f;
  border-radius: 8px;
  transform-origin: left center;
  transform: rotate(-16deg);
  animation: tail-sway 2.4s ease-in-out infinite;
  z-index: 0;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

@keyframes tail-sway {
  0%, 100% { transform: rotate(-16deg); }
  50% { transform: rotate(-34deg); }
}

/* 工作中：眼睛变开心弧线 + 耳朵抖动 */
.creature.working .eye {
  width: 10px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 17px;
}

.creature.working .cat-ear {
  animation: ear-twitch 0.9s ease-in-out infinite;
}

@keyframes ear-twitch {
  0%, 100% { transform: rotate(0deg); }
  30% { transform: rotate(-7deg); }
  70% { transform: rotate(5deg); }
}
</style>
