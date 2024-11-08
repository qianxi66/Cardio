<script setup lang="tsx">
import { useRouteParams, useRouteQuery } from "@vueuse/router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import conversations from "@/data/conversations.json";
import * as config from "@/config";
import { computed, nextTick, reactive, ref, watch, type Ref } from "vue";
import type { Report, ReportSummary } from "@/api/types";
import type { CancelTokenSource } from "axios";

import {
  getReport,
  createNote as createNoteAPI,
  deleteNote as deleteNoteAPI,
} from "@/api/patient";
import axios from "axios";
import { getUserInfo } from "@/api/user";
const patient_id = useRouteParams<number | null>("patient_id");
const report_id = useRouteParams<number | null>("report_id");
const select_log_ids_ = useRouteQuery<string[]>("logs");
const select_log_ids = computed(() => {
  if (select_log_ids_.value) {
    return select_log_ids_.value.map((id) => parseInt(id));
  } else {
    return [];
  }
});
const state = useRouteQuery<number>("state");
import { stateColors } from "@/config";
import { format, formatDistance } from "date-fns";

const cancelToken = ref<CancelTokenSource | null>(null);

const report = ref<Report | null>(null);
const loading = ref(true);
const editingNote = ref("");
const conversationRefs = ref<{ [key: number]: HTMLElement | null }>({});
const create_note_loading = ref(false);
const refresh = async () => {
  if (cancelToken.value) {
    cancelToken.value.cancel();
  }
  cancelToken.value = axios.CancelToken.source();
  report.value = null;
  loading.value = true;
  conversationRefs.value = {};
  report.value = await getReport(
    patient_id.value!,
    report_id.value!,
    cancelToken.value.token,
  );
  loading.value = false;
};

defineExpose({ refresh });

watch(
  report_id,
  async () => {
    if (!report_id.value) {
      report.value = null;
      loading.value = true;
      return;
    }
    console.log("fetching report", report_id.value);
    await refresh();
    nextTick(scroll);
  },
  { immediate: true },
);

watch(patient_id, () => {
  if (patient_id.value) {
    report_id.value = null;
  }
});
// group summaries by category
const summaries = computed(() => {
  if (!report.value?.summary) return {};
  const result: {
    [key: string]: ReportSummary[];
  } = {};
  for (const summary of report.value!.summary!) {
    if (!result[summary.category]) {
      result[summary.category] = [];
    }
    result[summary.category].push(summary);
  }
  return result;
});
const deleteNote = (note_id: number) => {
  report.value!.notes = report.value!.notes.filter(
    (note) => note.id !== note_id,
  );
  deleteNoteAPI(patient_id.value as number, report_id.value as number, note_id);
};

const createNote = async () => {
  if (editingNote.value) {
    // report.value!.notes.push({
    //   id: report.value!.notes.length + 1,
    //   content: editingNote.value,
    //   created_at: new Date(),
    //   user: {
    //     username: username
    //   },
    //   updated_at: new Date(),
    //   user_id: user_Id,
    //   report_id: report.value!.id
    // })
    create_note_loading.value = true;
    try {
      await createNoteAPI(
        patient_id.value as number,
        report_id.value as number,
        editingNote.value,
      );
    } catch (e) {
      console.error(e);
    } finally {
      create_note_loading.value = false;
    }
    editingNote.value = "";
    refresh();
  }
};
const scroll = () => {
  if (select_log_ids.value.length > 0) {
    if (report.value?.conversation_logs) {
      const min = Math.min(...select_log_ids.value);
      console.log("scrolling to", min);
      const el = conversationRefs.value[min];
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }
};
watch(select_log_ids, scroll);
</script>
<template>
  <ColoredCard
    color="#0094ff"
    rounded
    title="Conversation Summary"
    class="summary-card"
  >
    <Loading :loading="loading" :has-data="!!report">
      <template #loading>
        <div class="summary" v-for="i in 2" :key="i">
          <n-skeleton class="title" text style="height: 22.4"> </n-skeleton>
          <ul>
            <li v-for="j in 3" :key="j">
              <n-skeleton class="summary-content" text style="height: 16px">
              </n-skeleton>
            </li>
          </ul>
        </div>
        <div class="notes">
          <div class="title">Notes</div>
          <div class="notes-list">
            <div v-for="i in 3" :key="i" class="note">
              <n-skeleton
                class="summary-content"
                text
                style="height: 20px; margin-bottom: 2.4px"
              >
              </n-skeleton>
            </div>
            <n-input
              v-model:value="editingNote"
              placeholder="Add a note (press enter to submit)"
              @keyup.enter="createNote()"
            />
          </div>
        </div>
      </template>

      <div
        class="summary"
        v-for="category in Object.keys(summaries)"
        :key="category"
      >
        <div class="title">{{ category }}</div>
        <ul>
          <li v-for="summary in summaries[category]" :key="summary.id">
            <div class="summary-content">{{ summary.content }}</div>

            <div
              class="note-time"
              :title="format(summary.created_at, 'yyyy-MM-dd HH:mm:ss')"
            >
              {{
                formatDistance(summary.created_at, new Date(), {
                  addSuffix: true,
                })
              }}, created by AI
            </div>
          </li>
        </ul>
      </div>
      <div class="notes">
        <div class="title">Notes</div>
        <div class="notes-list">
          <ul v-for="note in report!.notes" :key="note.id" class="note">
            <li>
              <div class="note-left">
                <div>{{ note.content }}</div>
                <div
                  class="note-time"
                  :title="format(note.created_at, 'yyyy-MM-dd HH:mm:ss')"
                >
                  {{
                    formatDistance(note.created_at, new Date(), {
                      addSuffix: true,
                    })
                  }}, created by {{ note.user.name }}
                </div>
              </div>
            </li>
            <div class="space"></div>
            <n-button
              size="tiny"
              circle
              @click="deleteNote(note.id)"
              quaternary
            >
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
          </ul>
          <n-input
            v-model:value="editingNote"
            :loading="create_note_loading"
            placeholder="Add a note (press enter to submit)"
            @keyup.enter="createNote()"
            class="input"
          />
        </div>
      </div>
    </Loading>
  </ColoredCard>
  <ColoredCard
    color="#e6372e"
    rounded
    title="Detailed Log"
    :style="{
      '--color': stateColors[state],
    }"
  >
    <Loading :loading="loading" :has-data="!!report">
      <template #loading>
        <div
          v-for="i in 6"
          :key="i"
          :class="{
            message: true,
          }"
        >
          <div class="role">
            <n-skeleton text style="height: 16px; width: 60px"> </n-skeleton>
          </div>
          <div class="content">
            <n-skeleton text style="height: 16px" :repeat="2"> </n-skeleton>
          </div>
        </div>
      </template>
      <div
        v-for="message in report?.conversation_logs"
        :key="message.content"
        :class="{
          message: true,
          assistant: message.role === 'assistant',
          user: message.role === 'user',
          selected: select_log_ids.includes(message.id),
        }"
        :ref="(el) => (conversationRefs[message.id] = el)"
      >
        <div class="role">
          {{ message.role }}
          <div
            class="time"
            :title="format(message.created_at, 'yyyy-MM-dd HH:mm:ss')"
          >
            {{
              formatDistance(message.created_at, new Date(), {
                addSuffix: true,
              })
            }}
          </div>
        </div>
        <div class="content">
          {{ message.content.replace("CONVERSATION_END", "") }}
        </div>
      </div>
    </Loading>
  </ColoredCard>
</template>
<style scoped lang="scss">
.n-card {
  padding: 10px;
  flex: 1;
  min-height: 0;
  :deep(.n-card__content) {
    overflow: overlay;
    margin-top: 22px;
  }
}
.summary {
  .title {
    font-size: 14px;
    font-weight: 700;
    //margin-top:22px;
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
</style>
