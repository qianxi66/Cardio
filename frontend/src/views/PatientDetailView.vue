<script setup lang="ts">
import { useRouteParams } from "@vueuse/router";
import ColoredCard from "@/components/ColoredCard.vue";
import Dot from "@/components/Dot.vue";
import records from "@/data/records.json";
import patients from "@/data/patients.json";
import * as config from "@/config";
import { computed } from "vue";

const id = useRouteParams("patient_id");
const patient = computed(() => patients.find((p) => p.id === +id.value!)!);
</script>
<template>
  <div class="row">
    <div class="col" style="flex: 400px 1 1">
      <ColoredCard>
        <div class="participant-id">Patient {{ patient.participant_id }}</div>
        <div class="row demographic">
          <span class="age-sex">
            <b>{{ patient.age }} y.o.</b> {{ patient.gender }}
          </span>
          <span>
            {{ patient.EHR_id }}
          </span>
        </div>
        <div class="row patient-details">
          <div class="box">
            <div class="row">
              <div class="title">Medical History</div>
              <div class="space"></div>
              <div>Last Visit: 08/01/2002</div>
            </div>
            <p>1. Hypertension</p>
            <p>2. Diabetes</p>
            <p>3. Hyperlipidemia</p>
          </div>
          <div class="box">
            <div class="row">
              <div class="title">Medication</div>
            </div>
            <p>1. Lisinopril 10mg</p>
          </div>
        </div>
      </ColoredCard>
      <ColoredCard
        class="key-question"
        title="Key Question Overview"
        color="#4a239c"
        rounded
        style="flex: 1 1 400px"
      >
        <div class="records-table">
          <div class="table-row header">
            <div class="date">Date & Time (EST)</div>
            <div
              class="symptom"
              v-for="symptom of Object.keys(config.symptoms)"
              :key="symptom"
            >
              <n-tooltip trigger="hover">
                <template #trigger>
                  {{ symptom[0].toUpperCase() + symptom.slice(1) }}
                </template>
                <div>{{ config.symptoms[symptom].description }}</div>
              </n-tooltip>
            </div>
          </div>
          <div
            class="table-row record"
            v-for="record in records"
            :key="record.id"
          >
            <div class="date">{{ record.updated_at }}</div>
            <div
              class="symptom"
              v-for="symptom of Object.keys(config.symptoms)"
              :key="symptom"
            >
              <Dot
                :state="record[symptom]"
                @click="
                  $router.push({
                    name: 'patient.record.detail',
                    params: { patient_id: patient.id, record_id: record.id },
                  })
                "
              />
            </div>
          </div>
        </div>
      </ColoredCard>
    </div>
    <div class="col" style="flex: 0.5 1 100px">
      <router-view></router-view>
    </div>
  </div>
</template>
<style scoped lang="scss">
.row {
  flex-grow: 1;
  .col {
    flex-grow: 1;
    display: flex;
    height: 100%;
    flex-direction: column;
    row-gap: 8px;
  }
}
.participant-id {
  font-size: 16px;
  font-weight: 700;
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
  flex-shrink: 1;
  :deep(.n-card__content) {
    overflow: overlay;
  }
}
.records-table {
  width: 100%;
  .table-row {
    width: 100%;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    height: 48px;
    font-size: 12px;
    &.header {
      font-weight: 700;
      border-bottom: 1px solid #e6e6e6;
    }
    .date {
      flex: 0 0 130px;
    }
    .symptom {
      flex: 1 0 50px;
      display: flex;
      justify-content: center;
    }
    &:hover {
      outline: 1px solid #e6e6e6;
    }
.dot:hover {
  box-shadow: 0px 0px 8px 4px rgba(0, 0, 0, 0.2); /* More visible shadow */
  cursor: pointer;
  transform: scale(1.2); /* Slightly larger scale */
  animation: float .5s ease-in-out infinite;
}

/* Adjusted floating effect for smaller movement due to size */
@keyframes float {
  0%, 100% {
    transform: translateY(0) scale(1.2);
  }
  50% {
    transform: translateY(-3px) scale(1.2);
  }
}

  }
}
</style>
