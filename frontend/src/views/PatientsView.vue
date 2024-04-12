<script setup lang="ts">
import ColoredCard from "@/components/ColoredCard.vue";

const patients = [
  {
    id: 1,
    age: 44,
    gender: "male",
    EHR_id: "U82-19",
    alexa_user_id: "42253d34-a9d4-4185-a2d5-919e742bf0aa",
    medical_history: "",
    medication: "Experience know its executive three.",
    participant_id: "1",
    state: 2,
  },
  {
    id: 2,
    age: 47,
    gender: "female",
    EHR_id: "K76-47",
    alexa_user_id: "726e8756-c424-4be0-aef8-ebb0ddc0fbf6",
    medical_history: "",
    medication: "Traditional board agree there season without.",
    participant_id: "2",
    state: 3,
  },
  {
    id: 3,
    age: 66,
    gender: "female",
    EHR_id: "K04-33",
    alexa_user_id: "1cd7b523-b9f4-41d0-b132-6b14b79c7259",
    medical_history: "",
    medication: "Top figure politics position.",
    participant_id: "3",
    state: 4,
  },
  {
    id: 4,
    age: 46,
    gender: "male",
    EHR_id: "R55-62",
    alexa_user_id: "8e42a778-00ba-4859-b2f3-0d11ab884efc",
    medical_history: "",
    medication: "After world serve professional cost.",
    participant_id: "4",
    state: 1,
  },
  {
    id: 5,
    age: 31,
    gender: "female",
    EHR_id: "C05-53",
    alexa_user_id: "f4058dad-b3e4-4b57-b36a-30bbb54c6b75",
    medical_history: "",
    medication: "Behavior rule contain down walk scientist allow.",
    participant_id: "5",
    state: 4,
  },
  {
    id: 6,
    age: 73,
    gender: "female",
    EHR_id: "B06-92",
    alexa_user_id: "7c2045eb-6993-43da-a82d-be5d0271edea",
    medical_history: "",
    medication: "Provide establish form first recently than.",
    participant_id: "6",
    state: 4,
  },
  {
    id: 7,
    age: 41,
    gender: "male",
    EHR_id: "L51-13",
    alexa_user_id: "3fbcf8a2-dd73-4b1b-a5aa-143ff8046990",
    medical_history: "",
    medication: "Grow heart even recognize.",
    participant_id: "7",
    state: 2,
  },
  {
    id: 8,
    age: 89,
    gender: "male",
    EHR_id: "N28-73",
    alexa_user_id: "ccd7834e-3ad1-4c82-b076-b34521db0081",
    medical_history: "",
    medication: "Report short resource.",
    participant_id: "8",
    state: 0,
  },
  {
    id: 9,
    age: 83,
    gender: "female",
    EHR_id: "H54-70",
    alexa_user_id: "aa89ef93-1470-4df5-96bd-10e2b3ae6890",
    medical_history: "",
    medication: "Teach those country product population.",
    participant_id: "9",
    state: 3,
  },
  {
    id: 10,
    age: 71,
    gender: "male",
    EHR_id: "P94-32",
    alexa_user_id: "e729f3f0-cb5a-44d0-802f-19a62d00ed77",
    medical_history: "",
    medication: "Prove factor college chair with moment speak.",
    participant_id: "10",
    state: 2,
  },
  {
    id: 11,
    age: 80,
    gender: "male",
    EHR_id: "Y66-77",
    alexa_user_id: "73422278-82f8-4341-86ea-c49ccf1a1a47",
    medical_history: "",
    medication: "Understand statement turn off suddenly.",
    participant_id: "11",
    state: 3,
  },
  {
    id: 12,
    age: 43,
    gender: "male",
    EHR_id: "B49-90",
    alexa_user_id: "504aed66-25eb-40f9-915f-5c56d3efd471",
    medical_history: "",
    medication: "Sometimes during service.",
    participant_id: "12",
    state: 1,
  },
  {
    id: 13,
    age: 52,
    gender: "female",
    EHR_id: "V97-44",
    alexa_user_id: "0ca1fa4d-4868-4d35-8c67-5b7f7a0d2042",
    medical_history: "",
    medication: "Look door more however growth tonight.",
    participant_id: "13",
    state: 0,
  },
  {
    id: 14,
    age: 18,
    gender: "male",
    EHR_id: "X37-47",
    alexa_user_id: "0e93e811-02eb-4bd1-b1ef-8363670ff516",
    medical_history: "",
    medication: "Very American number success season part writer toward.",
    participant_id: "14",
    state: 2,
  },
  {
    id: 15,
    age: 63,
    gender: "male",
    EHR_id: "Y70-68",
    alexa_user_id: "4d146a14-a0fb-4d61-9dda-4cc31c54a612",
    medical_history: "",
    medication: "Store anything color head less relationship lay indeed.",
    participant_id: "15",
    state: 0,
  },
];
</script>
<template>
  <div class="row holder">
    <n-card class="patient-list" title="Patients List">
      <router-link
        v-for="p in patients"
        :key="p.id"
        :to="{
          name: 'patient.detail',
          params: { id: p.id },
        }"
      >
        <div class="patient-card">
          <div
            class="dot"
            :style="{
              '--color': [
                '#c1b9b6',
                '#4ca851',
                '#6283ac',
                '#f9d965',
                '#eb4c44',
              ][p['state']],
            }"
          ></div>
          <div class="patient-info">
            <div class="name">Patient {{ p.participant_id }}</div>
            <div class="age-sex">{{ p.age }} years, {{ p.gender }}</div>
          </div>
        </div>
      </router-link>
    </n-card>
    <router-view></router-view>
  </div>
</template>
<style scoped lang="scss">
.holder {
  flex: 1;
  min-height: 0;
  margin: 0 8px 8px 8px;
}
.patient-list {
  width: 300px;
}
.n-card:deep(.n-card__content) {
  padding: 0;
  overflow: overlay;
}
.patient-card {
  height: 64px;
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #e6e6e6;
}
.dot {
  width: 48px;
  height: 64px;
  display: flex;
  justify-content: center;
  align-items: center;
  &::after {
    content: "";
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background-color: var(--color);
    border-color: gray;
  }
}
.patient-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  color: black;
  cursor: pointer;
  .name {
    font-size: 16px;
    font-weight: 500;
  }
}
a {
  text-decoration: none;
}
</style>
