<script setup lang="tsx">
import { ref, computed, watch, nextTick } from "vue";
import ColoredCard from "@/components/ColoredCard.vue";
import DetailedWearableChart from "@/components/DetailedWearableChart.vue";
import { useRouteParams, useRouteQuery } from "@vueuse/router";
import { getConversationLogs } from "@/api/patient";
import type { ConversationLog } from "@/api/types";
import { format } from "date-fns";

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
  if (select_log_ids.value.length > 0) {
    const minId = Math.min(...select_log_ids.value);
    const el = conversationRefs.value[minId];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
};
watch(select_log_ids, () => nextTick(scrollToLogs));
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
    conversationLogs.value = await getConversationLogs(id);
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
const wearableRange = ref<"24h" | "7d">("24h");
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

const detailSymptoms = computed(() => {
  const source = logsForDate.value.find(
    (log) => log.symptoms_chest || log.symptoms_other,
  );
  if (!source) {
    return {
      chest: "no data",
      other: "no data",
    };
  }
  return {
    chest: source.symptoms_chest || "no data",
    other: source.symptoms_other || "no data",
  };
});

watch(logsForDate, () => nextTick(scrollToLogs), { flush: "post" });
</script>
<template>
  <div class="report-detail">
    <slot name="top-card">
      <ColoredCard
        color="#5171AB"
        rounded
        title="Detailed Wearable Sensor Data"
        class="summary-card detailed-wearable-card indigo-title full-title-bar"
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
        <div class="wearable-dual-chart">
          <div class="chart-section">
            <div class="chart-wrapper">
              <DetailedWearableChart
                :patient-id="patientIdParam ?? undefined"
                :range="wearableRange"
                :selected-series="selectedSeries"
                @toggle-series="toggleSeries"
              />
            </div>
          </div>
        </div>
      </ColoredCard>
    </slot>
    <ColoredCard
      color="#5171AB"
      rounded
      title="Conversational Log"
      class="conversation-card indigo-title full-title-bar"
    >
      <div class="conversation-panel conversation-left">
        <div class="conversation-title">Details Symptoms from Log</div>
        <div class="conversation-box conversation-detail">
          <div class="conversation-detail-scroll">
            <div class="detail-row">
              <div class="detail-label">Chest Discomfort</div>
              <div class="detail-value">{{ detailSymptoms.chest }}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Other Discomfort</div>
              <div class="detail-value">{{ detailSymptoms.other }}</div>
            </div>
          </div>
        </div>
      </div>
      <div class="conversation-panel conversation-right">
        <div class="conversation-title">Log History</div>
        <div class="conversation-box conversation-log">
          <div class="conversation-scroll" v-if="logsForDate.length > 0 || !conversationDate">
            <div
              :ref="(el) => setLogRef(el, log.id)"
              class="log-row"
              :class="[
                log.role === 'assistant' ? 'log-agent' : 'log-user',
                { 'log-selected': select_log_ids.includes(log.id) },
              ]"
              v-for="log in logsForDate"
              :key="log.id"
            >
              <div class="log-avatar" v-if="log.role === 'assistant'">
                <svg
                  width="800"
                  height="800"
                  viewBox="0 -64 640 640"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M32,224H64V416H32A31.96166,31.96166,0,0,1,0,384V256A31.96166,31.96166,0,0,1,32,224Zm512-48V448a64.06328,64.06328,0,0,1-64,64H160a64.06328,64.06328,0,0,1-64-64V176a79.974,79.974,0,0,1,80-80H288V32a32,32,0,0,1,64,0V96H464A79.974,79.974,0,0,1,544,176ZM264,256a40,40,0,1,0-40,40A39.997,39.997,0,0,0,264,256Zm-8,128H192v32h64Zm96,0H288v32h64ZM456,256a40,40,0,1,0-40,40A39.997,39.997,0,0,0,456,256Zm-8,128H384v32h64ZM640,256V384a31.96166,31.96166,0,0,1-32,32H576V224h32A31.96166,31.96166,0,0,1,640,256Z"
                    fill="#7892b5"
                  />
                </svg>
              </div>
              <div
                class="log-bubble"
                :class="log.role === 'assistant' ? 'log-agent-bubble' : 'log-user-bubble'"
              >
                {{ log.content }}
              </div>
              <div class="log-avatar" v-if="log.role !== 'assistant'">
                <svg viewBox="0 0 24 24">
                  <path
                    d="M12 12a4 4 0 1 0-4-4a4 4 0 0 0 4 4Zm0 2c-4.2 0-7.5 2-7.5 4.5V20h15v-1.5C19.5 16 16.2 14 12 14Z"
                    fill="currentColor"
                  />
                </svg>
              </div>
            </div>
          </div>
          <div v-else-if="logsForDate.length === 0 && conversationDate" class="log-empty-message">
            No conversation logs for this date
          </div>
        </div>
      </div>
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
  flex: 0 1 50%;
}
.report-detail .conversation-card {
  flex: 1 1 0;
  min-height: 0;
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
  color: #ffffff;
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
  border: 2px solid #ffffff;
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
  background: #ffffff;
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
  gap: 0;
  height: 100%;
  min-height: 0;
}
.conversation-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.conversation-left {
  flex: 0 0 40%;
  padding-right: 16px;
  box-sizing: border-box;
}
.conversation-right {
  flex: 0 0 60%;
  padding-left: 16px;
  box-sizing: border-box;
  border-right: none;
}
.conversation-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 16px;
}
.conversation-box {
  background-color: #f3f3f3;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.conversation-scroll {
  flex: 1 1 0;
  min-height: 0;
  overflow: auto;
  padding-right: 6px;
  padding-left: 6px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.conversation-detail {
  padding: 12px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.conversation-detail-scroll {
  height: 100%;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 6px;
  padding-left: 6px;
  box-sizing: border-box;
}
.detail-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.detail-label {
  font-size: 12px;
  font-weight: 700;
  color: #555555;
}
.detail-value {
  font-size: 14px;
  color: #808080;
  white-space: pre-wrap;
}
.conversation-log {
  padding: 12px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}
.log-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  scroll-margin-top: 8px;
  position: relative;
}
.log-row.log-selected::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px solid #5171ab;
  border-radius: 4px;
  pointer-events: none;
}
.log-row.log-agent.log-selected > .log-bubble.log-agent-bubble {
  padding-top: 5px;
  padding-bottom: 5px;
}
.log-row.log-user.log-selected {
  padding-top: 5px;
  padding-bottom: 5px;
}
.log-agent {
  justify-content: flex-start;
}
.log-user {
  justify-content: flex-end;
}
.log-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #ffffff;
  color: #8a8a8a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}
.log-avatar svg {
  width: 18px;
  height: 18px;
  transform: scale(1.1);
}
.log-bubble {
  padding: 10px 12px;
  border-radius: 12px;
  max-width: 70%;
  line-height: 1.4;
  font-size: 14px;
}
.log-agent-bubble {
  background: transparent;
  color: #222;
}
.log-user-bubble {
  background: #ffffff;
  color: #222;
  box-shadow: 0 0 0 1px #e6e6e6 inset;
}
.log-empty-message {
  color: #999999;
  font-size: 12px;
  text-align: center;
  padding: 16px;
  font-style: italic;
  height: 100%;
  display: flex;
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
  background-color: #5171AB !important;
  color: #fff;
}
.indigo-title :deep(.roundtag__round) {
  background-color: #5171AB !important;
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
.full-title-bar :deep(.roundtag__round) {
  display: none;
}
.full-title-bar :deep(.n-card.color-card) {
  border-left: none;
}
</style>
