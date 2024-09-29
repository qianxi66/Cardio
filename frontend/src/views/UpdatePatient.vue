<script setup lang="tsx">
import { ref, watch } from "vue";
import PatientForm from "../components/PatientForm.vue";
//import { useRouter } from "vue-router";
//import axios from "axios";
import { useRouteParams } from "@vueuse/router";
import type { Patient } from "@/api/types";
import { updatePatient, getPatient } from "@/api/patient";
import type { CancelTokenSource } from "axios";
import axios from "axios";
const patient = ref<Patient | null>(null);
const patient_id = useRouteParams("patient_id");
const cancelToken = ref<CancelTokenSource | null>(null);
const loading = ref(true);
interface FormData {
  EHR_id: string;
  medication: string;
  user: number[];
  medical_history: string;
  participant_id: string;
  gender: string;
  age: number | null;
}
const formData = ref<FormData>({
  EHR_id: "",
  medication: "",
  user: [],
  participant_id: "",
  medical_history: "",
  gender: "",
  age: null,
});

watch(
  patient_id,
  async () => {
    if (!patient_id.value) {
      patient.value = null;
      loading.value = false;
      return;
    }

    console.log("fetching patient", patient_id.value);

    if (cancelToken.value) {
      cancelToken.value.cancel();
    }

    cancelToken.value = axios.CancelToken.source();
    patient.value = null;
    loading.value = true;

    try {
      patient.value = await getPatient(
        parseInt(patient_id.value as string),
        cancelToken.value.token,
      );
      formData.value.EHR_id = patient.value.EHR_id;
      formData.value.medication = patient.value.medication;
      formData.value.user = patient.value.users.map((user) => user.id);
      formData.value.medical_history = patient.value.medical_history;
      formData.value.gender = patient.value.gender;
      formData.value.age = patient.value.age;
      formData.value.participant_id = patient.value.participant_id;
    } catch (error) {
      console.error("An error occurred while fetching patient info:", error);
      patient.value = null;
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

const handleupdatePatient = async (formData) => {
  try {
    console.log("ds");
    const response = await updatePatient(
      parseInt(patient_id.value as string),
      formData,
    );

    if (response.data.hasOwnProperty("message")) {
      notification.create({
        title: response.data.message,
      });
    } else {
      console.log("Patient created successfully:", response.data);
    }
  } catch (error) {
    if (error.response) {
      const errorMessage = error.response.data.message;
      console.error("Error creating patient:", errorMessage);
    } else {
      console.error("Network error:", error);
    }
  }
};
</script>

<template>
  <div>
    <div class="container">
      <h1>Update Patient</h1>
      <PatientForm v-model:model="formData" @submit="handleupdatePatient" />
    </div>
  </div>
</template>

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
