<!-- src/components/Login.vue -->
<template>
    <div class="login-container">
      <h2>login</h2>
      <form @submit.prevent="handleLogin">
        <div>
          <label for="username">username</label>
          <input type="text" id="username" v-model="username" />
        </div>
        <div>
          <label for="password">password</label>
          <input type="password" id="password" v-model="password" />
        </div>
        <div class="remember-me-container">
        <input type="checkbox" id="rememberMe" v-model="Rememberme" />
        <label for="rememberMe">Rememberme</label>
      </div>
        <button type="submit">start</button>
      </form>
    </div>
  </template>
  <script setup lang="tsx">
  import { ref } from 'vue'
  import axios from 'axios'
  import { useRouter } from 'vue-router'
  import { login } from '@/api/user'
  const router = useRouter()
  const username = ref('')
  const password = ref('')
  const Rememberme = ref(false)




  const handleLogin = async () => {
  try {
    const response = await login(username.value, password.value, Rememberme.value);
    console.log(response);
    const { token, userid } = response.token;
    localStorage.setItem('token', token);

    router.push('/patient');
  } catch (error) {
    console.error('Login failed:', error);
    alert('Please retry');
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
