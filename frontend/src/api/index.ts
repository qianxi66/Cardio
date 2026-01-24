import axios, { type AxiosRequestConfig } from "axios";
import { apiBasePath } from "@/config";
import router from "@/router";
export interface Patient {
  EHRid: string;
  medication: string;
  doctor: string;
  medicalhistory: string;
  switchValue: string;
  gender: string;
  age: number;
}
const request = axios.create({
  baseURL: apiBasePath,
  transformResponse: [
    (data, headers, status) => {
      // if json
      if (headers["content-type"] === "application/json") {
        return JSON.parse(data, dateReviver);
      }
      return data;
    },
  ],
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const errorHandler = (error: any) => {
  console.log("error", error);
  if (axios.isCancel(error) || error?.code === "ERR_CANCELED") {
    return;
  }
  const status = error?.response?.status;
  let message = "";
  if (error?.response?.data?.message) {
    message += error.response.data.message;
  } else if (error?.message) {
    message += error.message;
  }
  if (status === 401) {
    localStorage.removeItem("token");
    router.push("/login");
    window.$message.error("Login expired, please login again.");
  } else {
    window.$message.error("Error Occurred" + (message ? "," + message : "."));
  }
};

request.interceptors.response.use((response) => response.data, errorHandler);

const api = (req: AxiosRequestConfig<unknown>) =>
  new Promise((resolve, reject) => {
    if (!req.headers) {
      req.headers = {};
    }
    const token = localStorage.getItem("token");
    req.headers["Authorization"] = "Bearer " + token;
    request(req)
      .then((resp) => {
        resolve(resp);
      })
      .catch((err) => {
        console.log("error", err);
        if (axios.isCancel(err) || err?.code === "ERR_CANCELED") {
          return;
        }
        window.$message.error("Error Occurred" + (err ? "," + err : "."));
        reject(err);
      });
  });

// Custom reviver function to convert date strings to Date objects
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const dateReviver = (key: string, value: any) => {
  if (typeof value === "string" && key.endsWith("_at")) {
    const date = new Date(value);
    if (!isNaN(date.getTime()) && Number(value).toString() !== value) {
      return date;
    }
  }
  return value;
};

export default api;
