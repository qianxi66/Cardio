<script setup lang="ts">
import * as config from "@/config";
</script>
<template>
  <div class="table-row header">
    <div class="date">Date & Time (EST)</div>
    <div
      class="symptom"
      v-for="symptom of Object.keys(config.symptoms)"
      :key="symptom"
    >
      {{ config.symptoms[symptom].display_name }}
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-icon>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              xmlns:xlink="http://www.w3.org/1999/xlink"
              viewBox="0 0 32 32"
            >
              <path
                d="M17 22v-8h-4v2h2v6h-3v2h8v-2h-3z"
                fill="currentColor"
              ></path>
              <path
                d="M16 8a1.5 1.5 0 1 0 1.5 1.5A1.5 1.5 0 0 0 16 8z"
                fill="currentColor"
              ></path>
              <path
                d="M16 30a14 14 0 1 1 14-14a14 14 0 0 1-14 14zm0-26a12 12 0 1 0 12 12A12 12 0 0 0 16 4z"
                fill="currentColor"
              ></path>
            </svg>
          </n-icon>
        </template>
        <div>{{ config.symptoms[symptom].description }}</div>
      </n-tooltip>
    </div>
  </div>
</template>
