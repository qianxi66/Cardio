<script setup lang="tsx">
import { useRouteParams } from "@vueuse/router";
import { useRouteQuery } from "@vueuse/router";
import { useRouter } from "vue-router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import ReportDetailView from "@/views/ReportDetailView.vue";
import { computed, watch, ref, inject, nextTick, type Component } from "vue";
import type { Patient, Summary } from "@/api/types";
import { getPatient, getSummaries } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format } from "date-fns";
import type { CancelTokenSource } from "axios";
import axios from "axios";

const refreshPatients = inject("refreshPatients");
const patient_id = useRouteParams("patient_id");
const query_date_ = useRouteQuery<string | undefined>("date");

const patient = ref<Patient | null>(null);
const summaries = ref<Summary[]>([]);
const loading = ref(true);
const cancelToken = ref<CancelTokenSource | null>(null);
const dailySummaryDate = ref<number | null>(Date.now());
const wearableRange = ref<"24h" | "7d">("24h");
const dayOverviewScrollEl = ref<HTMLElement | null>(null);
const didAutoScrollDayOverview = ref(false);
const selectedSeries = ref<Record<string, boolean>>({
  "Heart Rate": true,
  Respiration: true,
  SpO2: true,
  "Heart Rate Variability": true,
});
const toggleSeries = (name: string) => {
  selectedSeries.value = {
    ...selectedSeries.value,
    [name]: !selectedSeries.value[name],
  };
};
const patientName = computed(() => {
  const data = patient.value as (Patient & { patient_name?: string; name?: string }) | null;
  return data?.patient_name || data?.name || data?.users?.[0]?.name || "--";
});
const participantIdLabel = computed(() => {
  return patient.value?.participant_id || "--";
});
const patientIdParam = computed(() => {
  const raw = patient_id.value;
  if (!raw) return undefined;
  const parsed = parseInt(raw as string, 10);
  return Number.isNaN(parsed) ? undefined : parsed;
});
const cancerType = computed(() => {
  return (patient.value as { cancer_type?: string } | null)?.cancer_type || "--";
});
const cancerStage = computed(() => {
  return (patient.value as { cancer_stage?: string } | null)?.cancer_stage || "--";
});
const treatmentType = computed(() => {
  return (patient.value as { treatment_type?: string } | null)?.treatment_type || "--";
});
const treatmentPlan = computed(() => {
  const data = patient.value as
    | {
        treatment_plan?: string;
        treatmentPlan?: string;
        plan?: string;
      }
    | null;
  return data?.treatment_plan || data?.treatmentPlan || data?.plan || "--";
});
const treatmentCycle = computed(() => {
  const data = patient.value as
    | {
        treatment_cycle?: string | number;
        treatmentCycle?: string | number;
        cycle?: string | number;
      }
    | null;
  const cycle = data?.treatment_cycle ?? data?.treatmentCycle ?? data?.cycle;
  return cycle === undefined || cycle === null || cycle === "" ? "--" : String(cycle);
});
const formatPatientDate = (value?: string | Date | null) => {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "--";
  }
  return format(parsed, "dd/MM/yyyy");
};
const nextAppointmentDate = computed(() => {
  const data = patient.value as
    | {
        next_appointment_date?: string | Date;
        nextAppointmentDate?: string | Date;
        appointment_date?: string | Date;
      }
    | null;
  const value =
    data?.next_appointment_date ?? data?.nextAppointmentDate ?? data?.appointment_date;
  return formatPatientDate(value ?? null);
});

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
    didAutoScrollDayOverview.value = false;
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
    summaries.value = await getSummaries(parseInt(patient_id.value as string));
    loading.value = false;
  },
  { immediate: true },
);

watch(
  query_date_,
  (dateStr) => {
    if (dateStr) {
      const ts = parseInt(dateStr, 10);
      if (!Number.isNaN(ts) && dailySummaryDate.value !== ts) {
        dailySummaryDate.value = ts;
      }
    }
  },
  { immediate: true },
);

watch(dailySummaryDate, (value) => {
  if (value === null) {
    if (query_date_.value !== undefined) {
      query_date_.value = undefined;
    }
    return;
  }
  const nextValue = String(value);
  if (query_date_.value !== nextValue) {
    query_date_.value = nextValue;
  }
});

const parseDateValue = (value?: string | Date) => {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
};

const dateKey = (value: Date) => format(value, "yyyy-MM-dd");

const summaryForDate = computed(() => {
  if (!summaries.value.length) {
    return null;
  }
  const target = dailySummaryDate.value ? new Date(dailySummaryDate.value) : null;
  if (target) {
    const targetKey = dateKey(target);
    const match = summaries.value.find((summary) => {
      const parsed = parseDateValue(summary.date);
      return parsed ? dateKey(parsed) === targetKey : false;
    });
    if (match) {
      return match;
    }
  }
  return summaries.value[0];
});

const router = useRouter();
const symptomState = (
  summary: Summary | null,
  symptomKey: string,
): number => {
  if (!summary) return 0;
  const raw = (summary as Record<string, unknown>)[`${symptomKey}_state`];
  const stateVal = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isNaN(stateVal) && stateVal > 0) {
    return Math.min(4, Math.max(1, Math.round(stateVal)));
  }
  const boolVal = (summary as Record<string, unknown>)[symptomKey] as
    | boolean
    | undefined;
  if (boolVal === true) return 2;
  if (boolVal === false) return 1;
  return 0;
};

const dayOverviewSymptoms = [
  {
    key: "short_of_breath",
    display_name: "Breath",
    description: "Shortness of Breath (Dyspnea)",
  },
  {
    key: "chest_discomfort",
    display_name: "Chest",
    description: "Chest Discomfort or Pain",
  },
  {
    key: "fatigue",
    display_name: "Fatigue",
    description: "Fatigue or Tiredness",
  },
  {
    key: "palpitation",
    display_name: "Palpitation",
    description: "Heart Palpitations",
  },
  {
    key: "swelling",
    display_name: "Swelling",
    description: "Swelling (Edema)",
  },
  {
    key: "syncope",
    display_name: "Syncope",
    description: "Fainting or Syncope",
  },
] as const;

const dayOverviewRows = computed(() => {
  const selectedKey = dailySummaryDate.value
    ? dateKey(new Date(dailySummaryDate.value))
    : null;
  return summaries.value
    .map((summary) => {
      const parsed = parseDateValue(summary.date);
      const summaryKey = parsed ? dateKey(parsed) : null;
      return {
        id: summary.id,
        summary,
        timestamp: parsed ? parsed.getTime() : null,
        dateLabel: parsed ? format(parsed, "MM/dd/yyyy") : "--",
        isSelected: !!selectedKey && !!summaryKey && selectedKey === summaryKey,
      };
    })
    .sort((a, b) => (b.timestamp ?? Number.MIN_SAFE_INTEGER) - (a.timestamp ?? Number.MIN_SAFE_INTEGER));
});

const dayOverviewRowHasData = (summary: Summary | null): boolean => {
  return dayOverviewSymptoms.some((symptom) => symptomState(summary, symptom.key) !== 0);
};

watch(
  [dayOverviewRows, loading],
  async ([rows, isLoading]) => {
    if (isLoading || didAutoScrollDayOverview.value || rows.length === 0) return;
    await nextTick();
    const container = dayOverviewScrollEl.value;
    if (!container) return;
    const target = container.querySelector<HTMLElement>('.day-overview-row[data-has-data="1"]');
    if (!target) {
      didAutoScrollDayOverview.value = true;
      return;
    }
    const deltaTop = target.getBoundingClientRect().top - container.getBoundingClientRect().top;
    container.scrollTop += deltaTop;
    didAutoScrollDayOverview.value = true;
  },
  { flush: "post" },
);

const selectDayOverview = (timestamp: number | null) => {
  if (timestamp === null) {
    return;
  }
  dailySummaryDate.value = timestamp;
};

const jumpToDayOverviewSummary = (
  summary: Summary | null,
  timestamp: number | null,
  symptom: string,
) => {
  if (!summary) return;
  const state = symptomState(summary, symptom);
  if (state === 0) return;
  if (timestamp !== null) {
    selectDayOverview(timestamp);
  }
  jumpToSummary(summary, symptom);
};

const jumpToSummary = (summary: Summary, symptom: string) => {
  const logsRaw = (summary as Record<string, unknown>)[
    `${symptom}_logs`
  ] as string | undefined;
  const logsArr: number[] =
    typeof logsRaw === "string"
      ? (JSON.parse(logsRaw || "[]") as number[])
      : Array.isArray(logsRaw)
        ? (logsRaw as number[])
        : [];
  const dateVal = summary.date;
  const dateTs =
    typeof dateVal === "string"
      ? new Date(dateVal).getTime()
      : dateVal instanceof Date
        ? dateVal.getTime()
        : null;
  router.push({
    name: "patient.detail",
    params: { patient_id: patient_id.value },
    query: {
      symptom,
      logs: logsArr,
      ...(dateTs != null && { date: String(dateTs) }),
    },
  });
};

const right = ref<Component | null>(null);

</script>

<template>
  <div class="patient-layout">
    <div class="row">
      <div class="col main-col">
      <ColoredCard class="information" rounded>
        <div class="card-top-header">
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
                      <n-icon :size="22">
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
            </div>
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
            </template>
          </Loading>
        </div>
        <div class="basic-information-content">
          <div class="basic-top-section">
            <Loading :loading="loading" :has-data="!!patient">
              <div class="row patient-details">
                <div class="box patient-info-box">
                  <div class="detail-line">
                    <span class="label">Cancer Type:</span>
                    <span class="value">{{ cancerType }}</span>
                  </div>
                  <div class="detail-line">
                    <span class="label">Cancer Diagnosis Date:</span>
                    <span class="value">{{ cancerStage }}</span>
                  </div>
                  <div class="detail-line">
                    <span class="label">Medication Allergy History:</span>
                    <span class="value">{{ treatmentType }}</span>
                  </div>
                </div>
                <div class="box patient-plan-box">
                  <div class="detail-line">
                    <span class="label">Treatment Plan:</span>
                    <span class="value">{{ treatmentPlan }}</span>
                  </div>
                  <div class="detail-line">
                    <span class="label">Treatment Cycle:</span>
                    <span class="value">{{ treatmentCycle }}</span>
                  </div>
                  <div class="detail-line">
                    <span class="label">Next Appointment Date:</span>
                    <span class="value">{{ nextAppointmentDate }}</span>
                  </div>
                </div>
              </div>
            </Loading>
          </div>
          <div class="daily-summary-content">
            <div class="overview-panel">
              <div class="panel-title">Admission History</div>

              <div class="overview-box">
                <div class="overview-box-content"></div>
              </div>
            </div>
            <div class="overview-panel">
              <div class="panel-title">Current Medications</div>
              <div class="overall-summary-box">
                <div class="overall-summary-content"></div>
              </div>
            </div>
          </div>
        </div>
      </ColoredCard>
      <ColoredCard
        class="day-navigator indigo-title full-title-bar"
        title="Patient's Daily Symptoms"
        color="#053251"
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
        <div class="day-navigator-content">
          <div class="ai-summary-section">
            <div class="ai-summary-title">AI-Generated Daily Summary</div>
            <div class="ai-summary-body">The patient reports symptoms of syncope and dyspnea. At certain points, they also exhibited a low heart rate alongside rapid breathing.</div>
          </div>
          <div class="day-overview-table">
            <div class="table-row day-overview-header">
              <div class="date">Date</div>
              <div
                class="symptom"
                v-for="symptom in dayOverviewSymptoms"
                :key="symptom.key"
              >
                {{ symptom.display_name }}
              </div>
            </div>

            <div ref="dayOverviewScrollEl" class="day-overview-scroll">
              <div
                class="table-row table-row-block day-overview-row"
                v-for="(row, index) in dayOverviewRows"
                :key="row.id"
                :data-has-data="dayOverviewRowHasData(row.summary) ? '1' : '0'"
                :class="{
                  odd: index % 2 === 1,
                  selected: row.isSelected,
                }"
                @click="selectDayOverview(row.timestamp)"
              >
                <div class="date">{{ row.dateLabel }}</div>
                <div
                  class="symptom"
                  v-for="symptom in dayOverviewSymptoms"
                  :key="`${row.id}-${symptom.key}`"
                  :class="{ clickable: symptomState(row.summary, symptom.key) !== 0 }"
                  @click.stop="
                    jumpToDayOverviewSummary(
                      row.summary,
                      row.timestamp,
                      symptom.key,
                    )
                  "
                >
                  <Dot :state="symptomState(row.summary, symptom.key)" />
                </div>
              </div>
              <div v-if="dayOverviewRows.length === 0" class="day-overview-empty">
                No daily summaries
              </div>
            </div>
          </div>
        </div>
      </ColoredCard>
    </div>
      <div class="col side-col">
        <div class="side-content">
          <router-view v-slot="{ Component }">
            <component :is="Component || ReportDetailView" ref="right">
              <template #top-card>
                <ColoredCard
                  class="detailed-wearable-card indigo-title full-title-bar"
                  title="Patient's Wearable Sensor Data"
                  color="#053251"
                  rounded
                >
                  <template #title-extra>
                    <div class="wearable-range-switch">
                      <button
                        type="button"
                        class="range-btn"
                        :class="{ active: wearableRange === '24h' }"
                        @click="wearableRange = '24h'"
                      >
                        <span class="range-dot" aria-hidden="true"></span>
                        <span>Last 24 Hrs</span>
                      </button>
                      <button
                        type="button"
                        class="range-btn"
                        :class="{ active: wearableRange === '7d' }"
                        @click="wearableRange = '7d'"
                      >
                        <span class="range-dot" aria-hidden="true"></span>
                        <span>Last 7 days</span>
                      </button>
                    </div>
                  </template>
                  <div class="wearable-chart-wrapper">
                    <DetailedWearableChart
                      :patient-id="patientIdParam ?? undefined"
                      :range="wearableRange"
                      :selected-series="selectedSeries"
                      @toggle-series="toggleSeries"
                    />
                  </div>
                </ColoredCard>
              </template>
            </component>
          </router-view>
        </div>
      </div>
      <div class="overview-connectors" aria-hidden="true">
        <span class="connector-tail"></span>
        <span class="connector-vertical"></span>
        <span class="connector-branch connector-branch-top"></span>
        <span class="connector-branch connector-branch-bottom"></span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.row {
  position: relative;
  flex-grow: 1;
  min-width: 0;
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
.overview-connectors {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 6;
}
.connector-tail,
.connector-vertical,
.connector-branch {
  position: absolute;
  background-color: #053251;
  opacity: 0.9;
}
.connector-tail {
  left: calc(53% - 10px);
  top: 41%;
  width: 10px;
  height: 4px;
}
.connector-vertical {
  left: calc(53% - 1px);
  top: calc(43% - 300px);
  width: 4px;
  height: 378px;
}
.connector-branch {
  left: calc(53% + 3px);
  width: 4px;
  height: 4px;
}
.connector-branch-top {
  top: calc(43% - 300px);
}
.connector-branch-bottom {
  top: calc(43% + 74px);
}
.main-col,
.side-col {
  min-width: 0;
  padding-bottom: 16px;
  box-sizing: border-box;
}

.row > .main-col {
  flex: 53 1 0;
}

.row > .side-col {
  flex: 47 1 0;
}

.patient-header {
  align-items: center;
  column-gap: 12px;
  width: 100%;
  overflow-y: hidden;
}
.information {
  flex: 4 1 0;
  min-height: 0;
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
  font-size: 25px;
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
.patient-nav-spacer {
  flex: 0 0 auto;
}
.detailed-wearable-card :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.detailed-wearable-card {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  border: 2px solid #053251 !important;
}
.wearable-chart-wrapper {
  flex: 1 1 0;
  min-height: 240px;
  overflow: hidden;
  display: flex;
  min-width: 0;
}
.wearable-range-switch {
  display: inline-flex;
  align-items: center;
  gap: 24px;
  margin-right: 6px;
}
.range-btn {
  border: none;
  background: transparent;
  color: #053251;
  height: 24px;
  padding: 0;
  font-size: 14px;
  font-weight: 700;
  line-height: 24px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  opacity: 0.9;
  transition: opacity 0.15s ease;
}
.range-btn:hover {
  opacity: 1;
}
.range-dot {
  width: 14px;
  height: 14px;
  border: 2px solid #053251;
  border-radius: 50%;
  box-sizing: border-box;
  position: relative;
  flex: 0 0 14px;
}
.range-btn.active {
  opacity: 1;
}
.range-btn.active .range-dot::after {
  content: "";
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #053251;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
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
.card-top-header {
  padding: 0 0 12px 0;
}
.card-top-header :deep(.n-spin),
.card-top-header :deep(.n-spin-container),
.card-top-header :deep(.n-spin-content) {
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
.patient-layout > .row:first-of-type {
  margin-top: 16px;
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
.detail-line {
  display: flex;
  column-gap: 6px;
  line-height: 22px;
}
.detail-line .label {
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
.patient-details > .box {
  height: 100%;
}
.patient-info-box {
  background-color: #fff;
  padding: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  row-gap: 4px;
}
.patient-plan-box {
  background-color: #fff;
  padding: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  row-gap: 4px;
}
.patient-info-box .detail-line {
  flex: 0 0 auto;
  align-items: center;
}
.patient-plan-box .detail-line {
  flex: 0 0 auto;
  align-items: center;
}
.basic-information-content {
  display: flex;
  flex-direction: column;
  row-gap: 0px;
  height: 100%;
  min-height: 0;
}
.basic-top-section {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
}
.basic-top-section :deep(.n-spin),
.basic-top-section :deep(.n-spin-container),
.basic-top-section :deep(.n-spin-content) {
  height: 100%;
  min-height: 0;
  width: 100%;
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
  min-width: 0;
  display: flex;
}
.daily-summary {
  flex: 2 1 0;
  min-height: 0;
  min-width: 0;
}
.day-navigator {
  flex: 6 1 0;
  min-height: 0;
}
.day-navigator :deep(.n-card__content) {
  height: 100%;
  min-height: 0;
}
.day-navigator-content {
  height: 100%;
  min-height: 0;
  background-color: #ffffff;
  box-sizing: border-box;
  padding: 0px 0px;
  display: flex;
  flex-direction: column;
}
.ai-summary-section {
  flex: 0 0 auto;
  padding-bottom: 16px;
  border-bottom: 2px solid #053251;
}
.ai-summary-title {
  font-size: 18px;
  font-weight: 700;
  color: #053251;
}
.ai-summary-body {
  margin-top: 8px;
  font-size: 12px;
  color: #333;
  line-height: 1.5;
}
.day-overview-table {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  font-size: 14px;
}
.day-overview-table .table-row {
  width: 100%;
  display: flex;
  align-items: center;
}
.day-overview-table .date {
  flex: 0 0 98px;
  padding-left: 8px;
  box-sizing: border-box;
  white-space: nowrap;
}
.day-overview-table .symptom {
  flex: 1 1 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 0;
}
.day-overview-table .symptom.clickable {
  cursor: pointer;
}
.day-overview-table .symptom :deep(.n-icon) {
  font-size: 12px;
}
.day-overview-header {
  flex: 0 0 38px;
  font-weight: 700;
  border-bottom: 1px solid #d9d9d9;
}
.day-overview-scroll {
  flex: 1 1 0;
  min-height: 0;
  overflow: auto;
}
.day-overview-row {
  height: 36px;
  cursor: pointer;
  background: #ffffff;
}
.day-overview-row.odd {
  background: #f3f3f3;
}
.day-overview-row:hover {
  background: #e9edf5;
}
.day-overview-row.selected {
  outline: none;
}
.day-overview-empty {
  height: 100%;
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999999;
}
.daily-summary-content {
  flex: 1 1 0;
  display: flex;
  column-gap: 16px;
  min-height: 0;
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
  padding: 12px 10px 12px 12px;
  overflow: hidden;
  box-sizing: border-box;
}
.overview-box-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  row-gap: 0;
  overflow: auto;
  padding-right: 4px;
  box-sizing: border-box;
}
.overview-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  font-size: 12px;
  line-height: 1;
  margin-bottom: 16px;
}

.overview-row-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.5;
}

.overview-label {
  font-weight: bold;
  margin-bottom: 4px;
  color: #333;
}

.overview-metrics-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #555;
  margin-top: 8px;
}

.overview-metric {
  white-space: nowrap;
}

.overview-metric b {
  font-weight: 800;
}

.symptoms-box {
  flex: 1 1 0;
  background-color: #fff;
  display: flex;
  column-gap: 12px;
  padding: 8px 12px;
  min-height: 0;
}
.symptoms-placeholder {
  flex: 1 1 0;
  min-height: 0;
}
.overall-summary-box {
  flex: 1 1 0;
  min-height: 0;
  background-color: #f3f3f3;
  padding: 12px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  row-gap: 10px;
}
.overall-summary-content {
  flex: 1 1 0;
  min-height: 0;
  overflow: auto;
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
  row-gap: 4px;
  font-size: 14px;
}
.symptom-row.clickable {
  cursor: pointer;
}
.symptom-row.clickable:hover {
  opacity: 0.8;
}
.indigo-title :deep(.roundtag__label) {
  background-color: #053251 !important;
  color: #fff;
}
.indigo-title :deep(.roundtag__round) {
  background-color: #053251 !important;
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
.full-title-bar.detailed-wearable-card :deep(.roundtag__label) {
  background-color: #d7d7d7 !important;
  border: 2px solid #053251 !important;
  border-left-width: 6px !important;
  border-bottom-width: 2px !important;
  border-top-width: 0px !important;
  border-right-width: 0px !important;
  box-sizing: border-box;
  color: #053251 !important;
}
.full-title-bar :deep(.roundtag__extra) {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
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
  flex: 4 1 0;
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
