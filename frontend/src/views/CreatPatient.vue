<template>
  <div>
    <div class="container">
      <h1>Create New Patient</h1>
      <PatientForm v-model:model="formData" @submit="handlecreatePatient" />
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import PatientForm from "../components/PatientForm.vue";
//import { useRouter } from "vue-router";
//import axios from "axios";
import { createPatient } from "@/api/patient";

import { getUserInfo } from "@/api/user";
const formData = ref({
  EHR_id: null,
  medication: null,
  user: null,
  medical_history: null,
  participant_id: null,
  gender: null,
  age: null,
});
const fetchUserInfo = async () => {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("Token not found");
      return;
    }
    const userInfoResponse = await getUserInfo(token);
    if (userInfoResponse.user_id) {
      formData.value.user = [userInfoResponse.user_id];
    }
  } catch (error) {
    console.error("An error occurred while fetching user info:", error);
  }
};
fetchUserInfo();
const handlecreatePatient = async (formData) => {
  try {
    console.log("ds");
    const response = await createPatient(formData);

    if (response.data.hasOwnProperty("message")) {
      notification.create({
        title: response.data.message,
      });
    } else {
      console.log("Patient created successfully:", response.data);
      // router.push("/patient");
    }
  } catch (error) {
    if (error.response) {
      const errorMessage = error.response.data.message;
      // message.error(errorMessage);
      console.error("Error creating patient:", errorMessage); //
    } else {
      console.error("Network error:", error);
    }
  }
};
</script>

<style scoped>
.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}
h1 {
  text-align: center;
  margin-bottom: 20px;
}
</style>
