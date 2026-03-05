<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
import { stateColors, stateMessages } from "@/symptoms";
import { type ButtonProps } from "naive-ui";
import { ref, computed } from "vue";

type ButtonThemeOverrides = NonNullable<ButtonProps["themeOverrides"]>;
const props = withDefaults(
  defineProps<{
    loading?: boolean;
    state?: number;
    editable?: boolean;
    reviewable?: boolean;
    isRead?: boolean | number;
    variant?: 'default' | 'wearable' | 'circle';
  }>(),
  {
    loading: false,
    state: 0,
    editable: false,
    reviewable: false,
    isRead: 0,
    variant: 'default',
  },
);
// on edit trigger
const emit = defineEmits(["update:state"]);
const buttonThemeOverrides: ButtonThemeOverrides = {
  colorHover: "white",
  colorPressed: "white",
  colorFocus: "white",
};
const popoverEl = ref<{ setShow: (value: boolean) => void } | null>(null);
const dotColor = computed(() => {
  if (props.state === undefined || props.state < 0) return "#1C274C";
  return stateColors[props.state] || stateColors[0];
});
</script>

<template>
  <div v-if="!editable">
    <div
      class="dot"
      v-if="!props.loading && props.state >= 0"
    >
      <!-- circle variant (also used for wearable to keep unified look) -->
      <span
        v-if="props.variant === 'wearable' || props.variant === 'circle'"
        class="dot-circle-fill"
        :style="{ '--dot-color': dotColor }"
      ></span>
      <!-- default variant: chat bubble -->
      <svg
        v-else
        class="dot-svg"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 13.5997 2.37562 15.1116 3.04346 16.4525C3.22094 16.8088 3.28001 17.2161 3.17712 17.6006L2.58151 19.8267C2.32295 20.793 3.20701 21.677 4.17335 21.4185L6.39939 20.8229C6.78393 20.72 7.19121 20.7791 7.54753 20.9565C8.88837 21.6244 10.4003 22 12 22Z"
          :fill="dotColor"
        />
      </svg>
    </div>
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
    <n-skeleton
      v-else
      box
      style="height: 16px; width: 16px; border-radius: 50%"
    />
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
        <Dot :state="props.state" :loading="props.loading" :is-read="props.isRead" :variant="props.variant"></Dot>
      </template>
      <n-button-group vertical>
        <n-button
          :theme-overrides="buttonThemeOverrides"
          v-for="state in [0, 1, 2, 3]"
          :key="state"
          ghost
          :type="props.state === state ? 'info' : 'default'"
          @click="
            () => {
              emit('update:state', state);
              popoverEl?.setShow(false);
            }
          "
        >
          <template #icon>
            <Dot :state="state" :is-read="1" :variant="props.variant"></Dot>
          </template>
          {{ stateMessages[state] }}
        </n-button>
        <n-button
          v-if="props.reviewable"
          @click="
            () => {
              emit('update:state', -1);
              popoverEl?.setShow(false);
            }
          "
        >
          <template #icon>
            <Dot :state="-1" :is-read="1" :variant="props.variant"></Dot>
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
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  font-size: 16px;
  border-radius: 50%;
  transform: scale(1);
  transition: transform 0.12s ease, filter 0.12s ease;
}
.dot:hover {
  transform: scale(1.2);
  filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.35));
}
.dot:active {
  transform: scale(1.2);
  filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.35));
}
.dot-svg {
  width: 100%;
  height: 100%;
  display: block;
}
.dot-circle-fill {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--dot-color);
  display: block;
}
:global(.n-icon-slot .dot) {
  width: calc(var(--n-icon-size) * 1.3);
  height: calc(var(--n-icon-size) * 1.3);
  font-size: calc(var(--n-icon-size) * 1.3);
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
