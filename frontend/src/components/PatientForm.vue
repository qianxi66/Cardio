<template>
  <n-modal
    v-model:visible="visible"
    title="Generate Patient"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <n-form :model="form" ref="formRef" :rules="rules">
      <n-form-item label="Age" path="age">
        <n-input v-model:value="form.age" />
      </n-form-item>
      <n-form-item label="Gender" path="gender">
        <n-select v-model:value="form.gender" :options="genderOptions" />
      </n-form-item>
      <n-form-item label="Doctor" path="doctor">
        <n-input v-model:value="form.doctor" />
      </n-form-item>
      <n-form-item label="Alexa ID" path="alexa_id">
        <n-input v-model:value="form.alexa_id" />
      </n-form-item>
      <n-form-item label="Medical History" path="medical_history">
        <n-input v-model:value="form.medical_history" />
      </n-form-item>
      <n-form-item label="Medication" path="medication">
        <n-input v-model:value="form.medication" />
      </n-form-item>
    </n-form>
  </n-modal>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { NModal, NForm, NFormItem, NInput, NSelect } from "naive-ui";

const visible = ref(false);
const form = ref({
  age: "",
  gender: "",
  doctor: "",
  alexa_id: "",
  medical_history: "",
  medication: "",
});

const genderOptions = [
  { label: "Male", value: "male" },
  { label: "Female", value: "female" },
];

const rules = {
  age: { required: true, message: "Age is required", trigger: "blur" },
  gender: { required: true, message: "Gender is required", trigger: "blur" },
  doctor: { required: true, message: "Doctor is required", trigger: "blur" },
  alexa_id: {
    required: true,
    message: "Alexa ID is required",
    trigger: "blur",
  },
  medical_history: {
    required: true,
    message: "Medical History is required",
    trigger: "blur",
  },
  medication: {
    required: true,
    message: "Medication is required",
    trigger: "blur",
  },
};

const formRef = ref(null);

const handleOk = async () => {
  if (formRef.value) {
    try {
      await formRef.value.validate();
      // Process form submission
      console.log("Form data:", form.value);
      // Clear the form
      form.value = {
        age: "",
        gender: "",
        doctor: "",
        alexa_id: "",
        medical_history: "",
        medication: "",
      };
      visible.value = false;
    } catch (err) {
      console.error("Validation failed:", err);
    }
  }
};

const handleCancel = () => {
  visible.value = false;
};
</script>
