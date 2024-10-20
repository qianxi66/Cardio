<script setup lang="ts">
import { ref, onMounted, toRefs } from "vue";
import { useMessage } from "naive-ui";
import { useRouter } from "vue-router";
import { getUsers } from "@/api/user";

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    required: false,
    default: false,
  },
});

const emit = defineEmits(["update:model", "submit"]);

const message = useMessage();
const router = useRouter();
const formRef = ref();
const userList = ref<{ label: string; value: number }[]>([]);

const { model } = toRefs(props);
let input = ref("");
const rules = ref({
  EHR_id: { required: false, trigger: ["blur", "input"] },
  participant_id: { required: true, trigger: ["blur", "input"] },
  medical_history: { required: false, trigger: ["blur", "input"] },
  medication: { required: false, trigger: ["blur", "input"] },
  user: { type: "array", required: false, trigger: ["blur", "change"] },
  gender: { type: "string", required: false, trigger: ["blur", "change"] },
  age: { type: "number", required: false, trigger: ["blur", "change"] },
  alexa_user_id: {
    type: "string",
    required: false,
    trigger: ["blur", "change"],
  },
});

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

const handleSubmit = async (e: MouseEvent) => {
  e.preventDefault();
  const form = formRef.value;
  if (form) {
    if (input.value) {
      model.value.gender = input.value;
    }
    form.validate(async (errors: any) => {
      if (!errors) {
        try {
          emit("submit", model.value);
        } catch (error: any) {
          message.error(`Submission failed: ${error.message}`);
        }
      } else {
        message.error("Form validation failed.");
      }
    });
  }
};

const loaduserList = () => {
  return new Promise<void>(async (resolve, reject) => {
    try {
      const users = await fetchUser();
      console.log("starting");
      if (users) {
        userList.value = users.map((user) => ({
          label: user.username,
          value: user.id,
        }));
        resolve();
      } else {
        console.warn("No users found.");
        userList.value = [];
        reject();
      }
    } catch (error) {
      console.error("Error fetching users:", error);
      userList.value = [];
      reject();
    }
  });
};

function handleGenderChange() {
  if (model.value.gender !== "other") {
    input.value = "";
  }
}

onMounted(async () => {
  await loaduserList();
  const loadGender = async () => {
    if (
      model.value.gender != "male" &&
      model.value.gender != "female" &&
      model.value.gender != null
    ) {
      input.value = model.value.gender;
      model.value.gender = "other";
    }

    console.log("After loadGender, gender:", model.value.gender);
  };
  loadGender();
});
</script>

<template>
  <n-card class="create-patient">
    <n-form ref="formRef" :model="model" :rules="rules" label-placement="top">
      <n-grid :cols="24" :x-gap="24">
        <n-form-item-gi :span="12" label="Age" path="age">
          <n-input-number
            :disabled="loading"
            :loading="loading"
            v-model:value="model.age"
            class="number"
            style="width: 100%"
          />
        </n-form-item-gi>

        <n-form-item-gi :span="12" label="Gender" path="gender">
          <n-radio-group
            v-model:value="model.gender"
            name="radiogroup1"
            @change="handleGenderChange"
            :disabled="loading"
          >
            <div class="gender-radio">
              <n-radio value="male"> male </n-radio>
              <n-radio value="female"> female </n-radio>
              <n-radio value="other"> </n-radio>
              <n-input
                v-model:value="input"
                :disabled="model.gender !== 'other'"
                small
                placeholder="other"
                style="max-width: 120px"
              />
            </div>
          </n-radio-group>
        </n-form-item-gi>

        <n-form-item-gi :span="12" label="Attending User" path="user">
          <n-select
            v-model:value="model.user"
            placeholder="Select"
            :options="userList"
            multiple
            :disabled="loading"
            :loading="loading"
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="EHR ID" path="EHR_id">
          <n-input
            :disabled="loading"
            :loading="loading"
            v-model:value="model.EHR_id"
            placeholder="Input"
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Participant ID" path="participant_id">
          <n-input
            :disabled="loading"
            :loading="loading"
            v-model:value="model.participant_id"
            placeholder="Input"
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Email" path="alexa_user_id">
          <n-input
            :disabled="loading"
            :loading="loading"
            v-model:value="model.alexa_user_id"
            placeholder="Input"
          />
        </n-form-item-gi>
        <n-form-item-gi
          :disabled="loading"
          :loading="loading"
          :span="12"
          label="Medical History"
          path="medical_history"
        >
          <n-input
            v-model:value="model.medical_history"
            type="textarea"
            :disabled="loading"
            :loading="loading"
            :autosize="{ minRows: 3, maxRows: 5 }"
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Medication" path="medication">
          <n-input
            v-model:value="model.medication"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 5 }"
            :disabled="loading"
            :loading="loading"
          />
        </n-form-item-gi>
        <n-gi :span="24">
          <div style="display: flex; justify-content: flex-end">
            <n-button
              :disabled="loading"
              :loading="loading"
              type="primary"
              @click="handleSubmit"
              >Submit</n-button
            >
          </div>
        </n-gi>
      </n-grid>
    </n-form>
  </n-card>
</template>

<style scoped lang="scss">
.create-patient {
  flex-basis: 230px;
  flex-grow: 0;
  flex-shrink: 0;
  min-height: 100%;
}

.number :deep(.n-input__suffix) .n-button {
  display: none !important;
}

.gender-radio {
  display: flex;
  flex-direction: row;
  justify-content: space-between;

  .n-radio {
    height: 34px;
    display: flex;
    align-items: center;
  }
  .n-input {
    margin-left: 10px;
  }
}
</style>
