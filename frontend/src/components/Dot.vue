<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
import { stateColors, stateMessages } from '@/config'
import { type ButtonProps } from 'naive-ui'
import { ref, computed } from 'vue'

type ButtonThemeOverrides = NonNullable<ButtonProps['themeOverrides']>
const props = withDefaults(
  defineProps<{ loading?: boolean; state?: number; editable?: boolean; reviewable?: boolean }>(),
  {
    loading: false,
    state: 0,
    editable: false,
    reviewable: false
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
  <div v-if="!editable">
    <div
      class="dot"
      v-if="!props.loading && props.state >= 0"
      :style="{
        '--color': stateColors[props.state!]
      }"
    ></div>
    <n-icon class="dot" v-else-if="!props.loading && props.state == -1">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        xmlns:xlink="http://www.w3.org/1999/xlink"
        viewBox="0 0 512 512"
      >
        <path
          d="M256 8C119.033 8 8 119.033 8 256s111.033 248 248 248s248-111.033 248-248S392.967 8 256 8zm0 48c110.532 0 200 89.451 200 200c0 110.532-89.451 200-200 200c-110.532 0-200-89.451-200-200c0-110.532 89.451-200 200-200m140.204 130.267l-22.536-22.718c-4.667-4.705-12.265-4.736-16.97-.068L215.346 303.697l-59.792-60.277c-4.667-4.705-12.265-4.736-16.97-.069l-22.719 22.536c-4.705 4.667-4.736 12.265-.068 16.971l90.781 91.516c4.667 4.705 12.265 4.736 16.97.068l172.589-171.204c4.704-4.668 4.734-12.266.067-16.971z"
          fill="currentColor"
        ></path>
      </svg>
    </n-icon>
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
        <Dot :state="props.state" :loading="props.loading"></Dot>
      </template>
      <n-button-group vertical>
        <n-button
          :theme-overrides="buttonThemeOverrides"
          v-for="state in [0, 1, 2, 3, 4]"
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
            <Dot :state="state"></Dot>
          </template>
          {{ stateMessages[state] }}
        </n-button>
        <n-button
          v-if="props.reviewable"
          @click="
            () => {
              emit('update:state', -1)
              popoverEl.setShow(false)
            }
          "
        >
          <template #icon>
            <Dot :state="-1"></Dot>
          </template>
          Reviewed
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