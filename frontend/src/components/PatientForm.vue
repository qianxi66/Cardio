<script lang="ts">
import { defineComponent, ref, watch, onMounted } from "vue";
import { useMessage } from "naive-ui";
import { getUsers } from "@/api/user";

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
  props: {
    formData: {
      type: Object,
      required: true,
    },
  },
  emits: ["update:formData", "submit"],
  setup(props, { emit }) {
    const formRef = ref(null);
    const message = useMessage();
    const generalOptions = ref<{ label: string; value: number }[]>([]);

    const loadGeneralOptions = async () => {
      try {
        const users = await fetchUser();
        if (users) {
          generalOptions.value = users.map((user) => {
            console.log("Processing user:", user.username);
            return {
              label: user.username,
              value: user.id,
            };
          });
        } else {
          console.warn("No users found.");
          generalOptions.value = [];
        }
      } catch (error) {
        console.error("Error fetching users:", error);
        generalOptions.value = [];
      }
    };

    // Load options when the component is mounted
    onMounted(() => {
      loadGeneralOptions();
    });

    const rules = {
      EHRid: {
        required: false,
        message: "please enter EHRid",
        trigger: ["blur", "input"],
      },
      medicalhistory: {
        required: false,
        message: "please enter medicalhistory",
        trigger: ["blur", "input"],
      },
      medication: {
        required: false,
        message: "please enter medication",
        trigger: ["blur", "input"],
      },
      user: {
        required: false,
        message: "please select user",
        trigger: ["blur", "change"],
      },
      gender: {
        type: "string",
        required: false,
        message: "please select gender",
        trigger: "change",
      },
      age: {
        type: "number",
        required: false,
        message: "please enter age",
        trigger: ["blur", "change"],
      },
    };

    const handleSubmit = (e: MouseEvent) => {
      e.preventDefault();
      formRef.value?.validate((errors) => {
        if (!errors) {
          emit("submit");
          message.success("success");
        } else {
          message.error("failed");
        }
      });
    };

    watch(
      () => props.formData,
      (newVal) => {
        emit("update:formData", newVal);
      },
      { deep: true },
    );

    return {
      formRef,
      generalOptions,
      rules,
      handleSubmit,
    };
  },
});
</script>
<template>
  <n-card class="create-patient">
    <n-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-placement="top"
    >
      <n-grid :cols="24" :x-gap="24">
        <n-form-item-gi :span="12" label="Age" path="age">
          <n-input-number v-model:value="formData.age" />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Gender" path="gender">
          <n-checkbox-group v-model:value="formData.gender">
            <n-space>
              <n-checkbox value="male">male</n-checkbox>
              <n-checkbox value="female">female</n-checkbox>
            </n-space>
          </n-checkbox-group>
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Attending user" path="user">
          <n-select
            v-model:value="formData.user"
            placeholder="Select"
            :options="generalOptions"
            multiple
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="EHR ID" path="EHRid">
          <n-input v-model:value="formData.EHRid" placeholder="Input" />
        </n-form-item-gi>
        <n-form-item-gi
          :span="12"
          label="Medical History"
          path="medicalhistory"
        >
          <n-input
            v-model:value="formData.medicalhistory"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 5 }"
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Medication" path="medication">
          <n-input
            v-model:value="formData.medication"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 5 }"
          />
        </n-form-item-gi>
        <n-gi :span="24">
          <div style="display: flex; justify-content: flex-end">
            <n-button round type="primary" @click="handleSubmit">
              submit
            </n-button>
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
