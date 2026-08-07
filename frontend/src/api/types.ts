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
    id?: number;
    admission_date?: string;
    discharge_date?: string;
    diagnosis?: string;
    symptoms?: string;
    notes?: string;
    careunit_name?: string;
    destination_unit_name?: string;
    discharge_status?: string;
    admission_type?: string;
    readmission_flag?: boolean;
    los_minutes?: number;
  }[];
  medications?: {
    id?: number;
    drug_name?: string;
    dosage?: string;
    start_date?: string;
    end_date?: string;
    route?: string;
    frequency?: string;
    schedule_hours?: string;
    dose_count?: number;
    is_current_medication?: boolean;
    order_source?: string;
  }[];
  preadmission_medications?: {
    id?: number;
    admission_history_id?: number;
    drug_name?: string;
    dosage?: string;
    frequency?: string;
    started_before_admission_date?: string;
    active_at_admission?: boolean;
    source_text?: string;
  }[];
  io_metrics?: {
    id?: number;
    admission_history_id?: number;
    metric_date?: string;
    io_event_count?: number;
    io_total_volume_ml?: number;
    io_total_volume_measurement_count?: number;
  }[];
  medication_execution_metrics?: {
    id?: number;
    admission_history_id?: number;
    metric_date?: string;
    ad_event_count?: number;
    me_event_count?: number;
    so_event_count?: number;
    med_admin_execution_event_count?: number;
  }[];
  summaries?: Summary[];
  // Only sent by GET /patients (the list endpoint), which embeds each patient's most
  // recent summary so the list can be rendered without a per-patient summaries request.
  latest_summary?: Summary | null;
  risks?: Risk[];
  conversation_logs?: ConversationLog[];
  notes?: { id: number; content: string; creator_type: string; created_at: string; created_by?: string }[];
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
  created_by?: string;
  creator_type?: string;
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
  read?: number;
  // syncope
  syncope_state?: number;
  syncope_logs?: string;
  // palpitation
  palpitation_state?: number;
  palpitation_logs?: string;
  // short_of_breath
  short_of_breath_state?: number;
  short_of_breath_logs?: string;
  short_of_breath_scale?: number;
  // chest_discomfort
  chest_discomfort_state?: number;
  chest_discomfort_logs?: string;
  chest_discomfort_scale?: number;
  // fatigue
  fatigue_state?: number;
  fatigue_logs?: string;
  // swelling
  swelling_state?: number;
  swelling_logs?: string;
  // heart_rate (wearable)
  heart_rate_state?: number;
  heart_rate_logs?: string;
  // respiration (wearable)
  respiration_state?: number;
  respiration_logs?: string;
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
