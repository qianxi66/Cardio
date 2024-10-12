<script setup lang="tsx">
import { useRouteParams, useRouteQuery } from '@vueuse/router'
import ColoredCard from '@/components/ColoredCard.vue'
import Dot from '@/components/Dot.vue'
import * as config from '@/config'
import { computed, watch, type Ref, ref, inject } from 'vue'
import type { Patient, Report } from '@/api/types'
import { getPatient, updateReport, createNote } from '@/api/patient'
import Loading from '@/components/Loading.vue'
import { format, formatDistance } from 'date-fns'
import router from '@/router'
import type { CancelTokenSource } from 'axios'
import ReportTableHeader from '@/components/ReportTableHeader.vue'
import axios from 'axios'
import CircleProgress from '@/components/CircleProgress.vue'
import { stateColors } from '@/config';//shihan
const refreshPatients = inject('refreshPatients')
const patient_id = useRouteParams('patient_id')
const report_id = useRouteParams('report_id')
const current_symptom = useRouteQuery('symptom')
//const report = ref({});//shihan
const report = ref<Report | null>(null);//shihan

let showall = useRouteQuery('showall', 'false', { transform: (v: string) => v === 'true' })

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
    query: {
      showall: showall.value.toString(),
      ...(symptom
        ? {
            symptom: symptom,
            logs: report[(symptom + '_logs') as keyof Report] as unknown as number[],
            state:
              report[symptom + '_state'] == 2
                ? config.symptoms[symptom].max_scale
                : report[symptom + '_state']
          }
        : {})
    }
  })
}

// const getColorByScale = (scale: number, state: number) => {
//   console.log('getColorByScale called with scale:', scale, 'and state:', state);
  
//   let color;
//   if (state === 0) {
//       color = stateColors[0];
//   } else if (state === 1) {
//     color = stateColors[1];
//   } else if (state >= 2) {
//     // If scale is not 0, assign color based on scale range
//     if (scale >= 1 && scale <= 3) {
//       color = stateColors[2]; 
//     } else if (scale >= 4 && scale <= 6) {
//       color = stateColors[3]; 
//     } else if (scale >= 7 && scale <= 10) {
//       color = stateColors[4];
//     }
//   }
//   console.log('Returning color:', color);
//   return color;
// };

const getSymptomColor = (symptom: string, report: Report) => {
  if (config.symptoms[symptom].likert) {
    const scale = report[symptom + '_scale'] as number;
    const state = report[symptom + '_state'] as number;
    return getColorByScale(scale, state);
  }
  return config.symptoms[symptom].color
}

const getColorByScale = (scale: number, state: number) => {
  console.log('getColorByScale called with scale:', scale, 'and state:', state);
  
  // Default color assignment
  let color = stateColors[state];  // If state is 0 or 1, return its color directly

  // Only apply scale-based color changes if state is >= 2
  if (state >= 2) {
    if (scale >= 1 && scale <= 3) {
      color = stateColors[2]; 
    } else if (scale >= 4 && scale <= 6) {
      color = stateColors[3]; 
    } else if (scale >= 7 && scale <= 10) {
      color = stateColors[4];
    }
  }

  console.log('Returning color:', color);
  return color;
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
const right = ref<Component | null>(null)
const updateState = async (id: number, report_id: number, symptom: string, state: number) => {
  const report = patient.value!.reports.find((r) => r.id === report_id)
  if (report) {
    const date = format(new Date(), 'yyyy-MM-dd HH:mm:ss')
    await createNote(
      id,
      report_id,
      `Severity of ${symptom} changed from ${['No Information', 'Normal', config.stateMessages[config.symptoms[symptom].max_scale]][report[symptom + '_state']]} to ${config.stateMessages[state]} at ${date}`
    )
    report[symptom + '_state'] = state
    await updateReport(id, report_id, { [symptom + '_state']: state })
    right.value.refresh()
    refreshPatients()
  }
}

</script>

<template>
  <div class="row">
    <div class="col" style="flex: 5 1 350px">
      <ColoredCard class="information">
        <Loading :loading="loading" :has-data="!!patient">
          <div class="participant-id">Older Adults {{ patient!.participant_id }}</div>
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
                <div class="title">Location</div>
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
            <ReportTableHeader></ReportTableHeader>
            <div
              v-for="(report, index) in patient!.reports"
              :key="index"
              :class="{
                'table-row-block': true,
                selected: report.id === parseInt(report_id),

                odd: index % 2 === 0
              }"
            >
              <div
                :class="{
                  'table-row': true,
                  report: true
                }"
              >
                <div class="date">
                  {{ format(report.created_at, 'yyyy-MM-dd HH:mm:ss') }}
                </div>
                <div class="symptom" v-for="symptom of Object.keys(config.symptoms)" :key="symptom">
                  <n-tooltip trigger="hover" v-if="config.symptoms[symptom].likert">
                    <template #trigger>
                      <circle-progress
                        :percent="report[symptom + '_scale'] * 10"
                        :color="getSymptomColor(symptom, report)"
                        :id="symptom"
                        style="width: 50px"
                      >
                        <dot-symptom
                          @update:state="updateState(patient.id, report.id, symptom, $event)"
                          :editable="
                            (current_symptom === symptom && report.id === parseInt(report_id)) ||
                            report[symptom + '_state'] === 0
                          "
                          :class="{
                            selected:
                              current_symptom === symptom && report.id === parseInt(report_id),
                            disabled: report[symptom + '_state'] === 0
                          }"
                          :state="report[symptom + '_state']"
                          @click="report[symptom + '_state'] !== 0 && jumpToReport(report, symptom)"
                          :color="getSymptomColor(symptom, report)"
                          :symptom="symptom"
                        />
                      </circle-progress>
                    </template>
                    <div>
                      {{ config.symptoms[symptom].display_name }}: {{ report[symptom + '_scale'] }}
                    </div>
                  </n-tooltip>
                  <circle-progress
                    :percent="report[symptom + '_scale'] * 10"
                    :color="getSymptomColor(symptom, report)"
                    :id="symptom"
                    style="width: 50px"
                    v-else
                    :visible="false"
                  >
                    <dot-symptom
                      @update:state="updateState(patient.id, report.id, symptom, $event)"
                      :editable="
                        (current_symptom === symptom && report.id === parseInt(report_id)) ||
                        report[symptom + '_state'] === 0
                      "
                      :class="{
                        selected: current_symptom === symptom && report.id === parseInt(report_id),
                        disabled: report[symptom + '_state'] === 0
                      }"
                      :state="report[symptom + '_state']"
                      @click="report[symptom + '_state'] !== 0 && jumpToReport(report, symptom)"
                      :color="getSymptomColor(symptom, report)"
                      :symptom="symptom"
                    />
                  </circle-progress>
                </div>
              </div>
            </div>
          </div>
          <template #loading>
            <div class="reports-table">
              <ReportTableHeader></ReportTableHeader>

              <template v-for="i in 10" :key="i">
                <div
                  :class="{
                    'table-row': true,
                    report: true
                  }"
                >
                  <n-skeleton text class="date" style="height: 19.2px; width: 130px"> </n-skeleton>
                  <div
                    class="symptom"
                    v-for="symptom of Object.keys(config.symptoms)"
                    :key="symptom"
                  >
                    <circle-progress
                      :percent="0"
                      :color="config.symptoms[symptom].color"
                      :id="symptom"
                      style="width: 50px"
                      :visible="config.symptoms[symptom].likert"
                    >
                      <Dot loading />
                    </circle-progress>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </loading>
      </ColoredCard>
    </div>
    <div class="col" style="flex: 1 1 250px">
      <router-view v-slot="{ Component }">
        <component :is="Component" ref="right" />
      </router-view>
    </div>
  </div>
</template>

<style scoped lang="scss">


.row {
  flex-grow: 1;
  .col {
    min-width: 0;
    flex-grow: 1;
    display: flex;
    height: 100%;
    flex-direction: column;
    row-gap: 8px;
  }
  overflow-x: hidden;
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
  max-width: 100%;
  :deep(.n-card__content) {
    max-width: 100%;
    min-width: 0;
    overflow-x: overlay;
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
