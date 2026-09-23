<template>
  <div class="creature" :class="{ working }">
    <div class="bear-body">
      <span class="bear-belly"></span>
    </div>
    <div class="bear-head">
      <span class="bear-ear ear-l"><i class="inner"></i></span>
      <span class="bear-ear ear-r"><i class="inner"></i></span>
      <span class="eye eye-l"></span>
      <span class="eye eye-r"></span>
      <span class="bear-muzzle">
        <i class="bear-nose"></i>
        <i class="bear-mouth"></i>
      </span>
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

.bear-head {
  position: absolute;
  top: 22px;
  left: 6px;
  width: 52px;
  height: 46px;
  background: linear-gradient(170deg, #c9955f 0%, #b98a5a 100%);
  border-radius: 50% 50% 46% 46%;
  box-shadow: 0 3px 8px rgba(160, 116, 70, 0.35);
  z-index: 2;
}

.bear-ear {
  position: absolute;
  top: -6px;
  width: 16px;
  height: 16px;
  background: #a87747;
  border-radius: 50%;
}

.ear-l { left: -2px; }
.ear-r { right: -2px; }

.bear-ear .inner {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 8px;
  height: 8px;
  background: #e2c39a;
  border-radius: 50%;
}

.eye {
  position: absolute;
  top: 14px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b2f2a;
  animation: pet-blink 4.5s infinite;
}

.eye-l { left: 10px; }
.eye-r { right: 10px; }

.bear-muzzle {
  position: absolute;
  top: 23px;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 17px;
  background: #ecd9bc;
  border-radius: 50%;
}

.bear-nose {
  position: absolute;
  top: 2px;
  left: 50%;
  transform: translateX(-50%);
  width: 8px;
  height: 6px;
  background: #6b4a2e;
  border-radius: 4px;
}

.bear-mouth {
  position: absolute;
  top: 9px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 5px;
  border-bottom: 2px solid #8a6a4c;
  border-radius: 0 0 10px 10px;
}

.blush {
  position: absolute;
  top: 24px;
  width: 7px;
  height: 4px;
  border-radius: 50%;
  background: rgba(255, 122, 150, 0.45);
}

.b-l { left: 3px; }
.b-r { right: 3px; }

.bear-body {
  position: absolute;
  top: 66px;
  left: 12px;
  width: 40px;
  height: 26px;
  background: linear-gradient(175deg, #c9955f 0%, #ab7c4e 100%);
  border-radius: 14px 14px 11px 11px;
  box-shadow: 0 3px 8px rgba(160, 116, 70, 0.35);
  z-index: 1;
  overflow: hidden;
}

.bear-belly {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 18px;
  background: #ecd9bc;
  border-radius: 50%;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：眼睛变开心弧线 */
.creature.working .eye {
  width: 9px;
  height: 5px;
  background: transparent;
  border: 2px solid #3b2f2a;
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  animation: none;
  top: 16px;
}
</style>
