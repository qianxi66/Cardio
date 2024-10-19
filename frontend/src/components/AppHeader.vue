<script setup lang="tsx">
import { computed } from "vue";
import { useDialog, useMessage } from "naive-ui";
import { useRouter, useRoute } from "vue-router";
import { useStorage } from "@vueuse/core";

const router = useRouter();
const route = useRoute();

const dialog = useDialog();
const message = useMessage();
window.$message = message;
window.$dialog = dialog;

const token = useStorage("token", "", localStorage);

const showLogoutButton = computed(() => {
  return token.value !== "" && route.path !== "/login";
});

const handleLogout = () => {
  dialog.warning({
    title: "Confirm Logout",
    content: "Are you sure you want to log out?",
    positiveText: "Confirm",
    negativeText: "Cancel",
    onPositiveClick: () => {
      localStorage.removeItem("token");
      router.push("/login");
      message.success("You have been logged out.");
    },
    onNegativeClick: () => {
      message.info("Logout canceled.");
    },
  });
};
</script>

<template>
  <header>
    <div class="container header">
      <a
        class="title"
        href="#"
        style="color: inherit; text-decoration: none"
        @click.prevent="$router.push('/')"
      >
        Elderly Care
      </a>
      <div class="space"></div>
      <div v-if="showLogoutButton" style="margin-right: 20px">
        <n-button text color="#fff" @click="handleLogout">logout</n-button>
      </div>
    </div>
  </header>
</template>

<style lang="scss">
.header {
  display: flex;
  flex-wrap: wrap;
  flex-direction: row;
  align-content: center;
  justify-content: flex-start;
  align-items: center;

  .title {
    margin-left: 25px;
    font-size: 25px;
  }

  .space {
    flex: 1;
  }
  height: 60px;

  :deep(.n-menu) {
    flex: auto 0 0;
    height: 60px;
    .n-menu-item {
      height: 60px;
    }
  }
}

header {
  display: flex;
  justify-content: center;
  margin-bottom: 8px;
  background-color: #041527;
  color: white;
}
</style>
