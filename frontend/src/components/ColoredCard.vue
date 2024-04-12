<script setup lang="tsx">
import { type CardProps } from "naive-ui";
import { computed } from "vue";
const props = defineProps<{
  title?: string;
  color?: string;
  rounded?: boolean;
}>();
type CardThemeOverrudes = NonNullable<CardProps["themeOverrides"]>;
const themeOverrides: CardThemeOverrudes = {
  borderRadius: "0px",
};

const title = computed(() => {
  return props.rounded ? null : props.title;
});
</script>
<template>
  <n-card
    :class="{
      'color-card': !!props.color,
      'rounded-card': !!props.rounded,
    }"
    :title="title"
    :theme-overrides="themeOverrides"
    :style="{
      '--card-color': props.color,
    }"
  >
    <div
      v-if="rounded"
      className="roundtag"
      :style="{ '--color': props.color, '--white-ratio': '75%' }"
    >
      <div className="roundtag__label">
        {{ props.title }}
      </div>
      <div className="roundtag__round"></div>
    </div>
    <slot></slot>
  </n-card>
</template>
<style scoped lang="scss">
.n-card {
  border: none;
  box-shadow: 4px 4px 4px rgba(0, 0, 0, 0.1);
  background-color: white;
  position: relative !important;
}
.n-card.color-card {
  border-left: 8px solid var(--card-color);
  padding-top: 34px;
}
.roundtag {
  font-weight: 500;
  font-size: 18px;
  display: flex;
  position: absolute;
  top: 0px;
  left: 0px;
}

.roundtag__label {
  background-color: color-mix(in srgb, var(--color), white var(--white-ratio));
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 10px;
  height: 34px;
}

.roundtag__round {
  background-color: color-mix(in srgb, var(--color), white var(--white-ratio));
  display: inline-block;
  border-radius: 0 17px 17px 0;
  width: 17px;
  height: 34px;
  z-index: 2;
  position: relative;
}

.roundtag:not(:first-child) .roundtag__label {
  position: relative;
  z-index: 1;
  margin-left: -34px;
  padding-left: 49px;
}
</style>
