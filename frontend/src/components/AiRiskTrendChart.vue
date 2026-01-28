<script setup lang="ts">
import * as echarts from "echarts";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useResizeObserver } from "@vueuse/core";

const wrapperEl = ref<HTMLDivElement | null>(null);
const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
const markerIndex = ref(20);
const isDragging = ref(false);

const dates = [
  "04 Jun",
  "05 Jun",
  "06 Jun",
  "07 Jun",
  "08 Jun",
  "09 Jun",
  "10 Jun",
  "11 Jun",
  "12 Jun",
  "13 Jun",
  "14 Jun",
  "15 Jun",
  "16 Jun",
  "17 Jun",
  "18 Jun",
  "19 Jun",
  "20 Jun",
  "21 Jun",
  "22 Jun",
  "23 Jun",
  "24 Jun",
];

const riskData = [
  18, 19, 20, 21, 22, 25, 28, 31, 33, 35, 38, 40, 42, 45, 48, 52, 55, 58, 62, 66, 70,
];

const getGridRect = () =>
  (chart as any).getModel().getComponent("grid").coordinateSystem.getRect();

const buildOption = (): echarts.EChartsOption => ({
  grid: { left: 24, right: 24, top: 20, bottom: 10, containLabel: true },
  xAxis: {
    type: "category",
    data: dates,
    axisTick: { show: false },
    axisLine: {
      show: true,
      lineStyle: { color: "#111", width: 2 },
      symbol: ["none", "arrow"],
      symbolSize: [8, 12],
    },
    axisLabel: { color: "#777", fontWeight: "bold", interval: 4 },
    boundaryGap: false,
  },
  yAxis: {
    type: "value",
    min: 0,
    max: 100,
    interval: 20,
    name: "Risk",
    nameLocation: "middle",
    nameGap: 34,
    nameTextStyle: { fontSize: 14, fontWeight: "bold", color: "#111" },
    axisLabel: {
      formatter: (value: number) => (value === 100 ? "100%" : ""),
      color: "#777",
      fontWeight: "bold",
    },
    splitLine: { lineStyle: { color: "#ddd", type: "dashed" } },
    axisLine: {
      show: true,
      lineStyle: { color: "#111", width: 2 },
      symbol: ["none", "arrow"],
      symbolSize: [8, 12],
    },
    axisTick: { show: false },
  },
  series: [
    {
      type: "line",
      data: riskData,
      smooth: true,
      showSymbol: false,
      lineStyle: {
        width: 3,
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: "#5dbd6c" },
          { offset: 0.33, color: "#c2ba61" },
          { offset: 0.66, color: "#fd9501" },
          { offset: 1, color: "#ed0904" },
        ]),
      },
    },
  ],
});

const applyOption = () => {
  if (!chart) return;
  chart.setOption(buildOption(), true);
  updateMarkerGraphic();
};

const updateMarkerGraphic = () => {
  if (!chart) return;
  const grid = getGridRect();
  const date = dates[markerIndex.value];
  const value = riskData[markerIndex.value];
  const xValue = chart.convertToPixel({ xAxisIndex: 0 }, date) as number;
  if (typeof xValue !== "number") return;
  chart.setOption(
    {
      graphic: [
        {
          id: "risk-hitbox",
          type: "rect",
          silent: true,
          shape: { x: xValue - 6, y: grid.y, width: 12, height: grid.height },
          style: { fill: "#ed0904", opacity: 0 },
          z: 8,
        },
        {
          id: "risk-line",
          type: "line",
          silent: true,
          shape: {
            x1: xValue,
            y1: grid.y,
            x2: xValue,
            y2: grid.y + grid.height,
          },
          style: {
            stroke: "#ed0904",
            lineWidth: 2,
            lineDash: [4, 4],
          },
          z: 9,
        },
        {
          id: "risk-label",
          type: "text",
          silent: true,
          x: xValue,
          y: grid.y - 6,
          style: {
            text: `${value}%`,
            fill: "#ed0904",
            fontWeight: "bold",
            fontSize: 12,
            align: "center",
            verticalAlign: "bottom",
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
    const date = dates[markerIndex.value];
    const xValue = chart.convertToPixel({ xAxisIndex: 0 }, date) as number;
    if (typeof xValue !== "number") return;
    const offsetX = evt?.offsetX;
    const offsetY = evt?.offsetY;
    if (typeof offsetX !== "number" || typeof offsetY !== "number") return;
    const withinY = offsetY >= grid.y && offsetY <= grid.y + grid.height;
    const nearLine = Math.abs(offsetX - xValue) <= threshold;
    if (!withinY || !nearLine) return;
    isDragging.value = true;
  };

  const handleMouseMove = (evt: any) => {
    if (!chart || !isDragging.value) return;
    const offsetX = evt?.offsetX;
    if (typeof offsetX !== "number") return;
    const raw = chart.convertFromPixel({ xAxisIndex: 0 }, offsetX);
    if (typeof raw === "number") {
      const idx = Math.max(0, Math.min(dates.length - 1, Math.round(raw)));
      if (idx !== markerIndex.value) {
        markerIndex.value = idx;
        updateMarkerGraphic();
      }
    }
  };

  const handleMouseUp = () => {
    isDragging.value = false;
  };

  zr.on("mousedown", handleMouseDown);
  zr.on("mousemove", handleMouseMove);
  zr.on("mouseup", handleMouseUp);
  zr.on("globalout", handleMouseUp);
};

onMounted(() => {
  if (!chartEl.value) return;
  chart = echarts.init(chartEl.value);
  applyOption();
  bindDragEvents();
  const handleResize = () => {
    chart?.resize();
    updateMarkerGraphic();
  };
  window.addEventListener("resize", handleResize);
  onBeforeUnmount(() => {
    window.removeEventListener("resize", handleResize);
  });
});

useResizeObserver(wrapperEl, () => {
  chart?.resize();
  updateMarkerGraphic();
});

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="ai-risk-chart" ref="wrapperEl">
    <div class="ai-risk-chart-body" ref="chartEl"></div>
    <div class="ai-risk-chart-title">Days Since 1st Treatment</div>
  </div>
</template>

<style scoped lang="scss">
.ai-risk-chart {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  min-width: 0;
  width: 100%;
}
.ai-risk-chart-title {
  font-size: 14px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 8px;
}
.ai-risk-chart-body {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
}
</style>
