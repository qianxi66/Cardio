# Cardio System

Cardio is a wearable-assisted patient monitoring system with:

- a dashboard frontend for clinical/professional users
- a Flask backend API and SQLite data store
- integrations for conversation logs and wearable-derived features

## Current backend data model (ER summary)

The main SQLAlchemy models are defined in `backend/recover/db.py`.

### Core entities

- `User`
  - Dashboard account (`username`, `password`, `email`, `name`)
  - Linked to patients through `user_patient_table` (many-to-many)
  - Owns auth `Token` records

- `Patient`
  - Identity and profile (`name`, `age`, `gender`, `participant_id`, `alexa_user_id`, `garmin_id`, `EHR_id`, `email`)
  - Cancer/treatment fields (`cancer_type`, `cancer_stage`, `treatment_type`, `treatment_plan`, `treatment_cycle`, `next_appointment_date`)
  - Parent of most clinical and monitoring tables

- `Token`
  - Session/auth token for a user (`token`, `userid`, `rememberme`, timestamps)

### Patient-linked clinical/monitoring tables

- `Summary`
  - Per-day symptom summary per patient
  - Contains dynamic `*_state`, `*_logs`, and optional `*_scale` fields based on symptom definitions

- `Risk`
  - Risk inference result (`risk_score`) and feature importances (`important_of_*`) with timestamp

- `ConversationLog`
  - Message-level conversation records (`role`, `content`, `date`)
  - Includes extracted symptom text fields (`symptoms_chest`, `symptoms_other`)

- `Note`
  - Clinical and AI notes (`creator_type` as `user` or `ai`)

- `AdmissionHistory`
  - Admission/discharge records and inpatient context

- `Medication`
  - Active and historical medication records

- `PreadmissionMedication`
  - Medication baseline before admission

- `IOMetric`
  - Intake/output metrics by date

- `MedicationExecutionMetric`
  - Medication administration execution metrics by date

### Relationship overview

- `User` <-> `Patient`: many-to-many (`user_patient_table`)
- `Patient` -> `Summary` / `Risk` / `ConversationLog` / `Note` / `AdmissionHistory` / `Medication` / `PreadmissionMedication` / `IOMetric` / `MedicationExecutionMetric`: one-to-many
- `User` -> `Token`: one-to-many

## Conversation log semantics

Conversation data for dashboard rendering is stored in `ConversationLog`:

- `role`: message role (`user`, `assistant`, etc.)
- `content`: message text
- `date`: message time
- optional extraction fields:
  - `symptoms_chest`
  - `symptoms_other`

The frontend uses these logs together with `Summary.*_logs` references for symptom-focused navigation/highlighting.

## Notes for contributors

- This file replaces legacy RECOVER-era draft notes.
- When schema changes, update both:
  - `backend/recover/db.py`
  - Alembic migrations under `backend/migrations/versions/`
