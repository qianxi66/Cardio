<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useResizeObserver } from "@vueuse/core";
import { getWearableTimeSeries, type WearableTimeSeries } from "@/api/patient";
import Loading from "@/components/Loading.vue";

const props = withDefaults(
  defineProps<{
    patientId?: number;
    range?: "24h" | "7d";
    showLegend?: boolean;
    selectedSeries?: Record<string, boolean>;
  }>(),
  {
    showLegend: true,
  },
);
const emit = defineEmits<{
  (e: "toggle-series", name: string): void;
}>();

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let cleanupZrDrag: (() => void) | null = null;
let cleanupWindowResize: (() => void) | null = null;

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
const windowRef = ref<{ start_ts: number; end_ts: number } | null>(null);
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
    lineType: "solid",
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
    lineType: "solid",
    markLine: true,
  },
]);
const selected = ref<Record<string, boolean>>(
  Object.fromEntries(seriesDefs.value.map((item) => [item.name, true])),
);
const getSeriesSelected = (name: string) => {
  if (props.selectedSeries && name in props.selectedSeries) {
    return !!props.selectedSeries[name];
  }
  return !!selected.value[name];
};
const isLoading = ref(false);
const markerTime = ref<string>("21:00");
const markerPixel = ref<number | null>(null);
const isDragging = ref(false);
const useCurrentTimeMarker = ref(true);
const denseSlotEpochs = ref<number[]>([]);
const axisEndHour = ref(0);
const markerIdx = ref(0);
let nowMarkerInterval: ReturnType<typeof setInterval> | null = null;

const normalizeSeriesLength = (data: Array<number | null>, size: number, fill: number | null) => {
  if (data.length === size) return data;
  if (data.length > size) return data.slice(0, size);
  return data.concat(Array.from({ length: size - data.length }, () => fill));
};

const timeToMinutes = (label: string): number => {
  const part = label.includes(" ") ? label.split(" ")[1] : label;
  if (!part?.includes(":")) return 0;
  const [h, m] = part.split(":").map(Number);
  return (Number.isNaN(h) ? 0 : h) * 60 + (Number.isNaN(m) ? 0 : m);
};

const mapBackendDataToStandardSlots = (
  backendTimes: string[],
  backendValues: Array<number | null>,
  standardTimes: string[],
  slotMinutes: number,
): Array<number | null> => {
  if (!backendTimes.length || !standardTimes.length) {
    return standardTimes.map(() => null);
  }
  return standardTimes.map((_slotLabel, slotIndex) => {
    const slotStart = slotIndex * slotMinutes;
    const slotEnd =
      slotIndex === standardTimes.length - 1 ? 24 * 60 : slotStart + slotMinutes;
    const values: number[] = [];
    backendTimes.forEach((t, i) => {
      const min = timeToMinutes(t);
      if (min >= slotStart && min < slotEnd) {
        const v = backendValues[i];
        if (v !== null && v !== undefined && Number.isFinite(v)) values.push(v);
      }
    });
    if (values.length === 0) return null;
    return values.reduce((a, b) => a + b, 0) / values.length;
  });
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

const buildDense24hTimes = () => {
  const now = new Date();
  const endDate = new Date(now);
  endDate.setMinutes(0, 0, 0);
  if (now.getMinutes() > 0 || now.getSeconds() > 0 || now.getMilliseconds() > 0) {
    endDate.setHours(endDate.getHours() + 1);
  }
  axisEndHour.value = endDate.getHours();
  const startDate = new Date(endDate.getTime() - 24 * 60 * 60 * 1000);
  const labels: string[] = [];
  const epochs: number[] = [];
  for (let ms = startDate.getTime(); ms <= endDate.getTime(); ms += 5 * 60 * 1000) {
    const d = new Date(ms);
    labels.push(`${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`);
    epochs.push(Math.floor(ms / 1000));
  }
  denseSlotEpochs.value = epochs;
  return labels;
};

const mapBackendDataToDense24h = (
  backendTimes: string[],
  backendValues: Array<number | null>,
  win: { start_ts: number; end_ts: number } | null,
) => {
  const epochs = denseSlotEpochs.value;
  const out: Array<number | null> = Array.from({ length: epochs.length }, () => null);
  if (!backendTimes.length || epochs.length === 0 || !win) return out;

  const startEpoch = epochs[0];
  const winStartDate = new Date(win.start_ts * 1000);
  let dayBase = Math.floor(
    new Date(winStartDate.getFullYear(), winStartDate.getMonth(), winStartDate.getDate()).getTime() / 1000,
  );
  let prevMinOfDay = -1;

  backendTimes.forEach((t, idx) => {
    const value = backendValues[idx];
    if (value === null || value === undefined || !Number.isFinite(value)) return;
    const timePart = t.includes(" ") ? t.split(" ")[1] : t;
    if (!timePart || !timePart.includes(":")) return;
    const [hStr, mStr] = timePart.split(":");
    const h = Number(hStr);
    const m = Number(mStr);
    if (Number.isNaN(h) || Number.isNaN(m)) return;
    const minOfDay = h * 60 + m;
    if (prevMinOfDay >= 0 && minOfDay < prevMinOfDay - 60) {
      dayBase += 86400;
    }
    prevMinOfDay = minOfDay;
    const epoch = dayBase + h * 3600 + m * 60;
    const slotIdx = Math.round((epoch - startEpoch) / 300);
    if (slotIdx >= 0 && slotIdx < out.length) {
      out[slotIdx] = value;
    }
  });
  return out;
};

const mapBackendDataToDateSlots = (
  backendTimes: string[],
  backendValues: Array<number | null>,
  standardTimes: string[],
) => {
  if (!backendTimes.length || !standardTimes.length) {
    return standardTimes.map(() => null);
  }

  return standardTimes.map((dayLabel) => {
    const values: number[] = [];
    backendTimes.forEach((t, i) => {
      const day = t.includes(" ") ? t.split(" ")[0] : t;
      if (day !== dayLabel) return;
      const v = backendValues[i];
      if (v !== null && v !== undefined && Number.isFinite(v)) {
        values.push(v);
      }
    });
    if (values.length === 0) return null;
    return values.reduce((a, b) => a + b, 0) / values.length;
  });
};

const roundSeriesValue = (seriesName: string, value: number | null): number | null => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return null;
  }
  if (seriesName === "Heart Rate") {
    return Math.round(value);
  }
  return Math.round(value * 10) / 10;
};

const roundSeriesData = (seriesName: string, data: Array<number | null>) =>
  data.map((value) => roundSeriesValue(seriesName, value));

const applySeriesData = (payload?: WearableTimeSeries) => {
  windowRef.value = payload?.window ?? null;

  const standardTimes = buildDefaultTimes(rangeValue.value);
  const useDense24h = rangeValue.value === "24h";
  const useDense7d = rangeValue.value === "7d";
  const denseTimes = useDense24h ? buildDense24hTimes() : standardTimes;
  times.value = useDense24h ? denseTimes : standardTimes;

  if (!payload) {
    seriesDefs.value.forEach((series) => {
      series.data = normalizeSeriesLength([], times.value.length, null);
    });
    applyOption();
    return;
  }

  const backendTimes = payload.times ?? [];
  if (useDense7d && backendTimes.length > 0) {
    // Keep 7d series dense (backend 3h points), while axis labels stay sparse via formatter.
    times.value = backendTimes;
  }
  const seriesMap: Record<string, Array<number | null>> = {
    "Heart Rate": payload.series?.heart_rate ?? [],
    Respiration: payload.series?.respiration ?? [],
    "Heart Rate Variability": payload.series?.heart_rate_variability ?? [],
  };

  seriesDefs.value.forEach((series) => {
    if (series.name in seriesMap) {
      const raw = seriesMap[series.name] ?? [];
      if (useDense24h) {
        const mapped =
          backendTimes.length > 0
            ? mapBackendDataToDense24h(backendTimes, raw, windowRef.value)
            : normalizeSeriesLength([], denseTimes.length, null);
        series.data = roundSeriesData(series.name, mapped);
      } else if (useDense7d) {
        const mapped =
          backendTimes.length > 0
            ? normalizeSeriesLength(raw, times.value.length, null)
            : normalizeSeriesLength([], times.value.length, null);
        series.data = roundSeriesData(series.name, mapped);
      } else {
        const mapped =
          backendTimes.length > 0
            ? mapBackendDataToDateSlots(backendTimes, raw, standardTimes)
            : normalizeSeriesLength([], standardTimes.length, null);
        series.data = roundSeriesData(series.name, mapped);
      }
      return;
    }
    if (series.name === "SpO2") {
      series.data = normalizeSeriesLength([], times.value.length, null);
    }
  });

  useCurrentTimeMarker.value = true;
  if (windowRef.value && times.value.length > 0) {
    updateMarkerToCurrentTime();
  } else {
    const foundIdx = times.value.indexOf(markerTime.value);
    markerIdx.value = foundIdx >= 0 ? foundIdx : Math.max(0, times.value.length - 2);
    markerTime.value = times.value[markerIdx.value] || times.value[0];
  }
  applyOption();
};

const getBinSeconds = () => {
  const len = times.value.length;
  if (!windowRef.value || len <= 1) return 1800;
  if (rangeValue.value === "24h" && len > 12) return 300;
  return Math.round((windowRef.value.end_ts - windowRef.value.start_ts) / Math.max(1, len - 1));
};

const updateMarkerToCurrentTime = () => {
  const win = windowRef.value;
  if (!win || times.value.length === 0) return;
  if (rangeValue.value === "24h" && denseSlotEpochs.value.length > 0) {
    const nowEpoch = Math.floor(Date.now() / 1000);
    const startEpoch = denseSlotEpochs.value[0];
    const slotIdx = Math.round((nowEpoch - startEpoch) / 300);
    const clampedIdx = Math.max(0, Math.min(times.value.length - 1, slotIdx));
    markerIdx.value = clampedIdx;
    markerTime.value = times.value[clampedIdx];
    return;
  }
  const now = Math.floor(Date.now() / 1000);
  const binSeconds = getBinSeconds();
  const span = win.end_ts - win.start_ts;
  if (span <= 0) return;
  const index = (now - win.start_ts) / binSeconds;
  const clampedIndex = Math.max(0, Math.min(times.value.length - 1, Math.floor(index)));
  markerIdx.value = clampedIndex;
  markerTime.value = times.value[clampedIndex];
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

const resetChartForRange = () => {
  windowRef.value = null;
  const nextTimes = rangeValue.value === "24h" ? buildDense24hTimes() : buildDefaultTimes(rangeValue.value);
  times.value = nextTimes;
  seriesDefs.value.forEach((series) => {
    series.data = normalizeSeriesLength([], nextTimes.length, null);
  });
  markerIdx.value = Math.max(0, Math.min(nextTimes.length - 1, markerIdx.value));
  markerTime.value = nextTimes[markerIdx.value] || nextTimes[0] || "0:00";
  applyOption();
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
  if (rangeValue.value === "24h" && times.value.length > 12) {
    return isLabeledTick24h(value) ? value : "";
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

const isLabeledTick24h = (value: string) => {
  const parsed = parseTimeLabel(value);
  if (!parsed) return false;
  return parsed.minute === 0 && parsed.hour % 3 === axisEndHour.value % 3;
};

const updateMarkerFromPixel = (centerX: number) => {
  if (!chart) return;
  const raw = chart.convertFromPixel({ xAxisIndex: 0 }, centerX);
  let next = markerTime.value;
  let nextIdx = markerIdx.value;
  if (typeof raw === "number") {
    nextIdx = Math.max(0, Math.min(times.value.length - 1, Math.round(raw)));
    next = times.value[nextIdx];
  } else if (typeof raw === "string") {
    next = raw;
    const foundIdx = times.value.indexOf(next);
    if (foundIdx >= 0) nextIdx = foundIdx;
  }
  markerIdx.value = nextIdx;
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
  formatter: (value: string, index: number) => {
    const label = formatXAxisLabel(value);
    if (!label) return "";
    const isActive = index === markerIdx.value;
    return isActive ? `{active|${label}}` : `{normal|${label}}`;
  },
  rich: {
    active: {
      color: "#000000",
      fontWeight: 700,
      fontSize: 12.5,
      fontFamily: "Arial Black",
    },
    normal: {
      color: "#808080",
      fontWeight: 700,
      fontSize: 12.5,
      fontFamily: "Arial Black",
    },
  },
});

const getTooltipPosition = (
  point: number[],
  _params: unknown,
  _dom: unknown,
  _rect: unknown,
  size: { contentSize: number[]; viewSize: number[] },
): [number, number] => {
  const [mouseX, mouseY] = point;
  const [contentWidth, contentHeight] = size.contentSize;
  const [viewWidth, viewHeight] = size.viewSize;
  const gap = 10;

  let x = mouseX + gap;
  let y = mouseY - contentHeight - gap;

  if (x + contentWidth > viewWidth - gap) {
    x = mouseX - contentWidth - gap;
  }
  if (x < gap) {
    x = gap;
  }

  if (y < gap) {
    y = mouseY + gap;
  }
  if (y + contentHeight > viewHeight - gap) {
    y = Math.max(gap, viewHeight - contentHeight - gap);
  }

  return [x, y];
};

const buildOption = (): echarts.EChartsOption => {
  const isDense24h = rangeValue.value === "24h" && times.value.length > 300;
  return {
  grid: {
    left: 0,
    right: 20,
    top: 20,
    // Keep extra room for rotated ticks + axis name in dense 24h mode.
    bottom: isDense24h ? 68 : 36,
    containLabel: true,
  },
  tooltip: {
    trigger: "axis",
    confine: true,
    appendToBody: false,
    position: getTooltipPosition,
  },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: times.value,
    name: rangeValue.value === "24h" ? "Last 24 Hrs" : "Last 7 days",
    nameLocation: "middle",
    nameGap: isDense24h ? 56 : 48,
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
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
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
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
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
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
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
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
        formatter: (value: number) => (value === 0 ? `${value}\n(ms)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#705ddd", width: 2 } },
      axisTick: { show: false },
    },
  ],
  series: seriesDefs.value.map((series) => {
    const isActive = getSeriesSelected(series.name);
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
  };
};

const applyOption = () => {
  chart?.setOption(buildOption(), true);
  scheduleResize();
};

const scheduleResize = () => {
  if (!chart) return;
  requestAnimationFrame(() => {
    chart?.resize();
    updateMarkerGraphic();
  });
};

const toggleSeries = (name: string) => {
  if (props.selectedSeries) {
    emit("toggle-series", name);
  } else {
    selected.value[name] = !selected.value[name];
  }
  applyOption();
};

const getNowMarkerPixelX = (): number | undefined => {
  if (!chart || !windowRef.value || !useCurrentTimeMarker.value) return undefined;
  const now = Math.floor(Date.now() / 1000);
  let axisValue: number | undefined;
  if (rangeValue.value === "24h" && denseSlotEpochs.value.length > 0) {
    const startEpoch = denseSlotEpochs.value[0];
    axisValue = Math.max(0, Math.min(denseSlotEpochs.value.length - 1, (now - startEpoch) / 300));
  } else {
    const { start_ts, end_ts } = windowRef.value;
    const span = end_ts - start_ts;
    if (span <= 0) return undefined;
    const n = times.value.length;
    if (n <= 0) return undefined;
    axisValue = Math.max(0, Math.min(n - 1, ((now - start_ts) / span) * (n - 1)));
  }
  const pixel = chart.convertToPixel({ xAxisIndex: 0 }, axisValue);
  return typeof pixel === "number" ? pixel : undefined;
};

const updateMarkerGraphic = () => {
  if (!chart) return;
  const grid = getGridRect();
  let xValue: number | undefined;
  if (useCurrentTimeMarker.value && windowRef.value && !isDragging.value) {
    xValue = getNowMarkerPixelX();
  }
  if (typeof xValue !== "number") {
    const baseXValue = chart.convertToPixel({ xAxisIndex: 0 }, markerIdx.value) as
      | number
      | undefined;
    xValue =
      typeof markerPixel.value === "number"
        ? clampToGrid(markerPixel.value, grid)
        : baseXValue;
  } else {
    xValue = clampToGrid(xValue, grid);
  }
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
            lineWidth: 2,
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
    const xValue = useCurrentTimeMarker.value
      ? getNowMarkerPixelX()
      : ((chart.convertToPixel({ xAxisIndex: 0 }, markerIdx.value) as
          | number
          | undefined));
    if (typeof xValue !== "number") return;
    const offsetX = evt?.offsetX;
    const offsetY = evt?.offsetY;
    if (typeof offsetX !== "number" || typeof offsetY !== "number") return;
    const withinY = offsetY >= grid.y && offsetY <= grid.y + grid.height;
    const nearLine = Math.abs(offsetX - xValue) <= threshold;
    if (!withinY || !nearLine) return;
    isDragging.value = true;
    useCurrentTimeMarker.value = false;
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

const startNowMarkerInterval = () => {
  if (nowMarkerInterval) return;
  nowMarkerInterval = setInterval(() => {
    if (useCurrentTimeMarker.value && windowRef.value && !isDragging.value) {
      updateMarkerGraphic();
    }
  }, 15000);
};

const stopNowMarkerInterval = () => {
  if (nowMarkerInterval) {
    clearInterval(nowMarkerInterval);
    nowMarkerInterval = null;
  }
};

onMounted(() => {
  if (!chartEl.value) return;
  chart = echarts.init(chartEl.value);
  applyOption();
  bindDragEvents();
  startNowMarkerInterval();
  const handleWindowResize = () => {
    scheduleResize();
  };
  window.addEventListener("resize", handleWindowResize);
  cleanupWindowResize = () => {
    window.removeEventListener("resize", handleWindowResize);
  };
  scheduleResize();
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
    // Prevent temporary dense x-axis labels while data is loading.
    resetChartForRange();
    fetchSeriesData(props.patientId);
  },
  { immediate: false },
);
watch(
  () => props.selectedSeries,
  () => {
    applyOption();
  },
  { deep: true },
);

useResizeObserver(chartEl, () => {
  scheduleResize();
});

onBeforeUnmount(() => {
  stopNowMarkerInterval();
  cleanupZrDrag?.();
  cleanupWindowResize?.();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="chart-wrapper">
    <div v-if="props.showLegend !== false" class="chart-legend">
      <button
        v-for="item in seriesDefs"
        :key="item.name"
        class="legend-item"
        :class="{ active: getSeriesSelected(item.name) }"
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
  width: 100%;
  min-width: 0;
  overflow: hidden;
}
.chart-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  column-gap: 12px;
  row-gap: 8px;
  margin-bottom: 8px;
  width: 100%;
  min-width: 0;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  min-width: 0;
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
  min-width: 0;
  overflow: hidden;
}
:deep(.n-spin),
:deep(.n-spin-container),
:deep(.n-spin-content) {
  flex: 1 1 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>