<script setup lang="ts">
import type { GlobalThemeOverrides } from "naive-ui";
import { NConfigProvider } from "naive-ui";
import AppHeader from "@/components/AppHeader.vue";

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
          <AppHeader />
          <div class="app-body">
            <RouterView></RouterView>
          </div>
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

.app-body {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
