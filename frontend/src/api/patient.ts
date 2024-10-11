import type { CancelToken } from "axios";
import api from ".";
import {
  type Patient,
  type Report,
  type creatPatientresp,
  type updatePatientreq,
  type updatePatientresp,
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

export const updatePatient = async (id: number, data: updatePatientreq) => {
  return (await api({
    url: `/patients/${id}`,
    method: "PATCH",
    data,
  })) as updatePatientresp;
};

export const createPatient = async (data: creatPatientresp) => {
  return (await api({
    url: `/patients`,
    method: "POST",
    data,
  })) as creatPatientresp;
};

export const updateReport = async (
  patient_id: number,
  report_id: number,
  data: Partial<Report>,
) => {
  return await api({
    url: `/patients/${patient_id}/report/${report_id}`,
    method: "PATCH",
    data,
  });
};

export const getReport = async (
  patient_id: number,
  report_id: number,
  cancelToken?: CancelToken,
) => {
  return (await api({
    url: `/patients/${patient_id}/report/${report_id}`,
    method: "GET",
    cancelToken,
  })) as Report;
};

export const deleteNote = async (
  patient_id: number,
  report_id: number,
  note_id: number,
) => {
  return await api({
    url: `/patients/${patient_id}/report/${report_id}/note/${note_id}`,
    method: "DELETE",
  });
};

export const createNote = async (
  patient_id: number,
  user_id: number,
  report_id: number,
  content: string,
) => {
  return await api({
    url: `/patients/${patient_id}/report/${report_id}/note`,
    method: "POST",
    data: { content, user_id: user_id },
  });
};
