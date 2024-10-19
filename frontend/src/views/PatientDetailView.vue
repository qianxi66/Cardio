<script setup lang="tsx">
import { useRouteParams, useRouteQuery } from "@vueuse/router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import * as config from "@/config";
import { computed, watch, type Ref, ref, inject } from "vue";
import type { Patient, Report } from "@/api/types";
import { getPatient, updateReport, createNote } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format, formatDistance } from "date-fns";
import router from "@/router";
import type { CancelTokenSource } from "axios";
import ReportTableHeader from "@/components/ReportTableHeader.vue";
import axios from "axios";
import CircleProgress from "@/components/CircleProgress.vue";
import { getUserInfo } from "@/api/user";
import { stateColors } from "@/config"; // shihan

const refreshPatients = inject("refreshPatients");
const patient_id = useRouteParams("patient_id");
const report_id = useRouteParams("report_id");
let user_Id = 0;

const current_symptom = useRouteQuery("symptom");
const report = ref<Report | null>(null);

const patient = ref<Patient | null>(null);
const loading = ref(true);
const cancelToken = ref<CancelTokenSource | null>(null);

watch(
  patient_id,
  async () => {
    console.log("patient_id changed", patient_id.value);
    if (!patient_id.value) {
      patient.value = null;
      loading.value = true;
      return;
    }
    console.log("fetching patient", patient_id.value);
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
    loading.value = false;
  },
  { immediate: true },
);

const fetchUserInfo = async () => {
  try {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("Token not found");
      return;
    }
    const userInfoResponse = await getUserInfo(token);
    if (userInfoResponse.user_id) {
      user_Id = userInfoResponse.user_id;
      console.log(user_Id);
    }
  } catch (error: any) {
    console.error("An error occurred while fetching user info:", error);
  }
};

fetchUserInfo();

const jumpToReport = (report: Report, symptom: string | undefined) => {
  router.push({
    name: "patient.report.detail",
    params: { patient_id: patient_id.value, report_id: report.id },
    query: {
      ...(symptom
        ? {
            symptom: symptom,
            logs: report[
              (symptom + "_logs") as keyof Report
            ] as unknown as number[],
            state:
              report[symptom + "_state"] == 2
                ? config.symptoms[symptom].max_scale
                : report[symptom + "_state"],
          }
        : {}),
    },
  });
};

watch(patient, () => {
  // get the latest report id
  if (patient.value) {
    const latestReport = patient.value.reports[0];
    if (latestReport) {
      const most_severe_symptom = Object.keys(config.symptoms).reduce(
        (acc: { state: number; symptom: string }, symptom: string) => {
          if (
            (latestReport[(symptom + "_state") as keyof Report] as number) >
            acc.state
          ) {
            acc.state = latestReport[
              (symptom + "_state") as keyof Report
            ] as number;
            acc.symptom = symptom;
          }
          return acc;
        },
        { state: 0, symptom: "" },
      );
      console.log(most_severe_symptom);
      jumpToReport(latestReport, most_severe_symptom.symptom);
    }
  }
});

const right = ref<Component | null>(null);
const updateState = async (
  id: number,
  report_id: number,
  symptom: string,
  state: number,
) => {
  console.log("updateState called with:", { id, report_id, symptom, state });

  const report = patient.value!.reports.find((r) => r.id === report_id);
  console.log("Found report:", report);

  if (report) {
    const date = format(new Date(), "yyyy-MM-dd HH:mm:ss");
    console.log("Formatted date:", date);

    const oldStateMessage = [
      "No Information",
      "Normal",
      config.stateMessages[config.symptoms[symptom].max_scale],
    ][report[symptom + "_state"]];
    const newStateMessage = config.stateMessages[state];
    console.log("State change:", { oldStateMessage, newStateMessage });

    await createNote(
      id,
      report_id,
      `Severity of ${symptom} changed from ${oldStateMessage} to ${newStateMessage} at ${date}`,
    );
    console.log("Note created for state change.");

    report[symptom + "_state"] = state;
    console.log(
      `Updated report state for ${symptom}:`,
      report[symptom + "_state"],
    );

    await updateReport(id, report_id, { [symptom + "_state"]: state });
    console.log("Report updated on server.");

    right.value?.refresh();
    console.log("Right panel refreshed.");

    refreshPatients?.();
    console.log("Patients data refreshed.");
  } else {
    console.warn("Report not found for report_id:", report_id);
  }
};
</script>

<template>
  <div class="row">
    <div class="col" style="flex: 5 1 350px">
      <ColoredCard class="information">
        <Loading :loading="loading" :has-data="!!patient">
          <div class="row">
            <div class="participant-id">
              Older Adults {{ patient!.participant_id }}
            </div>
            <div class="space"></div>
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button
                  quaternary
                  circle
                  @click="$router.push(`/patient/${patient_id}/update`)"
                >
                  <template #icon>
                    <n-icon>
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 16 16"
                      >
                        <g fill="none">
                          <path
                            d="M12.007 6.81l-5.949 5.95c-.319.318-.719.545-1.156.654l-2.283.57a.498.498 0 0 1-.604-.603l.57-2.283a2.49 2.49 0 0 1 .656-1.156l5.948-5.95l2.818 2.817zm1.41-4.226c.777.778.777 2.039 0 2.817l-.706.704l-2.817-2.818l.705-.703a1.992 1.992 0 0 1 2.817 0z"
                            fill="currentColor"
                          ></path>
                        </g>
                      </svg>
                    </n-icon>
                  </template>
                </n-button>
              </template>
              Edit Patient
            </n-tooltip>
          </div>
          <div class="row demographic">
            <span class="age-sex">
              <b>
                {{ patient!.age ? patient!.age + " y.o." : "" }}
              </b>
              {{ patient!.gender }}
            </span>
            <span>
              {{ patient!.EHR_id }}
            </span>
          </div>
          <div class="row patient-details">
            <div class="box">
              <div class="row">
                <div class="title">Location</div>
                <div class="space"></div>
                <div>Last Visit: No Information</div>
              </div>
              {{ patient!.medical_history }}
            </div>
            <div class="box">
              <div class="row">
                <div class="title">Medication</div>
              </div>
              {{ patient!.medication }}
            </div>
          </div>
          <template #loading>
            <n-skeleton
              class="participant-id"
              style="height: 25px; width: 100px"
            ></n-skeleton>
            <div class="row demographic">
              <n-skeleton class="age-sex" style="height: 21px"> </n-skeleton>
              <n-skeleton style="height: 21px; width: 38px"> </n-skeleton>
            </div>
            <div class="row patient-details">
              <div class="box">
                <div class="row">
                  <div class="title">Medical History</div>
                  <div class="space"></div>
                  <div>
                    <n-skeleton
                      text
                      style="display: inline-block; width: 150px"
                    >
                    </n-skeleton>
                  </div>
                </div>
                <n-skeleton text :repeat="2"></n-skeleton>
              </div>
              <div class="box">
                <div class="row">
                  <div class="title">Medication</div>
                </div>
                <n-skeleton text :repeat="2"></n-skeleton>
              </div>
            </div>
          </template>
        </Loading>
      </ColoredCard>
      <ColoredCard
        class="key-question"
        title="Key Question Overview"
        color="#4a239c"
        rounded
        style="flex: 1 1 400px"
      >
        <Loading :loading="loading" :has-data="!!patient">
          <div class="reports-table">
            <ReportTableHeader></ReportTableHeader>
            <div
              v-for="(report, index) in patient!.reports"
              :key="index"
              :class="{
                'table-row-block': true,
                selected: report.id === parseInt(report_id),

                odd: index % 2 === 0,
              }"
            >
              <div
                :class="{
                  'table-row': true,
                  report: true,
                }"
              >
                <div class="date">
                  {{ format(report.created_at, "yyyy-MM-dd HH:mm:ss") }}
                </div>
                <div
                  class="symptom"
                  v-for="symptom of Object.keys(config.symptoms)"
                  :key="symptom"
                >
                  <n-tooltip
                    trigger="hover"
                    v-if="config.symptoms[symptom].likert"
                  >
                    <template #trigger>
                      <circle-progress
                        :percent="report[symptom + '_scale'] * 10"
                        autocolor
                        color="red"
                        :id="symptom + index.toString()"
                        style="width: 50px"
                      >
                        <dot-likert
                          @update:state="
                            updateState(patient.id, report.id, symptom, $event)
                          "
                          :editable="
                            (current_symptom === symptom &&
                              report.id === parseInt(report_id)) ||
                            report[symptom + '_state'] === 0
                          "
                          :class="{
                            selected:
                              current_symptom === symptom &&
                              report.id === parseInt(report_id),
                            disabled: report[symptom + '_state'] === 0,
                          }"
                          :state="report[symptom + '_state']"
                          @click="
                            report[symptom + '_state'] !== 0 &&
                              jumpToReport(report, symptom)
                          "
                          :color="config.symptoms[symptom].color"
                          :symptom="symptom"
                        />
                      </circle-progress>
                    </template>
                    <div>
                      {{ config.symptoms[symptom].display_name }}:
                      {{ report[symptom + "_scale"] }}
                    </div>
                  </n-tooltip>
                  <circle-progress
                    v-else
                    :percent="0"
                    color="red"
                    :id="symptom"
                    style="width: 50px"
                    :visible="false"
                  >
                    <dot-symptom
                      @update:state="
                        updateState(patient.id, report.id, symptom, $event)
                      "
                      :editable="
                        (current_symptom === symptom &&
                          report.id === parseInt(report_id)) ||
                        report[symptom + '_state'] === 0
                      "
                      :class="{
                        selected:
                          current_symptom === symptom &&
                          report.id === parseInt(report_id),
                        disabled: report[symptom + '_state'] === 0,
                      }"
                      :state="report[symptom + '_state']"
                      @click="
                        report[symptom + '_state'] !== 0 &&
                          jumpToReport(report, symptom)
                      "
                      :color="config.symptoms[symptom].color"
                      :symptom="symptom"
                    />
                  </circle-progress>
                </div>
              </div>
            </div>
          </div>
          <template #loading>
            <div class="reports-table">
              <ReportTableHeader></ReportTableHeader>
              <template v-for="i in 10" :key="i">
                <div
                  :class="{
                    'table-row': true,
                    report: true,
                  }"
                >
                  <n-skeleton
                    text
                    class="date"
                    style="height: 19.2px; width: 130px"
                  >
                  </n-skeleton>
                  <div
                    class="symptom"
                    v-for="symptom of Object.keys(config.symptoms)"
                    :key="symptom"
                  >
                    <circle-progress
                      :percent="0"
                      :color="config.symptoms[symptom].color"
                      :id="symptom"
                      style="width: 50px"
                      :visible="config.symptoms[symptom].likert"
                    >
                      <Dot loading />
                    </circle-progress>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </Loading>
      </ColoredCard>
    </div>
    <div class="col" style="flex: 1 1 250px">
      <router-view v-slot="{ Component }">
        <component :is="Component" ref="right" />
      </router-view>
    </div>
  </div>
</template>

<style scoped lang="scss">
.row {
  flex-grow: 1;
  .col {
    min-width: 0;
    flex-grow: 1;
    display: flex;
    height: 100%;
    flex-direction: column;
    row-gap: 8px;
  }
  overflow-x: hidden;
}

.participant-id {
  font-size: 16px;
  line-height: 30px;
  font-weight: 700;
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
.demographic {
  margin: 10px 0px;
}
.patient-details {
  .box {
    max-height: 100px;
    overflow: overlay;
  }
}
.key-question {
  min-height: 0px;
  flex-grow: 1;
  max-width: 100%;
  :deep(.n-card__content) {
    max-width: 100%;
    min-width: 0;
    overflow-x: overlay;
  }
}
.information {
  flex: 0 0 210px;
  min-height: 0;
  :deep(.n-card__content) {
    overflow: overlay;
  }
}
</style>
