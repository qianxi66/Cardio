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
    AlexaIDNote,
    ConversationLog,
    Patient,
    Hospitalization, # New import
    Summary,          # New import
    Risk,             # New import
    ReportNote,
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
    """Creates 5 sample patients with specific cancer info."""
    with app.app_context():
        print("Creating 5 sample patients...")
        patient_data = [
            {
                "name": "Emily Johnson", "age": 20, "gender": "female",
                "ehr_id": "EHR-001", "alexa_user_id": "alexa-001",
                "participant_id": "test001", "garmin_id": "garmin-001",
                "cancer_type": "Breast Cancer", "cancer_stage": "IIA",
                "treatment_type": "Chemotherapy"
            },
            {
                "name": "Michael Brown", "age": 45, "gender": "male",
                "ehr_id": "EHR-002", "alexa_user_id": "alexa-002",
                "participant_id": "test002", "garmin_id": "garmin-002",
                "cancer_type": "Lung Cancer", "cancer_stage": "IIIB",
                "treatment_type": "Radiation Therapy"
            },
            {
                "name": "Sophia Davis", "age": 30, "gender": "female",
                "ehr_id": "EHR-003", "alexa_user_id": "alexa-003",
                "participant_id": "test003", "garmin_id": "garmin-003",
                "cancer_type": "Colon Cancer", "cancer_stage": "I",
                "treatment_type": "Surgery"
            },
            {
                "name": "David Wilson", "age": 60, "gender": "male",
                "ehr_id": "EHR-004", "alexa_user_id": "alexa-004",
                "participant_id": "test004", "garmin_id": "garmin-004",
                "cancer_type": "Prostate Cancer", "cancer_stage": "IV",
                "treatment_type": "Hormone Therapy"
            },
            {
                "name": "Olivia Moore", "age": 55, "gender": "female",
                "ehr_id": "EHR-005", "alexa_user_id": "alexa-005",
                "participant_id": "test005", "garmin_id": "garmin-005",
                "cancer_type": "Ovarian Cancer", "cancer_stage": "IIB",
                "treatment_type": "Targeted Therapy"
            },
        ]

        for i, data in enumerate(patient_data):
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
                last_read_at=datetime.utcnow()
            )
            db.session.add(patient)
        db.session.commit()
        print("Patients created successfully.")


@app.cli.command("create-hospitalizations")
def create_hospitalizations_cmd():
    """Creates two hospitalization records for each existing patient."""
    with app.app_context():
        print("Creating hospitalization records for all patients...")
        patients = Patient.query.all()
        for patient in patients:
            # First hospitalization
            hosp1_date = create_random_datetime(
                start_date=datetime.now() - timedelta(days=180),
                end_date=datetime.now() - timedelta(days=90)
            )
            hosp1 = Hospitalization(
                patient_id=patient.id,
                date=hosp1_date,
                event="Chemotherapy Initiation"
            )
            db.session.add(hosp1)

            # Second hospitalization
            hosp2_date = create_random_datetime(
                start_date=datetime.now() - timedelta(days=80),
                end_date=datetime.now() - timedelta(days=10)
            )
            hosp2 = Hospitalization(
                patient_id=patient.id,
                date=hosp2_date,
                event="Chemotherapy Complications"
            )
            db.session.add(hosp2)
        db.session.commit()
        print("Hospitalizations created successfully.")


@app.cli.command("create-summaries")
def create_summaries_cmd():
    """Creates one summary record for each existing patient."""
    with app.app_context():
        from .symptoms import symptom_descriptions

        print("Creating summary records for all patients...")
        patients = Patient.query.all()
        for patient in patients:
            summary = Summary(
                patient_id=patient.id,
                heart_rate_min=generate_random_float(50, 70),
                heart_rate_max=generate_random_float(90, 110),
                heart_rate_average=generate_random_float(70, 90),
                spo2_min=generate_random_float(90, 95),
                spo2_max=generate_random_float(96, 99),
                spo2_average=generate_random_float(94, 97),
                respiration_min=generate_random_float(12, 16),
                respiration_max=generate_random_float(18, 22),
                respiration_average=generate_random_float(14, 18),
                hrv_min=generate_random_float(20, 40),
                hrv_max=generate_random_float(60, 80),
                hrv_average=generate_random_float(40, 60),
                date=create_random_datetime(),
            )
            for symptom_name in symptom_descriptions:
                setattr(summary, f"{symptom_name}_state", random.randint(0, 2))
                setattr(summary, f"{symptom_name}_logs", "[]")
            db.session.add(summary)
        db.session.commit()
        print("Summaries created successfully.")


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
    def simulate_conversation(patient_id):
        has_symptoms = random.random() < 0.3
        active_symptoms = []
        if has_symptoms:
            possible_symptoms = ["breath", "chest", "palpitation", "swelling", "fatigue", "syncope"]
            active_symptoms = random.sample(possible_symptoms, k=random.randint(1, 2))
        
        checklist = ["breath", "chest", "palpitation", "swelling", "fatigue", "syncope"]
        random.shuffle(checklist)
        
        messages = []
        
        messages.append(("assistant", "Hello, this is the RECOVER research study chatbot assistant developed by Northeastern University Human-centered AI lab. Are you ready to start today's questions?"))
        messages.append(("user", "Yes, I am ready."))

        extracted_symptoms_chest = None
        extracted_symptoms_other = []

        for item in checklist:
            question_map = {
                "breath": "Are you having difficulty breathing or feeling short of breath?",
                "chest": "Are you experiencing any chest pain, pressure, or discomfort?",
                "palpitation": "Have you felt like your heart is racing, pounding, fluttering, or skipping beats?",
                "swelling": "Have you noticed any new or worsening swelling, particularly in your legs, ankles, or feet?",
                "fatigue": "Have you been feeling unusually tired, weak, or fatigued?",
                "syncope": "Have you fainted, passed out, or felt very dizzy like you might pass out?"
            }
            
            agent_q = question_map[item]
            messages.append(("assistant", agent_q))

            if item in active_symptoms:
                if item == "breath":
                    messages.append(("user", "Yes, a little bit."))
                    messages.append(("assistant", "Tell me about your shortness of breath, when does it usually happen?"))
                    messages.append(("user", "Mostly when I walk up the stairs."))
                    messages.append(("assistant", "On a scale of 1 to 10, with 10 being the most difficult, how would you rate it?"))
                    messages.append(("user", "About a 4."))
                    extracted_symptoms_other.append("shortness of breath (4/10)")
                
                elif item == "chest":
                    messages.append(("user", "Yes, I feel some pressure."))
                    messages.append(("assistant", "I'm sorry to hear that. Can you describe exactly where you feel the pain and what it feels like?"))
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

                elif item == "fatigue":
                    messages.append(("user", "Yes, I'm very tired."))
                    messages.append(("assistant", "Can you tell me more about this? Is it preventing you from doing your normal daily activities?"))
                    messages.append(("user", "Yes, I just want to sleep all day."))
                    messages.append(("assistant", "On a scale of 1 to 10, how would you rate your fatigue?"))
                    messages.append(("user", "8."))
                    extracted_symptoms_other.append("severe fatigue (8/10)")

                elif item == "syncope":
                    messages.append(("user", "Yes, I felt dizzy earlier."))
                    messages.append(("assistant", "That sounds concerning. Did you actually lose consciousness or fall down?"))
                    messages.append(("user", "No, just dizzy."))
                    messages.append(("assistant", "What were you doing when this happened?"))
                    messages.append(("user", "I stood up too fast."))
                    extracted_symptoms_other.append("dizziness (stood up fast)")
            else:
                messages.append(("user", "No."))

        messages.append(("assistant", "Is there anything else you'd like to comment on that I haven't asked about?"))
        messages.append(("user", "No, that's all."))

        messages.append(("assistant", "CONVERSATION_END Thank you for your time to provide information today. We'll talk again tomorrow."))

        cot_simulation = "breath: discussed\nchest: discussed\npalpitation: discussed\nswelling: discussed\nfatigue: discussed\nsyncope: discussed\nmisc: discussed\n==============\nAll checks completed. Proceeding to wrap up."
        symptoms_other_str = ", ".join(extracted_symptoms_other) if extracted_symptoms_other else None

        return {
            "messages": messages,
            "chain_of_thoughts": cot_simulation,
            "symptoms_chest": extracted_symptoms_chest,
            "symptoms_other": symptoms_other_str,
        }

    with app.app_context():
        print("Generating conversation logs for all patients...")
        patients = Patient.query.all()

        for patient in patients:
            for i in range(5):
                log_date = datetime.now() - timedelta(days=5 - i)
                log_data = simulate_conversation(patient.id)
                messages = log_data["messages"]
                cot = log_data["chain_of_thoughts"]
                symptoms_chest = log_data["symptoms_chest"]
                symptoms_other = log_data["symptoms_other"]

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
        
        db.session.commit()
        print("Conversation logs generated successfully.")
        
        print("Running process_patient_summary for each patient/date...")
        for patient in patients:
            for i in range(5):
                log_date = datetime.now() - timedelta(days=5 - i)
                process_patient_summary(patient.id, log_date)
        print("Summary processing complete.")

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


@app.cli.command("generate-report-notes")
def generate_report_notes_cmd():
    """Generates report notes, linking them to patients (since Report is removed)."""
    with app.app_context():
        print("Generating report notes for patients...")
        patients = Patient.query.all()
        users = User.query.all()
        if not users:
            print("No users found. Please create a user first with 'flask create-user'.")
            return
        
        for patient in patients:
            for _ in range(2): # Generate 2 notes per patient
                note = ReportNote(
                    patient_id=patient.id, # Link to patient instead of report
                    user_id=random.choice(users).id,
                    content=random.choice(
                        [
                            f"Follow up on {patient.name}'s recent symptoms.",
                            "Patient is responding well to treatment.",
                            "Monitor for signs of fatigue and provide support.",
                            "Discuss potential side effects of current medication.",
                        ]
                    ),
                    created_at=create_random_datetime()
                )
                db.session.add(note)
        db.session.commit()
        print("Report notes generated successfully.")
