<script setup lang="tsx">
import { useRouteParams } from '@vueuse/router'
import ColoredCard from '@/components/ColoredCard.vue'
import Dot from '@/components/Dot.vue'
import records from '@/data/records.json'
import patients from '@/data/patients.json'
import summaries_data from '@/data/summaries.json'
import conversations from '@/data/conversations.json'
import * as config from '@/config'
import { computed, ref, type Ref } from 'vue'
const patient_id = useRouteParams('patient_id')
const record_id = useRouteParams('record_id')
const patient = computed(() => patients.find((p) => p.id === +patient_id.value!)!)
const record = computed(() => records.find((r) => r.id === +record_id.value!)!)

// group summaries by category
const summaries = computed(() => {
  const result = {}
  for (const summary of summaries_data) {
    if (!result[summary.category]) {
      result[summary.category] = []
    }
    result[summary.category].push(summary)
  }
  return result
})
const notes: Ref<string[]> = ref(['a note', 'anoter note'])
const editingNote = ref('')
</script>
<template>
  <ColoredCard color="#0094ff" rounded title="Conversation Summary">
    <div class="summary" v-for="category in Object.keys(summaries)" :key="category">
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
        <div v-for="(note, index) in notes" :key="note" class="note">
          {{ note }}
          <div class="space"></div>
          <n-button size="tiny" circle @click="() => notes.splice(index, 1)" quaternary>
            <template #icon>
              <n-icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  xmlns:xlink="http://www.w3.org/1999/xlink"
                  viewBox="0 0 24 24"
                >
                  <path
                    d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10s10-4.47 10-10S17.53 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8s8 3.59 8 8s-3.59 8-8 8zm3.59-13L12 10.59L8.41 7L7 8.41L10.59 12L7 15.59L8.41 17L12 13.41L15.59 17L17 15.59L13.41 12L17 8.41z"
                    fill="currentColor"
                  ></path>
                </svg>
              </n-icon>
            </template>
          </n-button>
        </div>
        <n-input
          v-model:value="editingNote"
          placeholder="Add a note (prss enter to submit)"
          @keyup.enter="
            () => {
              notes.push(editingNote)
              editingNote = ''
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
        user: message.role === 'user'
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
  background-color: #c4f1ff;
  flex-direction: column;
  .title {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
  }
  .notes-list {
    flex: 1 1 0;
    .note {
      margin-left: 13px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      .space {
        flex: 1;
      }
    }
    .n-input {
      margin-top: 8px;
    }
  }
}
.message {
  display: flex;
  margin-bottom: 8px;
  border-radius: 2px;
  outline: 2px solid #f9d965;
  .role {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
  }
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.1);
  padding: 8px;
  .content {
    flex: 1;
    background-color: #f9d965;
  }
  &.assistant {
    background-color: #f5f5f5;
  }
  &.user {
  }
}
</style>
