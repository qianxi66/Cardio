<template>
  <div>
    <div class="container">
      <h1>Create New Patient</h1>
      <PatientForm v-model:formData="formData" @submit="createPatient" />
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import PatientForm from "../components/PatientForm.vue";
import { useRouter } from "vue-router";
import axios from "axios";

const router = useRouter(); // Initialize router

const formData = ref({
  EHRid: null,
  medication: null,
  user: null, //TODO:use id
  medicalhistory: null,
  gender: null,
  age: null,
});

const createPatient = async (formData) => {
  try {
    const response = await axios.post("/patients", formData);

    if (response.data.hasOwnProperty("message")) {
      notification.create({
        title: response.data.message,
      });
    } else {
      console.log("Patient created successfully:", response.data);
      router.push("/patient");
    }
  } catch (error) {
    if (error.response) {
      const errorMessage = error.response.data.message;
      // message.error(errorMessage);
      console.error("Error creating patient:", errorMessage);
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
