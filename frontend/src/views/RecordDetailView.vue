<script setup lang="tsx">
import { useRouteParams } from "@vueuse/router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import records from "@/data/records.json";
import patients from "@/data/patients.json";
import summaries_data from "@/data/summaries.json";
import conversations from "@/data/conversations.json";
import * as config from "@/config";
import { computed, ref } from "vue";

const patient_id = useRouteParams("patient_id");
const record_id = useRouteParams("record_id");
const patient = computed(
  () => patients.find((p) => p.id === +patient_id.value!)!,
);
const record = computed(() => records.find((r) => r.id === +record_id.value!)!);

// group summaries by category
const summaries = computed(() => {
  const result = {};
  for (const summary of summaries_data) {
    if (!result[summary.category]) {
      result[summary.category] = [];
    }
    result[summary.category].push(summary);
  }
  return result;
});
const notes: Ref<[string]> = ref(["a note", "anoter note"]);
const editingNote = ref("");
</script>
<template>
  <ColoredCard color="#0094ff" rounded title="Conversation Summary">
    <div
      class="summary"
      v-for="category in Object.keys(summaries)"
      :key="category"
    >
      <div class="title">{{ category }}</div>
      <ul>
        <li v-for="summary in summaries[category]" :key="summary.id">
          <div class="summary-content">{{ summary.content }}</div>
        </li>
      </ul>
    </div>
    <div class="notes">
      <div class="title">Notes</div>
      <div class="notes-list">
        <div v-for="note in notes" :key="note" class="note">
          {{ note }}
          <!-- <n-button size="tiny" type="error" round @click="() => notes.splice(index, 1)">
            x
          </n-button> -->
        </div>
        <n-input
          v-model:value="editingNote"
          placeholder="Add a note"
          size="tiny"
          @keyup.enter="
            () => {
              notes.push(editingNote);
              editingNote = '';
            }
          "
        />
      </div>
    </div>
  </ColoredCard>
  <ColoredCard color="#e6372e" rounded title="Detailed Log">
    <div
      v-for="message in conversations"
      :key="message.content"
      :class="{
        message: true,
        assistant: message.role === 'assistant',
        user: message.role === 'user',
      }"
    >
      <div class="role">
        {{ message.role }}
      </div>
      <div class="content">
        {{ message.content }}
      </div>
    </div>
  </ColoredCard>
</template>
<style scoped lang="scss">
.n-card {
  flex: 1;
  min-height: 0;
  :deep(.n-card__content) {
    overflow: overlay;
  }
}
.summary {
  .title {
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  ul {
    margin: 0;
  }
  margin-bottom: 8px;
}
.notes {
  display: flex;
  padding: 12px;
  background-color: #fff9c5;
  .title {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
  }
}
.message {
  display: flex;
  margin-bottom: 8px;
  .role {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
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
</style>
