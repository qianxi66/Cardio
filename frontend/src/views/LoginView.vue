<template>
  <n-card class="login-container">
    <n-h2>Login</n-h2>
    <n-form >
      <n-form-item label="Username">
        <n-input v-model:value="username" placeholder="Enter your username" />
      </n-form-item>
      <n-form-item label="Password">
        <n-input type="password" v-model:value="password" placeholder="Enter your password" />
      </n-form-item>
      <n-checkbox v-model:checked="Rememberme">Remember Me</n-checkbox>
      <n-button type="info" html-type="submit" @click="handleLogin">Start</n-button>
    </n-form>
  </n-card>
</template>

<script setup lang="tsx">
import { ref } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { login } from '@/api/user'
import { useNotification } from 'naive-ui'

const router = useRouter()
const username = ref('')
const password = ref('')
const Rememberme = ref(false)

      const notification = useNotification()

const handleLogin = async () => {
  try {
    const response = await login(username.value, password.value, Rememberme.value);
    if (response.hasOwnProperty('message')) {

      notification.create({
        title: response.message})
    }else{

    const { token, userid } = response.token;
    localStorage.setItem('token', token);
    router.push('/patient');
    }

  } catch (error: any) {
    if (error.response) {
      const errorMessage = error.response.data.message ;
      // message.error( errorMessage);
      }
  }
};

</script>

<style scoped>
.login-container {
  max-width: 300px;
  margin: 100px auto;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 5px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}
.login-container h2 {
  text-align: center;
  margin-bottom: 20px;
}
.login-container form {
  display: flex;
  flex-direction: column;
}
.login-container div {
  margin-bottom: 15px;
}
.login-container label {
  display: block;
  margin-bottom: 5px;
}
.login-container input {
  width: 100%;
  padding: 8px;
  box-sizing: border-box;
}
.remember-me-container {
  display: flex;
  align-items: center;
  margin: 0; /* Ensure no extra margin around the container */
}
.login-container button {
  padding: 10px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
}
.login-container button:hover {
  background-color: #0056b3;
}
</style>
