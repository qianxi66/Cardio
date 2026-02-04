<script setup lang="tsx">
import { ref, computed, watch } from "vue";
import ColoredCard from "@/components/ColoredCard.vue";
import AiRiskTrendChart from "@/components/AiRiskTrendChart.vue";
import AiRiskGauge from "@/components/AiRiskGauge.vue";
import { useRouteParams } from "@vueuse/router";
import { getConversationLogs, getRisks } from "@/api/patient";
import type { ConversationLog, Risk } from "@/api/types";
import { format } from "date-fns";

const conversationDate = ref<number | null>(Date.now());
const riskDate = ref<number | null>(Date.now());
const patient_id = useRouteParams("patient_id");
const risks = ref<Risk[]>([]);
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
      risks.value = [];
      conversationLogs.value = [];
      return;
    }
    loading.value = true;
    const id = parseInt(patient_id.value as string);
    risks.value = await getRisks(id);
    conversationLogs.value = await getConversationLogs(id);
    loading.value = false;
  },
  { immediate: true },
);

const riskForDate = computed(() => {
  if (!risks.value.length) {
    return null;
  }
  const target = riskDate.value ? new Date(riskDate.value) : null;
  if (target) {
    const targetKey = dateKey(target);
    const match = risks.value.find((risk) => {
      const parsed = parseDateValue(risk.date);
      return parsed ? dateKey(parsed) === targetKey : false;
    });
    if (match) {
      return match;
    }
  }
  return risks.value[0];
});

const normalizePercent = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 0;
  }
  const normalized = value <= 1 ? value * 100 : value;
  return Math.round(Math.max(0, Math.min(100, normalized)));
};

const riskScore = computed(() => normalizePercent(riskForDate.value?.risk_score));

const featureImportance = computed(() => {
  const risk = riskForDate.value;
  if (!risk) {
    return [];
  }
  return [
    { label: "Chest Discomfort", value: normalizePercent(risk.important_of_chest) },
    { label: "Heart Rate", value: normalizePercent(risk.important_of_heart) },
    { label: "Respiration", value: normalizePercent(risk.important_of_respiration) },
    { label: "HRV", value: normalizePercent(risk.important_of_hrv) },
  ];
});

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
    if (matches.length) {
      return matches;
    }
  }
  return conversationLogs.value;
});

const detailSymptoms = computed(() => {
  const source = logsForDate.value.find(
    (log) => log.symptoms_chest || log.symptoms_other,
  );
  if (!source) {
    return {
      chest: "n/a",
      other: "n/a",
    };
  }
  return {
    chest: source.symptoms_chest || "n/a",
    other: source.symptoms_other || "n/a",
  };
});
</script>
<template>
  <div class="report-detail">
    <ColoredCard
      color="#5171AB"
      rounded
      title="AI Risk Prediction"
      class="summary-card ai-risk-card indigo-title full-title-bar"
    >
      <template #title-extra>
        <n-date-picker v-model:value="riskDate" type="date" size="small" clearable />
      </template>
      <div class="ai-risk-content">
        <div class="ai-risk-top">
          <div class="ai-risk-panel left-panel">
            <div class="ai-risk-title">Cardiotoxicity Risk Score</div>
            <div class="risk-score">
              <div class="risk-gauge">
                <AiRiskGauge :value="riskScore" />
              </div>
              <div class="risk-desc">
                (The score predicts the <span style="font-weight: bold; color: #555555;">6-month</span> risk of cardiovascular complications based on <span style="font-weight: bold;"> EHR data, wearable sensors</span>, and <span style="font-weight: bold;"> self-reported symptoms</span>.)
              </div>
            </div>
          </div>
          <div class="ai-risk-panel right-panel">
            <div class="ai-risk-title">Feature Importance</div>
            <div class="feature-box">
              <div class="feature-list">
                <div
                  class="feature-item"
                  v-for="item in featureImportance"
                  :key="item.label"
                >
                  <span class="feature-label">{{ item.label }}</span>
                  <div class="feature-bar">
                    <div class="feature-fill" :style="{ width: `${item.value}%` }"></div>
                  </div>
                  <span class="feature-val">{{ Math.round(item.value) }}%</span>
                </div>
                <div v-if="featureImportance.length === 0" class="feature-item">
                  <span class="feature-label">n/a</span>
                  <div class="feature-bar">
                    <div class="feature-fill" style="width: 0%"></div>
                  </div>
                  <span class="feature-val">0%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="ai-risk-bottom">
          <AiRiskTrendChart />
        </div>
      </div>
    </ColoredCard>
    <ColoredCard
      color="#5171AB"
      rounded
      title="Conversational Log"
      class="conversation-card indigo-title full-title-bar"
    >
      <template #title-extra>
        <n-date-picker
          v-model:value="conversationDate"
          type="date"
          size="small"
          clearable
        />
      </template>
      <div class="conversation-panel conversation-left">
        <div class="conversation-title">Details Symptoms from Log</div>
        <div class="conversation-box conversation-detail">
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
      <div class="conversation-panel conversation-right">
        <div class="conversation-title">Log History</div>
        <div class="conversation-box conversation-log">
          <div class="conversation-scroll">
            <div
              class="log-row"
              :class="log.role === 'assistant' ? 'log-agent' : 'log-user'"
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
          <div v-if="logsForDate.length === 0" class="log-row log-agent">
            <div class="log-avatar">
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
            <div class="log-bubble log-agent-bubble">n/a</div>
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
  padding-right: 16px;
  box-sizing: border-box;
}
.report-detail .n-card {
  flex: 1 1 0;
  min-height: 0;
}
.report-detail .ai-risk-card {
  flex: 0 1 55%;
}
.report-detail .conversation-card {
  flex: 0 1 45%;
}
.ai-risk-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  min-width: 0;
}
.ai-risk-top {
  display: flex;
  gap: 16px;
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
}
.ai-risk-bottom {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}
.ai-risk-panel {
  flex: 1 1 0;
  min-height: 0;
}
.ai-risk-panel.right-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.feature-box {
  background-color: #f3f3f3;
  padding: 12px;
  box-sizing: border-box;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.ai-risk-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}
.risk-score {
  display: flex;
  gap: 8px;
  align-items: stretch;
  flex: 1 1 auto;
  min-height: 0;
  min-width: 50;
}
.risk-gauge {
  width: 200px;
  height: 100%;
  position: relative;
  flex: 0 0 auto;
}
.feature-label{
  text-align: right;
  padding-right: 12px;
  font-weight: 700;
  font-family: "Arial";
  color: #808080;  
}
.risk-desc {
  color: #808080;
  font-size: 12px;
  line-height: 1.4;
  flex: 1 1 auto;
  min-width: 0;
  max-width: none;
  align-self: center;
  overflow-wrap: anywhere;
}
.feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding-right: 6px;
}
.feature-item {
  display: grid;
  grid-template-columns: 130px 1fr 48px;
  align-items: center;
}
.feature-bar {
  height: 14px;
  background: #ffffff;
  border-radius: 4px;
  overflow: hidden;
  width: 80%;
}
.feature-fill {
  height: 100%;
  background: #5574aa;
}
.feature-val {
  font-weight: 700;
  color: #555;
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
  height: 100%;
  overflow: auto;
  padding-right: 6px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.conversation-detail {
  padding: 16px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 12px;
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
  gap: 8px;
  overflow-y: auto;
}
.log-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
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
    padding: 8px 12px;
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
  &.user {
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
