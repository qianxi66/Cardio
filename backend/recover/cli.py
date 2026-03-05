import json
import random
from datetime import datetime, timedelta
import bcrypt
import click
from sqlalchemy import text

# Assuming 'app' and 'db' are defined in .app and .db respectively
from .app import app
from .apis import process_patient_summary
from .db import (
    AdmissionHistory,
    AlexaIDNote,
    ConversationLog,
    Medication,
    Note,
    Patient,
    Summary,
    Risk,
    User,
    db,
)

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

# --- CLI Commands ---

@app.cli.command("create-patients")
def create_patients_cmd():
    """Creates 5 sample patients with full demo info."""
    with app.app_context():
        print("Creating 5 sample patients...")
        now = datetime.utcnow()
        patient_data = [
            {
                "name": "Emily Johnson", "age": 20, "gender": "Female",
                "ehr_id": "EHR-001", "alexa_user_id": "alexa-001",
                "participant_id": "test001", "garmin_id": "garmin-001",
                "cancer_type": "Breast Cancer",
                "cancer_stage": "2024-03-15",          # diagnosis date
                "treatment_type": "Penicillin, Aspirin",  # allergy history
                "treatment_plan": "AC-T Chemotherapy (Adriamycin + Cyclophosphamide followed by Taxol)",
                "treatment_cycle": "Cycle 3 of 6",
                "next_appointment_date": now + timedelta(days=14),
            },
            {
                "name": "Michael Brown", "age": 45, "gender": "Male",
                "ehr_id": "EHR-002", "alexa_user_id": "alexa-002",
                "participant_id": "test002", "garmin_id": "garmin-002",
                "cancer_type": "Lung Cancer",
                "cancer_stage": "2023-11-08",
                "treatment_type": "Sulfonamides",
                "treatment_plan": "Pembrolizumab (immunotherapy) + Carboplatin",
                "treatment_cycle": "Cycle 5 of 8",
                "next_appointment_date": now + timedelta(days=7),
            },
            {
                "name": "Sophia Davis", "age": 30, "gender": "Female",
                "ehr_id": "EHR-003", "alexa_user_id": "alexa-003",
                "participant_id": "test003", "garmin_id": "garmin-003",
                "cancer_type": "Colon Cancer",
                "cancer_stage": "2025-01-22",
                "treatment_type": "None known",
                "treatment_plan": "Laparoscopic colectomy + adjuvant FOLFOX",
                "treatment_cycle": "Cycle 1 of 4",
                "next_appointment_date": now + timedelta(days=21),
            },
            {
                "name": "David Wilson", "age": 60, "gender": "Male",
                "ehr_id": "EHR-004", "alexa_user_id": "alexa-004",
                "participant_id": "test004", "garmin_id": "garmin-004",
                "cancer_type": "Prostate Cancer",
                "cancer_stage": "2022-06-30",
                "treatment_type": "NSAIDs, Codeine",
                "treatment_plan": "Enzalutamide (hormone therapy) + Zoledronic acid",
                "treatment_cycle": "Ongoing maintenance",
                "next_appointment_date": now + timedelta(days=30),
            },
            {
                "name": "Olivia Moore", "age": 55, "gender": "Female",
                "ehr_id": "EHR-005", "alexa_user_id": "alexa-005",
                "participant_id": "test005", "garmin_id": "garmin-005",
                "cancer_type": "Ovarian Cancer",
                "cancer_stage": "2024-09-12",
                "treatment_type": "Contrast dye (iodine)",
                "treatment_plan": "Bevacizumab + Carboplatin + Paclitaxel",
                "treatment_cycle": "Cycle 2 of 6",
                "next_appointment_date": now + timedelta(days=10),
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
def create_admission_history_cmd():
    """Creates two admission history records for each existing patient."""
    with app.app_context():
        print("Creating admission history records for all patients...")
        patients = Patient.query.all()
        for patient in patients:
            adm1_date = create_random_datetime(
                start_date=datetime.now() - timedelta(days=180),
                end_date=datetime.now() - timedelta(days=90)
            )
            adm1 = AdmissionHistory(
                patient_id=patient.id,
                admission_date=adm1_date,
                discharge_date=adm1_date + timedelta(days=random.randint(2, 7)),
                diagnosis="Chemotherapy Initiation",
                symptoms="Nausea, fatigue, mild chest discomfort",
                notes="Patient tolerated first cycle moderately well."
            )
            db.session.add(adm1)

            adm2_date = create_random_datetime(
                start_date=datetime.now() - timedelta(days=80),
                end_date=datetime.now() - timedelta(days=10)
            )
            adm2 = AdmissionHistory(
                patient_id=patient.id,
                admission_date=adm2_date,
                discharge_date=adm2_date + timedelta(days=random.randint(1, 5)),
                diagnosis="Chemotherapy Complications",
                symptoms="Syncope, palpitations, shortness of breath",
                notes="Adjusted dosage. Monitor wearable readings closely."
            )
            db.session.add(adm2)
        db.session.commit()
        print("Admission history records created successfully.")


@app.cli.command("create-summaries")
def create_summaries_cmd():
    """Creates 5 days of summary records (today-4 to today) for each patient."""
    with app.app_context():
        from .symptoms import symptom_descriptions
        print("Creating 5-day summary records for all patients...")
        patients = Patient.query.all()
        for patient in patients:
            for days_ago in range(4, -1, -1):  # 4 days ago → today
                day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
                summary = Summary(patient_id=patient.id, date=day)
                for symptom_name in symptom_descriptions:
                    # Wearable symptoms get state 0-1; conversation ones get 0-3
                    max_state = 1 if symptom_name in ("heart_rate", "respiration") else 3
                    setattr(summary, f"{symptom_name}_state", random.randint(0, max_state))
                    setattr(summary, f"{symptom_name}_logs", "[]")
                    setattr(summary, f"{symptom_name}_read", 0)
                db.session.add(summary)
        db.session.commit()
        print("5-day summaries created successfully.")


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
        # symptom_msg_indices: backend_key → list of indices in messages[] that are
        # the meaningful back-and-forth about that symptom (for log highlighting)
        symptom_msg_indices = {}

        messages.append(("assistant", "Hello, this is the RECOVER research study chatbot assistant developed by Northeastern University Human-centered AI lab. Are you ready to start today's questions?"))
        messages.append(("user", "Yes, I am ready."))

        extracted_symptoms_chest = None
        extracted_symptoms_other = []

        question_map = {
            "breath":      "Are you having difficulty breathing or feeling short of breath?",
            "chest":       "Are you experiencing any chest pain, pressure, or discomfort?",
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
                elif item == "chest":
                    messages.append(("user", "Yes, I feel some pressure."))
                    messages.append(("assistant", "I'm sorry to hear that. Can you describe where you feel the pain and what it feels like?"))
                    messages.append(("user", "It's on the left side, kind of a dull ache."))
                    messages.append(("assistant", "On a scale of 1 to 10, how would you rate your chest discomfort?"))
                    messages.append(("user", "It's a 3, not too bad."))
                    extracted_symptoms_chest = "left side dull ache (3/10)"
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
                    messages.append(("assistant", "On a scale of 1 to 10, how would you rate it?"))
                    messages.append(("user", "Maybe a 2."))
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

        messages.append(("assistant", "Is there anything else you'd like to comment on that I haven't asked about?"))
        messages.append(("user", "No, that's all."))
        messages.append(("assistant", "CONVERSATION_END Thank you for your time to provide information today. We'll talk again tomorrow."))

        cot_simulation = "breath: discussed\nchest: discussed\npalpitation: discussed\nswelling: discussed\nsyncope: discussed\nmisc: discussed\n==============\nAll checks completed. Proceeding to wrap up."
        symptoms_other_str = ", ".join(extracted_symptoms_other) if extracted_symptoms_other else None

        return {
            "messages": messages,
            "symptom_msg_indices": symptom_msg_indices,
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

        for patient in patients:
            for i in range(5):
                log_date = datetime.now() - timedelta(days=4 - i)
                day_start = log_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                log_data = simulate_conversation()
                messages = log_data["messages"]
                symptom_msg_indices = log_data["symptom_msg_indices"]
                active_symptoms = log_data["active_symptoms"]
                skipped_symptoms = log_data["skipped_symptoms"]
                cot = log_data["chain_of_thoughts"]
                symptoms_chest = log_data["symptoms_chest"]
                symptoms_other = log_data["symptoms_other"]

                # Insert messages and keep object references to get IDs after flush
                log_objects = []
                for idx, (role, content) in enumerate(messages):
                    is_last = idx == len(messages) - 1
                    log = ConversationLog(
                        patient_id=patient.id,
                        role=role,
                        content=content,
                        chain_of_thoughts=cot if is_last else None,
                        symptoms_chest=symptoms_chest if is_last else None,
                        symptoms_other=symptoms_other if is_last else None,
                        date=log_date,
                    )
                    db.session.add(log)
                    log_objects.append(log)

                # Flush to get DB-assigned IDs without full commit
                db.session.flush()

                # Update the Summary for this day with correct symptom states + log IDs
                summary = Summary.query.filter_by(patient_id=patient.id).filter(
                    Summary.date >= day_start, Summary.date < day_end
                ).first()
                if summary:
                    for symptom_name in symptom_descriptions:
                        if symptom_name in ("heart_rate", "respiration"):
                            continue  # wearable — driven by MongoDB, leave as-is
                        if symptom_name in skipped_symptoms:
                            setattr(summary, f"{symptom_name}_state", 0)
                            setattr(summary, f"{symptom_name}_logs", "[]")
                        elif symptom_name in active_symptoms:
                            indices = symptom_msg_indices.get(symptom_name, [])
                            log_ids = [log_objects[idx].id for idx in indices if idx < len(log_objects)]
                            setattr(summary, f"{symptom_name}_state", 2)
                            setattr(summary, f"{symptom_name}_logs", json.dumps(log_ids))
                        else:
                            setattr(summary, f"{symptom_name}_state", 1)
                            setattr(summary, f"{symptom_name}_logs", "[]")
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
def create_medications_cmd():
    """Creates exactly 2 medication records per patient."""
    with app.app_context():
        print("Creating medication records for all patients...")
        now = datetime.utcnow()
        users = User.query.all()
        recorder_id = users[0].id if users else None
        med_pool = [
            {"drug_name": "Metoprolol",  "dosage": "25mg once daily",  "days_start": 120, "days_end": None},
            {"drug_name": "Furosemide",  "dosage": "40mg twice daily", "days_start": 90,  "days_end": 15},
            {"drug_name": "Lisinopril",  "dosage": "10mg once daily",  "days_start": 180, "days_end": None},
            {"drug_name": "Warfarin",    "dosage": "5mg once daily",   "days_start": 60,  "days_end": 10},
            {"drug_name": "Ondansetron", "dosage": "4mg as needed",    "days_start": 45,  "days_end": 20},
            {"drug_name": "Dexamethasone","dosage": "8mg before chemo","days_start": 30,  "days_end": None},
        ]
        patients = Patient.query.all()
        for patient in patients:
            selected = random.sample(med_pool, k=2)
            for tpl in selected:
                start = now - timedelta(days=tpl["days_start"])
                end = (now - timedelta(days=tpl["days_end"])) if tpl["days_end"] else None
                db.session.add(Medication(
                    patient_id=patient.id,
                    drug_name=tpl["drug_name"],
                    dosage=tpl["dosage"],
                    start_date=start,
                    end_date=end,
                    recorded_by_user_id=recorder_id,
                ))
        db.session.commit()
        print("Medication records created successfully.")


@app.cli.command("generate-notes")
def generate_notes_cmd():
    """Generates 1 AI summary note per day (5 days) + 3 random clinical notes per patient."""
    with app.app_context():
        print("Generating notes for patients...")
        patients = Patient.query.all()
        users = User.query.all()
        if not users:
            print("No users found. Please create a user first with 'flask create-user'.")
            return

        ai_summaries = [
            "AI Summary: Wearable data shows elevated heart rate and occasional palpitations. Patient reported shortness of breath during activity.",
            "AI Summary: Stable respiration and heart rate overnight. Conversational log indicates mild swelling in ankles; no syncope reported.",
            "AI Summary: Patient reported chest discomfort (3/10). Heart rate variability slightly reduced. Recommend clinical review.",
            "AI Summary: All wearable metrics within normal range. No symptoms reported in today's check-in.",
            "AI Summary: Fatigue and palpitations noted in conversation log. Wearable shows intermittent elevated HR. Monitor closely.",
        ]
        user_notes = [
            "Follow-up on recent chest discomfort episode; ordered ECG.",
            "Patient tolerating current medication cycle well. No dose adjustment needed.",
            "Discussed side effects of Furosemide. Patient instructed to weigh daily.",
            "Reviewed wearable trends with patient. Encouraged light walking.",
            "Patient anxious about upcoming appointment. Provided reassurance and care plan overview.",
        ]

        now = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)
        for patient in patients:
            # 1 AI note per day for past 5 days
            for days_ago in range(4, -1, -1):
                day = now - timedelta(days=days_ago)
                db.session.add(Note(
                    patient_id=patient.id,
                    user_id=None,
                    creator_type="ai",
                    content=ai_summaries[4 - days_ago],
                    created_at=day,
                ))
            # 3 random user notes spread across the 5 days
            for _ in range(3):
                days_ago = random.randint(0, 4)
                db.session.add(Note(
                    patient_id=patient.id,
                    user_id=random.choice(users).id,
                    creator_type="user",
                    content=random.choice(user_notes),
                    created_at=now - timedelta(days=days_ago, hours=random.randint(1, 10)),
                ))
        db.session.commit()
        print("Notes generated successfully.")
