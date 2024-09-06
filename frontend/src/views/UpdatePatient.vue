<template>
  <div>
    <div class="container">
      <h1>Update Patient</h1>
      <PatientForm :patient="patient" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import axios from "axios";
import AppHeader from "../components/AppHeader.vue";
import PatientForm from "../components/PatientForm.vue";

const patient = ref(null);

const route = useRoute();

onMounted(async () => {
  try {
    const patientId = route.params.id;
    const response = await axios.get(`/patients/${patientId}`);
    patient.value = response.data;
  } catch (error) {
    console.error("Failed to fetch patient data:", error);
  }
});
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
