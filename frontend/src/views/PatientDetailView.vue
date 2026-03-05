<script setup lang="tsx">
import { useRouteParams } from "@vueuse/router";
import { useRouteQuery } from "@vueuse/router";
import { useRouter } from "vue-router";
import type { DrawerPlacement } from "naive-ui";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import { markSymptomRead, updateSummarySymptomState } from "@/api/patient";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import ReportDetailView from "@/views/ReportDetailView.vue";
import { computed, watch, ref, inject, nextTick, onMounted, onBeforeUnmount, type Component } from "vue";
import type { Patient, Summary, ReportNote } from "@/api/types";
import { getPatient, getSummaries, getWearableCoverage, getNotes, type WearableCoverage } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format } from "date-fns";
import type { CancelTokenSource } from "axios";
import axios from "axios";

const refreshPatients = inject<(() => void | Promise<void>) | undefined>("refreshPatients");
const patient_id = useRouteParams("patient_id");
const query_date_ = useRouteQuery<string | undefined>("date");

const patient = ref<Patient | null>(null);
const summaries = ref<Summary[]>([]);
const reportNotes = ref<ReportNote[]>([]);
const wearableCoverage = ref<WearableCoverage>({});
const loading = ref(true);
const wearableLoading = ref(false);
const cancelToken = ref<CancelTokenSource | null>(null);
const dailySummaryDate = ref<number | null>(Date.now());
const wearableDate = computed(() => {
  if (!dailySummaryDate.value) return format(new Date(), "yyyy-MM-dd");
  return format(new Date(dailySummaryDate.value), "yyyy-MM-dd");
});
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

const aiSummaryBodyText = computed(() => {
  const notes = patient.value?.notes ?? [];
  const selectedDate = dailySummaryDate.value ? new Date(dailySummaryDate.value) : null;
  if (!selectedDate || Number.isNaN(selectedDate.getTime())) {
    return "no data for this date";
  }
  const selectedKey = dateKey(selectedDate);

  const match = notes
    .filter((note) => {
      if (note.creator_type?.toLowerCase() !== "ai") return false;
      const created = parseDateValue(note.created_at);
      return created ? dateKey(created) === selectedKey : false;
    })
    .sort((a, b) => {
      const at = parseDateValue(a.created_at)?.getTime() ?? 0;
      const bt = parseDateValue(b.created_at)?.getTime() ?? 0;
      return bt - at;
    })[0];

  if (!match?.content?.trim()) {
    return "no data for this date";
  }
  const createdAt = parseDateValue(match.created_at);
  const cleanedContent = match.content
    .trim()
    .replace(/^ai\s*summary\s*:?\s*/i, "");
  const timeLabel = createdAt ? format(createdAt, "HH:mm") : "--:--";
  return `${format(selectedDate, "MM/dd/yyyy")} ${timeLabel} ${cleanedContent}`;
});

const parseNoteTime = (value?: Date | string) => {
  if (!value) return 0;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
};

const clinicianNotes = computed(() => {
  const currentPatientId = patientIdParam.value;
  if (!currentPatientId || !reportNotes.value.length) {
    return [] as ReportNote[];
  }

  return reportNotes.value
    .filter((n) => n.patient_id === currentPatientId && (typeof n.user_id === "number" || !!n.user))
    .sort((a, b) => {
      const aTime = parseNoteTime(a.updated_at) || parseNoteTime(a.created_at);
      const bTime = parseNoteTime(b.updated_at) || parseNoteTime(b.created_at);
      return bTime - aTime;
    });
});

const admissionDrawerVisible = ref(false);
const medicationDrawerVisible = ref(false);
const notesDrawerVisible = ref(false);
const preadmissionMedDrawerVisible = ref(false);
const ioMetricDrawerVisible = ref(false);
const medExecDrawerVisible = ref(false);
const drawerPlacement = ref<DrawerPlacement>("right");

const openAdmissionDrawer = () => {
  admissionDrawerVisible.value = true;
};

const openMedicationDrawer = () => {
  medicationDrawerVisible.value = true;
};

const openNotesDrawer = () => {
  notesDrawerVisible.value = true;
};

const openPreadmissionMedDrawer = () => {
  preadmissionMedDrawerVisible.value = true;
};

const openIOMetricDrawer = () => {
  ioMetricDrawerVisible.value = true;
};

const openMedExecDrawer = () => {
  medExecDrawerVisible.value = true;
};

watch(
  patient_id,
  async () => {
    console.log("patient_id changed", patient_id.value);
    if (!patient_id.value) {
      patient.value = null;
      reportNotes.value = [];
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
    summaries.value = (await getSummaries(parseInt(patient_id.value as string))) ?? [];
    reportNotes.value = (await getNotes(parseInt(patient_id.value as string))) ?? [];
    loading.value = false;
    // Fetch MongoDB wearable coverage asynchronously — does not block patient info display
    const coverageDates = summaries.value
      .map((s) => { const p = parseDateValue(s.date); return p ? dateKey(p) : null; })
      .filter((d): d is string => d !== null);
    if (coverageDates.length) {
      wearableLoading.value = true;
      getWearableCoverage(
        parseInt(patient_id.value as string),
        coverageDates,
      ).then((cov) => {
        wearableCoverage.value = cov;
      }).catch(() => {
        wearableCoverage.value = {};
      }).finally(() => {
        wearableLoading.value = false;
      });
    }
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
    return Math.min(3, Math.max(1, Math.round(stateVal)));
  }
  const boolVal = (summary as Record<string, unknown>)[symptomKey] as
    | boolean
    | undefined;
  if (boolVal === true) return 2;
  if (boolVal === false) return 1;
  return 0;
};

// For wearable symptoms (heart_rate, respiration), override state from MongoDB coverage.
// state 1 = green (has data), state 0 = grey (no data / still loading).
const dotStateForSymptom = (
  summary: Summary | null,
  symptomKey: string,
  wearable: boolean,
): number => {
  if (!wearable) return symptomState(summary, symptomKey);
  if (!summary) return 0;
  const currentState = symptomState(summary, symptomKey);
  if (currentState > 0) return currentState;
  const parsed = parseDateValue(summary.date);
  if (!parsed) return 0;
  const key = dateKey(parsed);
  const cov = wearableCoverage.value[key];
  return cov ? 1 : 0;
};

const handleDayOverviewDotStateChange = async (
  summary: Summary | null,
  symptom: string,
  nextState: number,
) => {
  if (!summary || !patient_id.value) return;
  const patientId = Number(patient_id.value);
  const summaryRecord = summary as Record<string, unknown>;
  const stateKey = `${symptom}_state`;
  const readKey = "read";
  const prevState = Number(summaryRecord[stateKey]);
  const prevRead = summaryRecord[readKey];

  summaryRecord[stateKey] = nextState;
  summaryRecord[readKey] = 1;

  try {
    await updateSummarySymptomState(patientId, summary.id, symptom, nextState);
    await refreshPatients?.();
  } catch {
    if (!Number.isNaN(prevState)) {
      summaryRecord[stateKey] = prevState;
    }
    summaryRecord[readKey] = prevRead;
  }
};

const dayOverviewSymptoms = [
  { key: "syncope",         display_name: "Syncope",     description: "Fainting or Syncope",            wearable: false },
  { key: "palpitation",     display_name: "Palps",       description: "Heart Palpitations",             wearable: false },
  { key: "short_of_breath", display_name: "Breath",      description: "Shortness of Breath (Dyspnea)",  wearable: false },
  { key: "chest_discomfort",display_name: "Chest",       description: "Chest Discomfort or Pain",       wearable: false },
  { key: "swelling",        display_name: "Swelling",    description: "Swelling (Edema)",               wearable: false },
  { key: "heart_rate",      display_name: "Heart Rate",  description: "Heart Rate",                     wearable: true  },
  { key: "respiration",     display_name: "Resp",        description: "Respiration Rate",               wearable: true  },
];

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

const armedDayOverviewDotKey = ref<string | null>(null);

const getDayOverviewDotKey = (rowId: number, symptomKey: string) => `${rowId}-${symptomKey}`;

const isDayOverviewDotArmed = (rowId: number, symptomKey: string) =>
  armedDayOverviewDotKey.value === getDayOverviewDotKey(rowId, symptomKey);

const dayOverviewRowHasData = (summary: Summary | null): boolean => {
  return dayOverviewSymptoms.some((symptom) => symptomState(summary, symptom.key) !== 0);
};

const isSummaryRead = (summary: Summary | null): boolean => {
  if (!summary) return true;
  const readVal = (summary as Record<string, unknown>)["read"];
  return readVal === 1 || readVal === true;
};

const dayOverviewRowHasUnread = (summary: Summary | null): boolean => {
  return !isSummaryRead(summary);
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

const markDayOverviewRowRead = (summary: Summary | null) => {
  if (!summary || !patient_id.value) return;
  if (isSummaryRead(summary)) return;
  const patientId = Number(patient_id.value);
  markSymptomRead(patientId, summary.id)
    .then(() => {
      (summary as Record<string, unknown>)["read"] = 1;
    })
    .catch(() => {});
};

const handleDayOverviewRowClick = (row: { summary: Summary | null; timestamp: number | null }) => {
  selectDayOverview(row.timestamp);
  markDayOverviewRowRead(row.summary);
};

const jumpToDayOverviewSummary = (
  summary: Summary | null,
  timestamp: number | null,
  symptom: string,
  wearable: boolean,
) => {
  if (!summary) return;
  const state = dotStateForSymptom(summary, symptom, wearable);
  if (state === 0) return;
  if (timestamp !== null) {
    selectDayOverview(timestamp);
  }
  // Mark as read (fire-and-forget)
  const readVal = (summary as Record<string, unknown>)["read"];
  const isAlreadyRead = readVal === 1 || readVal === true;
  if (!isAlreadyRead && patient_id.value) {
    markSymptomRead(Number(patient_id.value), summary.id).then(() => {
      (summary as Record<string, unknown>)["read"] = 1;
    }).catch(() => {});
  }
  jumpToSummary(summary, symptom);
};

const handleDayOverviewDotClick = (
  row: { id: number; summary: Summary | null; timestamp: number | null },
  symptom: { key: string; wearable: boolean },
) => {
  const dotKey = getDayOverviewDotKey(row.id, symptom.key);
  if (armedDayOverviewDotKey.value !== dotKey) {
    armedDayOverviewDotKey.value = dotKey;
    jumpToDayOverviewSummary(row.summary, row.timestamp, symptom.key, symptom.wearable);
  }
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

// ── Dynamic connector positioning ──────────────────────────────────────────
const connectorRowEl = ref<HTMLElement | null>(null);
const connectorTailStyle = ref<Record<string, string>>({});
const connectorVerticalStyle = ref<Record<string, string>>({});
const connectorBranchTopStyle = ref<Record<string, string>>({});
const connectorBranchBottomStyle = ref<Record<string, string>>({});

const updateConnectors = () => {
  const rowEl = connectorRowEl.value;
  const rightComp = right.value as (typeof right.value & { $el?: HTMLElement }) | null;
  if (!rowEl || !rightComp?.$el) return;

  const reportEl = rightComp.$el as HTMLElement;
  const wearableCard = reportEl.querySelector('.detailed-wearable-card') as HTMLElement | null;
  const conversationCard = reportEl.querySelector('.conversation-card') as HTMLElement | null;
  if (!wearableCard || !conversationCard) return;

  const wearableHeader = wearableCard.querySelector('.n-card__header') as HTMLElement | null;
  const conversationHeader = conversationCard.querySelector('.n-card__header') as HTMLElement | null;
  if (!wearableHeader || !conversationHeader) return;

  const rowRect = rowEl.getBoundingClientRect();
  const wh = wearableHeader.getBoundingClientRect();
  const ch = conversationHeader.getBoundingClientRect();

  const wearableCenterY = (wh.top + wh.bottom) / 2 - rowRect.top;
  const conversationCenterY = (ch.top + ch.bottom) / 2 - rowRect.top;
  const midY = (wearableCenterY + conversationCenterY) / 2;

  connectorTailStyle.value = { top: `${midY - 2}px` };
  connectorVerticalStyle.value = {
    top: `${wearableCenterY - 2}px`,
    height: `${Math.max(conversationCenterY - wearableCenterY + 4, 4)}px`,
  };
  connectorBranchTopStyle.value = { top: `${wearableCenterY - 2}px` };
  connectorBranchBottomStyle.value = { top: `${conversationCenterY - 2}px` };
};

let _connectorRO: ResizeObserver | null = null;
onMounted(() => {
  nextTick(() => updateConnectors());
  _connectorRO = new ResizeObserver(() => updateConnectors());
  if (connectorRowEl.value) _connectorRO.observe(connectorRowEl.value);
  window.addEventListener('resize', updateConnectors);
});
onBeforeUnmount(() => {
  _connectorRO?.disconnect();
  window.removeEventListener('resize', updateConnectors);
});
watch(right, () => nextTick(updateConnectors));
watch(loading, () => nextTick(updateConnectors));

</script>

<template>
  <div class="patient-layout">
    <div class="row" ref="connectorRowEl">
      <div class="col main-col">
      <ColoredCard class="information" rounded>
        <div class="card-top-header">
          <Loading :loading="loading" :has-data="!!patient">
            <div class="row patient-header">
              <div class="patient-avatar" aria-hidden="true">
                <svg viewBox="0 0 512 512">
                  <path
                    d="M458.159,404.216c-18.93-33.65-49.934-71.764-100.409-93.431c-28.868,20.196-63.938,32.087-101.745,32.087
                    c-37.828,0-72.898-11.89-101.767-32.087c-50.474,21.667-81.479,59.782-100.398,93.431C28.731,448.848,48.417,512,91.842,512
                    c43.426,0,164.164,0,164.164,0s120.726,0,164.153,0C463.583,512,483.269,448.848,458.159,404.216z"
                    fill="currentColor"
                  />
                  <path
                    d="M256.005,300.641c74.144,0,134.231-60.108,134.231-134.242v-32.158C390.236,60.108,330.149,0,256.005,0
                    c-74.155,0-134.252,60.108-134.252,134.242V166.4C121.753,240.533,181.851,300.641,256.005,300.641z"
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
              <div class="patient-nav-spacer"></div>
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
                <div class="patient-nav-spacer"></div>
                <n-skeleton
                  style="height: 46px; width: 260px"
                ></n-skeleton>
              </div>
            </template>
          </Loading>
        </div>
        <div class="basic-information-content">
          <div class="basic-top-section">
            <div v-if="patient" class="row patient-details">
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
              <div v-if="patient" class="patient-action-bar">
                <div class="patient-action-cell">
                  <button type="button" class="panel-title panel-drawer-trigger" @click="openAdmissionDrawer">
                    Admission History
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button type="button" class="panel-title panel-drawer-trigger" @click="openMedicationDrawer">
                    Medications
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button type="button" class="panel-title panel-drawer-trigger" @click="openNotesDrawer">
                    Notes
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button type="button" class="panel-title panel-drawer-trigger" @click="openPreadmissionMedDrawer">
                    Pre-Admission Meds
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button type="button" class="panel-title panel-drawer-trigger" @click="openIOMetricDrawer">
                    I/O Metrics
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button type="button" class="panel-title panel-drawer-trigger" @click="openMedExecDrawer">
                    Med Execution
                  </button>
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
        <template #title-inline>
          <n-tooltip trigger="hover">
            <template #trigger>
              <button type="button" class="day-symptoms-info" aria-label="Daily symptoms help">
                <span class="day-symptoms-info-glyph" aria-hidden="true"></span>
              </button>
            </template>
            Click the report line to view detailed information or update the dot's status.
          </n-tooltip>
        </template>
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
            <div class="ai-summary-title">
              <svg
                class="ai-summary-title-icon"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <path
                  fill="currentColor"
                  d="M21 10.975V8a2 2 0 0 0-2-2h-6V4.688c.305-.274.5-.668.5-1.11a1.5 1.5 0 0 0-3 0c0 .442.195.836.5 1.11V6H5a2 2 0 0 0-2 2v2.998l-.072.005A.999.999 0 0 0 2 12v2a1 1 0 0 0 1 1v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5a1 1 0 0 0 1-1v-1.938a1.004 1.004 0 0 0-.072-.455c-.202-.488-.635-.605-.928-.632zM7 12c0-1.104.672-2 1.5-2s1.5.896 1.5 2-.672 2-1.5 2S7 13.104 7 12zm8.998 6c-1.001-.003-7.997 0-7.998 0v-2s7.001-.002 8.002 0l-.004 2zm-.498-4c-.828 0-1.5-.896-1.5-2s.672-2 1.5-2 1.5.896 1.5 2-.672 2-1.5 2z"
                />
              </svg>
              <span>AI-Generated Daily Summary</span>
            </div>
            <div class="ai-summary-body">{{ aiSummaryBodyText }}</div>
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
                @click="handleDayOverviewRowClick(row)"
              >
                <div class="date" :class="{ 'date-unread': dayOverviewRowHasUnread(row.summary) }">{{ row.dateLabel }}</div>
                <div
                  class="symptom"
                  v-for="symptom in dayOverviewSymptoms"
                  :key="`${row.id}-${symptom.key}`"
                  :class="{ clickable: true, 'dot-armed': isDayOverviewDotArmed(row.id, symptom.key) }"
                  @click.stop="handleDayOverviewDotClick(row, symptom)"
                >
                  <Dot
                    :state="dotStateForSymptom(row.summary, symptom.key, symptom.wearable)"
                    :isRead="(row.summary as any)?.read ?? 0"
                    :variant="'circle'"
                    :editable="isDayOverviewDotArmed(row.id, symptom.key)"
                    @update:state="handleDayOverviewDotStateChange(row.summary, symptom.key, $event)"
                    :loading="symptom.wearable && wearableLoading"
                  />
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
          </template>
                  <div class="wearable-chart-wrapper">
                    <DetailedWearableChart
                      :patient-id="patientIdParam ?? undefined"
                      :date="wearableDate"
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
        <span class="connector-tail" :style="connectorTailStyle"></span>
        <span class="connector-vertical" :style="connectorVerticalStyle"></span>
        <span class="connector-branch connector-branch-top" :style="connectorBranchTopStyle"></span>
        <span class="connector-branch connector-branch-bottom" :style="connectorBranchBottomStyle"></span>
      </div>
    </div>

    <n-drawer
      v-model:show="admissionDrawerVisible"
      :default-height="420"
      placement="bottom"
      resizable
    >
      <n-drawer-content title="Admission History">
        <template v-if="patient?.admission_histories?.length">
          <div class="drawer-table">
            <table>
              <thead>
                <tr>
                  <th>Admission</th>
                  <th>Discharge</th>
                  <th>Diagnosis</th>
                  <th>Symptoms</th>
                  <th>Care Unit</th>
                  <th>Dest Unit</th>
                  <th>Type</th>
                  <th>Discharge Status</th>
                  <th>Readmission</th>
                  <th>LOS (min)</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(ah, i) in patient.admission_histories" :key="`adm-${i}`">
                  <td>{{ formatPatientDate(ah.admission_date) }}</td>
                  <td>{{ ah.discharge_date ? formatPatientDate(ah.discharge_date) : 'Ongoing' }}</td>
                  <td>{{ ah.diagnosis || '--' }}</td>
                  <td>{{ ah.symptoms || '--' }}</td>
                  <td>{{ ah.careunit_name || '--' }}</td>
                  <td>{{ ah.destination_unit_name || '--' }}</td>
                  <td>{{ ah.admission_type || '--' }}</td>
                  <td>{{ ah.discharge_status || '--' }}</td>
                  <td>{{ ah.readmission_flag ? 'Yes' : 'No' }}</td>
                  <td>{{ ah.los_minutes ?? '--' }}</td>
                  <td>{{ ah.notes || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="overview-row-empty">No admission records.</div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer
      v-model:show="medicationDrawerVisible"
      :default-height="420"
      placement="bottom"
      resizable
    >
      <n-drawer-content title="Medications">
        <template v-if="patient?.medications?.length">
          <div class="drawer-table">
            <table>
              <thead>
                <tr>
                  <th>Drug</th>
                  <th>Dosage</th>
                  <th>Route</th>
                  <th>Frequency</th>
                  <th>Schedule</th>
                  <th>Doses</th>
                  <th>Start</th>
                  <th>End</th>
                  <th>Current</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(med, i) in patient.medications" :key="`med-${i}`">
                  <td>{{ med.drug_name }}</td>
                  <td>{{ med.dosage || '--' }}</td>
                  <td>{{ med.route || '--' }}</td>
                  <td>{{ med.frequency || '--' }}</td>
                  <td>{{ med.schedule_hours || '--' }}</td>
                  <td>{{ med.dose_count ?? '--' }}</td>
                  <td>{{ med.start_date ? formatPatientDate(med.start_date) : '--' }}</td>
                  <td>{{ med.end_date ? formatPatientDate(med.end_date) : 'Ongoing' }}</td>
                  <td>{{ med.is_current_medication ? 'Yes' : 'No' }}</td>
                  <td>{{ med.order_source || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="overview-row-empty">No medications recorded.</div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer
      v-model:show="notesDrawerVisible"
      :default-height="420"
      placement="bottom"
      resizable
    >
      <n-drawer-content title="Notes">
        <template v-if="clinicianNotes.length">
          <div class="drawer-table">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Created By</th>
                  <th>Content</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(note, i) in clinicianNotes" :key="`note-${i}`">
                  <td class="td-nowrap">{{ formatPatientDate(note.updated_at || note.created_at) }}</td>
                  <td class="td-nowrap">{{ (note as any).created_by || note.user?.username || '--' }}</td>
                  <td class="td-wrap">{{ note.content }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="overview-row-empty">No notes recorded.</div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer
      v-model:show="preadmissionMedDrawerVisible"
      :default-height="420"
      placement="bottom"
      resizable
    >
      <n-drawer-content title="Pre-Admission Medications">
        <template v-if="patient?.preadmission_medications?.length">
          <div class="drawer-table">
            <table>
              <thead>
                <tr>
                  <th>Drug</th>
                  <th>Dosage</th>
                  <th>Frequency</th>
                  <th>Started Before</th>
                  <th>Active at Admission</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(pm, i) in patient.preadmission_medications" :key="`pm-${i}`">
                  <td>{{ pm.drug_name }}</td>
                  <td>{{ pm.dosage || '--' }}</td>
                  <td>{{ pm.frequency || '--' }}</td>
                  <td>{{ pm.started_before_admission_date ? formatPatientDate(pm.started_before_admission_date) : '--' }}</td>
                  <td>{{ pm.active_at_admission ? 'Yes' : 'No' }}</td>
                  <td>{{ pm.source_text || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="overview-row-empty">No pre-admission medication records.</div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer
      v-model:show="ioMetricDrawerVisible"
      :default-height="420"
      placement="bottom"
      resizable
    >
      <n-drawer-content title="I/O Metrics">
        <template v-if="patient?.io_metrics?.length">
          <div class="drawer-table">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Events</th>
                  <th>Total Volume (mL)</th>
                  <th>Measurements</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(io, i) in patient.io_metrics" :key="`io-${i}`">
                  <td>{{ io.metric_date ? formatPatientDate(io.metric_date) : '--' }}</td>
                  <td>{{ io.io_event_count ?? '--' }}</td>
                  <td>{{ io.io_total_volume_ml != null ? io.io_total_volume_ml.toFixed(1) : '--' }}</td>
                  <td>{{ io.io_total_volume_measurement_count ?? '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="overview-row-empty">No I/O metric records.</div>
      </n-drawer-content>
    </n-drawer>

    <n-drawer
      v-model:show="medExecDrawerVisible"
      :default-height="420"
      placement="bottom"
      resizable
    >
      <n-drawer-content title="Med Administration Execution">
        <template v-if="patient?.medication_execution_metrics?.length">
          <div class="drawer-table">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Administered</th>
                  <th>Med Events</th>
                  <th>Standing Orders</th>
                  <th>Total Executions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(me, i) in patient.medication_execution_metrics" :key="`me-${i}`">
                  <td>{{ me.metric_date ? formatPatientDate(me.metric_date) : '--' }}</td>
                  <td>{{ me.ad_event_count ?? '--' }}</td>
                  <td>{{ me.me_event_count ?? '--' }}</td>
                  <td>{{ me.so_event_count ?? '--' }}</td>
                  <td>{{ me.med_admin_execution_event_count ?? '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <div v-else class="overview-row-empty">No medication execution records.</div>
      </n-drawer-content>
    </n-drawer>
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
  top: 3%;
  width: 4px;
  bottom: calc(46% + 3px);
}
.connector-branch {
  left: calc(53% + 3px);
  width: 4px;
  height: 4px;
}
.connector-branch-top {
  top: 3%;
}
.connector-branch-bottom {
  top: 53%;
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
  color: #053251;
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
.patient-meta {
  font-size: 14px;
  line-height: 30px;
  font-weight: 700;
}
.patient-nav-spacer {
  flex: 1 1 auto;
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
  flex-wrap: wrap;
  column-gap: 6px;
  line-height: 22px;
  white-space: normal;
  width: 100%;
}
.detail-line .label {
  font-weight: 700;
  flex: 0 0 auto;
}
.detail-line .value {
  min-width: 0;
  overflow-wrap: anywhere;
}
.demographic {
  margin: 0;
}
.patient-details {
  flex: 0 0 auto;
  align-items: stretch;
  min-height: 0;
  .box {
    overflow: visible;
  }
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
  align-items: flex-start;
}
.patient-plan-box .detail-line {
  flex: 0 0 auto;
  align-items: flex-start;
}
.patient-action-bar {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  column-gap: 10px;
  row-gap: 6px;
  align-items: center;
  margin-top: 6px;
}
.patient-action-cell {
  flex: 0 0 auto;
}
.panel-drawer-trigger {
  margin-top: 3px;
  align-self: flex-start;
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 3px;
  padding: 6px 12px;
  text-align: center;
  cursor: pointer;
  line-height: 1.2;
}
.panel-drawer-trigger:hover {
  border-color: #bfbfbf;
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
  flex-direction: column;
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
  background-color: #f3f3f3;
  background-clip: content-box;
}
.ai-summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
  color: #053251;
}
.ai-summary-title-icon {
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  padding-left: 4px;
}
.ai-summary-body {
  height: 42px;
  font-size: 14px;
  color: #333;
  line-height: 1.5;
  overflow: hidden;
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
.day-overview-table .symptom.dot-armed :deep(.dot) {
  box-shadow: 0 0 0 2px #808080;
  border-radius: 50%;
  transform: scale(1.2);
  transform-origin: center;
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
  outline: 2px solid #808080;
  outline-offset: -2px;
}
.day-overview-row .date.date-unread {
  font-weight: 700;
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
  padding: 4px 10px 4px 12px;
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
  padding: 4px 12px 4px 12px;
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
.admission-row {
  display: flex;
  align-items: baseline;
  column-gap: 12px;
  font-size: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #e8e8e8;
}
.admission-row:last-child {
  border-bottom: none;
}
.admission-dates {
  flex: 0 0 auto;
  color: #888;
  white-space: nowrap;
}
.admission-diagnosis {
  flex: 1 1 0;
  color: #333;
  font-weight: 500;
}
.medication-row {
  display: flex;
  align-items: baseline;
  column-gap: 12px;
  font-size: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #e8e8e8;
}
.medication-row:last-child {
  border-bottom: none;
}
.medication-name {
  flex: 1 1 0;
  font-weight: 600;
  color: #333;
}
.medication-dosage {
  font-weight: 400;
  color: #666;
}
.note-row {
  display: flex;
  align-items: flex-start;
  column-gap: 12px;
  font-size: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #e8e8e8;
}
.note-row:last-child {
  border-bottom: none;
}
.note-content {
  flex: 1 1 0;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
}
.drawer-table {
  width: 100%;
  overflow: auto;
}
.drawer-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  white-space: nowrap;
}
.drawer-table th,
.drawer-table td {
  border: 1px solid #e8e8e8;
  padding: 6px 10px;
  text-align: left;
}
.drawer-table th {
  background: #f5f5f5;
  font-weight: 700;
  color: #333;
  position: sticky;
  top: 0;
  z-index: 1;
}
.drawer-table tr:nth-child(even) {
  background: #fafafa;
}
.drawer-table tr:hover {
  background: #e9edf5;
}
.drawer-table .td-nowrap {
  white-space: nowrap;
}
.drawer-table .td-wrap {
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 200px;
  max-width: 500px;
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
  gap: 8px;
}
.day-symptoms-info {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1px solid #ffffff;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}
.day-symptoms-info-glyph {
  position: relative;
  width: 8px;
  height: 10px;
  display: inline-block;
}
.day-symptoms-info-glyph::before {
  content: "";
  position: absolute;
  left: 50%;
  top: 0;
  width: 2px;
  height: 2px;
  margin-left: -1px;
  border-radius: 50%;
  background: #ffffff;
}
.day-symptoms-info-glyph::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 4px;
  width: 2px;
  height: 6px;
  margin-left: -1px;
  border-radius: 1px;
  background: #ffffff;
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
