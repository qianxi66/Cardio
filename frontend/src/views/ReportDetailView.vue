<script setup lang="tsx">
import { ref, computed, watch, nextTick } from "vue";
import ColoredCard from "@/components/ColoredCard.vue";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import { useRouteParams, useRouteQuery } from "@vueuse/router";
import { getConversationLogs } from "@/api/patient";
import type { ConversationLog } from "@/api/types";
import { format } from "date-fns";

withDefaults(
  defineProps<{
    highlightColor?: string;
  }>(),
  {
    highlightColor: "#053251",
  },
);

const selectedDate = ref<number | null>(Date.now());
const conversationDate = computed<number | null>({
  get: () => selectedDate.value,
  set: (value) => {
    selectedDate.value = value;
  },
});

const select_log_ids_ = useRouteQuery<string | string[]>("logs");
const select_log_ids = computed(() => {
  const val = select_log_ids_.value;
  if (!val) return [];
  const arr = Array.isArray(val) ? val : [val];
  return arr
    .map((id) => parseInt(String(id), 10))
    .filter((n) => !Number.isNaN(n));
});

const symptom_query = useRouteQuery<string | undefined>("symptom");

const query_date_ = useRouteQuery<string | undefined>("date");
watch(
  query_date_,
  (dateStr) => {
    if (dateStr) {
      const ts = parseInt(dateStr, 10);
      if (!Number.isNaN(ts)) {
        selectedDate.value = ts;
      }
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
  const nextValue = String(value);
  if (query_date_.value !== nextValue) {
    query_date_.value = nextValue;
  }
});

const conversationRefs = ref<Record<number, HTMLElement | null>>({});
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

const formatLogTime = (value?: string | Date) => {
  const parsed = parseDateValue(value);
  if (!parsed) return "--:--:--";
  return format(parsed, "HH:mm:ss");
};

const dateKey = (value: Date) => format(value, "yyyy-MM-dd");

watch(
  patient_id,
  async () => {
    if (!patient_id.value) {
      conversationLogs.value = [];
      return;
    }
    loading.value = true;
    const id = parseInt(patient_id.value as string);
    conversationLogs.value = (await getConversationLogs(id)) ?? [];
    loading.value = false;
  },
  { immediate: true },
);

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
  if (!conversationDate.value) return format(new Date(), "yyyy-MM-dd");
  return format(new Date(conversationDate.value), "yyyy-MM-dd");
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
  const target = conversationDate.value ? new Date(conversationDate.value) : null;
  if (target) {
    const targetKey = dateKey(target);
    const matches = conversationLogs.value.filter((log) => {
      const parsed = parseDateValue(log.date);
      return parsed ? dateKey(parsed) === targetKey : false;
    });
    return matches;
  }
  return conversationLogs.value;
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
      title="Patient's Conversational Log"
      class="conversation-card indigo-title full-title-bar"
    >
      <div class="conversation-scroll" v-if="logsForDate.length > 0">
        <div
          :ref="(el) => setLogRef(el, log.id)"
          class="log-row"
          :class="{
            'log-selected': effectiveHighlightIds.has(log.id),
            'log-patient': log.role === 'user',
          }"
          v-for="log in logsForDate"
          :key="log.id"
        >
          <div class="log-role">{{ log.role === "assistant" ? "Assistant" : "Patient" }}</div>
          <div class="log-content">{{ log.content }}</div>
          <div class="log-time">{{ formatLogTime(log.date) }}</div>
        </div>
      </div>
      <div v-else class="log-empty-message">No conversation logs</div>
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
  align-items: center;
  gap: 12px;
  scroll-margin-top: 8px;
  position: relative;
  padding: 10px 14px;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #d9d9d9;
}
.log-row.log-patient {
  padding: 5px 14px;
  background: #f5f5f5;
}
.log-row.log-selected::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px solid var(--log-highlight-color, #053251);
  border-radius: 6px;
  pointer-events: none;
}
.log-role {
  flex: 0 0 92px;
  font-size: 14px;
  font-weight: 700;
  color: #4f4f4f;
}
.log-content {
  flex: 1 1 auto;
  min-width: 0;
  line-height: 1.35;
  font-size: 14px;
  color: #3f3f3f;
  white-space: pre-wrap;
  word-break: break-word;
}
.log-time {
  flex: 0 0 88px;
  text-align: right;
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
