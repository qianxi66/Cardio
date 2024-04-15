<script setup lang="ts">
import { useRouteParams, useRouteQuery } from '@vueuse/router'
import ColoredCard from '@/components/ColoredCard.vue'
import Dot from '@/components/Dot.vue'
import * as config from '@/config'
import { computed, watch, type Ref, ref } from 'vue'
import type { Patient, Report } from '@/api/types'
import { getPatient } from '@/api/patient'
import Loading from '@/components/Loading.vue'
import { format } from 'date-fns'
import router from '@/router'
import type { CancelStatic, CancelToken, CancelTokenSource } from 'axios'
import axios from 'axios'

const patient_id = useRouteParams('patient_id')
const report_id = useRouteParams('report_id')
const current_symptom = useRouteQuery('symptom')
const patient = ref<Patient | null>(null)
const loading = ref(true)
const cancelToken = ref<CancelTokenSource | null>(null)
watch(
  patient_id,
  async () => {
    if (!patient_id.value) {
      patient.value = null
      loading.value = true
      return
    }
    console.log('fetching patient', patient_id.value)
    if (cancelToken.value) {
      cancelToken.value.cancel()
    }
    cancelToken.value = axios.CancelToken.source()
    patient.value = null
    loading.value = true
    patient.value = await getPatient(parseInt(patient_id.value as string), cancelToken.value.token)
    loading.value = false
  },
  { immediate: true }
)
const jumpToReport = (report: Report, symptom: string | undefined) => {
  router.push({
    name: 'patient.report.detail',
    params: { patient_id: patient_id.value, report_id: report.id },
    query: symptom
      ? {
          symptom: symptom,
          logs: report[(symptom + '_logs') as keyof Report] as unknown as number[]
        }
      : {}
  })
}
watch(patient, () => {
  // get the latest report id
  if (patient.value) {
    const latestReport = patient.value.reports[0]
    if (latestReport) {
      const most_severe_symptom = Object.keys(config.symptoms).reduce(
        (acc: { state: number; symptom: string }, symptom: string) => {
          if ((latestReport[(symptom + '_state') as keyof Report] as number) > acc.state) {
            acc.state = latestReport[(symptom + '_state') as keyof Report] as number
            acc.symptom = symptom
          }
          return acc
        },
        { state: 0, symptom: '' }
      )
      console.log(most_severe_symptom)
      jumpToReport(latestReport, most_severe_symptom.symptom)
    }
  }
})
</script>
<template>
  <div class="row">
    <div class="col" style="flex: 400px 1 1">
      <ColoredCard class="information">
        <Loading :loading="loading" :has-data="!!patient">
          <div class="participant-id">Patient {{ patient!.participant_id }}</div>
          <div class="row demographic">
            <span class="age-sex">
              <b>{{ patient!.age }} y.o.</b> {{ patient!.gender }}
            </span>
            <span>
              {{ patient!.EHR_id }}
            </span>
          </div>
          <div class="row patient-details">
            <div class="box">
              <div class="row">
                <div class="title">Medical History</div>
                <div class="space"></div>
                <div>Last Visit: No Information</div>
              </div>
              {{ patient!.medical_history }}
            </div>
            <div class="box">
              <div class="row">
                <div class="title">Medication</div>
              </div>
              {{ patient!.medication }}
            </div>
          </div>
          <template #loading>
            <n-skeleton class="participant-id" style="height: 25px; width: 100px"></n-skeleton>
            <div class="row demographic">
              <n-skeleton class="age-sex" style="height: 21px"> </n-skeleton>
              <n-skeleton style="height: 21px; width: 38px"> </n-skeleton>
            </div>
            <div class="row patient-details">
              <div class="box">
                <div class="row">
                  <div class="title">Medical History</div>
                  <div class="space"></div>
                  <div>
                    <n-skeleton text style="display: inline-block; width: 150px"> </n-skeleton>
                  </div>
                </div>
                <n-skeleton text :repeat="2"></n-skeleton>
              </div>
              <div class="box">
                <div class="row">
                  <div class="title">Medication</div>
                </div>
                <n-skeleton text :repeat="2"></n-skeleton>
              </div>
            </div>
          </template>
        </Loading>
      </ColoredCard>
      <ColoredCard
        class="key-question"
        title="Key Question Overview"
        color="#4a239c"
        rounded
        style="flex: 1 1 400px"
      >
        <loading :loading="loading" :has-data="!!patient">
          <div class="reports-table">
            <div class="table-row header">
              <div class="date">Date & Time (EST)</div>
              <div class="symptom" v-for="symptom of Object.keys(config.symptoms)" :key="symptom">
                <n-tooltip trigger="hover">
                  <template #trigger>
                    {{ symptom[0].toUpperCase() + symptom.slice(1) }}
                  </template>
                  <div>{{ config.symptoms[symptom].description }}</div>
                </n-tooltip>
              </div>
            </div>
            <div
              :class="{
                'table-row': true,
                report: true,
                selected: report.id === parseInt(report_id)
              }"
              v-for="report in patient!.reports"
              :key="report.id"
            >
              <div class="date">{{ format(report.created_at, 'yyyy-MM-dd HH:mm:ss') }}</div>
              <div class="symptom" v-for="symptom of Object.keys(config.symptoms)" :key="symptom">
                <Dot
                  :class="{
                    selected: current_symptom === symptom && report.id === parseInt(report_id)
                  }"
                  :state="report[symptom + '_state']"
                  @click="
                    $router.push({
                      name: 'patient.report.detail',
                      params: { patient_id: patient!.id, report_id: report.id },
                      query: { symptom: symptom, logs: report[symptom + '_logs'] }
                    })
                  "
                />
              </div>
            </div>
          </div>
          <template #loading>
            <div class="reports-table">
              <div class="table-row header">
                <div class="date">Date & Time (EST)</div>
                <div class="symptom" v-for="symptom of Object.keys(config.symptoms)" :key="symptom">
                  <n-tooltip trigger="hover">
                    <template #trigger>
                      {{ symptom[0].toUpperCase() + symptom.slice(1) }}
                    </template>
                    <div>{{ config.symptoms[symptom].description }}</div>
                  </n-tooltip>
                </div>
              </div>

              <div
                :class="{
                  'table-row': true,
                  report: true
                }"
                v-for="i in 10"
                :key="i"
              >
                <n-skeleton text class="date" style="height: 19.2px; width: 130px"> </n-skeleton>
                <div class="symptom" v-for="symptom of Object.keys(config.symptoms)" :key="symptom">
                  <Dot loading />
                </div>
              </div>
            </div>
          </template>
        </loading>
      </ColoredCard>
    </div>
    <div class="col" style="flex: 0.5 1 100px">
      <router-view></router-view>
    </div>
  </div>
</template>
<style scoped lang="scss">
.row {
  flex-grow: 1;
  .col {
    flex-grow: 1;
    display: flex;
    height: 100%;
    flex-direction: column;
    row-gap: 8px;
  }
}
.participant-id {
  font-size: 16px;
  line-height: 24px;
  font-weight: 700;
}
.age-sex {
  width: 100px;
  display: inline-block;
}
.box {
  flex-basis: 0;
  flex-grow: 1;
  background-color: #f8f8f8;
  padding: 12px;
  .title {
    font-size: 16px;
    font-weight: 700;
  }
}
.demographic {
  margin: 10px 0px;
}
.patient-details {
  .box {
    max-height: 100px;
    overflow: overlay;
  }
}
.key-question {
  min-height: 0px;
  flex-grow: 1;
  flex-shrink: 1;
  :deep(.n-card__content) {
    overflow: overlay;
  }
}
.reports-table {
  width: 100%;
  .table-row {
    width: 100%;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    height: 48px;
    font-size: 12px;
    border-radius: 4px;
    &.header {
      font-weight: 700;
      border-bottom: 1px solid #e6e6e6;
    }
    .date {
      flex: 0 0 130px;
    }
    .symptom {
      flex: 1 0 50px;
      display: flex;
      justify-content: center;
    }
    &.selected {
      // outline: 2px solid #a1a1a1;
      background-color: #f0f0f0;
    }
    .dot:not(.selected):hover {
      box-shadow: 0px 0px 8px 4px rgba(0, 0, 0, 0.2); /* More visible shadow */
      cursor: pointer;
      transform: scale(1.2); /* Slightly larger scale */
      animation: float 0.5s ease-in-out infinite;
    }
    .dot.selected {
      outline: 2px solid #d4c5e2;
      transform: scale(1.2); /* Slightly larger scale */
    }

    /* Adjusted floating effect for smaller movement due to size */
    @keyframes float {
      0%,
      100% {
        transform: translateY(0) scale(1.2);
      }
      50% {
        transform: translateY(-3px) scale(1.2);
      }
    }
  }
}
.information {
  flex: 0 0 210px;
  min-height: 0;
  :deep(.n-card__content) {
    overflow: overlay;
  }
}
</style>
