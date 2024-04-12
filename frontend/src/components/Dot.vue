<!-- eslint-disable vue/multi-word-component-names -->
<script setup lang="ts">
const props = defineProps<{
  state: number;
}>();
</script>
<template>
  <div
    class="dot"
    :style="{
      '--color': ['#c1b9b6', '#4ca851', '#6283ac', '#f9d965', '#eb4c44'][
        props.state
      ],
    }"
  ></div>
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
