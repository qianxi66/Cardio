<script setup lang="tsx">
import { useRouteParams } from "@vueuse/router";
import { useRouteQuery } from "@vueuse/router";
import { useRouter } from "vue-router";
import type { DrawerPlacement } from "naive-ui";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import CircleProgress from "@/components/CircleProgress.vue";
import { markSymptomRead, updateSummarySymptomState, updateNote, createNote, deleteNote } from "@/api/patient";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import ReportDetailView from "@/views/ReportDetailView.vue";
import { computed, watch, ref, inject, nextTick, onMounted, onBeforeUnmount, type Component } from "vue";
import type { Patient, Summary, ReportNote } from "@/api/types";
import { getPatient, getSummaries, getWearableCoverage, getNotes, type WearableCoverage } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format } from "date-fns";
import type { CancelTokenSource } from "axios";
import axios from "axios";
import { stateColors } from "@/symptoms";

const refreshPatients = inject<(() => void | Promise<void>) | undefined>("refreshPatients");
const patient_id = useRouteParams("patient_id");
const query_date_ = useRouteQuery<string | undefined>("date");
const query_dot_state_ = useRouteQuery<string | undefined>("dot_state");

const patient = ref<Patient | null>(null);
const summaries = ref<Summary[]>([]);
const reportNotes = ref<ReportNote[]>([]);
const wearableCoverage = ref<WearableCoverage>({});
const loading = ref(true);
const wearableLoading = ref(false);
const cancelToken = ref<CancelTokenSource | null>(null);
const dailySummaryDate = ref<string | null>(null);
const DEFAULT_TIMEZONE = "America/New_York";

const toDateKey = (value: Date, timeZone = DEFAULT_TIMEZONE): string => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value || "";
  return `${pick("year")}-${pick("month")}-${pick("day")}`;
};

const toDateTimeLabel = (value: Date, timeZone = DEFAULT_TIMEZONE): string => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(value);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value || "";
  return `${pick("year")}-${pick("month")}-${pick("day")} ${pick("hour")}:${pick("minute")}`;
};

const getEtDateTimeParts = (value: Date, timeZone = DEFAULT_TIMEZONE) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(value);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value || "";
  return {
    year: pick("year"),
    month: pick("month"),
    day: pick("day"),
    hour: pick("hour"),
    minute: pick("minute"),
    second: pick("second"),
  };
};

const parseEtLikeDateTimeKey = (raw?: string | Date): string | null => {
  if (!raw) return null;
  if (typeof raw === "string") {
    const dateOnly = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateOnly) return `${dateOnly[1]}-${dateOnly[2]}-${dateOnly[3]} 00:00:00`;

    // If backend sends a naive datetime string without timezone marker,
    // treat it as an ET-like literal to avoid accidental local timezone conversion.
    const hasTime = /\d{2}:\d{2}/.test(raw);
    const hasZoneMarker = /(Z|[+-]\d{2}:?\d{2}|GMT|UTC)/i.test(raw);
    if (hasTime && !hasZoneMarker) {
      const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/);
      if (m) {
        const sec = m[6] || "00";
        return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${sec}`;
      }
    }
  }
  const parsed = parseDateValue(raw);
  if (!parsed) return null;
  const p = getEtDateTimeParts(parsed);
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`;
};

const toEtDateTimeLabel = (raw?: string | Date): string => {
  const key = parseEtLikeDateTimeKey(raw);
  if (!key) return "--";
  return key.slice(0, 16);
};

const toEtNowDateTimeString = () => {
  const p = getEtDateTimeParts(new Date());
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`;
};

const wearableDate = computed(() => {
  return dailySummaryDate.value || toDateKey(new Date());
});

if (!dailySummaryDate.value) {
  dailySummaryDate.value = toDateKey(new Date());
}
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
  return format(parsed, "yyyy-MM-dd");
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

const truncateToTwoLineApprox = (text: string, charsPerLine = 70) => {
  const normalized = (text || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  const maxChars = charsPerLine * 2;
  if (normalized.length <= maxChars) return normalized;
  const sliced = normalized.slice(0, maxChars);
  return `${sliced.replace(/[\s,.;:]+$/u, "")}...`;
};

const aiSummaryBody = computed(() => {
  const notes = patient.value?.notes ?? [];
  const selectedKey = dailySummaryDate.value;
  if (!selectedKey) {
    return { body: "no data for this date", time: "", createdBy: "" };
  }

  const match = notes
    .filter((note: any) => {
      return noteDateKeyET(note.created_at) === selectedKey;
    })
    .sort((a: any, b: any) => {
      const at = parseEtLikeDateTimeKey(a.created_at) || "";
      const bt = parseEtLikeDateTimeKey(b.created_at) || "";
      return bt.localeCompare(at);
    })[0];

  if (!match?.content?.trim()) {
    return { body: "no data for this date", time: "", createdBy: "" };
  }
  const isAi = String(match.creator_type || "").toLowerCase() === "ai";
  const rawBody = match.content.trim();
  const bodyFull = isAi ? stripAiSummaryPrefix(rawBody) : rawBody;
  const body = truncateToTwoLineApprox(bodyFull);
  const time = toEtDateTimeLabel(match.created_at);
  const createdBy = isAi
    ? "AI"
    : (match.created_by as string | undefined) ||
      (match.user?.username as string | undefined) ||
      "User";
  return { body, time, createdBy };
});

type DailySummaryEditableRow = {
  noteId: number;
  dateLabel: string;
  content: string;
  creatorLabel: string;
  createdAtKey: string;
};

type StagedNewNote = {
  tempId: number;
  content: string;
  created_at: string;
  created_by?: string;
  creator_type: "user";
};

const stripAiSummaryPrefix = (content?: string) => {
  return (content || "").trim().replace(/^ai\s*summary\s*:?\s*/i, "");
};

const dailySummaryRows = computed<DailySummaryEditableRow[]>(() => {
  const notes = patient.value?.notes ?? [];
  const persistedRows: DailySummaryEditableRow[] = notes
    .map((note: any) => {
      const createdAtKey = parseEtLikeDateTimeKey(note.created_at) || "";
      const isAi = String(note.creator_type || "").toLowerCase() === "ai";
      const dateLabel = toEtDateTimeLabel(note.created_at);
      const creatorLabel =
        (isAi && "AI") ||
        (note.created_by as string | undefined) ||
        (note.user?.username as string | undefined) ||
        (note.creator_type as string | undefined) ||
        "User";
      const baseContent = isAi ? stripAiSummaryPrefix(note.content) : (note.content || "");
      return {
        noteId: note.id as number,
        dateLabel,
        content: baseContent,
        creatorLabel,
        createdAtKey,
      };
    })
    .filter((row) => typeof row.noteId === "number");

  const stagedRows: DailySummaryEditableRow[] = stagedNewNotes.value.map((note) => {
    const createdAtKey = parseEtLikeDateTimeKey(note.created_at) || "";
    return {
      noteId: note.tempId,
      dateLabel: toEtDateTimeLabel(note.created_at),
      content: note.content,
      creatorLabel: note.created_by || "User",
      createdAtKey,
    };
  });

  return [...stagedRows, ...persistedRows].sort((a, b) =>
    b.createdAtKey.localeCompare(a.createdAtKey),
  );
});

const dailySummaryEditorVisible = ref(false);
const dailySummaryDrafts = ref<Record<number, string>>({});
const dailySummarySaving = ref(false);
const newNoteInput = ref("");
const newNoteSaving = ref(false);
const dailySummaryListEl = ref<HTMLElement | null>(null);
const stagedNewNotes = ref<StagedNewNote[]>([]);
const stagedNoteIdSeed = ref(-1);

const scrollDailySummaryListToTop = async () => {
  await nextTick();
  if (dailySummaryListEl.value) {
    dailySummaryListEl.value.scrollTop = 0;
  }
};

const reloadPatientNotes = async (patientId: number) => {
  const notes = (await getNotes(patientId)) ?? [];
  if (patient.value) {
    patient.value.notes = notes as any;
  }
};

const openDailySummaryEditor = () => {
  const nextDrafts: Record<number, string> = {};
  stagedNewNotes.value = [];
  stagedNoteIdSeed.value = -1;
  dailySummaryRows.value.forEach((row) => {
    nextDrafts[row.noteId] = row.content;
  });
  dailySummaryDrafts.value = nextDrafts;
  newNoteInput.value = "";
  dailySummaryEditorVisible.value = true;
  void scrollDailySummaryListToTop();
};

const saveAllDailySummaries = async () => {
  const patientId = patientIdParam.value;
  if (!patientId) return;
  sendNewNote();
  dailySummarySaving.value = true;
  let hasError = false;
  try {
    for (const row of dailySummaryRows.value) {
      if (row.noteId <= 0) continue;
      const nextContent = (dailySummaryDrafts.value[row.noteId] ?? "").trim();
      if (!nextContent || nextContent === row.content) continue;
      await updateNote(patientId, row.noteId, nextContent);
    }
    const stagedContents = stagedNewNotes.value
      .map((n) => (dailySummaryDrafts.value[n.tempId] ?? n.content).trim())
      .filter((v) => !!v);
    if (stagedContents.length) {
      await Promise.all(stagedContents.map((content) => createNote(patientId, content)));
    }
    await reloadPatientNotes(patientId);
    stagedNewNotes.value = [];
    stagedNoteIdSeed.value = -1;
    const nextDrafts: Record<number, string> = {};
    dailySummaryRows.value.forEach((row) => {
      nextDrafts[row.noteId] = row.content;
    });
    dailySummaryDrafts.value = nextDrafts;
  } catch (error) {
    hasError = true;
    console.error("Failed to save daily summaries", error);
  } finally {
    dailySummarySaving.value = false;
  }
  if (!hasError) {
    dailySummaryEditorVisible.value = false;
  }
};

const sendNewNote = () => {
  const content = newNoteInput.value?.trim();
  if (!content) return;
  const tempId = stagedNoteIdSeed.value;
  stagedNoteIdSeed.value -= 1;
  stagedNewNotes.value.unshift({
    tempId,
    content,
    created_at: toEtNowDateTimeString(),
    created_by: "User",
    creator_type: "user",
  });
  dailySummaryDrafts.value[tempId] = content;
  newNoteInput.value = "";
  void scrollDailySummaryListToTop();
};

const deleteDailySummary = async (noteId: number) => {
  if (noteId <= 0) {
    stagedNewNotes.value = stagedNewNotes.value.filter((n) => n.tempId !== noteId);
    const nextDrafts = { ...dailySummaryDrafts.value };
    delete nextDrafts[noteId];
    dailySummaryDrafts.value = nextDrafts;
    return;
  }
  const patientId = patientIdParam.value;
  if (!patientId) return;
  try {
    await deleteNote(patientId, noteId);
    await reloadPatientNotes(patientId);
    const nextDrafts = { ...dailySummaryDrafts.value };
    delete nextDrafts[noteId];
    dailySummaryDrafts.value = nextDrafts;
  } catch (error) {
    console.error("Failed to delete daily summary note", error);
  }
};

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
const isCompactLayout = ref(false);

const updateCompactLayout = () => {
  if (typeof window === "undefined") return;
  const shortEdge = Math.min(window.innerWidth, window.innerHeight);
  const ratio = window.innerHeight > 0 ? window.innerHeight / window.innerWidth : 1;
  const touchDevice = window.matchMedia("(pointer: coarse)").matches;
  isCompactLayout.value =
    window.innerWidth <= 1100 || (touchDevice && (shortEdge <= 1024 || ratio <= 1.45));
};

const dailySymptomsCardTitle = computed(() =>
  isCompactLayout.value ? "Symptoms" : "Patient's Daily Symptoms",
);

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
      .map((s) => summaryDateKey(s.date))
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
    if (!dateStr) return;
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      if (dailySummaryDate.value !== dateStr) {
        dailySummaryDate.value = dateStr;
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
  if (query_date_.value !== value) {
    query_date_.value = value;
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

const summaryDateKey = (value?: string | Date): string | null => {
  if (!value) return null;
  if (typeof value === "string") {
    const dateOnly = value.match(/^(\d{4}-\d{2}-\d{2})$/);
    if (dateOnly) return dateOnly[1];
    const datePrefix = value.match(/^(\d{4}-\d{2}-\d{2})/);
    if (datePrefix) return datePrefix[1];
    const rfcLike = value.match(/^[A-Za-z]{3},\s+(\d{2})\s+([A-Za-z]{3})\s+(\d{4})/);
    if (rfcLike) {
      const monthMap: Record<string, string> = {
        Jan: "01",
        Feb: "02",
        Mar: "03",
        Apr: "04",
        May: "05",
        Jun: "06",
        Jul: "07",
        Aug: "08",
        Sep: "09",
        Oct: "10",
        Nov: "11",
        Dec: "12",
      };
      const month = monthMap[rfcLike[2]];
      if (month) return `${rfcLike[3]}-${month}-${rfcLike[1]}`;
    }
  }
  const parsed = parseDateValue(value);
  if (!parsed) return null;
  return `${parsed.getUTCFullYear()}-${String(parsed.getUTCMonth() + 1).padStart(2, "0")}-${String(parsed.getUTCDate()).padStart(2, "0")}`;
};

const noteDateKeyET = (value?: string | Date): string | null => {
  if (typeof value === "string") {
    const dateOnly = value.match(/^(\d{4}-\d{2}-\d{2})$/);
    if (dateOnly) return dateOnly[1];
    const datePrefix = value.match(/^(\d{4}-\d{2}-\d{2})/);
    const hasTime = /\d{2}:\d{2}/.test(value);
    const hasZoneMarker = /(Z|[+-]\d{2}:?\d{2}|GMT|UTC)/i.test(value);
    if (datePrefix && (!hasTime || !hasZoneMarker)) {
      return datePrefix[1];
    }
  }
  const parsed = parseDateValue(value);
  return parsed ? toDateKey(parsed) : null;
};

const summaryForDate = computed(() => {
  if (!summaries.value.length) {
    return null;
  }
  const targetKey = dailySummaryDate.value;
  if (targetKey) {
    const match = summaries.value.find((summary) => {
      const key = summaryDateKey(summary.date);
      return key ? key === targetKey : false;
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

// For wearable symptoms, state comes from MongoDB sensor coverage:
// state 0 = grey (no data), state 1 = green (has data, normal), state 3 = red (has out-of-range values).
const symptomKeyToSensorField: Record<string, "heart_rate" | "respiration" | "spo2" | "hrv"> = {
  heart_rate: "heart_rate",
  respiration: "respiration",
  spo2: "spo2",
  hrv: "hrv",
};

const dotStateForSymptom = (
  summary: Summary | null,
  symptomKey: string,
  wearable: boolean,
): number => {
  if (!wearable) return symptomState(summary, symptomKey);
  if (!summary) return 0;
  const key = summaryDateKey(summary.date);
  if (!key) return 0;
  const cov = wearableCoverage.value[key];
  if (!cov) return 0;
  if (typeof cov === "boolean") {
    return 0;
  }
  const sensorField = symptomKeyToSensorField[symptomKey];
  if (!sensorField) return 0;
  if (!cov[sensorField]) return 0;
  const alertField = `${sensorField}_alert` as keyof typeof cov;
  return cov[alertField] ? 3 : 1;
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
  { key: "syncope",         display_name: "Syncope",     description: "Fainting or Syncope",            wearable: false, likert: false, color: "#eb4c44" },
  { key: "palpitation",     display_name: "Palps",       description: "Heart Palpitations",             wearable: false, likert: false, color: "#f9d965" },
  { key: "short_of_breath", display_name: "Breath",      description: "Shortness of Breath (Dyspnea)",  wearable: false, likert: true,  color: "#eb4c44" },
  { key: "chest_discomfort",display_name: "Chest",       description: "Chest Discomfort or Pain",       wearable: false, likert: true,  color: "#eb4c44" },
  { key: "fatigue",         display_name: "Fatigue",     description: "Fatigue or Tiredness",           wearable: false, likert: false, color: "#f9d965" },
  { key: "swelling",        display_name: "Swelling",    description: "Swelling (Edema)",               wearable: false, likert: false, color: "#f9d965" },
  { key: "heart_rate",      display_name: "HR",  description: "Heart Rate",                     wearable: true,  likert: false, color: "#4bbfd1" },
  { key: "respiration",     display_name: "Resp",        description: "Respiration Rate",               wearable: true,  likert: false, color: "#ffb700" },
  { key: "spo2",            display_name: "SpO2",        description: "Blood Oxygen Saturation",        wearable: true,  likert: false, color: "#63c0ff" },
  { key: "hrv",             display_name: "HRV",         description: "Heart Rate Variability",         wearable: true,  likert: false, color: "#41acc4" },
];

const dayOverviewRows = computed(() => {
  const selectedKey = dailySummaryDate.value;
  return summaries.value
    .map((summary) => {
      const summaryKey = summaryDateKey(summary.date);
      return {
        id: summary.id,
        summary,
        dateKey: summaryKey,
        dateLabel: summaryKey || "--",
        isSelected: !!selectedKey && !!summaryKey && selectedKey === summaryKey,
      };
    })
    .sort((a, b) => {
      if (!a.dateKey && !b.dateKey) return 0;
      if (!a.dateKey) return 1;
      if (!b.dateKey) return -1;
      return b.dateKey.localeCompare(a.dateKey);
    });
});

const armedDayOverviewDotKey = ref<string | null>(null);

const getDayOverviewDotKey = (rowId: number, symptomKey: string) => `${rowId}-${symptomKey}`;

const isDayOverviewDotArmed = (rowId: number, symptomKey: string) =>
  armedDayOverviewDotKey.value === getDayOverviewDotKey(rowId, symptomKey);

const dayOverviewRowHasData = (summary: Summary | null): boolean => {
  return dayOverviewSymptoms.some((symptom) => dotStateForSymptom(summary, symptom.key, symptom.wearable) !== 0);
};

const dayOverviewHasDataSignature = computed(() =>
  dayOverviewRows.value
    .map((row) => (dayOverviewRowHasData(row.summary) ? "1" : "0"))
    .join(""),
);

const getSymptomScale = (summary: Summary | null, symptomKey: string): number => {
  if (!summary) return 0;
  const value = (summary as Record<string, unknown>)[`${symptomKey}_scale`];
  const parsed = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(parsed) || parsed <= 0) return 0;
  return Math.min(10, Math.max(1, parsed));
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
  [dayOverviewRows, dayOverviewHasDataSignature, loading, wearableLoading],
  async ([rows, _signature, isLoading, isWearableLoading]) => {
    if (isLoading || isWearableLoading || didAutoScrollDayOverview.value || rows.length === 0) return;
    const targetRow = rows.find((row) => dayOverviewRowHasData(row.summary));
    if (!targetRow) {
      didAutoScrollDayOverview.value = true;
      return;
    }
    if (targetRow.dateKey) {
      dailySummaryDate.value = targetRow.dateKey;
    }
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

const selectDayOverview = (dateKey: string | null) => {
  if (!dateKey) {
    return;
  }
  dailySummaryDate.value = dateKey;
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

const handleDayOverviewRowClick = (row: { summary: Summary | null; dateKey: string | null }) => {
  selectDayOverview(row.dateKey);
  markDayOverviewRowRead(row.summary);
};

const jumpToDayOverviewSummary = (
  summary: Summary | null,
  dateKey: string | null,
  symptom: string,
  wearable: boolean,
) => {
  if (!summary) return;
  const state = dotStateForSymptom(summary, symptom, wearable);
  if (state === 0) return;
  // Mark as read (fire-and-forget)
  const readVal = (summary as Record<string, unknown>)["read"];
  const isAlreadyRead = readVal === 1 || readVal === true;
  if (!isAlreadyRead && patient_id.value) {
    markSymptomRead(Number(patient_id.value), summary.id).then(() => {
      (summary as Record<string, unknown>)["read"] = 1;
    }).catch(() => {});
  }
  jumpToSummary(summary, symptom, state, dateKey);
};

const handleDayOverviewDotClick = (
  row: { id: number; summary: Summary | null; dateKey: string | null },
  symptom: { key: string; wearable: boolean },
) => {
  const dotKey = getDayOverviewDotKey(row.id, symptom.key);
  if (armedDayOverviewDotKey.value !== dotKey) {
    armedDayOverviewDotKey.value = dotKey;
  }
  jumpToDayOverviewSummary(row.summary, row.dateKey, symptom.key, symptom.wearable);
};

const parseSummaryLogIds = (raw: unknown): number[] => {
  const parseTokenList = (tokens: string[]) =>
    tokens
      .map((token) => Number.parseInt(token, 10))
      .filter((id) => Number.isFinite(id));

  if (Array.isArray(raw)) {
    return raw
      .map((item) => Number.parseInt(String(item), 10))
      .filter((id) => Number.isFinite(id));
  }

  if (typeof raw !== "string") {
    return [];
  }

  const text = raw.trim();
  if (!text) return [];

  if (text.startsWith("[") && text.endsWith("]")) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        return parsed
          .map((item) => Number.parseInt(String(item), 10))
          .filter((id) => Number.isFinite(id));
      }
    } catch {
      // Fall back to comma-separated parsing.
    }
  }

  if (text.includes(",")) {
    return parseTokenList(text.split(",").map((part) => part.trim()).filter(Boolean));
  }

  const singleton = Number.parseInt(text, 10);
  return Number.isFinite(singleton) ? [singleton] : [];
};

const jumpToSummary = (
  summary: Summary,
  symptom: string,
  dotStateOverride?: number,
  dateKeyOverride?: string | null,
) => {
  const logsRaw = (summary as Record<string, unknown>)[`${symptom}_logs`];
  const logsArr = parseSummaryLogIds(logsRaw);
  const dateKey = dateKeyOverride || summaryDateKey(summary.date);
  const symptomStateValue = (summary as Record<string, unknown>)[`${symptom}_state`];
  const inferredDotState =
    typeof symptomStateValue === "number"
      ? symptomStateValue
      : typeof symptomStateValue === "string"
        ? Number.parseInt(symptomStateValue, 10)
        : 0;
  const dotState = typeof dotStateOverride === "number" ? dotStateOverride : inferredDotState;
  const queryLogs = logsArr
    .map((id) => Number.parseInt(String(id), 10))
    .filter((id) => Number.isFinite(id))
    .map((id) => String(id));
  router.push({
    name: "patient.detail",
    params: { patient_id: patient_id.value },
    query: {
      symptom,
      logs: queryLogs,
      dot_state: String(Number.isNaN(dotState) ? 0 : dotState),
      jump: String(Date.now()),
      ...(dateKey ? { date: dateKey } : {}),
    },
  });
};

const conversationHighlightColor = computed(() => {
  const raw = query_dot_state_.value;
  const parsed = raw !== undefined ? Number.parseInt(raw, 10) : Number.NaN;
  const idx = Number.isFinite(parsed) ? parsed : 0;
  return stateColors[idx] || "#053251";
});

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
  updateCompactLayout();
  nextTick(() => updateConnectors());
  _connectorRO = new ResizeObserver(() => updateConnectors());
  if (connectorRowEl.value) _connectorRO.observe(connectorRowEl.value);
  window.addEventListener('resize', updateConnectors);
  window.addEventListener("resize", updateCompactLayout);
});
onBeforeUnmount(() => {
  _connectorRO?.disconnect();
  window.removeEventListener('resize', updateConnectors);
  window.removeEventListener("resize", updateCompactLayout);
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
              <button
                type="button"
                class="patient-name patient-name-trigger"
                @click="$router.push(`/patient/${patient_id}/update`)"
              >
                {{ patientName }}
              </button>
              <div class="patient-meta">
                {{ patient!.age ? patient!.age + " y.o." : "" }}
                {{ patient!.gender }}
              </div>
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
                  <button
                    type="button"
                    class="panel-title panel-drawer-trigger"
                    @click="openAdmissionDrawer"
                  >
                    Admission History
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button
                    type="button"
                    class="panel-title panel-drawer-trigger"
                    @click="openIOMetricDrawer"
                  >
                    I/O Metrics
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button
                    type="button"
                    class="panel-title panel-drawer-trigger"
                    @click="openMedicationDrawer"
                  >
                    Medications
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button
                    type="button"
                    class="panel-title panel-drawer-trigger"
                    @click="openPreadmissionMedDrawer"
                  >
                    Pre-Adm Meds
                  </button>
                </div>
                <div class="patient-action-cell">
                  <button
                    type="button"
                    class="panel-title panel-drawer-trigger"
                    @click="openMedExecDrawer"
                  >
                    Med Execution
                  </button>
                </div>
              </div>
          </div>
        </div>
      </ColoredCard>
      <ColoredCard
        class="day-navigator indigo-title full-title-bar"
        :title="dailySymptomsCardTitle"
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
            v-model:formatted-value="dailySummaryDate"
            type="date"
            value-format="yyyy-MM-dd"
            size="small"
            clearable
          />
        </template>
        <div class="day-navigator-content">
          <div class="ai-summary-section">
            <div class="ai-summary-title">
              <span>Daily Summary</span>
              <button
                type="button"
                class="ai-summary-more-btn"
                @click="openDailySummaryEditor"
              >
                More
              </button>
            </div>
            <div class="ai-summary-body">
              <span class="ai-summary-body-text">{{ aiSummaryBody.body }}</span>
              <span class="ai-summary-body-meta">
                <span class="ai-summary-body-time">{{ aiSummaryBody.time }}</span>
                <span class="ai-summary-body-created-by" v-if="aiSummaryBody.createdBy">
                  Created by {{ aiSummaryBody.createdBy }}
                </span>
              </span>
            </div>
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
                  :class="{ 'dot-armed': isDayOverviewDotArmed(row.id, symptom.key) }"
                >
                  <n-tooltip
                    v-if="symptom.likert"
                    trigger="hover"
                    placement="top"
                  >
                    <template #trigger>
                      <CircleProgress
                        class="day-overview-dot-gauge"
                        :percent="getSymptomScale(row.summary, symptom.key) * 10"
                        :color="symptom.color"
                        :id="`${row.id}-${symptom.key}`"
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
                      </CircleProgress>
                    </template>
                    {{ symptom.display_name }}: {{ getSymptomScale(row.summary, symptom.key) }}
                  </n-tooltip>
                  <Dot
                    v-else
                    :state="dotStateForSymptom(row.summary, symptom.key, symptom.wearable)"
                    :isRead="(row.summary as any)?.read ?? 0"
                    :variant="'circle'"
                    :editable="isDayOverviewDotArmed(row.id, symptom.key)"
                    @update:state="handleDayOverviewDotStateChange(row.summary, symptom.key, $event)"
                    :loading="symptom.wearable && wearableLoading"
                    @click.stop="handleDayOverviewDotClick(row, symptom)"
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
            <component
              :is="Component || ReportDetailView"
              ref="right"
              :highlight-color="conversationHighlightColor"
            >
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

    <n-modal
      v-model:show="dailySummaryEditorVisible"
      preset="card"
      title="Edit Daily Summaries"
      style="width: min(920px, 92vw)"
    >
      <div class="summary-editor-panel">
        <div ref="dailySummaryListEl" class="summary-editor-list" v-if="dailySummaryRows.length">
          <div
            v-for="row in dailySummaryRows"
            :key="row.noteId"
            class="summary-editor-row"
          >
            <div class="summary-editor-input">
              <n-input
                v-model:value="dailySummaryDrafts[row.noteId]"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 5 }"
              />
            </div>
            <div class="summary-editor-meta">
              <div class="summary-editor-meta-main">
                <div class="summary-editor-time">{{ row.dateLabel }}</div>
                <div class="summary-editor-creator">
                  Created by
                  <span class="summary-editor-creator-name">{{ row.creatorLabel }}</span>
                </div>
              </div>
              <button
                type="button"
                class="summary-editor-delete-btn"
                aria-label="Delete note"
                @click="deleteDailySummary(row.noteId)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" />
                  <path d="M9 9L15 15M15 9L9 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                </svg>
              </button>
            </div>
          </div>
        </div>
        <div v-else class="summary-editor-empty">No daily summaries</div>
        <div class="summary-editor-footer">
          <div class="summary-editor-new-note">
            <n-input
              v-model:value="newNoteInput"
              placeholder="type your notes here (Press Enter to send)"
              size="small"
              clearable
              :disabled="newNoteSaving"
              @keydown.enter.prevent="sendNewNote"
            />
          </div>
          <n-button
            type="primary"
            size="small"
            :loading="dailySummarySaving"
            @click="saveAllDailySummaries"
          >
            Save & Close
          </n-button>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<style scoped lang="scss">
.row {
  position: relative;
  flex-grow: 1;
  min-width: 0;
  display: flex;
  gap: 16px;
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
  top: 260px;
  width: 10px;
  height: 4px;
}
.connector-vertical {
  left: calc((100% - 16px) * 0.53 + 6px);
  top: 19px;
  width: 4px;
  bottom: calc((100% - 32px) * 0.5 + 16px - 19px);
}
.connector-branch {
  left: calc((100% - 16px) * 0.53 + 6px);
  top: 19px;
  width: 12px;
  height: 4px;
}
.connector-branch-top {
  top: 19px;
}
.connector-branch-bottom {
  top: calc((100% - 32px) * 0.5 + 16px + 19px);
}
.main-col,
.side-col {
  min-width: 0;
  padding-bottom: 16px;
  box-sizing: border-box;
}

.row > .main-col {
  flex: 53 1 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
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
  flex: 0 0 var(--patient-info-card-height, 225px);
  height: var(--patient-info-card-height, 225px);
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
.patient-name-trigger {
  border: none;
  background: transparent;
  color: inherit;
  padding: 0;
  cursor: pointer;
  text-align: left;
}
.patient-name-trigger:hover {
  text-decoration: underline;
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
  padding-top: 26px;
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
  row-gap: 8px;
}
.patient-plan-box {
  background-color: #fff;
  padding: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  row-gap: 8px;
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
  margin-top: 12px;
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
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.panel-drawer-trigger:hover {
  border-color: #bfbfbf;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}
.basic-information-content {
  display: flex;
  flex-direction: column;
  row-gap: 0px;
}
.basic-top-section {
  flex: 0 0 auto;
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
  flex: 1 1 auto;
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
  padding-left: 8px;
}
.ai-summary-more-btn {
  margin-left: auto;
  margin-right: 6px;
  flex-shrink: 0;
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 3px;
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  cursor: pointer;
  line-height: 1.2;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.ai-summary-more-btn:hover {
  border-color: #bfbfbf;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}
.summary-editor-panel {
  display: flex;
  flex-direction: column;
  max-height: 70vh;
}
.summary-editor-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding-right: 4px;
}
.summary-editor-row {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(150px, 0.4fr);
  gap: 10px;
  align-items: start;
}
.summary-editor-input {
  min-width: 0;
}
.summary-editor-meta {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: #444;
  padding-top: 4px;
}
.summary-editor-meta-main {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.summary-editor-time {
  font-weight: 700;
  color: #053251;
}
.summary-editor-creator {
  color: #666;
}
.summary-editor-creator-name {
  font-weight: 600;
  margin-left: 4px;
}
.summary-editor-delete-btn {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  color: #999;
  cursor: pointer;
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.summary-editor-delete-btn:hover {
  background: #f0f0f0;
  color: #cc0000;
}
.summary-editor-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid #e5e5e5;
  margin-top: 12px;
  padding-top: 12px;
  background: #fff;
}
.summary-editor-new-note {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
  min-width: 0;
}
.summary-editor-new-note .n-input {
  flex: 1 1 auto;
  min-width: 0;
}
.summary-editor-new-note .n-input :deep(input::placeholder) {
  color: #999;
}
.summary-editor-empty {
  color: #999999;
  text-align: center;
  padding: 20px 0;
}
.ai-summary-body {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 42px;
  font-size: 14px;
  color: #333;
  line-height: 1.5;
  overflow: hidden;
}
.ai-summary-body-text {
  flex: 1 1 74%;
  min-width: 0;
  padding-left: 6px;
  padding-bottom: 0;
  line-height: 1.35;
  white-space: normal;
  overflow-wrap: break-word;
  word-break: break-word;
}
.ai-summary-body-time {
  white-space: nowrap;
  color: #666;
}
.ai-summary-body-meta {
  flex: 0 0 auto;
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  padding-right:6px;
}
.ai-summary-body-created-by {
  color: #666;
  white-space: nowrap;
  font-size: 12px;
}
.day-overview-table {
  --day-overview-date-width: 98px;
  --day-overview-symptom-width: 73px;
  --day-overview-col-count: 10;
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  font-size: 14px;
  overflow-x: auto;
  overflow-y: hidden;
}
.day-overview-table .table-row {
  width: max-content;
  min-width: max(
    100%,
    calc(
      var(--day-overview-date-width) +
      var(--day-overview-col-count) * var(--day-overview-symptom-width)
    )
  );
  display: flex;
  align-items: center;
}
.day-overview-table .date {
  flex: 0 0 var(--day-overview-date-width);
  padding-left: 8px;
  box-sizing: border-box;
  white-space: nowrap;
}
.day-overview-table .symptom {
  flex: 0 0 var(--day-overview-symptom-width);
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
  width: max-content;
  min-width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}
.day-overview-row {
  height: 45px;
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
.day-overview-dot-gauge {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: -2px;
}
.day-overview-dot-gauge :deep(.content) {
  transform: translateX(-50%) translateY(60%);
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
  flex: 0 0 var(--patient-info-card-height, 225px);
  height: var(--patient-info-card-height, 225px);
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

@media (max-width: 1100px) {
  .patient-layout > .row:first-of-type {
    margin-top: 2px;
  }
  .row {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
    overflow-y: auto;
    padding: 0 12px 12px;
    box-sizing: border-box;
  }
  .row .col {
    height: auto;
    min-height: 0;
  }
  .overview-connectors {
    display: none;
  }
  .row > .main-col,
  .row > .side-col {
    flex: 0 0 auto;
    width: 100%;
    padding-bottom: 0;
  }
  .information {
    flex: 0 0 auto;
    height: auto;
    min-height: 0;
  }
  .day-navigator {
    flex: 0 0 auto;
    min-height: 0;
  }
  .day-navigator :deep(.n-card__content),
  .day-navigator-content {
    height: auto;
    min-height: 0;
  }
  .day-navigator-content {
    display: block;
  }
  .day-overview-table {
    --day-overview-date-width: 138px;
    --day-overview-symptom-width: 74px;
    flex: 0 0 auto;
    display: block;
    min-height: 0;
    overflow: auto;
    max-height: 360px;
    padding-bottom: 4px;
  }
  .day-overview-table .table-row {
    width: max-content;
    min-width: max(
      100%,
      calc(
        var(--day-overview-date-width) +
        var(--day-overview-col-count) * var(--day-overview-symptom-width)
      )
    );
  }
  .day-overview-table .date {
    flex: 0 0 var(--day-overview-date-width);
    padding-left: 12px;
  }
  .day-overview-table .symptom {
    flex: 0 0 var(--day-overview-symptom-width);
    min-width: var(--day-overview-symptom-width);
  }
  .day-overview-scroll {
    min-height: 0;
    max-height: none;
    overflow: visible;
    flex: 0 0 auto;
  }
  .wearable-chart-wrapper {
    overflow: auto;
    min-height: 260px;
  }
  .wearable-chart-wrapper :deep(.chart-wrapper) {
    min-width: 460px;
  }
  .side-content {
    display: block;
  }
  .side-content :deep(.report-detail) {
    row-gap: 12px;
    padding-right: 0;
    height: auto;
    min-height: 0;
  }
  .side-content :deep(.report-detail .n-card) {
    flex: 0 0 auto;
    min-height: 320px;
  }
  .side-content :deep(.report-detail .conversation-card) {
    min-height: 360px;
  }
}
</style>
