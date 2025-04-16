import type { UseUrlSearchParamsOptions } from "@vueuse/core";

export type Patient = {
  id: number;
  age: number;
  gender: string;
  users: User[];
  EHR_id: string;
  alexa_user_id?: string;
  medical_history: string;
  medication: string;
  participant_id: string;
  garmin_id?: string;
  reports: Report[]; // Relationship: One-to-Many with Report
  conversationLogs: ConversationLog[]; // Relationship: One-to-Many with ConversationLog
  read: boolean;
  last_read_at: Date;
  reviewed: boolean;
  state: number;
};

export type updatePatientreq = {
  EHRid: string;
  medication: string;
  user: number[];
  medicalhistory: string;
  participantid: string;
  gender: string;
  age: number;
  garmin_id?: string;
};
export type updatePatientresp = {
  patient_id: number;
};

export type creatPatientresp = {
  EHRid: string;
  medication: string;
  user: number[];
  medicalhistory: string;
  participantid: string;
  gender: string;
  age: number;
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
  password: string;
  email: string;
  name: string;
  reportNotes: ReportNote[]; // Relationship: One-to-Many with ReportNote
};

export type Report = {
  id: number;
  patient_id: number;
  created_at: Date;
  updated_at: Date;
  pain_state: number;
  pain_read: boolean;
  pain_logs: string;
  breathing_state: number;
  breathing_read: boolean;
  breathing_logs: string;
  fever_state: number;
  fever_read: boolean;
  fever_logs: string;
  stools_state: number;
  stools_read: boolean;
  stools_logs: string;
  drainage_state: number;
  drainage_read: boolean;
  drainage_logs: string;
  activity_state: number;
  activity_read: boolean;
  activity_logs: string;
  conscious_state: number;
  conscious_read: boolean;
  conscious_logs: string;
  constipation_state: number;
  constipation_read: boolean;
  constipation_logs: string;
  diarrhea_state: number;
  diarrhea_read: boolean;
  diarrhea_logs: string;
  eating_state: number;
  eating_read: boolean;
  eating_logs: string;
  swelling_state: number;
  swelling_read: boolean;
  swelling_logs: string;
  mood_state: number;
  mood_read: boolean;
  mood_logs: string;
  notes: ReportNote[]; // Relationship: One-to-Many with ReportNote
  summary: ReportSummary[]; // Relationship: One-to-Many with ReportSummary
  conversation_logs: ConversationLog[]; // Relationship: One-to-Many with ConversationLog
};

export type ReportNote = {
  id: number;
  report_id: number;
  user_id: number;
  user: User;
  content: string;
  created_at: Date;
  updated_at: Date;
};

export type ReportSummary = {
  id: number;
  report_id: number;
  category: string;
  content: string;
  conversation_log_ids: string;
  highlight_keywords: string;

  created_at: Date;
};

export type ConversationLog = {
  id: number;
  patient_id: number;
  report_id: number;
  role: string;
  content: string;
  created_at: Date;
};
