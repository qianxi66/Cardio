<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useResizeObserver } from "@vueuse/core";
import { getWearableTimeSeries, type WearableTimeSeries } from "@/api/patient";
import Loading from "@/components/Loading.vue";

const props = defineProps<{
  patientId?: number;
  range?: "24h" | "7d";
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let cleanupZrDrag: (() => void) | null = null;

const defaultTimes = [
  "0:00",
  "3:00",
  "6:00",
  "9:00",
  "12:00",
  "15:00",
  "18:00",
  "21:00",
  "24:00",
];
const times = ref<string[]>([...defaultTimes]);
const rangeValue = computed(() => props.range ?? "24h");
const seriesDefs = ref([
  {
    name: "Heart Rate",
    color: "#4bbfd1",
    data: [] as Array<number | null>,
    yAxisIndex: 0,
    lineType: "solid",
  },
  {
    name: "Respiration",
    color: "#ec48d3",
    data: [] as Array<number | null>,
    yAxisIndex: 1,
    lineType: "dashed",
  },
  {
    name: "SpO2",
    color: "#0fb54c",
    data: [] as Array<number | null>,
    yAxisIndex: 2,
    lineType: [14, 3, 2, 3],
  },
  {
    name: "Heart Rate Variability",
    color: "#705ddd",
    data: [] as Array<number | null>,
    yAxisIndex: 3,
    lineType: [14, 6],
    markLine: true,
  },
]);
const selected = ref<Record<string, boolean>>(
  Object.fromEntries(seriesDefs.value.map((item) => [item.name, true])),
);
const isLoading = ref(false);
const markerTime = ref<string>("21:00");
const markerPixel = ref<number | null>(null);
const isDragging = ref(false);

const normalizeSeriesLength = (data: Array<number | null>, size: number, fill: number | null) => {
  if (data.length === size) return data;
  if (data.length > size) return data.slice(0, size);
  return data.concat(Array.from({ length: size - data.length }, () => fill));
};

const buildDefaultTimes = (nextRange: "24h" | "7d") => {
  if (nextRange === "24h") {
    return [
      "0:00",
      "3:00",
      "6:00",
      "9:00",
      "12:00",
      "15:00",
      "18:00",
      "21:00",
      "24:00",
    ];
  }
  const labels: string[] = [];
  const now = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(now.getDate() - i);
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    labels.push(`${month}/${day}`);
  }
  return labels;
};

const applySeriesData = (payload?: WearableTimeSeries) => {
  const standardTimes = buildDefaultTimes(rangeValue.value);
  times.value = standardTimes;

  if (!payload) {
    seriesDefs.value.forEach((series) => {
      series.data = normalizeSeriesLength([], standardTimes.length, null);
    });
    applyOption();
    return;
  }

  const seriesMap: Record<string, Array<number | null>> = {
    "Heart Rate": payload.series?.heart_rate ?? [],
    Respiration: payload.series?.respiration ?? [],
    "Heart Rate Variability": payload.series?.heart_rate_variability ?? [],
  };

  seriesDefs.value.forEach((series) => {
    if (series.name in seriesMap) {
      const next = seriesMap[series.name] ?? [];
      series.data = normalizeSeriesLength(next, standardTimes.length, null);
      return;
    }
    if (series.name === "SpO2") {
      series.data = normalizeSeriesLength([], standardTimes.length, null);
    }
  });

  if (!times.value.includes(markerTime.value)) {
    markerTime.value =
      times.value[Math.max(0, times.value.length - 2)] || times.value[0];
  }
  applyOption();
};

const fetchSeriesData = async (patientId?: number) => {
  if (!patientId) {
    applySeriesData();
    return;
  }
  isLoading.value = true;
  try {
    const data = await getWearableTimeSeries(patientId, rangeValue.value);
    applySeriesData(data);
  } catch (error) {
    console.error("Failed to fetch wearable series data", error);
    applySeriesData();
  } finally {
    isLoading.value = false;
  }
};

const formatXAxisLabel = (value: string) => {
  if (rangeValue.value === "7d") {
    if (!value.includes(" ")) {
      return value;
    }
    if (value.endsWith("00:00")) {
      return value.split(" ")[0];
    }
    return "";
  }
  return value;
};

const parseTimeLabel = (value: string) => {
  const timePart = value.includes(" ") ? value.split(" ")[1] : value;
  if (!timePart.includes(":")) return null;
  const [hourText, minuteText] = timePart.split(":");
  const hour = Number(hourText);
  const minute = Number(minuteText);
  if (Number.isNaN(hour) || Number.isNaN(minute)) return null;
  return { hour, minute };
};

const shouldShowLabel = (value: string) => {
  return true;
};

const updateMarkerFromPixel = (centerX: number) => {
  if (!chart) return;
  const raw = chart.convertFromPixel({ xAxisIndex: 0 }, centerX);
  let next = markerTime.value;
  if (typeof raw === "number") {
    const idx = Math.max(0, Math.min(times.value.length - 1, Math.round(raw)));
    next = times.value[idx];
  } else if (typeof raw === "string") {
    next = raw;
  }
  if (next !== markerTime.value) {
    markerTime.value = next;
  }
  updateMarkerGraphic();
};

const clampToGrid = (x: number, grid: { x: number; y: number; width: number; height: number }) =>
  Math.min(grid.x + grid.width, Math.max(grid.x, x));

const getCenterXFromTarget = (target: any) => {
  if (!target) return undefined;
  const offsetX = typeof target.x === "number" ? target.x : 0;
  const shape = target.shape;
  if (shape && typeof shape.x1 === "number" && typeof shape.x2 === "number") {
    return (shape.x1 + shape.x2) / 2 + offsetX;
  }
  if (shape && typeof shape.x === "number" && typeof shape.width === "number") {
    return shape.x + shape.width / 2 + offsetX;
  }
  if (typeof target.x === "number") return target.x;
  return undefined;
};

const getGridRect = () =>
  (chart as any).getModel().getComponent("grid").coordinateSystem.getRect();

const getLegendDashArray = (lineType: any) => {
  if (Array.isArray(lineType)) return lineType.join(" ");
  if (lineType === "dashed") return "6 6";
  return undefined;
};

const getXAxisAxisLabel = () => ({
  rotate: 45,
  fontSize: 12.5,
  fontFamily: "Arial Black",
  interval: 0,
  formatter: (value: string) => {
    const label = formatXAxisLabel(value);
    if (!label) return "";
    return value === markerTime.value ? `{active|${label}}` : `{normal|${label}}`;
  },
  rich: {
    active: {
      color: "#000000",
      fontWeight: "bold",
      fontSize: 12.5,
      fontFamily: "Arial Black",
    },
    normal: {
      color: "#808080",
      fontWeight: "bold",
      fontSize: 12.5,
      fontFamily: "Arial Black",
    },
  },
});

const buildOption = (): echarts.EChartsOption => ({
  grid: { left: 0, right: 20, top: 20, bottom: 20, containLabel: true },
  tooltip: { trigger: "axis" },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: times.value,
    name: "Time",
    nameLocation: "middle",
    nameGap: 50,
    nameTextStyle: {
      color: "#000000",
      fontSize: 13,
      fontFamily: "system-ui",
      fontWeight: 1000,
    },
    axisLabel: {
      ...getXAxisAxisLabel(),
      margin: 12,
      lineHeight: 16,
    },
    axisTick: { show: false },
    axisLine: { show: true, lineStyle: { color: "#000000", width: 2 } },
  },
  yAxis: [
    {
      type: "value",
      position: "left",
      min: 0,
      max: 150,
      interval: 50,
      axisLabel: {
        color: "#4bbfd1",
        fontWeight: "bold",
        formatter: (value: number) => (value === 0 ? `${value}\n(bpm)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#4bbfd1", width: 2 } },
      axisTick: { show: false },
    },
    {
      type: "value",
      position: "left",
      offset: 40,
      min: 5,
      max: 20,
      interval: 5,
      axisLabel: {
        color: "#ec48d3",
        fontWeight: "bold",
        formatter: (value: number) => (value === 5 ? `${value}\n(bpm)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#ec48d3", width: 2 } },
      axisTick: { show: false },
    },
    {
      type: "value",
      position: "right",
      min: 94,
      max: 100,
      interval: 2,
      axisLabel: {
        formatter: (value: number) => `${value}\n%`,
        color: "#0fb54c",
        fontWeight: "bold",
      },
      axisLine: { show: true, lineStyle: { color: "#0fb54c", width: 2 } },
      axisTick: { show: false },
    },
    {
      type: "value",
      position: "right",
      offset: 40,
      min: 0,
      max: 150,
      interval: 50,
      axisLabel: {
        color: "#705ddd",
        fontWeight: "bold",
        formatter: (value: number) => (value === 0 ? `${value}\n(ms)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#705ddd", width: 2 } },
      axisTick: { show: false },
    },
  ],
  series: seriesDefs.value.map((series) => {
    const isActive = selected.value[series.name];
    return {
      name: series.name,
      type: "line",
      yAxisIndex: series.yAxisIndex,
      data: isActive ? series.data : [],
      smooth: true,
      connectNulls: false,
      showSymbol: false,
      symbol: "none",
      symbolSize: 0,
      lineStyle: {
        color: series.color,
        type: series.lineType as any,
      },
      itemStyle: { color: series.color },
      markLine: undefined,
    };
  }),
});

const applyOption = () => {
  chart?.setOption(buildOption(), true);
  updateMarkerGraphic();
};

const toggleSeries = (name: string) => {
  selected.value[name] = !selected.value[name];
  applyOption();
};

const updateMarkerGraphic = () => {
  if (!chart) return;
  const grid = getGridRect();
  const baseXValue = chart.convertToPixel({ xAxisIndex: 0 }, markerTime.value) as
    | number
    | undefined;
  const xValue =
    typeof markerPixel.value === "number"
      ? clampToGrid(markerPixel.value, grid)
      : baseXValue;
  if (typeof xValue !== "number") return;
  chart.setOption(
    {
      xAxis: {
        axisLabel: getXAxisAxisLabel(),
      },
      graphic: [
        {
          id: "marker-hitbox",
          type: "rect",
          silent: true,
          cursor: "ew-resize",
          shape: {
            x: xValue - 6,
            y: grid.y,
            width: 12,
            height: grid.height,
          },
          style: {
            fill: "#705ddd",
            opacity: 0,
          },
          z: 9,
        },
        {
          id: "marker-line",
          type: "line",
          silent: true,
          shape: {
            x1: xValue,
            y1: grid.y,
            x2: xValue,
            y2: grid.y + grid.height,
          },
          style: {
            stroke: "#705ddd",
            lineWidth: 1,
            lineDash: [4, 4],
          },
          z: 10,
        },
      ],
    },
    false,
  );
};

const bindDragEvents = () => {
  if (!chart) return;
  const zr = chart.getZr();
  const threshold = 8;

  const handleMouseDown = (evt: any) => {
    if (!chart) return;
    const grid = getGridRect();
    const xValue = chart.convertToPixel({ xAxisIndex: 0 }, markerTime.value) as
      | number
      | undefined;
    if (typeof xValue !== "number") return;
    const offsetX = evt?.offsetX;
    const offsetY = evt?.offsetY;
    if (typeof offsetX !== "number" || typeof offsetY !== "number") return;
    const withinY = offsetY >= grid.y && offsetY <= grid.y + grid.height;
    const nearLine = Math.abs(offsetX - xValue) <= threshold;
    if (!withinY || !nearLine) return;
    isDragging.value = true;
    markerPixel.value = clampToGrid(offsetX, grid);
    updateMarkerGraphic();
  };

  const handleMouseMove = (evt: any) => {
    if (!chart || !isDragging.value) return;
    const grid = getGridRect();
    const offsetX = evt?.offsetX;
    if (typeof offsetX !== "number") return;
    markerPixel.value = clampToGrid(offsetX, grid);
    updateMarkerGraphic();
  };

  const handleMouseUp = (evt: any) => {
    if (!chart || !isDragging.value) return;
    const grid = getGridRect();
    const offsetX = evt?.offsetX;
    if (typeof offsetX !== "number") return;
    isDragging.value = false;
    markerPixel.value = null;
    updateMarkerFromPixel(clampToGrid(offsetX, grid));
  };

  zr.on("mousedown", handleMouseDown);
  zr.on("mousemove", handleMouseMove);
  zr.on("mouseup", handleMouseUp);
  zr.on("globalout", handleMouseUp);

  cleanupZrDrag = () => {
    zr.off("mousedown", handleMouseDown);
    zr.off("mousemove", handleMouseMove);
    zr.off("mouseup", handleMouseUp);
    zr.off("globalout", handleMouseUp);
  };
};

onMounted(() => {
  if (!chartEl.value) return;
  chart = echarts.init(chartEl.value);
  applyOption();
  bindDragEvents();
});

watch(
  () => props.patientId,
  (nextId) => {
    fetchSeriesData(nextId);
  },
  { immediate: true },
);

watch(
  () => props.range,
  () => {
    fetchSeriesData(props.patientId);
  },
  { immediate: false },
);

useResizeObserver(chartEl, () => {
  chart?.resize();
  updateMarkerGraphic();
});

onBeforeUnmount(() => {
  cleanupZrDrag?.();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="chart-wrapper">
    <div class="chart-legend">
      <button
        v-for="item in seriesDefs"
        :key="item.name"
        class="legend-item"
        :class="{ active: selected[item.name] }"
        @click="toggleSeries(item.name)"
      >
        <span class="legend-box" :style="{ '--color': item.color }"></span>
        <span class="legend-label" :style="{ color: item.color }">
          {{ item.name }}
        </span>
        <svg class="legend-line" viewBox="0 0 30 2" aria-hidden="true">
          <line
            x1="0"
            y1="1"
            x2="30"
            y2="1"
            :stroke="item.color"
            stroke-width="2"
            :stroke-dasharray="getLegendDashArray(item.lineType)"
          />
        </svg>
      </button>
    </div>
    <Loading :loading="isLoading" :has-data="true" :debounce-ms="150">
      <div class="chart" ref="chartEl"></div>
    </Loading>
  </div>
</template>

<style scoped lang="scss">
.chart-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  min-height: 220px;
}
.chart-legend {
  display: flex;
  flex-wrap: nowrap;
  justify-content: space-between;
  column-gap: 0;
  row-gap: 8px;
  margin-bottom: 8px;
  width: 100%;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
}
.legend-item:not(.active) {
  opacity: 0.5;
}
.legend-box {
  width: 12px;
  height: 12px;
  border: 2px solid var(--color);
  border-radius: 2px;
  position: relative;
  box-sizing: border-box;
}
.legend-item.active .legend-box {
  background-color: var(--color);
}
.legend-item.active .legend-box::after {
  content: "";
  position: absolute;
  width: 6px;
  height: 3px;
  border-left: 2px solid #fff;
  border-bottom: 2px solid #fff;
  transform: rotate(-45deg);
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) rotate(-45deg);
}
.legend-label {
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.legend-line {
  width: 30px;
  height: 8px;
  display: block;
}
.chart {
  flex: 1 1 0;
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>