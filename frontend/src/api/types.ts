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
  treatment_plan?: string;
  treatment_cycle?: string;
  next_appointment_date?: Date | string;
  last_read_at?: Date | string;
  admission_histories?: {
    admission_date?: string;
    discharge_date?: string;
    diagnosis?: string;
    symptoms?: string;
  }[];
  medications?: {
    drug_name?: string;
    dosage?: string;
    start_date?: string;
    end_date?: string;
  }[];
  summaries?: Summary[];
  risks?: Risk[];
  conversation_logs?: ConversationLog[];
  notes?: { id: number; content: string; creator_type: string; created_at: string }[];
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
  treatment_plan?: string;
  treatment_cycle?: string;
  next_appointment_date?: string;
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
  treatment_plan?: string;
  treatment_cycle?: string;
  next_appointment_date?: string;
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
  // syncope
  syncope_state?: number;
  syncope_logs?: string;
  syncope_read?: number;
  // palpitation
  palpitation_state?: number;
  palpitation_logs?: string;
  palpitation_read?: number;
  // short_of_breath
  short_of_breath_state?: number;
  short_of_breath_logs?: string;
  short_of_breath_read?: number;
  // chest_discomfort
  chest_discomfort_state?: number;
  chest_discomfort_logs?: string;
  chest_discomfort_read?: number;
  // swelling
  swelling_state?: number;
  swelling_logs?: string;
  swelling_read?: number;
  // heart_rate (wearable)
  heart_rate_state?: number;
  heart_rate_logs?: string;
  heart_rate_read?: number;
  // respiration (wearable)
  respiration_state?: number;
  respiration_logs?: string;
  respiration_read?: number;
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
