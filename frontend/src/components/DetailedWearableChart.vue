<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useResizeObserver } from "@vueuse/core";
import { getWearableTimeSeries, type WearableTimeSeries } from "@/api/patient";
import Loading from "@/components/Loading.vue";
import { format } from "date-fns";

const props = withDefaults(
  defineProps<{
    patientId?: number;
    range?: "24h" | "7d";
    date?: string;
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
const dateValue = computed(() => props.date ?? "");
const windowRef = ref<{ start_ts: number; end_ts: number } | null>(null);
const seriesDefs = ref([
  {
    name: "Heart Rate",
    color: "#0c81d1",
    data: [] as Array<number | null>,
    yAxisIndex: 0,
    lineType: "solid",
  },
  {
    name: "Respiration",
    color: "#a586f4",
    data: [] as Array<number | null>,
    yAxisIndex: 1,
    lineType: "solid",
  },
  {
    name: "SpO2",
    color: "#63c0ff",
    data: [] as Array<number | null>,
    yAxisIndex: 2,
    lineType: [14, 3, 2, 3],
  },
  {
    name: "Heart Rate Variability",
    color: "#41acc4",
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

const DEFAULT_TIMEZONE = "America/New_York";
const ALERT_COLOR = "#eb4c44";
const ALERT_BG_COLOR = "#fddcdc";
const TOOLTIP_NORMAL_COLOR = "#808080";

const getTimeZone = (win?: { timezone?: string } | null) => win?.timezone || DEFAULT_TIMEZONE;

const getZonedParts = (epochMs: number, timeZone: string) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(epochMs));
  const pick = (type: string) => Number(parts.find((p) => p.type === type)?.value || 0);
  return {
    year: pick("year"),
    month: pick("month"),
    day: pick("day"),
    hour: pick("hour"),
    minute: pick("minute"),
    second: pick("second"),
  };
};

const getTimeZoneOffsetMs = (epochMs: number, timeZone: string) => {
  const roundedMs = Math.floor(epochMs / 1000) * 1000;
  const parts = getZonedParts(roundedMs, timeZone);
  const asUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
  );
  return asUtc - roundedMs;
};

const ceilHourEpochInZone = (epochSec: number, timeZone: string) => {
  const epochMs = epochSec * 1000;
  const offsetMs = getTimeZoneOffsetMs(epochMs, timeZone);
  const zonedMs = epochMs + offsetMs;
  const zoned = new Date(zonedMs);
  let anchorZonedMs = Date.UTC(
    zoned.getUTCFullYear(),
    zoned.getUTCMonth(),
    zoned.getUTCDate(),
    zoned.getUTCHours(),
    0,
    0,
    0,
  );
  if (zoned.getUTCMinutes() > 0 || zoned.getUTCSeconds() > 0 || zoned.getUTCMilliseconds() > 0) {
    anchorZonedMs += 3600 * 1000;
  }
  let anchorEpochMs = anchorZonedMs - offsetMs;
  const anchorOffsetMs = getTimeZoneOffsetMs(anchorEpochMs, timeZone);
  if (anchorOffsetMs !== offsetMs) {
    anchorEpochMs = anchorZonedMs - anchorOffsetMs;
  }
  return Math.floor(anchorEpochMs / 1000);
};

const formatHourMinuteInZone = (epochSec: number, timeZone: string) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    hour: "numeric",
    minute: "2-digit",
  }).formatToParts(new Date(epochSec * 1000));
  const hour = parts.find((p) => p.type === "hour")?.value || "0";
  const minute = parts.find((p) => p.type === "minute")?.value || "00";
  return `${Number(hour)}:${minute}`;
};

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

const buildDense24hTimes = (win?: { end_ts: number; timezone?: string } | null) => {
  const timeZone = getTimeZone(win);
  const baseEnd = win?.end_ts ?? Math.floor(Date.now() / 1000);
  const endEpoch = ceilHourEpochInZone(baseEnd, timeZone);
  const endHourParts = getZonedParts(endEpoch * 1000, timeZone);
  axisEndHour.value = endHourParts.hour;
  const startEpoch = endEpoch - 24 * 60 * 60;
  const labels: string[] = [];
  const epochs: number[] = [];
  for (let sec = startEpoch; sec <= endEpoch; sec += 15 * 60) {
    labels.push(formatHourMinuteInZone(sec, timeZone));
    epochs.push(sec);
  }
  denseSlotEpochs.value = epochs;
  return labels;
};

const mapBackendDataToDense24h = (
  backendValues: Array<number | null>,
) => {
  const epochs = denseSlotEpochs.value;
  const out: Array<number | null> = Array.from({ length: epochs.length }, () => null);
  if (epochs.length === 0 || backendValues.length === 0) return out;

  const maxLen = Math.min(backendValues.length, out.length);
  for (let idx = 0; idx < maxLen; idx += 1) {
    const value = backendValues[idx];
    if (value === null || value === undefined || !Number.isFinite(value)) continue;
    out[idx] = value;
  }
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

const isAlertValue = (seriesName: string, value: number | null): boolean => {
  if (value === null || value === undefined || !Number.isFinite(value)) return false;
  if (seriesName === "Heart Rate") return value > 120 || value < 60;
  if (seriesName === "Respiration") return value > 24 || value < 8;
  if (seriesName === "SpO2") return value < 94;
  if (seriesName === "Heart Rate Variability") return value < 15;
  return false;
};

const splitSeriesByAlert = (seriesName: string, data: Array<number | null>) => {
  const normal: Array<number | null> = [];
  const alert: Array<number | null> = [];
  data.forEach((value, index) => {
    if (value === null || value === undefined || !Number.isFinite(value)) {
      normal.push(null);
      alert.push(null);
      return;
    }
    const isAlert = isAlertValue(seriesName, value);
    if (isAlert) {
      normal.push(null);
      alert.push(value);
      // keep line visually continuous when switching from normal -> alert
      if (index > 0 && normal[index - 1] !== null && alert[index - 1] === null) {
        alert[index - 1] = data[index - 1];
      }
      return;
    }
    normal.push(value);
    alert.push(null);
    // keep line visually continuous when switching from alert -> normal
    if (index > 0 && alert[index - 1] !== null && normal[index - 1] === null) {
      normal[index - 1] = data[index - 1];
    }
  });
  return { normal, alert };
};

const getAlertIntervals = () => {
  const total = times.value.length;
  if (total === 0) return [] as Array<{ startIndex: number; endIndex: number }>;
  const combined = Array.from({ length: total }, () => false);
  seriesDefs.value.forEach((series) => {
    // Use rendered alert series (with pivot points) so markArea aligns with visible red line.
    const split = splitSeriesByAlert(series.name, series.data);
    for (let i = 0; i < total; i += 1) {
      if (split.alert[i] !== null && split.alert[i] !== undefined) {
        combined[i] = true;
      }
    }
  });
  const intervals: Array<{ startIndex: number; endIndex: number }> = [];
  let start = -1;
  for (let i = 0; i < total; i += 1) {
    if (combined[i] && start < 0) {
      start = i;
    }
    if ((!combined[i] || i === total - 1) && start >= 0) {
      const endIndex = combined[i] && i === total - 1 ? i : i - 1;
      intervals.push({ startIndex: start, endIndex });
      start = -1;
    }
  }
  return intervals;
};

const getTooltipValue = (raw: unknown): number | null => {
  if (Array.isArray(raw)) {
    const value = raw[1];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
};

const formatTooltipValue = (seriesName: string, value: number) => {
  if (seriesName === "Heart Rate") return `${Math.round(value)}`;
  return `${Math.round(value * 10) / 10}`;
};

const applySeriesData = (payload?: WearableTimeSeries) => {
  windowRef.value = payload?.window ?? null;
  denseSlotEpochs.value = [];
  // Use the dense times array from the backend (15-min bins) if available,
  // otherwise fall back to the sparse 9-point placeholder grid.
  times.value = payload?.times?.length ? payload.times : buildDefaultTimes("24h");

  if (!payload) {
    seriesDefs.value.forEach((series) => {
      series.data = normalizeSeriesLength([], times.value.length, null);
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
      const raw = seriesMap[series.name] ?? [];
      series.data = roundSeriesData(
        series.name,
        normalizeSeriesLength(raw, times.value.length, null),
      );
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
  if (!windowRef.value || len <= 1) return 10800;
  return Math.round((windowRef.value.end_ts - windowRef.value.start_ts) / Math.max(1, len - 1));
};

const updateMarkerToCurrentTime = () => {
  const win = windowRef.value;
  if (!win || times.value.length === 0) return;
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
  // Don't fetch (or show) data for future dates
  if (dateValue.value) {
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    if (dateValue.value > todayStr) {
      applySeriesData();
      return;
    }
  }
  isLoading.value = true;
  try {
    const data = await getWearableTimeSeries(patientId, dateValue.value);
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
  denseSlotEpochs.value = [];
  const nextTimes = buildDefaultTimes("24h");
  times.value = nextTimes;
  seriesDefs.value.forEach((series) => {
    series.data = normalizeSeriesLength([], nextTimes.length, null);
  });
  markerIdx.value = Math.max(0, Math.min(nextTimes.length - 1, markerIdx.value));
  markerTime.value = nextTimes[markerIdx.value] || nextTimes[0] || "0:00";
  applyOption();
};

const THREE_HOUR_LABELS = new Set(["0:00", "3:00", "6:00", "9:00", "12:00", "15:00", "18:00", "21:00", "24:00"]);
const formatXAxisLabel = (value: string) => {
  return THREE_HOUR_LABELS.has(value) ? value : "";
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
  const isDense24h = times.value.length > 50;
  const alertMarkAreaData = getAlertIntervals().map((segment) => {
    // Keep boundaries on actual alert points to avoid trailing +15min offset.
    return [{ xAxis: segment.startIndex }, { xAxis: segment.endIndex }];
  });
  return {
  grid: {
    left: 0,
    right: 20,
    top: 20,
    bottom: isDense24h ? 52 : 30,
    containLabel: true,
  },
  tooltip: {
    trigger: "axis",
    confine: true,
    appendToBody: false,
    position: getTooltipPosition,
    formatter: (params: any) => {
      const items = Array.isArray(params) ? params : [params];
      if (!items.length) return "";
      const dataIndex = items[0]?.dataIndex ?? 0;
      let timeLabel: string;
      if (windowRef.value && times.value.length > 1) {
        const { start_ts, end_ts } = windowRef.value;
        const binSeconds = (end_ts - start_ts) / Math.max(1, times.value.length - 1);
        const epoch = start_ts + dataIndex * binSeconds;
        timeLabel = format(new Date(epoch * 1000), "yyyy-MM-dd HH:mm");
      } else {
        timeLabel = items[0]?.axisValueLabel ?? items[0]?.name ?? "";
      }
      const bySeries = new Map<string, { value: number | null }>();
      items.forEach((item: any) => {
        const rawName = String(item?.seriesName || "");
        const seriesName = rawName.endsWith(" (Alert)")
          ? rawName.slice(0, -8)
          : rawName;
        const value = getTooltipValue(item?.value);
        const existing = bySeries.get(seriesName);
        if (!existing || (existing.value === null && value !== null)) {
          bySeries.set(seriesName, { value });
        }
      });
      const rows = seriesDefs.value
        .map((series) => {
          const value = bySeries.get(series.name)?.value ?? null;
          const displayValue = value === null ? "--" : formatTooltipValue(series.name, value);
          const isAlert = value !== null && isAlertValue(series.name, value);
          const rowColor = isAlert ? ALERT_COLOR : TOOLTIP_NORMAL_COLOR;
          return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;color:${rowColor};font-weight:700;">
            <span>${series.name}</span>
            <span>${displayValue}</span>
          </div>`;
        })
        .join("");
      return `<div>
        <div style="margin-bottom:4px;font-weight:700;">${timeLabel}</div>
        ${rows}
      </div>`;
    },
  },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: times.value,
    name: "Time",
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
        color: "#0c81d1",
        fontWeight: "bold",
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
        formatter: (value: number) => (value === 0 ? `${value}\n(bpm)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#0c81d1", width: 2 } },
      axisTick: { show: false },
    },
    {
      type: "value",
      position: "left",
      offset: 40,
      min: 10,
      max: 40,
      interval: 10,
      axisLabel: {
        color: "#a586f4",
        fontWeight: "bold",
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
        formatter: (value: number) => (value === 10 ? `${value}\n(bpm)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#a586f4", width: 2 } },
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
        color: "#63c0ff",
        fontWeight: "bold",
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
      },
      axisLine: { show: true, lineStyle: { color: "#63c0ff", width: 2 } },
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
        color: "#41acc4",
        fontWeight: "bold",
        showMinLabel: true,
        showMaxLabel: true,
        hideOverlap: false,
        formatter: (value: number) => (value === 0 ? `${value}\n(ms)` : `${value}`),
      },
      axisLine: { show: true, lineStyle: { color: "#41acc4", width: 2 } },
      axisTick: { show: false },
    },
  ],
  series: [
    {
      name: "Alert Background",
      type: "line",
      yAxisIndex: 0,
      data: [],
      showSymbol: false,
      symbol: "none",
      lineStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      silent: true,
      tooltip: { show: false },
      markArea: {
        silent: true,
        itemStyle: {
          color: ALERT_BG_COLOR,
          opacity: 0.75,
        },
        data: alertMarkAreaData,
      },
      z: 0,
    },
    ...seriesDefs.value.flatMap((series) => {
    const isActive = getSeriesSelected(series.name);
    const data = isActive ? series.data : [];
    const split = splitSeriesByAlert(series.name, data);
    return [
      {
        name: series.name,
        type: "line",
        yAxisIndex: series.yAxisIndex,
        data: split.normal,
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
        z: 2,
      },
      {
        name: `${series.name} (Alert)`,
        type: "line",
        yAxisIndex: series.yAxisIndex,
        data: split.alert,
        smooth: true,
        connectNulls: false,
        showSymbol: false,
        symbol: "none",
        symbolSize: 0,
        lineStyle: {
          color: ALERT_COLOR,
          type: series.lineType as any,
          width: 3,
        },
        itemStyle: { color: ALERT_COLOR },
        markLine: undefined,
        z: 3,
      },
    ];
    }),
  ],
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
  const { start_ts, end_ts } = windowRef.value;
  const span = end_ts - start_ts;
  if (span <= 0) return undefined;
  const n = times.value.length;
  if (n <= 0) return undefined;
  const axisValue = Math.max(0, Math.min(n - 1, ((now - start_ts) / span) * (n - 1)));
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
            fill: "#41acc4",
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
            stroke: "#41acc4",
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
  () => props.date,
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
        <svg class="legend-line" viewBox="0 0 20 2" aria-hidden="true">
          <line
            x1="0"
            y1="1"
            x2="20"
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
  min-height: 264px;
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
  width: 20px;
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