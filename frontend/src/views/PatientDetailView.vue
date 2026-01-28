<script setup lang="tsx">
import { useRouteParams } from "@vueuse/router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import * as config from "@/symptoms";
import { computed, watch, type Ref, ref, inject } from "vue";
import { useResizeObserver } from "@vueuse/core";
import type { Patient, Report } from "@/api/types";
import { getPatient } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format } from "date-fns";
import router from "@/router";
import type { CancelTokenSource } from "axios";
import axios from "axios";
import { getUserInfo } from "@/api/user";

type HospitalizationEntry = {
  date?: string;
  therapy?: string;
  treatment?: string;
};

const refreshPatients = inject("refreshPatients");
const patient_id = useRouteParams("patient_id");
const report_id = useRouteParams("report_id");
let user_Id = 0;

const report = ref<Report | null>(null);

const patient = ref<Patient | null>(null);
const loading = ref(true);
const cancelToken = ref<CancelTokenSource | null>(null);
const dailySummaryDate = ref<number | null>(Date.now());
const symptomsLeft = ref([
  { label: "Shortness of Breath", state: 1 },
  { label: "Chest Discomfort", state: 1 },
  { label: "Fatigue", state: 1 },
]);
const symptomsRight = ref([
  { label: "Palpitation", state: 2 },
  { label: "Swelling", state: 1 },
  { label: "Syncope", state: 2 },
]);
const patientName = computed(() => {
  const data = patient.value as (Patient & { patient_name?: string; name?: string }) | null;
  return data?.patient_name || data?.name || data?.users?.[0]?.name || "n/a";
});
const participantIdLabel = computed(() => {
  return patient.value?.participant_id || "n/a";
});
const cancerType = computed(() => {
  return (patient.value as { cancer_type?: string } | null)?.cancer_type || "n/a";
});
const cancerStage = computed(() => {
  return (patient.value as { cancer_stage?: string } | null)?.cancer_stage || "n/a";
});
const treatmentType = computed(() => {
  return (patient.value as { treatment_type?: string } | null)?.treatment_type || "n/a";
});
const hospitalizations = computed(() => {
  const raw = (patient.value as { hospitalizations?: HospitalizationEntry[] } | null)
    ?.hospitalizations;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((entry) => ({
      date: entry?.date || "",
      therapy: entry?.therapy || entry?.treatment || "",
    }))
    .filter((entry) => entry.date || entry.therapy);
});
const formatHospitalizationDate = (value: string) => {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "n/a";
  }
  return format(parsed, "dd/MM/yyyy");
};

watch(
  patient_id,
  async () => {
    console.log("patient_id changed", patient_id.value);
    if (!patient_id.value) {
      patient.value = null;
      loading.value = true;
      return;
    }
    console.log("fetching patient", patient_id.value);
    if (cancelToken.value) {
      cancelToken.value.cancel();
    }
    cancelToken.value = axios.CancelToken.source();
    patient.value = null;
    loading.value = true;
    patient.value = await getPatient(
      parseInt(patient_id.value as string),
      cancelToken.value.token,
    );
    loading.value = false;
  },
  { immediate: true },
);

const fetchUserInfo = async () => {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("Token not found");
      return;
    }
    const userInfoResponse = await getUserInfo(token);
    if (userInfoResponse.user_id) {
      user_Id = userInfoResponse.user_id;
      console.log(user_Id);
    }
  } catch (error: any) {
    console.error("An error occurred while fetching user info:", error);
  }
};

fetchUserInfo();

const jumpToReport = (report: Report, symptom: string | undefined) => {
  router.push({
    name: "patient.report.detail",
    params: { patient_id: patient_id.value, report_id: report.id },
    query: {
      ...(symptom
        ? {
            symptom: symptom,
            logs: report[
              (symptom + "_logs") as keyof Report
            ] as unknown as number[],
            state:
              report[symptom + "_state"] == 2
                ? config.symptoms[symptom].max_scale
                : report[symptom + "_state"],
          }
        : {}),
    },
  });
};

watch(patient, () => {
  // get the latest report id
  if (patient.value) {
    const latestReport = patient.value.reports[0];
    if (latestReport) {
      const most_severe_symptom = Object.keys(config.symptoms).reduce(
        (acc: { state: number; symptom: string }, symptom: string) => {
          if (
            (latestReport[(symptom + "_state") as keyof Report] as number) >
            acc.state
          ) {
            acc.state = latestReport[
              (symptom + "_state") as keyof Report
            ] as number;
            acc.symptom = symptom;
          }
          return acc;
        },
        { state: 0, symptom: "" },
      );
      console.log(most_severe_symptom);
      jumpToReport(latestReport, most_severe_symptom.symptom);
    }
  }
});

const right = ref<Component | null>(null);
const navEl = ref<HTMLDivElement | null>(null);

const updateNavWidths = () => {
  if (!navEl.value) return;
  const buttons = Array.from(navEl.value.querySelectorAll<HTMLButtonElement>(".nav-btn"));
  if (!buttons.length) return;
  let maxWidth = 0;
  buttons.forEach((btn) => {
    btn.style.width = "auto";
  });
  buttons.forEach((btn) => {
    const width = btn.getBoundingClientRect().width;
    if (width > maxWidth) maxWidth = width;
  });
  if (maxWidth > 0) {
    const target = `${Math.ceil(maxWidth)}px`;
    buttons.forEach((btn) => {
      btn.style.width = target;
    });
  }
};

useResizeObserver(navEl, () => {
  updateNavWidths();
});
</script>

<template>
  <div class="patient-layout">
    <div class="patient-header-wrapper">
      <Loading :loading="loading" :has-data="!!patient">
        <div class="row patient-header">
          <div class="patient-avatar" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path
                d="M12 12a4 4 0 1 0-4-4a4 4 0 0 0 4 4Zm0 2c-4.2 0-7.5 2-7.5 4.5V20h15v-1.5C19.5 16 16.2 14 12 14Z"
                fill="currentColor"
              />
            </svg>
          </div>
          <div class="patient-name">
            {{ patientName }}
          </div>
          <div class="patient-meta">
            {{ patient!.age ? patient!.age + " y.o." : "" }}
            {{ patient!.gender }}
          </div>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                @click="$router.push(`/patient/${patient_id}/update`)"
              >
                <template #icon>
                  <n-icon>
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 16 16"
                    >
                      <g fill="none">
                        <path
                          d="M12.007 6.81l-5.949 5.95c-.319.318-.719.545-1.156.654l-2.283.57a.498.498 0 0 1-.604-.603l.57-2.283a2.49 2.49 0 0 1 .656-1.156l5.948-5.95l2.818 2.817zm1.41-4.226c.777.778.777 2.039 0 2.817l-.706.704l-2.817-2.818l.705-.703a1.992 1.992 0 0 1 2.817 0z"
                          fill="currentColor"
                        ></path>
                      </g>
                    </svg>
                  </n-icon>
                </template>
              </n-button>
            </template>
            Edit Patient
          </n-tooltip>
          <div class="patient-nav-spacer"></div>
          <div class="patient-nav" ref="navEl">
            <button class="nav-btn active" type="button">Homepage</button>
            <button class="nav-btn" type="button">Quick View</button>
            <button class="nav-btn" type="button">Medications</button>
            <button class="nav-btn" type="button">Results</button>
            <button class="nav-btn" type="button">Therapy</button>
            <button class="nav-btn" type="button">Orders</button>
            <button class="nav-btn" type="button">Oncology</button>
          </div>
        </div>
        <div class="row demographic"></div>
        <template #loading>
          <div class="row patient-header">
            <div class="patient-avatar skeleton-avatar"></div>
            <n-skeleton
              class="patient-name"
              style="height: 30px; width: 180px"
            ></n-skeleton>
            <n-skeleton
              class="patient-meta"
              style="height: 21px; width: 120px"
            ></n-skeleton>
          </div>
          <div class="row demographic"></div>
        </template>
      </Loading>
    </div>
    <div class="row">
      <div class="col main-col">
      <ColoredCard class="information">
        <Loading :loading="loading" :has-data="!!patient">
          <div class="row patient-details">
            <div class="box patient-info-box">
              <div class="detail-line">
                <span class="label">Cancer Type:</span>
                <span class="value">{{ cancerType }}</span>
              </div>
              <div class="detail-line">
                <span class="label">Cancer Stage:</span>
                <span class="value">{{ cancerStage }}</span>
              </div>
              <div class="detail-line">
                <span class="label">Treatment Type:</span>
                <span class="value">{{ treatmentType }}</span>
              </div>
            </div>
            <div class="box-group">
              <div class="title">Hospitalizations</div>
              <div class="box hospitalizations-box">
                <div class="hospitalizations">
                  <div class="hospitalization-entry">
                    <span class="date">07/20/2023</span>
                    <span class="therapy">Chemotherapy Initiation</span>
                  </div>
                  <div class="hospitalization-entry">
                    <span class="date">08/22/2023</span>
                    <span class="therapy">Chemotherapy Complications</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Loading>
      </ColoredCard>
      <ColoredCard
        class="daily-summary indigo-title full-title-bar"
        title="Daily Summary"
        color="#5171AB"
        rounded
      >
        <template #title-extra>
          <n-date-picker
            v-model:value="dailySummaryDate"
            type="date"
            size="small"
            clearable
          />
        </template>
        <div class="daily-summary-content">
          <div class="overview-panel">
            <div class="panel-title">Wearable Sensor Data Overview</div>
            <div class="overview-box"></div>
          </div>
          <div class="overview-panel">
            <div class="panel-title">Symptoms Overview</div>
            <div class="symptoms-box">
              <div class="symptoms-column">
                <div
                  class="symptom-row"
                  v-for="(item, index) in symptomsLeft"
                  :key="item.label"
                >
                  <Dot
                    :state="item.state"
                    editable
                    @update:state="(val) => (symptomsLeft[index].state = val)"
                  />
                  <span>{{ item.label }}</span>
                </div>
              </div>
              <div class="symptoms-column">
                <div
                  class="symptom-row"
                  v-for="(item, index) in symptomsRight"
                  :key="item.label"
                >
                  <Dot
                    :state="item.state"
                    editable
                    @update:state="(val) => (symptomsRight[index].state = val)"
                  />
                  <span>{{ item.label }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ColoredCard>
      <ColoredCard
        class="detailed-wearable indigo-title full-title-bar"
        title="Detailed Wearable Sensor Data"
        color="#5171AB"
        rounded
      >
        <div class="chart-wrapper">
          <DetailedWearableChart />
        </div>
      </ColoredCard>
    </div>
      <div class="col side-col">
        <div class="side-content">
          <router-view v-slot="{ Component }">
            <component :is="Component" ref="right" />
          </router-view>
        </div>
      </div>
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
    row-gap: 16px;
  }
  overflow-x: hidden;
}
.main-col,
.side-col {
  flex: 1 1 0;
  padding-bottom: 16px;
  box-sizing: border-box;
}

.patient-header {
  align-items: center;
  column-gap: 12px;
  width: 100%;
}
.patient-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: #ffffff;
  color: #9a9a9a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}
.patient-avatar svg {
  width: 20px;
  height: 20px;
}
.skeleton-avatar {
  background-color: #f3f3f3;
}
.patient-name {
  font-size: 30px;
  line-height: 36px;
  font-weight: 700;
}
.patient-header {
  align-items: flex-end;
}
.patient-meta {
  font-size: 16px;
  line-height: 30px;
  font-weight: 700;
}
.patient-nav {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  margin-left: auto;
}
.patient-nav-spacer {
  flex: 0 0 auto;
}
.nav-btn {
  border: 1px solid #bfcaf0;
  background: #fff;
  color: #2f5ca8;
  padding: 6px 12px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 2px;
  cursor: pointer;
  white-space: nowrap;
  text-align: center;
}
.nav-btn.active {
  background: #3f5fa5;
  color: #fff;
  border-color: #3f5fa5;
}
.participant-id {
  font-size: 16px;
  line-height: 30px;
  font-weight: 700;
}
.patient-header-wrapper {
  height: 76px;
  padding: 8px 16px 8px 0px;
  display: flex;
  align-items: center;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
}
.patient-header-wrapper :deep(.n-spin),
.patient-header-wrapper :deep(.n-spin-container),
.patient-header-wrapper :deep(.n-spin-content) {
  overflow: hidden;
  width: 100%;
}
.patient-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  flex: 1 1 0;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}
.icon-button {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
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
.box-group {
  flex-basis: 0;
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  row-gap: 6px;
  .title {
    font-size: 14px;
    font-weight: 700;
  }
}
.detail-line {
  display: flex;
  column-gap: 6px;
  line-height: 22px;
}
.detail-line .label {
  font-weight: 700;
}
.hospitalizations {
  margin-top: 0px;
  display: flex;
  flex-direction: column;
  row-gap: 4px;
  font-size: 12px;
}
.hospitalization-entry {
  display: flex;
  column-gap: 8px;
}
.hospitalization-entry .date {
  min-width: 90px;
  font-weight: 700;
}
.demographic {
  margin: 0;
}
.patient-details {
  flex-grow: 1;
  align-items: stretch;
  min-height: 0;
  .box {
    overflow: overlay;
  }
}
.patient-details > .box,
.patient-details > .box-group {
  height: 100%;
}
.hospitalizations-box {
  background-color: #f3f3f3;
  font-size: 12px !important;
  padding: 6px 12px;
}
.patient-info-box {
  background-color: #fff;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.patient-info-box .detail-line {
  flex: 1 1 0;
  align-items: center;
}
.side-col {
  padding-top: 0px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-sizing: border-box;
}
.side-content {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
}
.daily-summary {
  flex: 2 1 0;
  min-height: 0;
}
.daily-summary-content {
  display: flex;
  column-gap: 12px;
  height: 100%;
}
.overview-panel {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  row-gap: 12px;
  min-height: 0;
}
.panel-title {
  font-size: 14px;
  font-weight: 700;
}
.overview-box {
  flex: 1 1 0;
  min-height: 0;
  background-color: #f3f3f3;
}
.symptoms-box {
  flex: 1 1 0;
  background-color: #fff;
  display: flex;
  column-gap: 12px;
  padding: 8px 12px;
  min-height: 0;
}
.symptoms-column {
  flex: 0 0 50%;
  display: flex;
  flex-direction: column;
  row-gap: 16px;
}
.symptoms-column:first-child {
  flex: 0 0 60%;
}
.symptoms-column:last-child {
  flex: 0 0 40%;
}
.symptom-row {
  display: flex;
  align-items: center;
  column-gap: 8px;
  row-gap: 8px;
  font-size: 14px;
}
.detailed-wearable {
  flex: 3 1 0;
  min-height: 0;
  :deep(.n-card__content) {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
}
.chart-wrapper {
  flex: 1 1 0;
  min-height: 0;
}
.chart-wrapper :deep(.chart) {
  min-height: 220px;
}
.indigo-title :deep(.roundtag__label) {
  background-color: #5171AB !important;
  color: #fff;
}
.indigo-title :deep(.roundtag__round) {
  background-color: #5171AB !important;
}
.full-title-bar :deep(.roundtag) {
  width: 100%;
  left: 0;
  right: 0;
}
.full-title-bar :deep(.roundtag__label) {
  width: 100%;
  justify-content: flex-start;
  padding: 0 12px;
  border-radius: 0;
}
.full-title-bar :deep(.roundtag__round) {
  display: none;
}
.full-title-bar :deep(.n-card.color-card) {
  border-left: none;
}
.empty-card {
  height: 100%;
}
.table-row-block {
  cursor: pointer;
}
.information {
  flex: 1 1 0;
  min-height: 0;
  :deep(.n-card__content) {
    overflow: overlay;
    padding: 16px 16px;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  :deep(.n-spin),
  :deep(.n-spin-container),
  :deep(.n-spin-content) {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }
}
</style>
