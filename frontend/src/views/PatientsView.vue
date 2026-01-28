<script setup lang="ts">
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import { getPatients, updatePatient } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { ref, watch, computed, provide, onMounted } from "vue";
import { useRouteParams } from "@vueuse/router";
import { type Patient } from "@/api/types";
import router from "@/router";
import { NCard, NInput } from "naive-ui";

const patients = ref<Patient[] | null>(null);
const loading = ref(true);
const searchTerm = ref("");
const patient_id = useRouteParams<number>("patient_id");

const filteredPatients = computed(() => {
  let result = patients.value ? patients.value.slice() : [];

  if (searchTerm.value) {
    const term = searchTerm.value.toLowerCase();
    result = result.filter(
      (p) =>
        (p.participant_id && p.participant_id.toLowerCase().includes(term)) ||
        (p.age && p.age.toString().includes(term)) ||
        (p.gender && p.gender.toLowerCase().includes(term)),
    );
  }

  return result;
});

const loadPatient = () =>
  getPatients().then((res) => {
    patients.value = res;
    loading.value = false;
    console.log(res);
    console.log(patient_id.value);
    if (!patient_id.value && res.length > 0) {
      router.push({
        name: "patient.detail",
        params: { patient_id: res[0].id },
      });
    }
  });

onMounted(() => {
  loadPatient();
});
provide("refreshPatients", loadPatient);

watch(patient_id, () => {
  console.log("patient_id changed", patient_id.value);
  if (patient_id.value === undefined) {
    if (patients.value?.length && patients.value?.length > 0) {
      router.push({
        name: "patient.detail",
        params: { patient_id: patients.value![0].id },
      });
    } else {
      loadPatient();
    }
  } else {
    const patient = patients.value?.find((p) => p.id == patient_id.value);
    if (patient) {
      patient.read = true;
    }
  }
});

const updateState = (id: number, state: number) => {
  const patient = patients.value!.find((p) => p.id == id);
  if (patient) {
    if (state >= 0) {
      patient.state = state;
      patient.reviewed = false;
      updatePatient(id, { state, reviewed: false });
    } else {
      patient.reviewed = true;
      updatePatient(id, { reviewed: true });
    }
    setTimeout(loadPatient, 100);
  }
};
</script>

<template>
  <div class="row holder">
    <n-card class="patient-list">
      <template #header>
        <div class="header row">
          <div class="title">Patient List</div>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                @click="$router.push('/create_patient')"
              >
                <template #icon>
                  <n-icon size="35" quaternary type="primary">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 512 512"
                    >
                      <path
                        d="M368.5 240H272v-96.5c0-8.8-7.2-16-16-16s-16 7.2-16 16V240h-96.5c-8.8 0-16 7.2-16 16
                        0 4.4 1.8 8.4 4.7 11.3 2.9 2.9 6.9 4.7 11.3 4.7H240v96.5c0 4.4 1.8 8.4 4.7
                        11.3 2.9 2.9 6.9 4.7 11.3 4.7 8.8 0 16-7.2 16-16V272h96.5c8.8 0
                        16-7.2 16-16s-7.2-16-16-16z"
                      />
                    </svg>
                  </n-icon>
                </template>
              </n-button>
            </template>
            Create a Patient
          </n-tooltip>
        </div>
        <div class="filterpart">
          <n-input
            v-model:value="searchTerm"
            placeholder="Search by Participant ID"
            @keydown.esc="searchTerm = ''"
            clearable
          >
          </n-input>
        </div>
      </template>
      <Loading
        :loading="loading"
        :has-data="filteredPatients.length !== 0"
        class="patient-list"
      >
        <div
          :class="{
            'patient-card': true,
            selected: p.id == patient_id,
            read: p.read,
          }"
          v-for="p in filteredPatients"
          :key="p.id"
        >
          <div class="dot-holder">
            <Dot
              @update:state="updateState(p.id, $event)"
              :state="p.reviewed ? -1 : p.state"
              editable
              reviewable
            ></Dot>
          </div>
          <component
            :is="p.id == patient_id ? 'div' : 'router-link'"
            :to="{
              name: 'patient.detail',
              params: { patient_id: p.id },
            }"
            class="patient-info"
          >
            <div class="name">
              {{ p.patient_name || p.users?.[0]?.name || "n/a" }}
            </div>
            <div class="age-sex">
              <span v-if="p.age">{{ p.age }} y.o.</span>
              <span v-if="p.age && p.gender"> , </span>
              <span v-if="p.gender">{{ p.gender }}</span>
            </div>
          </component>
        </div>
        <template #loading>
          <div class="patient-card" v-for="i in 10" :key="i">
            <div class="dot-holder">
              <Dot loading></Dot>
            </div>
            <div class="patient-info">
              <n-skeleton
                class="name"
                text
                style="width: 100px; height: 22px"
              />
              <n-skeleton
                class="age-sex"
                text
                style="width: 70px; margin-top: 3px"
              />
            </div>
          </div>
        </template>
      </Loading>
    </n-card>
    <div class="patient-detail">
      <router-view></router-view>
    </div>
  </div>
</template>

<style scoped lang="scss">
.header {
  display: flex;
  height: 50px;
}
.title {
  flex-grow: 1;
  font-size: 20px;
  height: 28px;
  margin-bottom: 8px;
  margin-left: 0px;
}
.holder {
  flex: 1;
  min-height: 0;
  margin: 0;
  background-color: #f3f3f3;
}
.patient-detail {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
}
.patient-list {
  flex-basis: 200px;
  flex-grow: 0;
  flex-shrink: 0;
  min-height: 100%;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.2);
}
.n-card:deep(.n-card__content) {
  padding: 0;
  overflow: overlay;
}
.filterpart {
  margin-left: 0px;
}
.icon-button {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
}

.dot-holder {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 48px;
  height: 64px;
}
.patient-card {
  height: 84px;
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #e6e6e6;
  border-radius: 4px;
  &:not(.read) {
    font-weight: 800;
    .name {
      font-weight: 800;
    }
  }
}
.patient-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  color: black;
  .name {
    font-size: 15px;
    font-weight: 500;
  }
}
a {
  text-decoration: none;
}
.selected {
  background-color: #f3f3f3; 
  cursor: default;
}
</style>
