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
  const tokenValue = typeof token.value === "string" ? token.value.trim() : "";
  const storageToken = (localStorage.getItem("token") || "").trim();
  const hasToken = tokenValue !== "" || storageToken !== "";
  return hasToken && route.path !== "/login";
});

const showPatientMenuButton = computed(() => {
  const tokenValue = typeof token.value === "string" ? token.value.trim() : "";
  const storageToken = (localStorage.getItem("token") || "").trim();
  const hasToken = tokenValue !== "" || storageToken !== "";
  return hasToken && route.path !== "/login";
});

const togglePatientSidebar = () => {
  window.dispatchEvent(new Event("toggle-patient-sidebar"));
};

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
      <button
        v-if="showPatientMenuButton"
        type="button"
        class="menu-trigger"
        aria-label="Toggle patient list"
        @click="togglePatientSidebar"
      >
        ≡
      </button>
      <a
        class="title"
        href="#"
        style="color: inherit; text-decoration: none"
        @click.prevent="$router.push('/')"
      >
        Cardiotoxicity Monitoring Dashboard
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

  .menu-trigger {
    border: none;
    background: transparent;
    color: #ffffff;
    font-size: 30px;
    line-height: 1;
    padding: 0 8px 2px 12px;
    margin-right: 12px;
    cursor: pointer;
  }

  .space {
    flex: 1;
  }
  height: 45px;

  :deep(.n-menu) {
    flex: auto 0 0;
    height: 45px;
    .n-menu-item {
      height: 45px;
    }
  }
}

@media (max-width: 1100px) {
  .header {
    height: 40px;
    .menu-trigger {
      font-size: 24px;
      margin-right: 8px;
      padding: 0 8px 2px 10px;
    }
    .title {
      margin-left: 0;
      font-size: 13px;
      line-height: 1.2;
    }
  }
}

header {
  display: flex;
  justify-content: center;
  margin-bottom: 0;
  background-color: #383838;
  color: white;
}
</style>