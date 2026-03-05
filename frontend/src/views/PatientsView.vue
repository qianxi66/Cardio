<script setup lang="ts">
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import { getPatients, getSummaries, getWearableCoverage } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { ref, watch, computed, provide, onMounted } from "vue";
import { useRouteParams } from "@vueuse/router";
import { type Patient, type Summary } from "@/api/types";
import router from "@/router";
import { NCard, NInput } from "naive-ui";

const patients = ref<Patient[] | null>(null);
const loading = ref(true);
const searchTerm = ref("");
const patient_id = useRouteParams<number>("patient_id");
const DEFAULT_TIMEZONE = "America/New_York";

const dailySymptomKeys = [
  "syncope",
  "palpitation",
  "short_of_breath",
  "chest_discomfort",
  "swelling",
  "heart_rate",
  "respiration",
];

const toDateKey = (value: unknown, timeZone = DEFAULT_TIMEZONE): string | null => {
  if (!value) return null;
  if (typeof value === "string") {
    const dateOnly = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (dateOnly) return `${dateOnly[1]}-${dateOnly[2]}-${dateOnly[3]}`;
  }
  const date = value instanceof Date ? value : new Date(String(value));
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value;
  const y = pick("year");
  const m = pick("month");
  const d = pick("day");
  if (!y || !m || !d) return null;
  return `${y}-${m}-${d}`;
};

const getSummaryDateKey = (summary: Summary): string | null =>
  toDateKey(summary.date, DEFAULT_TIMEZONE);

const getLatestSummaryDateKey = (summaries: Summary[]): string | null => {
  const keys = summaries
    .map((summary) => getSummaryDateKey(summary))
    .filter((key): key is string => !!key)
    .sort();
  if (!keys.length) return null;
  return keys[keys.length - 1];
};

const getMaxNonWearableSeverityForDate = (
  summaries: Summary[],
  dateKey: string,
): number => {
  let maxSeverity = 0;
  summaries.forEach((summary) => {
    if (getSummaryDateKey(summary) !== dateKey) return;
    dailySymptomKeys.forEach((symptomKey) => {
      const raw = (summary as Record<string, unknown>)[`${symptomKey}_state`];
      const value = Number(raw);
      if (!Number.isNaN(value)) {
        maxSeverity = Math.max(maxSeverity, Math.min(3, Math.max(0, Math.round(value))));
      }
    });
  });
  return maxSeverity;
};

const getPatientSeverity = async (patient: Patient): Promise<number> => {
  const summaries = (patient.summaries ?? []) as Summary[];
  if (!summaries.length) return 0;

  const todayKey = toDateKey(new Date(), DEFAULT_TIMEZONE);
  const latestKey = getLatestSummaryDateKey(summaries);
  const targetDateKey = todayKey && summaries.some((s) => getSummaryDateKey(s) === todayKey)
    ? todayKey
    : latestKey;
  if (!targetDateKey) return 0;

  let maxSeverity = getMaxNonWearableSeverityForDate(summaries, targetDateKey);
  try {
    const wearableCoverage = await getWearableCoverage(patient.id, [targetDateKey]);
    if (wearableCoverage?.[targetDateKey]) {
      maxSeverity = Math.max(maxSeverity, 1);
    }
  } catch {
  }
  return maxSeverity;
};

const sortPatientsBySeverity = (items: Patient[]): Patient[] =>
  items.slice().sort((a, b) => {
    const severityDiff = (b.state ?? 0) - (a.state ?? 0);
    if (severityDiff !== 0) return severityDiff;
    const aParticipant = (a.participant_id ?? "").toLowerCase();
    const bParticipant = (b.participant_id ?? "").toLowerCase();
    if (aParticipant !== bParticipant) {
      return aParticipant.localeCompare(bParticipant);
    }
    return a.id - b.id;
  });

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

  return sortPatientsBySeverity(result);
});

const loadPatient = async () => {
  loading.value = true;
  try {
    const res = await getPatients();
    const mapped = await Promise.all(
      (res ?? []).map(async (item) => {
        const summaries = await getSummaries(item.id).catch(() => []);
        const patientWithSummaries: Patient = {
          ...item,
          summaries,
        };
        const severity = await getPatientSeverity(patientWithSummaries);
        return {
          ...item,
          summaries,
          read: !!item.last_read_at,
          state: severity,
          reviewed: false,
        };
      }),
    );
    patients.value = sortPatientsBySeverity(mapped);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadPatient();
});
provide("refreshPatients", loadPatient);

watch(patient_id, (newVal) => {
  if (newVal === undefined || newVal === null) {
    if (!localStorage.token) return;
    if (patients.value?.length) {
      router.push({ name: "patient.detail", params: { patient_id: patients.value[0].id } });
    } else {
      loadPatient();
    }
  } else {
    const patient = patients.value?.find((p) => p.id == newVal);
    if (patient) {
      patient.read = true;
    }
  }
});

// When patients list loads, auto-navigate to first patient if none is selected
watch(patients, (list) => {
  if (!patient_id.value && list?.length) {
    router.push({ name: "patient.detail", params: { patient_id: list[0].id } });
  }
});

</script>

<template>
  <div class="row holder">
    <n-card class="patient-list">
      <template #header>
        <div class="header">
          <div class="title">Patient List</div>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                @click="$router.push('/create_patient')"
              >
                <template #icon>
                  <n-icon size="17.5" quaternary type="primary">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="120 120 272 272"
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
            <Dot :state="p.state" :is-read="1" variant="circle"></Dot>
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
              {{ p.name || p.users?.[0]?.name || "n/a" }}
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
              <Dot loading variant="circle"></Dot>
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
  align-items: center;
  flex-wrap: nowrap;
  justify-content: space-between;
  min-height: 30px;
  margin-bottom: 8px;
  margin-top: 14px;
}
.title {
  flex-grow: 1;
  min-width: 0;
  white-space: nowrap;
  font-size: 18px;
  line-height: 28px;
  font-weight: 700;
  margin: 0;
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
  flex-basis: 170px;
  flex-grow: 0;
  flex-shrink: 0;
  min-height: 100%;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.2);
}
.n-card:deep(.n-card__content) {
  padding: 0 6px 0 0;
  overflow: overlay;
  background-color: #ffffff;
}
.filterpart {
  margin-left: 0;
}
.patient-list:deep(.n-card-header) {
  padding: 16px;
}
.patient-list:deep(.n-card-header__main) {
  width: 100%;
}
.patient-list:deep(.n-input) {
  margin-top: 0;
}
.header :deep(.n-button) {
  width: 24px;
  height: 24px;
  min-width: 24px;
  padding: 0;
  flex: 0 0 auto;
}
.header :deep(.n-icon) {
  line-height: 1;
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
  height: 63px;
}
.patient-card {
  height: 63px;
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
    font-size: 14px;
    font-weight: 500;
  }
}
a {
  text-decoration: none;
}
.patient-card.selected {
  border: 2px solid #808080;
  background-color: transparent;
  cursor: default;
}
</style>
