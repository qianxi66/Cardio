<script setup lang="ts">
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import { getPatients, updatePatient } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { ref, watch } from "vue";
import { useRouteParams } from "@vueuse/router";
import { type Patient } from "@/api/types";
import router from "@/router";
import { provide, inject } from "vue";
const patients = ref<Patient[] | null>(null);
const loading = ref(true);

const patient_id = useRouteParams<number>("patient_id");
const loadPatient = () =>
  getPatients().then((res) => {
    patients.value = res;
    loading.value = false;
    if (!patient_id.value) {
      router.push({
        name: "patient.detail",
        params: { patient_id: res[0].id },
      });
    }
  });
loadPatient();
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
    if (patients.value?.find((p) => p.id == patient_id.value)) {
      patients.value!.find((p) => p.id == patient_id.value)!.read = true;
    }
  }
});
const updateState = (id: number, state: number) => {
  if (state >= 0) {
    patients.value!.find((p) => p.id == id)!.state = state;
    patients.value!.find((p) => p.id == id)!.reviewed = false;
    updatePatient(id, { state, reviewed: false });
  } else {
    patients.value!.find((p) => p.id == id)!.reviewed = true;
    updatePatient(id, { reviewed: true });
  }
  setTimeout(loadPatient, 100);
};
</script>
<template>
  <div class="row holder">
    <n-card class="patient-list" title="Patients List">
      <loading
        :loading="loading"
        :has-data="patients?.length !== 0"
        class="patient-list"
      >
        <div
          :class="{
            'patient-card': true,
            selected: p.id == patient_id,
            read: p.read,
          }"
          v-for="p in patients"
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
            <div class="name">Patient {{ p.participant_id }}</div>
            <div class="age-sex">{{ p.age }} y.o., {{ p.gender }}</div>
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
      </loading>
    </n-card>
    <router-view></router-view>
  </div>
</template>
<style scoped lang="scss">
.holder {
  flex: 1;
  min-height: 0;
  margin: 0 8px 8px 8px;
}
.patient-list {
  flex-basis: 230px;
  flex-grow: 0;
  flex-shrink: 0;
  min-height: 100%;
}
.n-card:deep(.n-card__content) {
  padding: 0;
  overflow: overlay;
}

.dot-holder {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 48px;
  height: 64px;
}
.patient-card {
  height: 64px;
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
    font-size: 16px;
    font-weight: 500;
  }
}
a {
  text-decoration: none;
}
.selected {
  // border: 2px solid #a1a1a1;
  box-shadow: inset 0px 0px 0px 2px #a1a1a1;
  cursor: default;
}
</style>
