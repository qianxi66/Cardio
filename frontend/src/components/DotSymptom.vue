<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
import { stateColors, stateMessages } from '@/config'
import { type ButtonProps } from 'naive-ui'
import { ref } from 'vue'
type ButtonThemeOverrides = NonNullable<ButtonProps['themeOverrides']>
const props = withDefaults(
  defineProps<{ loading?: boolean; state?: number; color: string; editable?: boolean }>(),
  {
    loading: false,
    state: 0,
    editable: false
  }
)
// on edit trigger
const emit = defineEmits(['update:state'])
const buttonThemeOverrides: ButtonThemeOverrides = {
  colorHover: 'white',
  colorPressed: 'white',
  colorFocus: 'white'
}
const popoverEl = ref<HTMLElement | null>(null)
</script>
<template>
  <div v-if="!editable" class="dot-container">
    <div
      class="dot"
      v-if="!props.loading && props.state >= 0"
      :style="{
        '--color': [stateColors[0], stateColors[1], props.color][props.state]
      }"
    ></div>
    <n-skeleton v-else box style="height: 24px; width: 24px; border-radius: 50%" />
  </div>
  <div v-else>
    <n-popover
      ref="popoverEl"
      trigger="click"
      :show-arrow="false"
      raw
      placement="bottom-start"
      :theme-overrides="{ boxShadow: 'none' }"
    >
      <template #trigger>
        <dot-symptom
          :state="props.state"
          :color="props.color"
          :loading="props.loading"
        ></dot-symptom>
      </template>
      <n-button-group vertical>
        <n-button
          :theme-overrides="buttonThemeOverrides"
          v-for="state in [0, 1, 2]"
          :key="state"
          ghost
          :type="props.state === state ? 'info' : 'default'"
          @click="
            () => {
              emit('update:state', state)
              popoverEl.setShow(false)
            }
          "
        >
          <template #icon>
            <dot-symptom :color="color" :state="state"></dot-symptom>
          </template>
          {{ stateMessages[state] }}
        </n-button>
      </n-button-group>
    </n-popover>
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
