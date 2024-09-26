<script lang="ts">
import { defineComponent, ref, onMounted } from "vue";
import { useMessage } from "naive-ui";
import { useRouter } from "vue-router";
import { getUsers } from "@/api/user";

import { getUserInfo } from "@/api/user";
import { log } from "console";
const fetchUser = async () => {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("Token not found");
      return;
    }

    const userInfoResponse = await getUsers(token);
    return userInfoResponse;
  } catch (error: any) {
    console.error("An error occurred while fetching user info:", error);
  }
};

export default defineComponent({
  emits: ["update:model", "submit"],
  setup(props, { emit }) {
    const message = useMessage();
    const router = useRouter();
    const formRef = ref();
    const generalOptions = ref<{ label: string; value: number }[]>([]);

    const model = ref({
      age: null,
      gender: null,
      EHRid: null,
      user: [],
      medicalhistory: null,
      medication: null,
    });

    const rules = ref({
      EHRid: { required: false, trigger: ["blur", "input"] },
      medicalhistory: { required: false, trigger: ["blur", "input"] },
      medication: { required: false, trigger: ["blur", "input"] },
      user: { type: "array", required: false, trigger: ["blur", "change"] },
      gender: { type: "string", required: false, trigger: "change" },
      age: { type: "number", required: false, trigger: ["blur", "change"] },
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
          model.value.user = [userInfoResponse.user_id];
        }
      } catch (error: any) {
        console.error("An error occurred while fetching user info:", error);
      }
    };

    fetchUserInfo();
    const handleSubmit = async (e: MouseEvent) => {
      e.preventDefault();
      const form = formRef.value;
      if (form) {
        form.validate(async (errors: any) => {
          if (!errors) {
            try {
              emit("submit", model.value);
              message.success("Success");
              await router.push("/patient");
            } catch (error) {
              message.error(`Submission failed: ${error.message}`);
            }
          } else {
            message.error("Form validation failed.");
          }
        });
      }
    };

    const loadGeneralOptions = async () => {
      try {
        const users = await fetchUser();
        if (users) {
          generalOptions.value = users.map((user) => ({
            label: user.username,
            value: user.id,
          }));
        } else {
          console.warn("No users found.");
          generalOptions.value = [];
        }
      } catch (error) {
        console.error("Error fetching users:", error);
        generalOptions.value = [];
      }
    };

    onMounted(() => {
      loadGeneralOptions();
    });

    return {
      generalOptions,
      handleSubmit,
      formRef,
      model,
      rules,
    };
  },
});
</script>

<template>
  <n-card class="create-patient">
    <n-form ref="formRef" :model="model" :rules="rules" label-placement="top">
      <n-grid :cols="24" :x-gap="24">
        <n-form-item-gi :span="12" label="Age" path="age">
          <n-input-number v-model:value="model.age" />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Gender" path="gender">
          <n-checkbox-group v-model:value="model.gender">
            <n-space>
              <n-checkbox value="male">Male</n-checkbox>
              <n-checkbox value="female">Female</n-checkbox>
            </n-space>
          </n-checkbox-group>
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Attending User" path="user">
          <n-select
            v-model:value="model.user"
            placeholder="Select"
            :options="generalOptions"
            multiple
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="EHR ID" path="EHRid">
          <n-input v-model:value="model.EHRid" placeholder="Input" />
        </n-form-item-gi>
        <n-form-item-gi
          :span="12"
          label="Medical History"
          path="medicalhistory"
        >
          <n-input
            v-model:value="model.medicalhistory"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 5 }"
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Medication" path="medication">
          <n-input
            v-model:value="model.medication"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 5 }"
          />
        </n-form-item-gi>
        <n-gi :span="24">
          <div style="display: flex; justify-content: flex-end">
            <n-button round type="primary" @click="handleSubmit"
              >Submit</n-button
            >
          </div>
        </n-gi>
      </n-grid>
    </n-form>
  </n-card>
</template>

<style>
.create-patient {
  flex-basis: 230px;
  flex-grow: 0;
  flex-shrink: 0;
  min-height: 100%;
}
</style>
