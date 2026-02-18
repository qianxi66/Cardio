<script setup lang="tsx">
import { useRouteParams } from "@vueuse/router";
import { useRouteQuery } from "@vueuse/router";
import { useRouter } from "vue-router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import ReportDetailView from "@/views/ReportDetailView.vue";
import { computed, watch, ref, inject, type Component } from "vue";
import { useResizeObserver } from "@vueuse/core";
import type { Patient, Summary } from "@/api/types";
import { getPatient, getSummaries } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format } from "date-fns";
import type { CancelTokenSource } from "axios";
import axios from "axios";

type HospitalizationEntry = {
  date?: string;
  therapy?: string;
  treatment?: string;
  event?: string;
};

const refreshPatients = inject("refreshPatients");
const patient_id = useRouteParams("patient_id");
const query_date_ = useRouteQuery<string | undefined>("date");

const patient = ref<Patient | null>(null);
const summaries = ref<Summary[]>([]);
const loading = ref(true);
const cancelToken = ref<CancelTokenSource | null>(null);
const dailySummaryDate = ref<number | null>(Date.now());
const patientName = computed(() => {
  const data = patient.value as (Patient & { patient_name?: string; name?: string }) | null;
  return data?.patient_name || data?.name || data?.users?.[0]?.name || "n/a";
});
const participantIdLabel = computed(() => {
  return patient.value?.participant_id || "n/a";
});
const patientIdParam = computed(() => {
  const raw = patient_id.value;
  if (!raw) return undefined;
  const parsed = parseInt(raw as string, 10);
  return Number.isNaN(parsed) ? undefined : parsed;
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
      therapy: entry?.therapy || entry?.treatment || entry?.event || "",
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

const formatMetric = (value?: number | null, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return Number(value).toFixed(digits);
};

const wearableOverviewRows = computed(() => {
  const summary = summaryForDate.value;
  if (!summary) {
    return [];
  }
  return [
    {
      label: "Heart rate",
      unit: "BPM",
      average: formatMetric(summary.heart_rate_average, 0),
      max: formatMetric(summary.heart_rate_max, 0),
      min: formatMetric(summary.heart_rate_min, 0),
    },
    {
      label: "SpO2",
      unit: "%",
      average: formatMetric(summary.spo2_average),
      max: formatMetric(summary.spo2_max),
      min: formatMetric(summary.spo2_min),
    },
    {
      label: "Respiration",
      unit: "BPM",
      average: formatMetric(summary.respiration_average),
      max: formatMetric(summary.respiration_max),
      min: formatMetric(summary.respiration_min),
    },
    {
      label: "HRV",
      unit: "ms",
      average: formatMetric(summary.hrv_average),
      max: formatMetric(summary.hrv_max),
      min: formatMetric(summary.hrv_min),
    },
  ];
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
  return boolVal ? 2 : 1;
};

const symptomsLeft = computed(() => {
  const summary = summaryForDate.value;
  return [
    {
      label: "Shortness of Breath",
      symptom: "short_of_breath",
      state: symptomState(summary, "short_of_breath"),
    },
    {
      label: "Chest Discomfort",
      symptom: "chest_discomfort",
      state: symptomState(summary, "chest_discomfort"),
    },
    {
      label: "Fatigue",
      symptom: "fatigue",
      state: symptomState(summary, "fatigue"),
    },
  ];
});

const symptomsRight = computed(() => {
  const summary = summaryForDate.value;
  return [
    {
      label: "Palpitation",
      symptom: "palpitation",
      state: symptomState(summary, "palpitation"),
    },
    {
      label: "Swelling",
      symptom: "swelling",
      state: symptomState(summary, "swelling"),
    },
    {
      label: "Syncope",
      symptom: "syncope",
      state: symptomState(summary, "syncope"),
    },
  ];
});

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
    display_name: "Faint",
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
        dateLabel: parsed ? format(parsed, "yyyy-MM-dd") : "n/a",
        isSelected: !!selectedKey && !!summaryKey && selectedKey === summaryKey,
      };
    })
    .sort((a, b) => (b.timestamp ?? Number.MIN_SAFE_INTEGER) - (a.timestamp ?? Number.MIN_SAFE_INTEGER));
});

const selectDayOverview = (timestamp: number | null) => {
  if (timestamp === null) {
    return;
  }
  dailySummaryDate.value = timestamp;
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
                <div class="hospitalizations-scroll">
                  <div class="hospitalizations">
                  <div
                    class="hospitalization-entry"
                    v-for="(entry, index) in hospitalizations"
                    :key="`${entry.date}-${index}`"
                  >
                    <span class="date">{{ formatHospitalizationDate(entry.date) }}</span>
                    <span class="therapy">{{ entry.therapy || "n/a" }}</span>
                  </div>
                  <div v-if="hospitalizations.length === 0" class="hospitalization-entry">
                    <span class="date">n/a</span>
                    <span class="therapy">n/a</span>
                  </div>
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

            <div class="overview-box">
              <div class="overview-box-content">
                <div
                  class="overview-row"
                  v-for="item in wearableOverviewRows"
                  :key="item.label"
                >
                  <div> <b>{{ item.label }}</b> ({{ item.unit }})</div>
                  <div class="overview-metrics-group">
                    <span class="overview-metric">
                      <b>{{ item.average }}</b> (average);
                    </span>
                    <span class="overview-metric">
                      <b>{{ item.max }}</b> (max);
                    </span>
                    <span class="overview-metric">
                      <b>{{ item.min }}</b> (min)
                    </span>
                  </div>
                </div>
                <div v-if="wearableOverviewRows.length === 0" class="overview-row-empty">
                  <div class="overview-label">n/a</div>
                  <div class="overview-metrics-group">
                    <span class="overview-metric">n/a</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="overview-panel">
            <div class="panel-title">Symptoms Overview</div>
            <div class="symptoms-box">
              <div class="symptoms-column">
                <div
                  class="symptom-row"
                  v-for="(item, index) in symptomsLeft"
                  :key="item.label"
                  :class="{ clickable: item.state !== 0 && summaryForDate }"
                  @click="
                    item.state !== 0 &&
                      summaryForDate &&
                      jumpToSummary(summaryForDate, item.symptom)
                  "
                >
                  <Dot :state="item.state" />
                  <span>{{ item.label }}</span>
                </div>
              </div>
              <div class="symptoms-column">
                <div
                  class="symptom-row"
                  v-for="(item, index) in symptomsRight"
                  :key="item.label"
                  :class="{ clickable: item.state !== 0 && summaryForDate }"
                  @click="
                    item.state !== 0 &&
                      summaryForDate &&
                      jumpToSummary(summaryForDate, item.symptom)
                  "
                >
                  <Dot :state="item.state" />
                  <span>{{ item.label }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </ColoredCard>
      <ColoredCard
        class="day-navigator indigo-title full-title-bar"
        title="Daily Symptom Overview"
        color="#5171AB"
        rounded
      >
        <div class="day-navigator-content">
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

            <div class="day-overview-scroll">
              <div
                class="table-row table-row-block day-overview-row"
                v-for="(row, index) in dayOverviewRows"
                :key="row.id"
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
            <component :is="Component || ReportDetailView" ref="right" />
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
.information {
  flex: 1.2 1 0;
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
.hospitalizations-scroll {
  height: 100%;
  overflow: auto;
  padding-right: 4px;
  box-sizing: border-box;
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
  padding: 6px 10px 6px 12px;
  overflow: hidden;
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
.day-navigator {
  flex: 0 0 280px;
  min-height: 140px;
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
}
.day-overview-table {
  height: 100%;
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
.symptom-row.clickable {
  cursor: pointer;
}
.symptom-row.clickable:hover {
  opacity: 0.8;
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
  flex: 1.2 1 0;
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
