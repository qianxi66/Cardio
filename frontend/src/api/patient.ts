import type { CancelToken } from "axios";
import api from ".";
import {type Patient } from "./types";

export const getPatients = async () => {
  return await api({
    url: '/patients',
    method: 'GET',
  }) as Patient[];
};

export const getPatient = async (id: number, cancelToken?: CancelToken) => {
    return await api({
        url: `/patients/${id}`,
        method: 'GET',
        cancelToken,
    }) as Patient;
}
