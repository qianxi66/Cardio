<script setup lang="tsx">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from "vue";
import ColoredCard from "@/components/ColoredCard.vue";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import { useRouteParams, useRouteQuery } from "@vueuse/router";
import { getConversationLogs } from "@/api/patient";
import type { ConversationLog } from "@/api/types";

withDefaults(
  defineProps<{
    highlightColor?: string;
  }>(),
  {
    highlightColor: "#053251",
  },
);

const selectedDate = ref<string | null>(null);
const conversationDate = computed<string | null>({
  get: () => selectedDate.value,
  set: (value) => {
    selectedDate.value = value;
  },
});

const select_log_ids_ = useRouteQuery<string | string[]>("logs");
const select_log_ids = computed(() => {
  const val = select_log_ids_.value;
  if (!val) return [];
  const parts = (Array.isArray(val) ? val : [val]).flatMap((item) => {
    const raw = String(item).trim();
    if (!raw) return [] as string[];

    // Support logs as JSON array string, e.g. "[12,13]".
    if (raw.startsWith("[") && raw.endsWith("]")) {
      try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed.map((x) => String(x));
      } catch {
        // Fall through to comma-separated parsing.
      }
    }

    // Support comma-separated IDs, e.g. "12,13".
    if (raw.includes(",")) {
      return raw.split(",").map((x) => x.trim()).filter(Boolean);
    }

    return [raw];
  });

  const deduped = Array.from(new Set(parts));
  return deduped
    .map((id) => parseInt(id, 10))
    .filter((n) => Number.isFinite(n));
});

const symptom_query = useRouteQuery<string | undefined>("symptom");
const jump_query = useRouteQuery<string | undefined>("jump");

const query_date_ = useRouteQuery<string | undefined>("date");
watch(
  query_date_,
  (dateStr) => {
    if (!dateStr) return;
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      selectedDate.value = dateStr;
    }
  },
  { immediate: true },
);

watch(selectedDate, (value) => {
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

const conversationRefs = ref<Record<number, HTMLElement | null>>({});
const isRefreshingLogs = ref(false);
const logsRefreshTimer = ref<number | null>(null);
const pendingExplicitJump = ref(false);
const setLogRef = (el: unknown, id: number) => {
  if (el instanceof HTMLElement) {
    conversationRefs.value[id] = el;
  }
};

const scrollToLogs = () => {
  const ids = effectiveHighlightIds.value;
  if (ids.size > 0) {
    const minId = Math.min(...ids);
    const el = conversationRefs.value[minId];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
};
const patient_id = useRouteParams("patient_id");
const conversationLogs = ref<ConversationLog[]>([]);
const loading = ref(true);
const DEFAULT_TIMEZONE = "America/New_York";

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

function toDateKey(value: Date, timeZone = DEFAULT_TIMEZONE): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value || "";
  return `${pick("year")}-${pick("month")}-${pick("day")}`;
}

if (!selectedDate.value) {
  selectedDate.value = toDateKey(new Date());
}

const formatLogTime = (value?: string | Date) => {
  const parsed = parseDateValue(value);
  if (!parsed) return "--";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: DEFAULT_TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(parsed);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value || "";
  return `${pick("year")}-${pick("month")}-${pick("day")} ${pick("hour")}:${pick("minute")}`;
};

const loadConversationLogs = async (showLoading = true) => {
  if (!patient_id.value) {
    conversationLogs.value = [];
    loading.value = false;
    return;
  }
  if (isRefreshingLogs.value) return;
  isRefreshingLogs.value = true;
  try {
    if (showLoading) {
      loading.value = true;
    }
    const id = parseInt(patient_id.value as string, 10);
    conversationLogs.value = (await getConversationLogs(id)) ?? [];
  } finally {
    if (showLoading) {
      loading.value = false;
    }
    isRefreshingLogs.value = false;
  }
};

watch(
  patient_id,
  async () => {
    await loadConversationLogs(true);
  },
  { immediate: true },
);

onMounted(() => {
  logsRefreshTimer.value = window.setInterval(() => {
    void loadConversationLogs(false);
  }, 15000);
});

onBeforeUnmount(() => {
  if (logsRefreshTimer.value !== null) {
    window.clearInterval(logsRefreshTimer.value);
    logsRefreshTimer.value = null;
  }
});

const patientIdParam = computed(() => {
  const raw = patient_id.value;
  if (!raw) return undefined;
  const parsed = parseInt(raw as string, 10);
  return Number.isNaN(parsed) ? undefined : parsed;
});
const selectedSeries = ref<Record<string, boolean>>({
  "Heart Rate": true,
  Respiration: true,
  SpO2: true,
  "Heart Rate Variability": true,
});
const wearableDate = computed(() => {
  return conversationDate.value || toDateKey(new Date());
});
const toggleSeries = (name: string) => {
  selectedSeries.value = {
    ...selectedSeries.value,
    [name]: !selectedSeries.value[name],
  };
};

const logsForDate = computed(() => {
  if (!conversationLogs.value.length) {
    return [];
  }
  const targetKey = conversationDate.value;
  const logs = targetKey
    ? conversationLogs.value.filter((log) => {
        const parsed = parseDateValue(log.date);
        return parsed ? toDateKey(parsed) === targetKey : false;
      })
    : [...conversationLogs.value];
  return logs.sort((a, b) => {
    const ta = parseDateValue(a.date)?.getTime() ?? 0;
    const tb = parseDateValue(b.date)?.getTime() ?? 0;
    return ta - tb;
  });
});

const emptyLogsMessage = computed(() => {
  const targetKey = conversationDate.value;
  if (!targetKey) {
    return "No conversation logs";
  }
  return `No conversation logs for ${targetKey}`;
});

// Keyword patterns for symptom-based conversation log highlighting
const symptomPatterns: Record<string, RegExp> = {
  syncope: /faint|pass(?:ed|ing)?\s*out|dizz(?:y|iness)|lightheaded|syncop/i,
  palpitation: /palpit|racing|pounding|flutter|skipping\s*beat/i,
  short_of_breath: /breath|short\s*of\s*breath|breathing/i,
  chest_discomfort: /chest\s*(?:pain|pressure|discomfort|tight)/i,
  swelling: /swell|edema/i,
  heart_rate: /heart\s*rate/i,
  respiration: /respirat|breathing\s*rate/i,
};

// Effective highlighted log IDs: use explicit _logs IDs if available,
// otherwise fall back to keyword matching on conversation content
const effectiveHighlightIds = computed<Set<number>>(() => {
  if (select_log_ids.value.length > 0) {
    return new Set(select_log_ids.value);
  }
  const sym = symptom_query.value;
  if (!sym || !logsForDate.value.length) return new Set<number>();

  const pattern = symptomPatterns[sym];
  if (!pattern) return new Set<number>();

  const ids = new Set<number>();
  const logs = logsForDate.value;
  for (let i = 0; i < logs.length; i++) {
    const log = logs[i];
    if (log.role === "assistant" && pattern.test(log.content || "")) {
      ids.add(log.id);
      // Also highlight the patient's response (next message)
      if (i + 1 < logs.length && logs[i + 1].role === "user") {
        ids.add(logs[i + 1].id);
      }
    }
  }
  return ids;
});

watch(effectiveHighlightIds, () => nextTick(scrollToLogs));
watch(logsForDate, () => nextTick(scrollToLogs), { flush: "post" });
watch(jump_query, () => nextTick(scrollToLogs));
</script>
<template>
  <div class="report-detail" :style="{ '--log-highlight-color': highlightColor }">
    <slot name="top-card">
      <ColoredCard
        color="#053251"
        rounded
        title="Detailed Wearable Sensor Data"
        class="summary-card detailed-wearable-card indigo-title full-title-bar"
      >
        <template #title-extra>
        </template>
        <div class="wearable-dual-chart">
          <div class="chart-section">
            <div class="chart-wrapper">
              <DetailedWearableChart
                :patient-id="patientIdParam ?? undefined"
                :date="wearableDate"
                :selected-series="selectedSeries"
                @toggle-series="toggleSeries"
              />
            </div>
          </div>
        </div>
      </ColoredCard>
    </slot>
    <ColoredCard
      color="#053251"
      rounded
      title="Conversational Log"
      class="conversation-card indigo-title full-title-bar"
    >
      <div class="conversation-scroll" v-if="logsForDate.length > 0">
        <div
          :ref="(el) => setLogRef(el, log.id)"
          class="log-row"
          :class="{
            'log-selected': effectiveHighlightIds.has(Number(log.id)),
            'log-patient': log.role === 'user',
          }"
          v-for="log in logsForDate"
          :key="log.id"
        >
          <div class="log-meta">
            <div class="log-role">
              <span v-if="log.role === 'user'" class="log-patient-avatar" aria-hidden="true">
                <svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
                  <path d="M458.159,404.216c-18.93-33.65-49.934-71.764-100.409-93.431c-28.868,20.196-63.938,32.087-101.745,32.087c-37.828,0-72.898-11.89-101.767-32.087c-50.474,21.667-81.479,59.782-100.398,93.431C28.731,448.848,48.417,512,91.842,512c43.426,0,164.164,0,164.164,0s120.726,0,164.153,0C463.583,512,483.269,448.848,458.159,404.216z" fill="currentColor" />
                  <path d="M256.005,300.641c74.144,0,134.231-60.108,134.231-134.242v-32.158C390.236,60.108,330.149,0,256.005,0c-74.155,0-134.252,60.108-134.252,134.242V166.4C121.753,240.533,181.851,300.641,256.005,300.641z" fill="currentColor" />
                </svg>
              </span>
              {{ log.role === "assistant" ? "Assistant" : "Patient" }}
            </div>
            <div class="log-time">{{ formatLogTime(log.date) }}</div>
          </div>
          <div class="log-content">{{ log.content }}</div>
        </div>
      </div>
      <div v-else class="log-empty-message">{{ emptyLogsMessage }}</div>
    </ColoredCard>
  </div>
</template>
<style scoped lang="scss">
.n-card {
  flex: 1;
  min-height: 0;
  min-width: 0;
  :deep(.n-card__content) {
    overflow: overlay;
    margin-top: 4px;
  }
}
.report-detail {
  display: flex;
  flex-direction: column;
  height: 100%;
  row-gap: 16px;
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  padding-right: 16px;
  box-sizing: border-box;
}
.report-detail .n-card {
  flex: 1 1 0;
  min-height: 0;
}
.report-detail .detailed-wearable-card {
  flex: 1 1 0;
  border: 2px solid #053251 !important;
}
.report-detail .conversation-card {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 2px solid #053251 !important;
}
.detailed-wearable-card :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}
.wearable-range-switch {
  display: inline-flex;
  align-items: center;
  gap: 16px;
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
.wearable-dual-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  min-height: 0;
  min-width: 0;
}
.chart-section {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.chart-wrapper {
  flex: 1 1 0;
  min-height: 180px;
  min-width: 0;
  overflow: hidden;
}
.chart-wrapper :deep(.chart) {
  min-height: 180px;
}
.conversation-card :deep(.n-card__content) {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.conversation-scroll {
  flex: 1 1 0;
  min-height: 0;
  overflow: auto;
  padding: 12px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.log-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  scroll-margin-top: 8px;
  position: relative;
  padding: 10px 14px;
  background: #ffffff;
  // Shared by the .log-selected highlight ring below so the two radii can't drift apart.
  --log-row-radius: 6px;
  --log-row-border-width: 1px;
  border-radius: var(--log-row-radius);
  border: var(--log-row-border-width) solid #d9d9d9;
}
.log-row.log-patient {
  padding: 5px 14px;
  background: #f5f5f5;
}
.log-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.log-row.log-selected::after {
  content: "";
  position: absolute;
  // An absolutely positioned child is laid out against the *padding* box, i.e. inside the
  // 1px border, where staying concentric would require a smaller radius. Pull it back out
  // onto the border box instead so it shares the row's radius exactly and cleanly covers
  // the base border, rather than leaving a sliver of it showing at the corners.
  inset: calc(-1 * var(--log-row-border-width));
  border: 2px solid var(--log-highlight-color, #053251);
  border-radius: var(--log-row-radius);
  pointer-events: none;
}
.log-role {
  font-size: 14px;
  font-weight: 700;
  color: #4f4f4f;
  display: flex;
  align-items: center;
  gap: 5px;
}
.log-patient-avatar {
  width: 14px;
  height: 14px;
  color: #053251;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.log-patient-avatar svg {
  width: 14px;
  height: 14px;
}
.log-content {
  width: 100%;
  line-height: 1.35;
  font-size: 14px;
  color: #3f3f3f;
  white-space: pre-wrap;
  word-break: break-word;
}
.log-time {
  font-size: 14px;
  color: #8c8c8c;
}
.log-empty-message {
  color: #999999;
  font-size: 14px;
  text-align: center;
  padding: 16px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 6px;
  padding-right: 6px;
}
.summary {
  .title {
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
    margin-left: 12px;
  }
  ul {
    margin: 0;
  }
  padding: 8px;
}
.summary-card {
  :deep(.n-card__content) {
    padding: 16px 16px;
  }
}
// .input{
//   margin: 4px;
//   width: calc(100% - 2 * 10px);

// }
.notes {
  display: flex;
  padding: 8px;
  background-color: #c4f1ff;
  flex-direction: column;
  .title {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
    margin-left: 12px;
    margin-top: 12px;
  }
  .notes-list {
    flex: 1 1 0;
    .note {
      margin-right: 12px;
      margin-left: 0px;
      margin-bottom: 0px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      .space {
        flex: 1;
      }
    }
    .n-input {
      margin: 10px;
      width: calc(100% - 20px);
    }
  }
}
.message {
  scroll-margin-top: 8px;
  display: flex;
  margin-bottom: 8px;
  border-radius: 2px;
  &.selected {
    outline: 2px solid var(--color);
  }
  .role {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
    .time {
      font-size: 0.6em;
      color: #666;
    }
  }
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.1);
  padding: 8px;
  .content {
    flex: 1;
  }
  &.assistant {
    background-color: #f5f5f5;
  }
}
.note-time {
  font-size: 0.6em;
  color: #666;
}
.indigo-title :deep(.roundtag__label) {
  background-color: #053251 !important;
  color: #fff;
}
.indigo-title :deep(.roundtag__round) {
  background-color: #053251 !important;
}
.empty-card {
  height: 100%;
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
.full-title-bar.detailed-wearable-card :deep(.roundtag__label),
.full-title-bar.conversation-card :deep(.roundtag__label) {
  background-color: #d7d7d7 !important;
  border: 2px solid #053251 !important;
  border-left-width: 6px !important;
  border-bottom-width: 2px !important;
  border-top-width: 0px !important;
  border-right-width: 0px !important;
  box-sizing: border-box;
  color: #053251 !important;
}
.full-title-bar :deep(.roundtag__round) {
  display: none;
}
.full-title-bar :deep(.n-card.color-card) {
  border-left: none;
}
</style>
