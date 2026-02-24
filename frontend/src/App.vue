<script setup lang="ts">
import type { GlobalThemeOverrides } from "naive-ui";
import { NConfigProvider } from "naive-ui";

const themeOverrides: GlobalThemeOverrides = {
  common: {
    bodyColor: "#e6e6e6",
  },
  Button: {
    color: "white",
  },
};
</script>

<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <RouterView></RouterView>
          <n-global-style></n-global-style>
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.n-config-provider {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  justify-content: flex-start;
}
</style>
