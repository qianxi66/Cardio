import "./assets/main.scss";

import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import type { useDialog, useMessage } from "naive-ui";

const app = createApp(App);
declare global {
  interface Window {
    $dialog: ReturnType<typeof useDialog>;
    $message: ReturnType<typeof useMessage>;
  }
}
app.use(router);

app.mount("#app");
