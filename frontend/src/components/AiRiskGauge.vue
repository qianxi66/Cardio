<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useResizeObserver } from "@vueuse/core";

const props = defineProps<{
  value: number;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
const GAUGE_RADIUS = "128%";
const GAUGE_CENTER: [string, string] = ["50%", "80%"];

const clampValue = (value: number) => Math.max(0, Math.min(100, value));

const getActiveGradient = (value: number) => {
  const v = clampValue(value);
  if (v <= 33) {
    return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
      { offset: 0, color: "#5dbd6c" },
      { offset: 1, color: "#c2ba61" },
    ]);
  }
  if (v <= 66) {
    return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
      { offset: 0, color: "#c2ba61" },
      { offset: 1, color: "#fd9501" },
    ]);
  }
  return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
    { offset: 0, color: "#fd9501" },
    { offset: 1, color: "#ed0904" },
  ]);
};

const getValueColor = (value: number) => {
  const v = clampValue(value);
  if (v <= 33) return "#c2ba61";
  if (v <= 66) return "#fd9501";
  return "#ed0904";
};

const valueColor = computed(() => getValueColor(props.value));

const buildOption = (value: number): echarts.EChartsOption => {
  const ratio = clampValue(value) / 100;
  return {
    series: [
      {
        type: "gauge",
        startAngle: 180,
        endAngle: 0,
        min: 0,
        max: 100,
        radius: GAUGE_RADIUS,
        center: GAUGE_CENTER,
        axisLine: {
          lineStyle: {
            width: 34,
            color: [
              [ratio, getActiveGradient(value)],
              [1, "#f3f3f3"],
            ],
          },
        },
        pointer: {
          show: true,
          width: 4,
          length: "60%",
          itemStyle: { color: "#555B6B" },
        },
        anchor: {
          show: true,
          size: 8,
          itemStyle: { color: "#555B6B" },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: false },
        detail: { show: false },
        data: [{ value }],
      },
    ],
  };
};

const applyOption = () => {
  if (!chart) return;
  chart.setOption(buildOption(props.value), true);
};

onMounted(() => {
  if (!chartEl.value) return;
  chart = echarts.init(chartEl.value);
  applyOption();
});

watch(
  () => props.value,
  () => applyOption(),
);

useResizeObserver(chartEl, () => {
  chart?.resize();
  // Re-apply option on container resize/HMR to avoid stale gauge radius.
  applyOption();
});

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="ai-risk-gauge">
    <div class="ai-risk-gauge-chart" ref="chartEl"></div>
    <div class="ai-risk-gauge-value" :style="{ color: valueColor }">
      {{ clampValue(props.value) }}%
    </div>
  </div>
</template>

<style scoped lang="scss">
.ai-risk-gauge {
  width: 100%;
  height: 100%;
  min-height: 90px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
}
.ai-risk-gauge-chart {
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
}
.ai-risk-gauge-value {
  font-size: 20px;
  font-weight: 800;
}
</style>
