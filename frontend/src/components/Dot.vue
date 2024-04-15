<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
const props = withDefaults(defineProps<{ loading?: boolean; state?: number }>(), {
  loading: false,
  state: 0
})
</script>
<template>
  <div
    class="dot"
    v-if="!props.loading"
    :style="{
      '--color': ['#c1b9b6', '#4ca851', '#6283ac', '#f9d965', '#eb4c44'][props.state!]
    }"
  ></div>
  <n-skeleton v-else box style="height: 24px; width: 24px; border-radius: 50%" />
</template>

<style scoped lang="scss">
.dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--color);
  border-color: gray;
  box-sizing: border-box;
}
</style>
