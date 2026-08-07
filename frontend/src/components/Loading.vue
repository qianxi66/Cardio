<template>
  <n-spin :show="loadingDebounced">
    <template #description>
      <slot name="description"> </slot>
    </template>
    <slot v-if="hasData"> </slot>
    <!-- Distinguish "finished loading, nothing to show" from "still loading". Keying the
         placeholder off hasData alone meant an empty result set rendered the loading
         skeleton forever. Only applies when an `empty` slot is supplied, so callers
         without one keep the previous behaviour. -->
    <slot v-else-if="!loading && $slots.empty" name="empty"></slot>
    <slot v-else name="loading">
      <n-skeleton v-if="!hasData" text :repeat="3"></n-skeleton>
    </slot>
  </n-spin>
</template>

<script lang="ts" setup>
import { useDebounce } from "@vueuse/core";
import { toRef } from "vue";

const props = withDefaults(
  defineProps<{
    loading: boolean;
    hasData: boolean;
    debounceMs?: number;
  }>(),
  {
    debounceMs: 0,
  },
);
const loadingDebounced = useDebounce<boolean>(
  toRef(props, "loading"),
  props.debounceMs,
);
</script>
