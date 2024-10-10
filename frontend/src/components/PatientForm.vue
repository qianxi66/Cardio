<script lang="ts">
import { defineComponent, ref, onMounted, toRefs } from "vue";
import { useMessage } from "naive-ui";
import { useRouter } from "vue-router";
import { getUsers } from "@/api/user";
import { log } from "console";
import { Console } from "console";

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
    model: {
      type: Object,
      required: true,
    },
  },
  emits: ["update:model", "submit"],
  setup(props, { emit }) {
    const message = useMessage();
    const router = useRouter();
    const formRef = ref();
    const generalOptions = ref<{ label: string; value: number }[]>([]);

    const { model } = toRefs(props);
    let input = ref("");
    const rules = ref({
      EHR_id: { required: false, trigger: ["blur", "input"] },
      participant_id: { required: false, trigger: ["blur", "input"] },
      medical_history: { required: false, trigger: ["blur", "input"] },
      medication: { required: false, trigger: ["blur", "input"] },
      user: { type: "array", required: false, trigger: ["blur", "change"] },
      gender: { type: "string", required: false, trigger: ["blur", "change"] },
      age: { type: "number", required: false, trigger: ["blur", "change"] },
    });

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

    const loadGeneralOptions = () => {
      return new Promise(async (resolve, reject) => {
        try {
          const users = await fetchUser();
          console.log("starting");
          if (users) {
            generalOptions.value = users.map((user) => ({
              label: user.username,
              value: user.id,
            }));
            resolve();
          } else {
            console.warn("No users found.");
            generalOptions.value = [];
            reject();
          }
        } catch (error) {
          console.error("Error fetching users:", error);
          generalOptions.value = [];
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
      await loadGeneralOptions();
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

    return {
      handleGenderChange,
      generalOptions,
      handleSubmit,
      formRef,
      model,
      rules,
      input,
    };
  },
});
</script>

<template>
  <n-card class="create-patient">
    <n-form ref="formRef" :model="model" :rules="rules" label-placement="top">
      <n-grid :cols="24" :x-gap="24">
        <n-form-item-gi :span="12" label="Age" path="age">
          <!-- <n-input :input-props="{inputmode:'numeric' ,pattern:'\d*'}" v-model:value="model.age" class="number" /> -->
          <n-input-number v-model:value="model.age" class="number" />
        </n-form-item-gi>

        <n-form-item-gi :span="12" label="Gender" path="gender">
          <n-radio-group
            v-model:value="model.gender"
            name="radiogroup1"
            @change="handleGenderChange"
          >
            <n-space>
              <div class="gender-radio">
                <n-radio value="male"> male </n-radio>
                <n-radio value="female"> female </n-radio>
                <n-radio value="other"> </n-radio>
              </div>
              <n-input
                v-model:value="input"
                :disabled="model.gender !== 'other'"
                small
                placeholder="other"
                style="max-width: 120px"
              />
            </n-space>
          </n-radio-group>
        </n-form-item-gi>

        <n-form-item-gi :span="12" label="Attending User" path="user">
          <n-select
            v-model:value="model.user"
            placeholder="Select"
            :options="generalOptions"
            multiple
          />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="EHR ID" path="EHR_id">
          <n-input v-model:value="model.EHR_id" placeholder="Input" />
        </n-form-item-gi>
        <n-form-item-gi :span="12" label="Participant ID" path="participant_id">
          <n-input v-model:value="model.participant_id" placeholder="Input" />
        </n-form-item-gi>
        <n-form-item-gi
          :span="12"
          label="Medical History"
          path="medical_history"
        >
          <n-input
            v-model:value="model.medical_history"
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

.number .n-input-number__controls {
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
}
</style>
