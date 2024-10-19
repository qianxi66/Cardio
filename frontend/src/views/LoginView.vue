<template>
  <div class="holder">
    <n-card class="login-container">
      <n-h2>Login</n-h2>
      <n-form>
        <n-form-item label="Username">
          <n-input v-model:value="username" placeholder="Enter your username" />
        </n-form-item>
        <n-form-item label="Password">
          <n-input
            type="password"
            v-model:value="password"
            placeholder="Enter your password"
          />
        </n-form-item>
        <div class="row" style="margin-bottom: 24px">
          <n-checkbox v-model:checked="Rememberme">Remember Me</n-checkbox>
        </div>
        <div class="row">
          <n-button
            :loading="loading"
            attr-type="submit"
            type="info"
            @click="handleLogin"
            style="width: 100%"
          >
            Login
          </n-button>
        </div>
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="tsx">
import { ref } from "vue";
import axios from "axios";
import { useRouter } from "vue-router";
import { login } from "@/api/user";

const router = useRouter();
const username = ref("");
const password = ref("");
const Rememberme = ref(false);
const loading = ref(false);

const handleLogin = async () => {
  try {
    loading.value = true;
    const response = await login(
      username.value,
      password.value,
      Rememberme.value,
    );
    loading.value = false;
    if (Object.prototype.hasOwnProperty.call(response, "message")) {
      console.log(response);
      if (response.message == "WRONG USERNAME") {
        window.$dialog.error({
          title: "Wrong Username",
          content: "Please check your username and password",
          positiveText: "Continue",
        });
      } else if (response.message == "WRONG PASSWORD") {
        window.$dialog.error({
          title: "Wrong Password",
          content: "Please check your username and password",
          positiveText: "Continue",
        });
      }
    } else {
      const { token, userid } = response.token;
      localStorage.setItem("token", token);
      console.log(localStorage.getItem("token"));
      router.push("/patient");
    }
  } catch (error: any) {
    loading.value = false;
    console.log(error);
    if (error.response) {
      const errorMessage = error.response.data.message;
      // message.error( errorMessage);
    }
  }
};
</script>

<style scoped lang="scss">
.holder {
  flex-grow: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-container {
  max-width: 300px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 5px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}
</style>
