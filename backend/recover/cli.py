import json
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import bcrypt
import click
from sqlalchemy import text
from sqlalchemy.orm import Query

# Assuming 'app' and 'db' are defined in .app and .db respectively
from .app import app
from .apis import process_patient_summary, _generate_ai_note_for_patient
from .db import (
    AdmissionHistory,
    AlexaIDNote,
    ConversationLog,
    IOMetric,
    Medication,
    MedicationExecutionMetric,
    Note,
    Patient,
    PreadmissionMedication,
    Summary,
    Risk,
    User,
    db,
)

EASTERN_TZ = ZoneInfo("America/New_York")

def create_random_datetime(start_date=None, end_date=None):
    """Generates a random datetime object within a specified range."""
    if start_date is None:
        start_date = datetime.now() - timedelta(days=365) # Default to last year
    if end_date is None:
        end_date = datetime.now()
    
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_days = random.randrange(days_between_dates)
    random_seconds = random.randrange(86400) # seconds in a day
    return start_date + timedelta(days=random_days, seconds=random_seconds)

def generate_random_float(min_val, max_val, decimal_places=2):
    """Generates a random float within a range, with specified decimal places."""
    return round(random.uniform(min_val, max_val), decimal_places)

def generate_random_int(min_val, max_val):
    """Generates a random integer within a range."""
    return random.randint(min_val, max_val)


def generate_doctor_insight_note():
    """Generates a doctor-authored note with personal clinical judgment (not table-summary text)."""
    templates = [
        "Bedside assessment: patient appears {appearance}. My clinical impression is {impression}. I am most concerned about {concern}. Plan: {plan}.",
        "Progress note: trajectory is {trajectory}. In my judgment this is {judgment}. I recommend {recommendation} and reassess in 24h.",
        "Attending note: reviewed current status with patient. I think the main issue is {main_issue}. Differential includes {differential}. Next step: {next_step}.",
        "Clinical opinion: response to treatment is {response}. Given {reasoning}, I prefer {preferred_action}. If no improvement, consider {backup_plan}.",
        "Rounding impression: overall condition is {overall}. Key risk is {key_risk}. I discussed goals with patient and will {follow_up_plan}.",
    ]
    fill = {
        "appearance": random.choice(["fatigued but stable", "comfortable at rest", "mildly dyspneic", "anxious but cooperative"]),
        "impression": random.choice(["compensated heart failure", "possible treatment-related cardiotoxicity", "volume overload with gradual response", "stable but fragile recovery"]),
        "concern": random.choice(["recurrent arrhythmia", "renal function drift", "early decompensation overnight", "post-discharge readmission risk"]),
        "plan": random.choice(["adjust diuretic strategy", "continue current regimen with close monitoring", "repeat ECG and chemistry panel", "coordinate with cardiology consult"]),
        "trajectory": random.choice(["slightly improving", "unchanged", "fluctuating", "better than expected"]),
        "judgment": random.choice(["clinically acceptable for now", "borderline and needs close watch", "encouraging but not yet discharge-ready", "suggestive of a slow recovery curve"]),
        "recommendation": random.choice(["maintain telemetry for another day", "optimize beta-blocker dosing", "continue supportive care", "target symptom-guided medication adjustment"]),
        "main_issue": random.choice(["hemodynamic variability", "persistent exertional symptoms", "medication tolerance", "insufficient functional reserve"]),
        "differential": random.choice(["ischemia vs demand mismatch", "infection vs inflammatory response", "drug effect vs disease progression", "volume status imbalance"]),
        "next_step": random.choice(["trend labs and reassess tomorrow", "optimize meds and re-evaluate symptoms", "hold discharge and continue monitoring", "review with multidisciplinary team"]),
        "response": random.choice(["partial", "gradual", "limited", "clinically meaningful"]),
        "reasoning": random.choice(["current tolerance and symptom profile", "today's exam and bedside findings", "risk/benefit discussion with patient", "likely short-term instability risk"]),
        "preferred_action": random.choice(["conservative optimization first", "stepwise medication titration", "continued inpatient observation", "targeted specialist input"]),
        "backup_plan": random.choice(["advanced imaging", "escalated monitoring", "therapy switch", "higher-acuity transfer if needed"]),
        "overall": random.choice(["stable", "guarded", "improving", "clinically mixed"]),
        "key_risk": random.choice(["symptom recurrence", "electrolyte-related events", "overnight decompensation", "readmission within 30 days"]),
        "follow_up_plan": random.choice(["reassess tomorrow morning", "update treatment strategy after labs", "coordinate close outpatient follow-up", "revisit goals if course changes"]),
    }
    return random.choice(templates).format(**fill)


def generate_concise_doctor_note(patient, admission=None):
    """Generate a concise 1-2 sentence doctor note reflecting clinical observation, not a structured data dump."""
    cancer = patient.cancer_type or "cancer"
    unit = admission.careunit_name if admission else None

    observations = [
        f"Patient tolerating {cancer} treatment well today; no acute concerns.",
        f"Mild fatigue noted, likely treatment-related. Will continue to monitor.",
        f"Reported intermittent nausea this morning; appetite fair. No intervention needed for now.",
        f"Vitals stable overnight. Patient ambulating without difficulty.",
        f"Slight increase in lower extremity edema; adjusted fluid management.",
        f"Patient reports improved energy compared to yesterday. Continue current plan.",
        f"Noted mild tachycardia on rounds; likely volume-related. Will recheck after hydration.",
        f"Pain well-controlled on current regimen. No new complaints.",
        f"Discussed discharge planning with patient; waiting on latest lab results.",
        f"Patient anxious about treatment progress — provided reassurance and reviewed timeline.",
        f"Low-grade fever overnight (37.8°C), resolved by morning. Monitoring for recurrence.",
        f"Chest clear on auscultation. No signs of respiratory compromise.",
        f"Mild dizziness on standing; orthostatic precautions reinforced.",
        f"Lab trends improving — WBC normalizing, renal function stable.",
        f"Patient slept poorly; consider sleep hygiene consult if pattern persists.",
        f"No significant interval change. Recommend maintaining current therapeutic approach.",
        f"Noticed mild bruising at IV site; rotated access. No signs of infection.",
        f"Appetite improving, tolerated full meal. Encouraging sign for recovery trajectory.",
        f"Reviewed imaging with radiology — findings consistent with expected treatment response.",
        f"Family meeting held; discussed goals of care and next treatment cycle expectations.",
    ]

    if unit:
        location_notes = [
            f"Rounding in {unit}: patient clinically stable, no acute issues identified.",
            f"Seen in {unit} — overall impression is gradual improvement. Continue current orders.",
            f"Assessed in {unit}; plan remains unchanged pending overnight observation.",
        ]
        observations.extend(location_notes)

    return random.choice(observations)


CAREUNIT_POOL = [
    ("1", "CCU"),
    ("53", "C-SICU"),
    ("54", "CSRU"),
    ("69", "MICU"),
    ("70", "MICU-A"),
    ("72", "MSICU"),
]

DESTINATION_POOL = [
    ("30", "CC7"), ("40", "FA6A"), ("42", "FA7A"), ("54", "CSRU"),
    ("59", "CC1B"), ("60", "CC6A"), ("62", "FA2"), ("63", "FA3"),
    ("69", "MICU"), ("1", "CCU"),
]

DISCHARGE_STATUS_POOL = ["Home", "Rehab", "SNF", "Expired", "No Disch Status", "Other"]
DISCHARGE_STATUS_WEIGHTS = [0.45, 0.16, 0.15, 0.03, 0.12, 0.09]
ADMISSION_TYPE_POOL = ["emergency", "elective", "urgent"]
ADMISSION_TYPE_WEIGHTS = [0.50, 0.25, 0.25]

MEDICATION_CATALOG = [
    {"drug_name": "Acetaminophen", "dosage": "650mg", "route": "PO", "frequency": "Q6H:PRN", "schedule_hours": None, "dose_count": None},
    {"drug_name": "Aspirin", "dosage": "81mg", "route": "PO", "frequency": "QD", "schedule_hours": "10", "dose_count": 1},
    {"drug_name": "Atorvastatin", "dosage": "10mg", "route": "PO", "frequency": "QD", "schedule_hours": "22", "dose_count": 1},
    {"drug_name": "Metoprolol", "dosage": "25mg", "route": "PO", "frequency": "BID", "schedule_hours": "08,20", "dose_count": 1},
    {"drug_name": "Lisinopril", "dosage": "10mg", "route": "PO", "frequency": "QD", "schedule_hours": "09", "dose_count": 1},
    {"drug_name": "Furosemide", "dosage": "40mg", "route": "PO", "frequency": "BID", "schedule_hours": "08,16", "dose_count": 1},
    {"drug_name": "Heparin", "dosage": "5000U", "route": "SC", "frequency": "Q8H", "schedule_hours": "06,14,22", "dose_count": 1},
    {"drug_name": "Ondansetron", "dosage": "4mg", "route": "IV", "frequency": "Q6H:PRN", "schedule_hours": None, "dose_count": None},
    {"drug_name": "Dexamethasone", "dosage": "8mg", "route": "IV", "frequency": "QD", "schedule_hours": "08", "dose_count": 1},
    {"drug_name": "Amiodarone HCl", "dosage": "200mg", "route": "PO", "frequency": "BID", "schedule_hours": "08,20", "dose_count": 1},
    {"drug_name": "Pantoprazole", "dosage": "40mg", "route": "IV", "frequency": "Q24H", "schedule_hours": "06", "dose_count": 1},
    {"drug_name": "Levofloxacin", "dosage": "500mg", "route": "PO", "frequency": "Q24H", "schedule_hours": "16", "dose_count": 1},
]

PREADMISSION_MED_POOL = [
    ("Aspirin", "81mg", "QD"),
    ("Atorvastatin", "20mg", "QD"),
    ("Metoprolol", "50mg", "BID"),
    ("Lisinopril", "10mg", "QD"),
    ("Amlodipine", "5mg", "QD"),
    ("Furosemide", "20mg", "QD"),
    ("Warfarin", "5mg", "QD"),
    ("Clopidogrel", "75mg", "QD"),
    ("Levothyroxine", "50mcg", "QD"),
]


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d")


def _patient_query(limit=None):
    query: Query = Patient.query.order_by(Patient.id)
    if limit:
        query = query.limit(limit)
    return query


def _print_created_stats(label, rows):
    print(f"{label}: created {len(rows)} rows")
    for idx, row in enumerate(rows[:3], start=1):
        snapshot = {col.name: getattr(row, col.name) for col in row.__table__.columns}
        print(f"  sample{idx}: {snapshot}")


def _validate_admissions(patients):
    ok = True
    for patient in patients:
        admissions = AdmissionHistory.query.filter_by(patient_id=patient.id).order_by(AdmissionHistory.admission_date).all()
        prev_discharge = None
        for adm in admissions:
            if adm.discharge_date and adm.admission_date >= adm.discharge_date:
                ok = False
            if prev_discharge and adm.admission_date < prev_discharge:
                ok = False
            if adm.discharge_date:
                prev_discharge = adm.discharge_date
    print(f"Admission datetime validity: {'PASS' if ok else 'FAIL'}")


def _validate_io(rows):
    ok = all(r.io_total_volume_measurement_count <= r.io_event_count for r in rows)
    print(f"I/O measurement_count <= event_count: {'PASS' if ok else 'FAIL'}")


def _validate_med_exec(rows):
    ok = all(r.med_admin_execution_event_count == (r.ad_event_count + r.me_event_count + r.so_event_count) for r in rows)
    print(f"med_admin_execution_event_count = ad + me + so: {'PASS' if ok else 'FAIL'}")

# --- CLI Commands ---

@app.cli.command("create-patients")
def create_patients_cmd():
    """Creates 10 sample patients with full demo info."""
    with app.app_context():
        print("Creating 10 sample patients...")
        now = datetime.utcnow()
        patient_data = [
            {
                "name": "Yuxuan Lu", "age": 20, "gender": "Female",
                "ehr_id": "EHR-001", "alexa_user_id": "alexa-001",
                "participant_id": "test001", "garmin_id": "garmin-001",
                "cancer_type": "Breast Cancer",
                "cancer_stage": "2024-03-15",          # diagnosis date
                "treatment_type": "Penicillin",  # medication allergy history (single value)
                "treatment_plan": "AC-T Chemotherapy",
                "treatment_cycle": "Cycle 3 of 6",
                "next_appointment_date": now + timedelta(days=14),
            },
            {
                "name": "Bo Sun", "age": 45, "gender": "Male",
                "ehr_id": "EHR-002", "alexa_user_id": "alexa-002",
                "participant_id": "test002", "garmin_id": "garmin-002",
                "cancer_type": "Lung Cancer",
                "cancer_stage": "2023-11-08",
                "treatment_type": "Sulfonamides",
                "treatment_plan": "Pembrolizumab",
                "treatment_cycle": "Cycle 5 of 8",
                "next_appointment_date": now + timedelta(days=7),
            },
            {
                "name": "Dakuo Wang", "age": 30, "gender": "Female",
                "ehr_id": "EHR-003", "alexa_user_id": "alexa-003",
                "participant_id": "test003", "garmin_id": "garmin-003",
                "cancer_type": "Colon Cancer",
                "cancer_stage": "2025-01-22",
                "treatment_type": "None known",
                "treatment_plan": "Laparoscopic Colectomy",
                "treatment_cycle": "Cycle 1 of 4",
                "next_appointment_date": now + timedelta(days=21),
            },
            {
                "name": "David Wilson", "age": 60, "gender": "Male",
                "ehr_id": "EHR-004", "alexa_user_id": "alexa-004",
                "participant_id": "test004", "garmin_id": "garmin-004",
                "cancer_type": "Prostate Cancer",
                "cancer_stage": "2022-06-30",
                "treatment_type": "Codeine",
                "treatment_plan": "Enzalutamide",
                "treatment_cycle": "Ongoing maintenance",
                "next_appointment_date": now + timedelta(days=30),
            },
            {
                "name": "Menglin Zhao", "age": 55, "gender": "Female",
                "ehr_id": "EHR-005", "alexa_user_id": "alexa-005",
                "participant_id": "test005", "garmin_id": "garmin-005",
                "cancer_type": "Ovarian Cancer",
                "cancer_stage": "2024-09-12",
                "treatment_type": "Iodine",
                "treatment_plan": "Bevacizumab",
                "treatment_cycle": "Cycle 2 of 6",
                "next_appointment_date": now + timedelta(days=10),
            },
            {
                "name": "James Carter", "age": 63, "gender": "Male",
                "ehr_id": "EHR-006", "alexa_user_id": "alexa-006",
                "participant_id": "test006", "garmin_id": "garmin-006",
                "cancer_type": "Liver Cancer",
                "cancer_stage": "2024-06-21",
                "treatment_type": "No known allergies",
                "treatment_plan": "Atezolizumab",
                "treatment_cycle": "Cycle 4 of 8",
                "next_appointment_date": now + timedelta(days=9),
            },
            {
                "name": "Grace Taylor", "age": 41, "gender": "Female",
                "ehr_id": "EHR-007", "alexa_user_id": "alexa-007",
                "participant_id": "test007", "garmin_id": "garmin-007",
                "cancer_type": "Thyroid Cancer",
                "cancer_stage": "2023-12-03",
                "treatment_type": "Latex",
                "treatment_plan": "Levothyroxine Suppression",
                "treatment_cycle": "Maintenance",
                "next_appointment_date": now + timedelta(days=16),
            },
            {
                "name": "Henry Walker", "age": 68, "gender": "Male",
                "ehr_id": "EHR-008", "alexa_user_id": "alexa-008",
                "participant_id": "test008", "garmin_id": "garmin-008",
                "cancer_type": "Kidney Cancer",
                "cancer_stage": "2024-02-14",
                "treatment_type": "Sulfa",
                "treatment_plan": "Sunitinib",
                "treatment_cycle": "Cycle 2 of 6",
                "next_appointment_date": now + timedelta(days=11),
            },
            {
                "name": "Ava Martinez", "age": 34, "gender": "Female",
                "ehr_id": "EHR-009", "alexa_user_id": "alexa-009",
                "participant_id": "test009", "garmin_id": "garmin-009",
                "cancer_type": "Leukemia",
                "cancer_stage": "2025-02-10",
                "treatment_type": "Penicillin",
                "treatment_plan": "Imatinib",
                "treatment_cycle": "Cycle 1 of 4",
                "next_appointment_date": now + timedelta(days=6),
            },
            {
                "name": "Noah Anderson", "age": 52, "gender": "Male",
                "ehr_id": "EHR-010", "alexa_user_id": "alexa-010",
                "participant_id": "test010", "garmin_id": "garmin-010",
                "cancer_type": "Pancreatic Cancer",
                "cancer_stage": "2024-10-01",
                "treatment_type": "Iodine",
                "treatment_plan": "FOLFIRINOX",
                "treatment_cycle": "Cycle 3 of 12",
                "next_appointment_date": now + timedelta(days=13),
            },
        ]

        for data in patient_data:
            patient = Patient(
                name=data["name"],
                age=data["age"],
                gender=data["gender"],
                EHR_id=data["ehr_id"],
                alexa_user_id=data["alexa_user_id"],
                participant_id=data["participant_id"],
                garmin_id=data["garmin_id"],
                cancer_type=data["cancer_type"],
                cancer_stage=data["cancer_stage"],
                treatment_type=data["treatment_type"],
                treatment_plan=data["treatment_plan"],
                treatment_cycle=data["treatment_cycle"],
                next_appointment_date=data["next_appointment_date"],
                last_read_at=datetime.utcnow(),
            )
            db.session.add(patient)
        db.session.commit()
        print("Patients created successfully.")


@app.cli.command("create-admission-history")
@click.option("--patients-limit", type=int, default=None, help="Only process first N patients.")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option("--start-date", type=str, default=None, help="Admission generation window start (YYYY-MM-DD).")
@click.option("--end-date", type=str, default=None, help="Admission generation window end (YYYY-MM-DD).")
@click.option("--clear-existing", is_flag=True, help="Clear existing admission_history rows before creating.")
def create_admission_history_cmd(patients_limit, seed, start_date, end_date, clear_existing):
    """Creates 2-6 non-overlapping admission records per patient with enriched fields."""
    with app.app_context():
        if seed is not None:
            random.seed(seed)
        if clear_existing:
            AdmissionHistory.query.delete()
            db.session.commit()

        start_dt = _parse_date(start_date) or (datetime.utcnow() - timedelta(days=365))
        end_dt = _parse_date(end_date) or datetime.utcnow()
        print("Creating admission history records for all patients...")
        patients = _patient_query(patients_limit).all()
        created_rows = []
        for patient in patients:
            n_adm = random.randint(2, 6)
            segment_days = max((end_dt - start_dt).days // n_adm, 5)
            prev_discharge = None
            for idx in range(n_adm):
                seg_start = start_dt + timedelta(days=idx * segment_days)
                seg_end = min(end_dt - timedelta(days=2), seg_start + timedelta(days=segment_days - 1))
                if prev_discharge and seg_start <= prev_discharge:
                    seg_start = prev_discharge + timedelta(hours=random.randint(6, 36))
                if seg_start >= seg_end:
                    seg_end = seg_start + timedelta(days=2)

                admission_date = create_random_datetime(seg_start, seg_end)
                still_admitted = (idx == n_adm - 1 and random.random() < 0.15)
                discharge_date = None if still_admitted else admission_date + timedelta(days=random.randint(1, 18), hours=random.randint(0, 20))
                if discharge_date and discharge_date <= admission_date:
                    discharge_date = admission_date + timedelta(hours=8)

                readmission_flag = False
                if prev_discharge:
                    readmission_flag = (admission_date - prev_discharge).days <= 30

                cu_id, cu_name = random.choice(CAREUNIT_POOL)
                du_id, du_name = random.choice(DESTINATION_POOL)
                discharge_status = None if still_admitted else random.choices(DISCHARGE_STATUS_POOL, weights=DISCHARGE_STATUS_WEIGHTS, k=1)[0]
                admission_type = random.choices(ADMISSION_TYPE_POOL, weights=ADMISSION_TYPE_WEIGHTS, k=1)[0]
                los_minutes = None
                if discharge_date:
                    los_minutes = int((discharge_date - admission_date).total_seconds() // 60)

                adm = AdmissionHistory(
                    patient_id=patient.id,
                    admission_date=admission_date,
                    discharge_date=discharge_date,
                    diagnosis=random.choice([
                        "Chemotherapy Initiation",
                        "Chemotherapy Complications",
                        "Congestive Heart Failure",
                        "Coronary Artery Disease",
                        "Pneumonia",
                        "Acute Coronary Syndrome",
                        "Hypoxia",
                    ]),
                    symptoms=random.choice([
                        "Nausea, fatigue, mild chest discomfort",
                        "Syncope, palpitations, shortness of breath",
                        "Leg swelling, exertional dyspnea",
                        "Intermittent dizziness, poor appetite",
                    ]),
                    notes=random.choice([
                        "Adjusted dosage and arranged telemetry monitoring.",
                        "Observed overnight for rhythm instability.",
                        "Improved after supportive care and medication optimization.",
                    ]),
                    careunit_id=cu_id,
                    careunit_name=cu_name,
                    destination_unit_id=du_id,
                    destination_unit_name=du_name,
                    discharge_status=discharge_status,
                    admission_type=admission_type,
                    readmission_flag=readmission_flag,
                    los_minutes=los_minutes,
                )
                db.session.add(adm)
                created_rows.append(adm)
                if discharge_date:
                    prev_discharge = discharge_date
        db.session.commit()
        _print_created_stats("admission_history", created_rows)
        _validate_admissions(patients)
        print("Admission history records created successfully.")


@app.cli.command("create-summaries")
def create_summaries_cmd():
    """Creates 10 days of summary records (today-9 to today) for each patient."""
    with app.app_context():
        from .symptoms import symptom_descriptions
        print("Creating 10-day summary records for all patients...")
        patients = Patient.query.all()
        now_naive = datetime.now(EASTERN_TZ).replace(tzinfo=None)
        now_midnight = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
        for patient in patients:
            for days_ago in range(9, -1, -1):  # 9 days ago → today
                day = now_midnight - timedelta(days=days_ago)
                summary = Summary(patient_id=patient.id, date=day, read=0)
                for symptom_name in symptom_descriptions:
                    # heart_rate / respiration are wearable-driven (MongoDB), do not synthesize green state here
                    if symptom_name in ("heart_rate", "respiration"):
                        setattr(summary, f"{symptom_name}_state", 0)
                        setattr(summary, f"{symptom_name}_logs", "[]")
                        continue
                    # conversation symptoms use synthetic states
                    state_val = random.randint(0, 3)
                    setattr(summary, f"{symptom_name}_state", state_val)
                    setattr(summary, f"{symptom_name}_logs", "[]")
                    if symptom_descriptions[symptom_name].get("likert", False):
                        scale_val = random.randint(1, 10) if state_val >= 2 else 0
                        setattr(summary, f"{symptom_name}_scale", scale_val)
                db.session.add(summary)
        db.session.commit()
        print("10-day summaries created successfully.")


@app.cli.command("create-risks")
def create_risks_cmd():
    """Creates 20 continuous risk records for each existing patient."""
    with app.app_context():
        print("Creating 20 continuous risk records for each patient...")
        patients = Patient.query.all()
        for patient in patients:
            # Generate 20 days of data starting from 19 days ago up to today
            for i in range(20):
                current_date = datetime.utcnow() - timedelta(days=19 - i) 
                risk = Risk(
                    patient_id=patient.id,
                    risk_score=generate_random_float(0.1, 0.9),
                    important_of_chest=generate_random_float(0.01, 0.3),
                    important_of_heart=generate_random_float(0.01, 0.3),
                    important_of_respiration=generate_random_float(0.01, 0.3),
                    important_of_hrv=generate_random_float(0.01, 0.3),
                    date=current_date # Use current_date for continuous records
                )
                db.session.add(risk)
        db.session.commit()
        print("Continuous risk records created successfully.")


@app.cli.command("generate-conversation-logs")
def generate_conversation_logs_cmd():
    # Map conversation symptom keys → backend symptom keys
    CONV_TO_SYMPTOM = {
        "breath":      "short_of_breath",
        "chest":       "chest_discomfort",
        "fatigue":     "fatigue",
        "palpitation": "palpitation",
        "swelling":    "swelling",
        "syncope":     "syncope",
    }

    def simulate_conversation():
        has_symptoms = random.random() < 0.5
        active_symptoms = []
        if has_symptoms:
            possible_symptoms = list(CONV_TO_SYMPTOM.keys())
            active_symptoms = random.sample(possible_symptoms, k=random.randint(1, 2))

        all_questions = list(CONV_TO_SYMPTOM.keys())
        num_skip = random.choices([0, 1, 2], weights=[0.5, 0.35, 0.15])[0]
        skipped = random.sample(all_questions, k=num_skip) if num_skip else []
        checklist = [q for q in all_questions if q not in skipped]
        random.shuffle(checklist)

        messages = []
        # symptom_msg_indices: backend_key → list of indices in messages[]
        # that are the meaningful back-and-forth about that symptom (for log highlighting)
        symptom_msg_indices = {}
        # symptom_scales: backend_key → numeric 1–10 severity taken from the scripted dialogue
        symptom_scales = {}

        messages.append(("assistant", "Hello, this is the Cardio research study chatbot assistant developed by Northeastern University Human-centered AI lab. Are you ready to start today's questions?"))
        messages.append(("user", "Yes, I am ready."))

        extracted_symptoms_chest = None
        extracted_symptoms_other = []

        question_map = {
            "breath":      "Are you having difficulty breathing or feeling short of breath?",
            "chest":       "Are you experiencing any chest pain, pressure, or discomfort?",
            "fatigue":     "Have you been feeling unusually tired, weak, or fatigued?",
            "palpitation": "Have you felt like your heart is racing, pounding, fluttering, or skipping beats?",
            "swelling":    "Have you noticed any new or worsening swelling, particularly in your legs, ankles, or feet?",
            "syncope":     "Have you fainted, passed out, or felt very dizzy like you might pass out?",
        }

        for item in checklist:
            q_idx = len(messages)
            messages.append(("assistant", question_map[item]))

            if item in active_symptoms:
                idx_before = len(messages)
                if item == "breath":
                    messages.append(("user", "Yes, a little bit."))
                    messages.append(("assistant", "Tell me about your shortness of breath, when does it usually happen?"))
                    messages.append(("user", "Mostly when I walk up the stairs."))
                    messages.append(("assistant", "On a scale of 1 to 10, with 10 being the most difficult, how would you rate it?"))
                    messages.append(("user", "About a 4."))
                    extracted_symptoms_other.append("shortness of breath (4/10)")
                    symptom_scales[CONV_TO_SYMPTOM[item]] = 4
                elif item == "chest":
                    messages.append(("user", "Yes, I feel some pressure."))
                    messages.append(("assistant", "I'm sorry to hear that. Can you describe where you feel the pain and what it feels like?"))
                    messages.append(("user", "It's on the left side, kind of a dull ache."))
                    messages.append(("assistant", "On a scale of 1 to 10, how would you rate your chest discomfort?"))
                    messages.append(("user", "It's a 3, not too bad."))
                    extracted_symptoms_chest = "left side dull ache (3/10)"
                    symptom_scales[CONV_TO_SYMPTOM[item]] = 3
                elif item == "fatigue":
                    messages.append(("user", "Yes, I have felt more tired today."))
                    messages.append(("assistant", "Can you tell me more? Is it affecting your normal daily activities?"))
                    messages.append(("user", "I feel tired after basic tasks."))
                    extracted_symptoms_other.append("fatigue)")
                elif item == "palpitation":
                    messages.append(("user", "Yes, sometimes."))
                    messages.append(("assistant", "How often are you noticing this, and when did it start?"))
                    messages.append(("user", "Started this morning, happens every hour."))
                    messages.append(("assistant", "Does this happen when you are resting or only when you are active?"))
                    messages.append(("user", "Even when resting."))
                    extracted_symptoms_other.append("palpitations (resting)")
                elif item == "swelling":
                    messages.append(("user", "Yes, my ankles look puffy."))
                    messages.append(("assistant", "Tell me more about the swelling. Is it in one leg or both?"))
                    messages.append(("user", "Both ankles."))
                    extracted_symptoms_other.append("swelling in ankles")
                elif item == "syncope":
                    messages.append(("user", "Yes, I felt dizzy earlier."))
                    messages.append(("assistant", "That sounds concerning. Did you actually lose consciousness or fall down?"))
                    messages.append(("user", "No, just dizzy."))
                    messages.append(("assistant", "What were you doing when this happened?"))
                    messages.append(("user", "I stood up too fast."))
                    extracted_symptoms_other.append("dizziness (stood up fast)")
                # Track all message indices from the question through the exchange
                symptom_msg_indices[CONV_TO_SYMPTOM[item]] = list(range(q_idx, len(messages)))
            else:
                messages.append(("user", "No."))
                # Even when the patient denies the symptom, record the Q+A as logs
                symptom_msg_indices[CONV_TO_SYMPTOM[item]] = list(range(q_idx, len(messages)))

        messages.append(("assistant", "Is there anything else you'd like to comment on that I haven't asked about?"))
        messages.append(("user", "No, that's all."))
        messages.append(("assistant", "CONVERSATION_END Thank you for your time to provide information today. We'll talk again tomorrow."))

        cot_simulation = "breath: discussed\nchest: discussed\npalpitation: discussed\nswelling: discussed\nsyncope: discussed\nmisc: discussed\n==============\nAll checks completed. Proceeding to wrap up."
        symptoms_other_str = ", ".join(extracted_symptoms_other) if extracted_symptoms_other else None

        return {
            "messages": messages,
            "symptom_msg_indices": symptom_msg_indices,
            "symptom_scales": symptom_scales,
            "active_symptoms": [CONV_TO_SYMPTOM[k] for k in active_symptoms],
            "skipped_symptoms": [CONV_TO_SYMPTOM[k] for k in skipped],
            "chain_of_thoughts": cot_simulation,
            "symptoms_chest": extracted_symptoms_chest,
            "symptoms_other": symptoms_other_str,
        }

    with app.app_context():
        from .symptoms import symptom_descriptions
        print("Generating conversation logs for all patients...")
        patients = Patient.query.all()
        # Rebuild logs from scratch to avoid duplicated/misaligned history.
        ConversationLog.query.delete()
        db.session.flush()

        now_naive = datetime.now(EASTERN_TZ).replace(tzinfo=None)
        for patient in patients:
            for i in range(10):
                log_date = now_naive - timedelta(days=9 - i)
                day_start = log_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                log_data = simulate_conversation()
                messages = log_data["messages"]
                symptom_msg_indices = log_data["symptom_msg_indices"]
                symptom_scales = log_data["symptom_scales"]
                active_symptoms = log_data["active_symptoms"]
                skipped_symptoms = log_data["skipped_symptoms"]
                cot = log_data["chain_of_thoughts"]
                symptoms_chest = log_data["symptoms_chest"]
                symptoms_other = log_data["symptoms_other"]

                # Insert messages and keep object references to get IDs after flush
                log_objects = []
                minute_cursor = random.randint(8 * 60, 10 * 60)
                for idx, (role, content) in enumerate(messages):
                    is_last = idx == len(messages) - 1
                    # Keep strict chronological order so UI never shows role-order inversions.
                    if idx > 0:
                        minute_cursor += random.randint(2, 4)
                    minute_of_day = min(minute_cursor, 23 * 60 + 59)
                    msg_time = day_start + timedelta(
                        minutes=minute_of_day,
                        seconds=min(idx * 2, 59),
                    )
                    log = ConversationLog(
                        patient_id=patient.id,
                        role=role,
                        content=content,
                        chain_of_thoughts=cot if is_last else None,
                        symptoms_chest=symptoms_chest if is_last else None,
                        symptoms_other=symptoms_other if is_last else None,
                        date=msg_time,
                    )
                    db.session.add(log)
                    log_objects.append(log)

                # Flush to get DB-assigned IDs without full commit
                db.session.flush()

                # Update the Summary for this day with correct symptom states + log IDs
                summary = Summary.query.filter_by(patient_id=patient.id).filter(
                    Summary.date >= day_start, Summary.date < day_end
                ).first()
                if summary is None:
                    summary = Summary(patient_id=patient.id, date=day_start, read=0)
                    for symptom_name in symptom_descriptions:
                        setattr(summary, f"{symptom_name}_state", 0)
                        setattr(summary, f"{symptom_name}_logs", "[]")
                        if symptom_descriptions[symptom_name].get("likert", False):
                            setattr(summary, f"{symptom_name}_scale", 0)
                    db.session.add(summary)
                    db.session.flush()
                if summary:
                    all_log_ids = [obj.id for obj in log_objects]
                    for symptom_name in symptom_descriptions:
                        if symptom_name in ("heart_rate", "respiration"):
                            # Allow colored wearable dots to navigate to same-day conversation logs.
                            setattr(summary, f"{symptom_name}_logs", json.dumps(all_log_ids))
                            continue
                        if symptom_name in skipped_symptoms:
                            setattr(summary, f"{symptom_name}_state", 0)
                            setattr(summary, f"{symptom_name}_logs", "[]")
                            if symptom_descriptions[symptom_name].get("likert", False):
                                setattr(summary, f"{symptom_name}_scale", 0)
                        elif symptom_name in active_symptoms:
                            indices = symptom_msg_indices.get(symptom_name, [])
                            log_ids = [log_objects[idx].id for idx in indices if idx < len(log_objects)]
                            setattr(summary, f"{symptom_name}_state", 2)
                            setattr(summary, f"{symptom_name}_logs", json.dumps(log_ids))
                            if symptom_descriptions[symptom_name].get("likert", False):
                                scale_val = int(symptom_scales.get(symptom_name, 0) or 0)
                                scale_val = max(1, min(10, scale_val)) if scale_val > 0 else 0
                                setattr(summary, f"{symptom_name}_scale", scale_val)
                        else:
                            # Discussed but symptom not present (patient answered "No.")
                            indices = symptom_msg_indices.get(symptom_name, [])
                            log_ids = [log_objects[idx].id for idx in indices if idx < len(log_objects)]
                            setattr(summary, f"{symptom_name}_state", 1)
                            setattr(summary, f"{symptom_name}_logs", json.dumps(log_ids))
                            if symptom_descriptions[symptom_name].get("likert", False):
                                setattr(summary, f"{symptom_name}_scale", 0)
                    db.session.add(summary)

        db.session.commit()
        print("Conversation logs and summaries updated successfully.")

@app.cli.command("create-user")
@click.option("--username", required=True, type=str, help="Username for the new user")
@click.option("--password", required=True, type=str, help="Password for the new user")
@click.option("--email", required=True, type=str, help="Email for the new user")
@click.option("--name", required=True, type=str, help="Real name for the new user")
def create_user_cmd(username, password, email, name):
    """Creates a new user."""
    with app.app_context():
        print(f"Creating user with username {username}")

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            print(f"User with username '{username}' or email '{email}' already exists.")
            return

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        user = User(username=username, password=hashed_password, email=email, name=name)
        db.session.add(user)
        db.session.commit()

        print(f"User '{username}' created successfully.")

@app.cli.command("reset-password")
@click.option("--username", required=True, type=str, help="Username for the user")
@click.option("--password", required=True, type=str, help="New password for the user")
def reset_password_cmd(username, password):
    """Resets the password for an existing user."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"User with username '{username}' does not exist.")
            return

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        user.password = hashed_password
        db.session.commit()

        print(f"Password for user '{username}' reset successfully.")


@app.cli.command("assign-patient")
@click.option("--user-id", required=True, type=int, help="ID of the user")
@click.option("--patient-id", required=True, type=int, help="ID of the patient")
def assign_patient_cmd(user_id, patient_id):
    """Assigns a patient to a user (many-to-many relationship)."""
    with app.app_context():
        print(f"Assigning patient with ID {patient_id} to user with ID {user_id}")

        user = User.query.get(user_id)
        patient = Patient.query.get(patient_id)

        if not user:
            print(f"User with ID '{user_id}' does not exist.")
            return

        if not patient:
            print(f"Patient with ID '{patient_id}' does not exist.")
            return

        # Check whether the relation exists
        if patient in user.patients:
            print(
                f"User with ID '{user_id}' already has access to patient with ID '{patient_id}'."
            )
            return

        user.patients.append(patient)
        db.session.commit()

        print(
            f"Patient with ID '{patient_id}' assigned to user with ID '{user_id}' successfully."
        )


@app.cli.command("create-single-patient")
@click.option("--name", required=True, type=str)
@click.option("--age", required=True, type=int)
@click.option("--gender", required=True, type=str)
@click.option("--ehr-id", required=True, type=str)
@click.option("--alexa-user-id", type=str, default=None)
@click.option("--participant-id", type=str, default=None)
@click.option("--garmin-id", type=str, default=None)
@click.option("--cancer-type", type=str, default=None)
@click.option("--cancer-stage", type=str, default=None)
@click.option("--treatment-type", type=str, default=None)
def create_single_patient_cmd(
    name, age, gender, ehr_id, alexa_user_id, participant_id, garmin_id,
    cancer_type, cancer_stage, treatment_type
):
    """Creates a single patient with specified details."""
    with app.app_context():
        print(f"Creating patient: {name}")
        patient = Patient(
            name=name,
            age=age,
            gender=gender,
            EHR_id=ehr_id,
            alexa_user_id=alexa_user_id,
            participant_id=participant_id,
            garmin_id=garmin_id,
            cancer_type=cancer_type,
            cancer_stage=cancer_stage,
            treatment_type=treatment_type,
            last_read_at=datetime.utcnow()
        )
        db.session.add(patient)
        db.session.commit()
        print(f"Patient '{name}' created successfully with ID: {patient.id}")


@app.cli.command("create-alexa-note")
@click.option("--alexa-user-id", required=True, type=str, help="Alexa User ID")
def create_alexa_note_cmd(alexa_user_id):
    """Creates an AlexaIDNote record."""
    with app.app_context():
        existing_note = AlexaIDNote.query.filter_by(alexa_user_id=alexa_user_id).first()
        if existing_note:
            print(f"AlexaIDNote for '{alexa_user_id}' already exists.")
            return

        note = AlexaIDNote(alexa_user_id=alexa_user_id)
        db.session.add(note)
        db.session.commit()
        print(f"AlexaIDNote for '{alexa_user_id}' created successfully.")


@app.cli.command("create-medications")
@click.option("--patients-limit", type=int, default=None, help="Only process first N patients.")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option("--clear-existing", is_flag=True, help="Clear existing medication rows before creating.")
def create_medications_cmd(patients_limit, seed, clear_existing):
    """Creates 4-20 medication records per patient and fills enriched medication fields."""
    with app.app_context():
        if seed is not None:
            random.seed(seed)
        if clear_existing:
            Medication.query.delete()
            db.session.commit()

        print("Creating medication records for all patients...")
        now = datetime.utcnow()
        users = User.query.all()
        recorder_id = users[0].id if users else None
        patients = _patient_query(patients_limit).all()
        created_rows = []
        for patient in patients:
            medication_count = random.randint(4, 20)
            for _ in range(medication_count):
                tpl = random.choice(MEDICATION_CATALOG)
                start_days = random.randint(10, 240)
                start = now - timedelta(days=start_days)
                if random.random() < 0.62:
                    end = None
                else:
                    end_offset = random.randint(1, max(2, start_days - 1))
                    end = now - timedelta(days=end_offset)
                is_current = (end is None) or (end > now)

                med = Medication(
                    patient_id=patient.id,
                    drug_name=tpl["drug_name"],
                    dosage=tpl["dosage"],
                    start_date=start,
                    end_date=end,
                    recorded_by_user_id=recorder_id,
                    route=tpl["route"],
                    frequency=tpl["frequency"],
                    schedule_hours=tpl["schedule_hours"],
                    dose_count=tpl["dose_count"],
                    is_current_medication=is_current,
                    order_source=random.choice(["inpatient_order", "outpatient_list", "imported"]),
                )
                db.session.add(med)
                created_rows.append(med)
        db.session.commit()
        _print_created_stats("medication", created_rows)
        print("Medication records created successfully.")


@app.cli.command("create-preadmission-medications")
@click.option("--patients-limit", type=int, default=None, help="Only process first N patients.")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option("--clear-existing", is_flag=True, help="Clear existing preadmission medication rows before creating.")
def create_preadmission_medications_cmd(patients_limit, seed, clear_existing):
    """Creates 0-8 baseline preadmission medications per patient."""
    with app.app_context():
        if seed is not None:
            random.seed(seed)
        if clear_existing:
            PreadmissionMedication.query.delete()
            db.session.commit()

        patients = _patient_query(patients_limit).all()
        created_rows = []
        print("Creating preadmission medication records...")
        for patient in patients:
            first_adm = AdmissionHistory.query.filter_by(patient_id=patient.id).order_by(AdmissionHistory.admission_date).first()
            row_count = random.randint(1, 8)
            meds = random.sample(PREADMISSION_MED_POOL, k=min(row_count, len(PREADMISSION_MED_POOL)))
            names = []
            for drug_name, dosage, frequency in meds:
                started_date = None
                if first_adm:
                    started_date = first_adm.admission_date - timedelta(days=random.randint(14, 540))
                pm = PreadmissionMedication(
                    patient_id=patient.id,
                    admission_history_id=first_adm.id if first_adm else None,
                    drug_name=drug_name,
                    dosage=dosage,
                    frequency=frequency,
                    started_before_admission_date=started_date,
                    source_text=f"Baseline med from history: {drug_name} {dosage} {frequency}",
                    active_at_admission=random.random() < 0.8,
                )
                db.session.add(pm)
                created_rows.append(pm)
                names.append(drug_name)

        db.session.commit()
        _print_created_stats("preadmission_medication", created_rows)
        print("Preadmission medication records created successfully.")


@app.cli.command("create-io-metrics")
@click.option("--patients-limit", type=int, default=None, help="Only process first N patients.")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option("--clear-existing", is_flag=True, help="Clear existing io_metric rows before creating.")
def create_io_metrics_cmd(patients_limit, seed, clear_existing):
    """Creates I/O aggregate metrics per patient per admission day."""
    with app.app_context():
        if seed is not None:
            random.seed(seed)
        if clear_existing:
            IOMetric.query.delete()
            db.session.commit()

        patients = _patient_query(patients_limit).all()
        created_rows = []
        print("Creating I/O metrics...")
        for patient in patients:
            admissions = AdmissionHistory.query.filter_by(patient_id=patient.id).all()
            for adm in admissions:
                end = adm.discharge_date or datetime.utcnow()
                days = max((end.date() - adm.admission_date.date()).days + 1, 1)
                for day_offset in range(days):
                    metric_date = adm.admission_date.date() + timedelta(days=day_offset)
                    # long-tail event distribution: many moderate, some very high
                    io_event_count = min(220, max(5, int(random.lognormvariate(3.2, 0.65))))
                    io_total_volume_measurement_count = random.randint(max(1, int(io_event_count * 0.65)), io_event_count)
                    # positive correlation with measurement count
                    per_measurement_volume = random.uniform(35.0, 110.0)
                    io_total_volume_ml = round(io_total_volume_measurement_count * per_measurement_volume, 2)

                    io_row = IOMetric(
                        patient_id=patient.id,
                        admission_history_id=adm.id,
                        metric_date=metric_date,
                        io_event_count=io_event_count,
                        io_total_volume_ml=io_total_volume_ml,
                        io_total_volume_measurement_count=io_total_volume_measurement_count,
                    )
                    db.session.add(io_row)
                    created_rows.append(io_row)
        db.session.commit()
        _print_created_stats("io_metric", created_rows)
        _validate_io(created_rows)
        print("I/O metrics created successfully.")


@app.cli.command("create-med-admin-executions")
@click.option("--patients-limit", type=int, default=None, help="Only process first N patients.")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option("--clear-existing", is_flag=True, help="Clear existing medication_execution_metric rows before creating.")
def create_med_admin_executions_cmd(patients_limit, seed, clear_existing):
    """Creates medication administration execution aggregates per admission day."""
    with app.app_context():
        if seed is not None:
            random.seed(seed)
        if clear_existing:
            MedicationExecutionMetric.query.delete()
            db.session.commit()

        patients = _patient_query(patients_limit).all()
        created_rows = []
        print("Creating medication execution metrics...")
        for patient in patients:
            med_order_count = Medication.query.filter_by(patient_id=patient.id).count()
            admissions = AdmissionHistory.query.filter_by(patient_id=patient.id).all()
            for adm in admissions:
                end = adm.discharge_date or datetime.utcnow()
                los_days = max((end.date() - adm.admission_date.date()).days + 1, 1)
                for day_offset in range(los_days):
                    metric_date = adm.admission_date.date() + timedelta(days=day_offset)
                    base = max(8, int((med_order_count * 0.6) + (los_days * random.uniform(0.8, 2.0))))
                    me_event_count = max(1, int(base * random.uniform(0.70, 0.85)))
                    so_event_count = max(0, int(base * random.uniform(0.05, 0.15)))
                    ad_event_count = max(0, int(base * random.uniform(0.02, 0.08)))
                    med_admin_execution_event_count = ad_event_count + me_event_count + so_event_count

                    row = MedicationExecutionMetric(
                        patient_id=patient.id,
                        admission_history_id=adm.id,
                        metric_date=metric_date,
                        ad_event_count=ad_event_count,
                        me_event_count=me_event_count,
                        so_event_count=so_event_count,
                        med_admin_execution_event_count=med_admin_execution_event_count,
                    )
                    db.session.add(row)
                    created_rows.append(row)
        db.session.commit()
        _print_created_stats("medication_execution_metric", created_rows)
        _validate_med_exec(created_rows)
        print("Medication execution metrics created successfully.")


@app.cli.command("generate-notes")
def generate_notes_cmd():
    """Generates structured doctor-authored notes only."""
    with app.app_context():
        print("Generating user notes for patients...")
        patients = Patient.query.all()
        users = User.query.all()
        if not users:
            print("No users found. Please create a user first with 'flask create-user'.")
            return
        # Only regenerate user-authored notes; keep AI notes managed by generate-ai-summaries.
        Note.query.filter_by(creator_type="user").delete()
        db.session.flush()

        now_naive = datetime.now(EASTERN_TZ).replace(tzinfo=None)
        now = now_naive.replace(hour=8, minute=0, second=0, microsecond=0)
        created_rows = []
        for patient in patients:
            admissions = AdmissionHistory.query.filter_by(patient_id=patient.id).order_by(AdmissionHistory.admission_date).all()
            summary_days = (
                Summary.query.filter_by(patient_id=patient.id)
                .order_by(Summary.date.asc())
                .all()
            )
            valid_days = [
                s.date.replace(hour=0, minute=0, second=0, microsecond=0)
                for s in summary_days
                if s.date and (now_naive - s.date.replace(hour=0, minute=0, second=0, microsecond=0)).days <= 9
            ]
            if not valid_days:
                valid_days = [
                    now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=d)
                    for d in range(9, -1, -1)
                ]

            # 3~8 random user notes spread across admission periods
            for _ in range(random.randint(3, 8)):
                base_day = random.choice(valid_days)
                note_time = base_day.replace(
                    hour=random.randint(9, 20),
                    minute=random.randint(0, 59),
                    second=0,
                    microsecond=0,
                )

                same_day_admission = None
                for adm in admissions:
                    adm_end = adm.discharge_date or now
                    if adm.admission_date <= note_time <= adm_end:
                        same_day_admission = adm
                        break

                note_content = generate_concise_doctor_note(patient, same_day_admission)

                user_note = Note(
                    patient_id=patient.id,
                    user_id=random.choice(users).id,
                    creator_type="user",
                    content=note_content,
                    created_at=note_time,
                )
                db.session.add(user_note)
                created_rows.append(user_note)
        db.session.commit()
        _print_created_stats("doctor_notes", created_rows)
        print("User notes generated successfully.")


@app.cli.command("generate-ai-summaries")
def generate_ai_summaries_cmd():
    """Regenerates AI notes for the latest 10 report days per patient."""
    with app.app_context():
        from .symptoms import symptom_descriptions

        def build_fallback_ai_summary(summary):
            if summary is None:
                return "AI Summary: No conversation or wearable records available for today."

            active_parts = []
            for symptom_name, symptom_meta in symptom_descriptions.items():
                if symptom_name in ("heart_rate", "respiration"):
                    continue
                state_val = int(getattr(summary, f"{symptom_name}_state", 0) or 0)
                if state_val < 2:
                    continue
                label = symptom_meta.get("display_name", symptom_name.replace("_", " ").title())
                if symptom_meta.get("likert", False):
                    scale_val = int(getattr(summary, f"{symptom_name}_scale", 0) or 0)
                    if scale_val > 0:
                        active_parts.append(f"{label} ({scale_val}/10)")
                        continue
                active_parts.append(label)

            wearable_parts = []
            hr = getattr(summary, "heart_rate_average", None)
            resp = getattr(summary, "respiration_average", None)
            hrv = getattr(summary, "hrv_average", None)
            if hr is not None:
                wearable_parts.append(f"HR avg {round(float(hr), 1)} bpm")
            if resp is not None:
                wearable_parts.append(f"Resp avg {round(float(resp), 1)} bpm")
            if hrv is not None:
                wearable_parts.append(f"HRV avg {round(float(hrv), 1)} ms")

            if active_parts and wearable_parts:
                return f"AI Summary: Reported symptoms: {', '.join(active_parts)}. Wearable overview: {', '.join(wearable_parts)}."
            if active_parts:
                return f"AI Summary: Reported symptoms: {', '.join(active_parts)}."
            if wearable_parts:
                return f"AI Summary: Wearable overview: {', '.join(wearable_parts)}."
            return "AI Summary: No significant symptoms reported today; continue routine monitoring."

        def et_day_window_to_utc(day_start_naive):
            day_end_naive = day_start_naive + timedelta(days=1)
            start_utc = (
                day_start_naive.replace(tzinfo=EASTERN_TZ)
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
            end_utc = (
                day_end_naive.replace(tzinfo=EASTERN_TZ)
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
            return start_utc, end_utc

        print("Regenerating AI summaries for latest 10 days...")
        patients = Patient.query.all()
        Note.query.filter_by(creator_type="ai").delete()
        db.session.flush()

        now_naive = datetime.now(EASTERN_TZ).replace(tzinfo=None)
        generated_count = 0
        fallback_count = 0

        for patient in patients:
            summary_days = (
                Summary.query.filter_by(patient_id=patient.id)
                .order_by(Summary.date.asc())
                .all()
            )
            valid_days = [
                s.date.replace(hour=0, minute=0, second=0, microsecond=0)
                for s in summary_days
                if s.date and (now_naive - s.date.replace(hour=0, minute=0, second=0, microsecond=0)).days <= 9
            ]
            valid_days = sorted(set(valid_days))
            if len(valid_days) > 10:
                valid_days = valid_days[-10:]
            if not valid_days:
                valid_days = [
                    now_naive.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=d)
                    for d in range(9, -1, -1)
                ]

            for day_start in valid_days:
                note_window_start, note_window_end = et_day_window_to_utc(day_start)
                day_end = day_start + timedelta(days=1)
                try:
                    _generate_ai_note_for_patient(patient.id, day_start)
                except Exception as e:
                    print(f"  AI generation skipped for patient {patient.id} {day_start.date()}: {e}")

                existing = (
                    Note.query.filter_by(patient_id=patient.id, creator_type="ai")
                    .filter(Note.created_at >= note_window_start, Note.created_at < note_window_end)
                    .first()
                )
                if existing is None:
                    summary = (
                        Summary.query.filter_by(patient_id=patient.id)
                        .filter(Summary.date >= day_start, Summary.date < day_end)
                        .first()
                    )
                    db.session.add(
                        Note(
                            patient_id=patient.id,
                            user_id=None,
                            creator_type="ai",
                            content=build_fallback_ai_summary(summary),
                            created_at=(
                                day_start.replace(hour=20, minute=0, second=0, microsecond=0)
                                .replace(tzinfo=EASTERN_TZ)
                                .astimezone(timezone.utc)
                                .replace(tzinfo=None)
                            ),
                        )
                    )
                    fallback_count += 1
                generated_count += 1

        db.session.commit()
        print(f"AI summaries generated for {generated_count} patient-day rows.")
        if fallback_count:
            print(f"Fallback AI summaries used: {fallback_count}")


@app.cli.command("sync-today-ai-summaries")
def sync_today_ai_summaries_cmd():
    """Create today's AI note at ET midnight and refresh it when data is available."""
    with app.app_context():
        day_start = datetime.now(EASTERN_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        )
        day_end = day_start + timedelta(days=1)
        note_window_start = (
            day_start.replace(tzinfo=EASTERN_TZ).astimezone(timezone.utc).replace(tzinfo=None)
        )
        note_window_end = (
            day_end.replace(tzinfo=EASTERN_TZ).astimezone(timezone.utc).replace(tzinfo=None)
        )
        note_time = (
            day_start.replace(hour=0, minute=0, second=0, microsecond=0)
            .replace(tzinfo=EASTERN_TZ)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        placeholder = "AI Summary: No valid conversation or wearable data available for today."

        print(f"Syncing AI summaries for {day_start.date()}...")
        patients = Patient.query.all()
        created = 0
        updated = 0
        refreshed = 0

        for patient in patients:
            existing = (
                Note.query.filter_by(patient_id=patient.id, creator_type="ai")
                .filter(Note.created_at >= note_window_start, Note.created_at < note_window_end)
                .first()
            )
            if existing is None:
                db.session.add(
                    Note(
                        patient_id=patient.id,
                        user_id=None,
                        creator_type="ai",
                        content=placeholder,
                        created_at=note_time,
                    )
                )
                created += 1
            else:
                if not (existing.content or "").strip():
                    existing.content = placeholder
                    existing.created_at = note_time
                    updated += 1

            has_logs = (
                ConversationLog.query.filter_by(patient_id=patient.id)
                .filter(ConversationLog.date >= day_start, ConversationLog.date < day_end)
                .count()
                > 0
            )
            summary = (
                Summary.query.filter_by(patient_id=patient.id)
                .filter(Summary.date >= day_start, Summary.date < day_end)
                .first()
            )
            has_wearable = False
            if summary is not None:
                has_wearable = any(
                    getattr(summary, field, None) is not None
                    for field in ("heart_rate_average", "respiration_average", "hrv_average")
                )

            if has_logs or has_wearable:
                _generate_ai_note_for_patient(patient.id, day_start)
                refreshed += 1

        db.session.commit()
        print(f"Created placeholders: {created}")
        print(f"Updated empty placeholders: {updated}")
        print(f"Refreshed from data: {refreshed}")


@app.cli.command("seed-clinical-details")
@click.option("--patients-limit", type=int, default=None, help="Only process first N patients.")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility.")
@click.option("--start-date", type=str, default=None, help="Admission generation window start (YYYY-MM-DD).")
@click.option("--end-date", type=str, default=None, help="Admission generation window end (YYYY-MM-DD).")
@click.option("--clear-existing", is_flag=True, help="Clear related tables before seeding.")
def seed_clinical_details_cmd(patients_limit, seed, start_date, end_date, clear_existing):
    """One-click seeding pipeline for clinical-detail tables and notes."""
    with app.app_context():
        if clear_existing:
            Note.query.delete()
            MedicationExecutionMetric.query.delete()
            IOMetric.query.delete()
            PreadmissionMedication.query.delete()
            Medication.query.delete()
            AdmissionHistory.query.delete()
            db.session.commit()
            print("Cleared existing related records.")

    ctx = click.get_current_context()
    ctx.invoke(
        create_admission_history_cmd,
        patients_limit=patients_limit,
        seed=seed,
        start_date=start_date,
        end_date=end_date,
        clear_existing=False,
    )
    ctx.invoke(create_medications_cmd, patients_limit=patients_limit, seed=seed, clear_existing=False)
    ctx.invoke(create_preadmission_medications_cmd, patients_limit=patients_limit, seed=seed, clear_existing=False)
    ctx.invoke(create_io_metrics_cmd, patients_limit=patients_limit, seed=seed, clear_existing=False)
    ctx.invoke(create_med_admin_executions_cmd, patients_limit=patients_limit, seed=seed, clear_existing=False)
    ctx.invoke(generate_notes_cmd)

    with app.app_context():
        patients = _patient_query(patients_limit).all()
        min_ok = True
        for patient in patients:
            if AdmissionHistory.query.filter_by(patient_id=patient.id).count() < 1:
                min_ok = False
            if Medication.query.filter_by(patient_id=patient.id).count() < 1:
                min_ok = False
            if IOMetric.query.filter_by(patient_id=patient.id).count() < 1:
                min_ok = False
            if MedicationExecutionMetric.query.filter_by(patient_id=patient.id).count() < 1:
                min_ok = False
        print(f"Per-patient key-table minimum check (>=1 row): {'PASS' if min_ok else 'FAIL'}")
