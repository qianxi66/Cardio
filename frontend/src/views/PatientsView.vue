<script setup lang="ts">
import ColoredCard from '@/components/ColoredCard.vue'
import Dot from '@/components/Dot.vue'
import { getPatients } from '@/api/patient'
import Loading from '@/components/Loading.vue'
import { ref } from 'vue'
import { useRouteParams } from '@vueuse/router'
import { type Patient } from '@/api/types'
import router from '@/router'
const patients = ref<Patient[]>([])
const loading = ref(true)

const patient_id = useRouteParams('patient_id')
getPatients().then((res) => {
  patients.value = res
  loading.value = false
  if (!patient_id.value) {
    router.push({
      name: 'patient.detail',
      params: { patient_id: res[0].id }
    })
  }
})
</script>
<template>
  <div class="row holder">
    <n-card class="patient-list" title="Patients List">
      <loading :loading="loading" :has-data="patients.length !== 0" class="patient-list">
        <router-link
          v-for="p in patients"
          :key="p.id"
          :to="{
            name: 'patient.detail',
            params: { patient_id: p.id }
          }"
        >
          <div
            :class="{
              'patient-card': true,
              selected: p.id == parseInt(patient_id)
            }"
          >
            <div class="dot-holder">
              <Dot :state="p.state"></Dot>
            </div>
            <div class="patient-info">
              <div class="name">Patient {{ p.participant_id }}</div>
              <div class="age-sex">{{ p.age }} y.o., {{ p.gender }}</div>
            </div>
          </div>
        </router-link>
        <template #loading>
          <div class="patient-card" v-for="i in 10" :key="i">
            <div class="dot-holder">
              <n-skeleton box style="height: 24px; width: 24px; border-radius: 50%" />
            </div>
            <div class="patient-info">
              <n-skeleton class="name" text style="width: 100px; height: 22px" />
              <n-skeleton class="age-sex" text style="width: 70px; margin-top: 3px" />
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
  flex-basis: 250px;
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
}
.patient-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  color: black;
  cursor: pointer;
  .name {
    font-size: 16px;
    font-weight: 500;
  }
}
a {
  text-decoration: none;
}
.selected {
  background-color: #f0f0f0;
}
</style>
