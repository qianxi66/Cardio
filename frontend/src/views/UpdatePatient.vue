<script setup lang="tsx">
import { onMounted, ref, watch } from "vue";
import router from "@/router";
//import axios from "axios";
import { useRouteParams } from "@vueuse/router";
import type { Patient } from "@/api/types";
import { updatePatient, getPatient } from "@/api/patient";
import type { CancelTokenSource } from "axios";
import axios from "axios";
const patient = ref<Patient | null>(null);
const patient_id = useRouteParams("patient_id", 0, {
  transform: (v) => v as number,
});

const loading = ref(true);
const formData = ref({
  name: "",
  EHR_id: "",
  user: [],
  participant_id: "",
  alexa_user_id: "",
  gender: "",
  age: null,
  garmin_id: "",
  cancer_type: "",
  cancer_stage: "",
  treatment_type: "",
});

onMounted(async () => {
  console.log("formData", formData.value);
  patient.value = null;
  loading.value = true;

  try {
    patient.value = await getPatient(patient_id.value);
    formData.value.name = patient.value.name;
    formData.value.EHR_id = patient.value.EHR_id;
    formData.value.user = patient.value.users.map((user) => user.id);
    formData.value.gender = patient.value.gender;
    formData.value.age = patient.value.age;
    formData.value.participant_id = patient.value.participant_id;
    formData.value.alexa_user_id = patient.value.alexa_user_id;
    formData.value.garmin_id = patient.value.garmin_id;
    formData.value.cancer_type = patient.value.cancer_type;
    formData.value.cancer_stage = patient.value.cancer_stage;
    formData.value.treatment_type = patient.value.treatment_type;
  } catch (error) {
    console.error("An error occurred while fetching patient info:", error);
    patient.value = null;
  } finally {
    loading.value = false;
  }
});

const handleupdatePatient = async (formData) => {
  try {
    for (const key of ["EHR_id", "participant_id", "alexa_user_id", "gender"]) {
      if (formData[key]) {
        formData[key] = formData[key].trim();
      }
    }
    const response = await updatePatient(patient_id.value, formData);

    console.log("patientid:" + response.patient_id);

    if (Object.prototype.hasOwnProperty.call(response, "message")) {
      window.$message.success(response.message);
      router.push({
        name: "patient.detail",
        params: { patient_id: patient_id.value },
      });
    } else {
      console.log("Patient updated successfully:", response);
      window.$message.success("Patient updated successfully");
      router.push({
        name: "patient.detail",
        params: { patient_id: patient_id.value },
      });
    }
  } catch (error) {
    if (error.response) {
      const errorMessage = error.response.data.message;
      console.error("Error creating patient:", errorMessage);
      window.$message.error(errorMessage);
    } else {
      console.error("Network error:", error);
      window.$message.error("Network error");
    }
  }
};
</script>

<template>
  <div>
    <div class="container">
      <h1>Update Patient</h1>
      <PatientForm
        :loading="loading"
        v-model:model="formData"
        @submit="handleupdatePatient"
      />
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
