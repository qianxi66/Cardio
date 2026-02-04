import type { UseUrlSearchParamsOptions } from "@vueuse/core";

export type Patient = {
  id: number;
  name: string;
  age: number;
  gender: string;
  users: User[];
  EHR_id?: string;
  alexa_user_id?: string;
  participant_id?: string;
  garmin_id?: string;
  cancer_type?: string;
  cancer_stage?: string;
  treatment_type?: string;
  last_read_at?: Date | string;
  hospitalizations?: {
    date?: string;
    event?: string;
  }[];
  summaries?: Summary[];
  risks?: Risk[];
  conversation_logs?: ConversationLog[];
  report_notes?: ReportNote[];
  read?: boolean;
  reviewed?: boolean;
  state?: number;
};

export type UpdatePatientRequest = {
  name?: string;
  age?: number;
  gender?: string;
  EHR_id?: string;
  ehr_id?: string;
  alexa_user_id?: string;
  participant_id?: string;
  garmin_id?: string;
  cancer_type?: string;
  cancer_stage?: string;
  treatment_type?: string;
  user?: number[];
};
export type UpdatePatientResponse = {
  patient_id: number;
};

export type CreatePatientRequest = {
  name: string;
  age?: number;
  gender?: string;
  EHR_id?: string;
  ehr_id?: string;
  alexa_user_id?: string;
  participant_id?: string;
  garmin_id?: string;
  cancer_type?: string;
  cancer_stage?: string;
  treatment_type?: string;
  user: number[];
};
// Define the type for the token object
export type Token = {
  created_at: string; // Date in string format
  id: number; // ID as a number
  rememberme: boolean; // Remember me flag as a boolean
  token: string; // Token as a string
  updated_at: string; // Date in string format
  userid: number; // User ID as a number
};

// Define the type for the response object
export type LoginResponse = {
  token: Token; // Token object
};

export type UserInfoResponse = {
  user_id: number;
  username: string;
};
export type User = {
  id: number;
  username: string;
  password?: string;
  email: string;
  name: string;
  report_notes?: ReportNote[];
};

export type ReportNote = {
  id: number;
  patient_id: number;
  user_id: number;
  user?: User;
  content: string;
  created_at: Date;
  updated_at: Date;
};

export type ConversationLog = {
  id: number;
  patient_id: number;
  role: string;
  content: string;
  chain_of_thoughts?: string;
  symptoms_chest?: string;
  symptoms_other?: string;
  date: Date | string;
};

export type Summary = {
  id: number;
  patient_id: number;
  heart_rate_min?: number;
  heart_rate_max?: number;
  heart_rate_average?: number;
  spo2_min?: number;
  spo2_max?: number;
  spo2_average?: number;
  respiration_min?: number;
  respiration_max?: number;
  respiration_average?: number;
  hrv_min?: number;
  hrv_max?: number;
  hrv_average?: number;
  short_of_breath?: boolean;
  chest_discomfort?: boolean;
  fatigue?: boolean;
  palpitation?: boolean;
  swelling?: boolean;
  syncope?: boolean;
  date: Date | string;
};

export type Risk = {
  id: number;
  patient_id: number;
  risk_score: number;
  important_of_chest?: number;
  important_of_heart?: number;
  important_of_respiration?: number;
  important_of_hrv?: number;
  date: Date | string;
};
