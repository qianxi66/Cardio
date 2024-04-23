<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
import { stateColors } from '@/config'
const props = withDefaults(defineProps<{ loading?: boolean; state?: number; color: string }>(), {
  loading: false,
  state: 0
})
</script>
<template>
  <div>
    <div
      class="dot"
      v-if="!props.loading && props.state >= 0"
      :style="{
        '--color': [stateColors[0], stateColors[1], props.color][props.state]
      }"
    ></div>
    <n-skeleton v-else box style="height: 24px; width: 24px; border-radius: 50%" />
  </div>
</template>

<style scoped lang="scss">
* {
  line-height: 1;
}
.dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--color);
  border-color: gray;
  box-sizing: border-box;
  font-size: 24px;
}
:global(.n-icon-slot .dot) {
  width: var(--n-icon-size);
  height: var(--n-icon-size);
  font-size: var(--n-icon-size);
}
.n-button {
  --n-color: white !important;
  --n-color-hover: white !important;
  --n-color-pressed: white !important;
  --n-color-focus: white !important;
  --n-color-disabled: white !important;
  position: relative;
  :deep(.n-button__content) {
    margin-left: var(--n-icon-size);
  }
  :deep(.n-button__icon) {
    position: absolute;
    left: 0;
    transform: translateX(50%);
  }
}
</style>
