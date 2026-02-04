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

export const getPatient = async (id: number, cancelToken?: CancelToken) => {
  return (await api({
    url: `/patients/${id}`,
    method: "GET",
    cancelToken,
  })) as Patient;
};

export const updatePatient = async (id: number, data: UpdatePatientRequest) => {
  return (await api({
    url: `/patients/${id}`,
    method: "PATCH",
    data,
  })) as UpdatePatientResponse;
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
    heart_rate_variability: Array<number | null>;
  };
  window: {
    start_ts: number;
    end_ts: number;
    timezone: string;
  };
  range?: string;
};

export const getWearableTimeSeries = async (id: number, range = "24h") => {
  return (await api({
    url: `/patients/${id}/wearable/timeseries`,
    params: { range },
    method: "GET",
  })) as WearableTimeSeries;
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
