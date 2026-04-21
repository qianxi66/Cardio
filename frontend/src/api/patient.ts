import type { CancelToken } from "axios";
import api from ".";
import {
  type Patient,
  type CreatePatientRequest,
  type UpdatePatientRequest,
  type UpdatePatientResponse,
  type Summary,
  type Risk,
  type ConversationLog,
  type ReportNote,
} from "./types";

export const getPatients = async () => {
  return (await api({
    url: "/patients",
    method: "GET",
  })) as Patient[];
};

const patientInFlight = new Map<string, Promise<Patient>>();
const patientCache = new Map<string, { data: Patient; cachedAt: number }>();
const PATIENT_CACHE_TTL_MS = 30 * 60 * 1000;

export const getPatient = async (id: number, cancelToken?: CancelToken) => {
  const key = `${id}`;
  const now = Date.now();
  const cached = patientCache.get(key);
  if (cached && now - cached.cachedAt < PATIENT_CACHE_TTL_MS) {
    return cached.data;
  }

  if (!cancelToken) {
    const inFlight = patientInFlight.get(key);
    if (inFlight) {
      return inFlight;
    }
  }

  const req = (api({
    url: `/patients/${id}`,
    method: "GET",
    cancelToken,
  }) as Promise<Patient>)
    .then((data) => {
      patientCache.set(key, { data, cachedAt: Date.now() });
      return data;
    })
    .finally(() => {
      if (!cancelToken) {
        patientInFlight.delete(key);
      }
    });

  if (!cancelToken) {
    patientInFlight.set(key, req);
  }

  return req;
};

export const updatePatient = async (id: number, data: UpdatePatientRequest) => {
  const result = (await api({
    url: `/patients/${id}`,
    method: "PATCH",
    data,
  })) as UpdatePatientResponse;
  patientCache.delete(`${id}`);
  patientInFlight.delete(`${id}`);
  return result;
};

export const createPatient = async (data: CreatePatientRequest) => {
  return (await api({
    url: `/patients`,
    method: "POST",
    data,
  })) as CreatePatientRequest;
};

export type WearableTimeSeries = {
  times: string[];
  series: {
    heart_rate: Array<number | null>;
    respiration: Array<number | null>;
    spo2?: Array<number | null>;
    heart_rate_variability: Array<number | null>;
  };
  window: {
    start_ts: number;
    end_ts: number;
    timezone: string;
  };
  range?: string;
};

const wearableTimeseriesInFlight = new Map<string, Promise<WearableTimeSeries>>();
const wearableTimeseriesCache = new Map<
  string,
  { data: WearableTimeSeries; cachedAt: number }
>();
const WEARABLE_CACHE_TTL_MS = 30 * 60 * 1000;

export const getWearableTimeSeries = async (id: number, date: string) => {
  const key = `${id}:${date}`;
  const now = Date.now();
  const cached = wearableTimeseriesCache.get(key);
  if (cached && now - cached.cachedAt < WEARABLE_CACHE_TTL_MS) {
    return cached.data;
  }
  const inFlight = wearableTimeseriesInFlight.get(key);
  if (inFlight) {
    return inFlight;
  }

  const req = (api({
    url: `/patients/${id}/wearable/timeseries`,
    params: { date },
    method: "GET",
  }) as Promise<WearableTimeSeries>)
    .then((data) => {
      wearableTimeseriesCache.set(key, { data, cachedAt: Date.now() });
      return data;
    })
    .finally(() => {
      wearableTimeseriesInFlight.delete(key);
    });

  wearableTimeseriesInFlight.set(key, req);
  return req;
};

export const getSummaries = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/summaries`,
    method: "GET",
  })) as Summary[];
};

export const getRisks = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/risks`,
    method: "GET",
  })) as Risk[];
};

export const getConversationLogs = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/conversation_logs`,
    method: "GET",
  })) as ConversationLog[];
};

export const getNotes = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/notes`,
    method: "GET",
  })) as ReportNote[];
};

export const createNote = async (patient_id: number, content: string) => {
  return await api({
    url: `/patients/${patient_id}/notes`,
    method: "POST",
    data: { content },
  });
};

export const deleteNote = async (patient_id: number, note_id: number) => {
  return await api({
    url: `/patients/${patient_id}/notes/${note_id}`,
    method: "DELETE",
  });
};

export const updateNote = async (patient_id: number, note_id: number, content: string) => {
  return await api({
    url: `/patients/${patient_id}/notes/${note_id}`,
    method: "PATCH",
    data: { content },
  });
};

export const markSymptomRead = async (
  patient_id: number,
  summary_id: number,
) => {
  return await api({
    url: `/patients/${patient_id}/summaries/${summary_id}/read`,
    method: "PATCH",
    data: { read: 1 },
  });
};

export const updateSummarySymptomState = async (
  patient_id: number,
  summary_id: number,
  symptom: string,
  state: number,
) => {
  return await api({
    url: `/patients/${patient_id}/summaries/${summary_id}`,
    method: "PATCH",
    data: {
      [`${symptom}_state`]: state,
    },
  });
};

export type WearableCoverage = Record<string, boolean>;

export const getWearableCoverage = async (
  patient_id: number,
  dates: string[],
): Promise<WearableCoverage> => {
  if (!dates.length) return {};
  const params = new URLSearchParams();
  dates.forEach((d) => params.append("dates", d));
  return (await api({
    url: `/patients/${patient_id}/wearable-coverage?${params.toString()}`,
    method: "GET",
  })) as WearableCoverage;
};

export const getPreadmissionMedications = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/preadmission_medications`,
    method: "GET",
  })) as NonNullable<import("./types").Patient["preadmission_medications"]>;
};

export const getIOMetrics = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/io_metrics`,
    method: "GET",
  })) as NonNullable<import("./types").Patient["io_metrics"]>;
};

export const getMedicationExecutionMetrics = async (patient_id: number) => {
  return (await api({
    url: `/patients/${patient_id}/medication_execution_metrics`,
    method: "GET",
  })) as NonNullable<import("./types").Patient["medication_execution_metrics"]>;
};
