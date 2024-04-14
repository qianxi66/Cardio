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
import { type InputProps } from 'naive-ui'
type InputThemeOverrides = NonNullable<InputProps['themeOverrides']>
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
const themeOverrides: InputThemeOverrides = {
  color: 'transparent',
  border: 'none',
  borderHover: '1px solid rgb(224, 224, 230)',
}
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
        <div v-for="note in notes" :key="note" class="note">
          {{ note }}
          <n-button size="tiny" circle @click="() => notes.splice(index, 1)" quaternary>
            <template #icon>
              <n-icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  xmlns:xlink="http://www.w3.org/1999/xlink"
                  viewBox="0 0 24 24"
                >
                  <g fill="none">
                    <path
                      d="M18.75 4a3.25 3.25 0 0 1 3.245 3.066L22 7.25v9.5a3.25 3.25 0 0 1-3.066 3.245L18.75 20h-8.501a3.25 3.25 0 0 1-2.085-.756l-.155-.139l-4.995-4.75a3.25 3.25 0 0 1-.116-4.594l.116-.116l4.995-4.75a3.25 3.25 0 0 1 2.032-.888L10.25 4h8.501zm0 1.5h-8.501a1.75 1.75 0 0 0-1.08.372l-.126.11l-4.996 4.75l-.062.062a1.75 1.75 0 0 0-.054 2.352l.116.122l4.996 4.75c.285.27.65.437 1.039.474l.167.008h8.501a1.75 1.75 0 0 0 1.744-1.607l.006-.143v-9.5a1.75 1.75 0 0 0-1.607-1.744L18.75 5.5zm-7.304 2.897l.084.073L14 10.939l2.47-2.47a.75.75 0 0 1 1.133.977l-.073.084L15.061 12l2.47 2.47a.75.75 0 0 1-.977 1.133l-.084-.073L14 13.061l-2.47 2.47a.75.75 0 0 1-1.133-.977l.073-.084L12.94 12l-2.47-2.47a.75.75 0 0 1 .976-1.133z"
                      fill="currentColor"
                    ></path>
                  </g>
                </svg>
              </n-icon>
            </template>
          </n-button>
        </div>
        <n-input
          v-model:value="editingNote"
          placeholder="Add a note"
          size="tiny"
          :theme-overrides="themeOverrides"
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
  background-color: #fff9c5;
  .title {
    width: 80px;
    font-size: 14px;
    font-weight: 700;
  }
  .notes-list {
    flex: 1 1 0;
    .note {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
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
