<template>
  <div class="creature" :class="[{ working }, 'mood-' + (mood || 'normal')]">
    <div class="panda-body">
      <span class="panda-belly"></span>
    </div>
    <div class="panda-head">
      <span class="panda-ear ear-l"></span>
      <span class="panda-ear ear-r"></span>
      <span class="eye-patch patch-l"><i class="eye"></i></span>
      <span class="eye-patch patch-r"><i class="eye"></i></span>
      <span class="panda-nose"></span>
      <span class="panda-mouth"></span>
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

.panda-head {
  position: absolute;
  top: 22px;
  left: 5px;
  width: 54px;
  height: 48px;
  background: linear-gradient(170deg, #ffffff 0%, #f2f4f7 100%);
  border: 2px solid #dfe3e8;
  border-radius: 50%;
  box-shadow: 0 3px 8px rgba(120, 130, 145, 0.28);
  z-index: 2;
}

.panda-ear {
  position: absolute;
  top: -7px;
  width: 17px;
  height: 17px;
  background: #3a3f45;
  border-radius: 50%;
}

.ear-l { left: -1px; }
.ear-r { right: -1px; }

.eye-patch {
  position: absolute;
  top: 13px;
  width: 16px;
  height: 12px;
  background: #3a3f45;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.patch-l { left: 7px; transform: rotate(14deg); }
.patch-r { right: 7px; transform: rotate(-14deg); }

.eye-patch .eye {
  width: 5px;
  height: 5px;
  background: #ffffff;
  border-radius: 50%;
  animation: pet-blink 4.8s infinite;
}

.panda-nose {
  position: absolute;
  top: 26px;
  left: 50%;
  transform: translateX(-50%);
  width: 8px;
  height: 6px;
  background: #3a3f45;
  border-radius: 4px;
}

.panda-mouth {
  position: absolute;
  top: 33px;
  left: 50%;
  transform: translateX(-50%);
  width: 10px;
  height: 5px;
  border-bottom: 2px solid #3a3f45;
  border-radius: 0 0 10px 10px;
}

.panda-body {
  position: absolute;
  top: 66px;
  left: 12px;
  width: 40px;
  height: 26px;
  background: linear-gradient(175deg, #4a5057 0%, #3a3f45 100%);
  border-radius: 14px 14px 11px 11px;
  box-shadow: 0 3px 8px rgba(90, 98, 108, 0.35);
  z-index: 1;
  overflow: hidden;
}

.panda-belly {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 18px;
  background: #f2f4f7;
  border-radius: 50%;
}

@keyframes pet-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.1); }
}

/* 工作中：眼白变星星亮色 + 耳朵快速小幅摆动 */
.creature.working .eye-patch .eye {
  background: #ffd34d;
  box-shadow: 0 0 5px rgba(255, 211, 77, 0.9);
  animation: none;
}

.creature.working .panda-ear {
  animation: ear-bounce 0.8s ease-in-out infinite;
}

@keyframes ear-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}
</style>
