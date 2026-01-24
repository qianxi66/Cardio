import json
import random
from datetime import datetime, timedelta
import bcrypt
import click
from sqlalchemy import text

from .app import app
from .symptoms import symptom_descriptions
from .db import (
    AlexaIDNote,
    ConversationLog,
    Patient,
    Report,
    ReportNote,
    ReportSummary,
    User,
    db,
)


def initialize_reports():
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            for i in range(10):
                # Random state, read false, empty logs
                symptom_kwargs = [
                    {f"{symptom}_state": 0, f"{symptom}_logs": "[]"}
                    for symptom in symptom_descriptions.keys()
                ]
                symptom_kwargs_ = dict(
                    (k, v) for d in symptom_kwargs for k, v in d.items()
                )

                likerts = [
                    (
                        f"{symptom}_scale",
                        random.randint(1, 10)
                        if symptom_kwargs_[f"{symptom}_state"] == 2
                        else 0,
                    )
                    for symptom, description in symptom_descriptions.items()
                    if description["likert"]
                ]
                print(symptom_kwargs_)
                print(likerts)
                symptom_kwargs = dict(
                    (k, v) for d in symptom_kwargs for k, v in d.items()
                )
                symptom_kwargs.update(likerts)

                report = Report(patient_id=patient.id, **symptom_kwargs)
                db.session.add(report)

            # Update created_at
            reports = Report.query.filter_by(patient_id=patient.id).all()
            for i, report in enumerate(reports):
                report.created_at = datetime.utcnow() - timedelta(days=(i + 1))
                db.session.add(report)

            patient.state = max(
                [
                    symptom_descriptions[symptom]["max_scale"]
                    if getattr(reports[0], f"{symptom}_state") == 2
                    else getattr(reports[0], f"{symptom}_state")
                    for symptom in symptom_descriptions.keys()
                ]
            )
            db.session.add(patient)
        db.session.commit()


def generate_conversation_logs():
    with app.app_context():
        reports = Report.query.all()
        for report in reports:
            for _ in range(10):  # Generate 10 logs per report
                log = ConversationLog(
                    patient_id=report.patient_id,
                    report_id=report.id,
                    role=random.choice(["assistant", "user"]),
                    content=random.choice(
                        [
                            "How are you feeling today?",
                            "I'm feeling okay, just a bit tired.",
                            "Make sure to rest. Do you need any help with your medication?",
                            "Yes, please remind me to take my medication at 7 PM.",
                            "Will do. Do you have any other concerns?",
                            "No, that's all for today. Thank you.",
                            "You're welcome! Have a good day.",
                        ]
                    ),
                    created_at=datetime.utcnow(),
                )
                db.session.add(log)
        db.session.commit()


def update_reports():
    with app.app_context():
        reports = Report.query.all()
        for report in reports:
            logs = ConversationLog.query.filter_by(report_id=report.id).all()
            log_ids = [log.id for log in logs]
            for symptom in symptom_descriptions.keys():
                # Find random logs
                random_logs = random.sample(log_ids, 3)
                setattr(report, f"{symptom}_logs", json.dumps(random_logs))
            db.session.add(report)
        db.session.commit()


def generate_summaries():
    with app.app_context():
        reports = Report.query.all()
        for r in reports:
            for i in range(5):
                summary = ReportSummary(
                    report_id=r.id,
                    category=random.choice(
                        ["Summary", "Additional Comments", "Recommendations"]
                    ),
                    content=random.choice(
                        [
                            "Patient is feeling better today",
                            "Patient is feeling worse today",
                            "Patient is feeling the same today",
                        ]
                    ),
                    conversation_log_ids="",
                    highlight_keywords="",
                )
                summary.created_at = datetime.utcnow() - timedelta(days=(i + 1))
                db.session.add(summary)
        db.session.commit()


def generate_notes():
    with app.app_context():
        reports = Report.query.all()
        for r in reports:
            for i in range(3):
                note = ReportNote(
                    report_id=r.id,
                    user_id=1,
                    content=random.choice(
                        [
                            "Should check in with patient tomorrow",
                            "Shouldn't be a problem",
                            "Keep watch",
                        ]
                    ),
                )
                db.session.add(note)
        db.session.commit()


@app.cli.command("generate-reports")
def generate_reports():
    initialize_reports()


def create_report_for_patient(patient):
    # Random state, read false, empty logs
    symptom_kwargs = [
        {f"{symptom}_state": 0, f"{symptom}_logs": "[]"}
        for symptom in symptom_descriptions.keys()
    ]
    symptom_kwargs_ = dict((k, v) for d in symptom_kwargs for k, v in d.items())

    likerts = [
        (
            f"{symptom}_scale",
            random.randint(1, 10) if symptom_kwargs_[f"{symptom}_state"] == 2 else 0,
        )
        for symptom, description in symptom_descriptions.items()
        if description["likert"]
    ]
    print(symptom_kwargs_)
    print(likerts)
    symptom_kwargs = dict((k, v) for d in symptom_kwargs for k, v in d.items())
    symptom_kwargs.update(likerts)

    report = Report(patient_id=patient.id, **symptom_kwargs)
    db.session.add(report)

    # Update created_at
    reports = Report.query.filter_by(patient_id=patient.id).all()
    for i, report in enumerate(reports):
        report.created_at = datetime.utcnow() - timedelta(days=(10))
        db.session.add(report)

    patient.state = max(
        [
            symptom_descriptions[symptom]["max_scale"]
            if getattr(reports[-1], f"{symptom}_state") == 2
            else getattr(reports[-1], f"{symptom}_state")
            for symptom in symptom_descriptions.keys()
            if getattr(reports[-1], f"{symptom}_state") is not None
        ]
    )
    db.session.add(patient)


@app.cli.command("generate-empty-reports")
def generate_empty_reports():
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            create_report_for_patient(patient)
        db.session.commit()


@app.cli.command("generate-summaries")
def generate_summaries_cmd():
    generate_summaries()


@app.cli.command("generate-notes")
def generate_notes_cmd():
    generate_notes()


@app.cli.command("generate-patients")
def generate_patients():
    with app.app_context():
        with db.engine.connect() as connection:
            sql = """INSERT INTO patient (id, age, gender, EHR_id, alexa_user_id, medical_history, medication, participant_id, last_read_at, reviewed, state, garmin_id) VALUES(1, 25, 'male', 'E01-01', NULL, 'no information', 'no information', 'T001', '1970-01-01', false, 0, NULL);
INSERT INTO patient (id, age, gender, EHR_id, alexa_user_id, medical_history, medication, participant_id, last_read_at, reviewed, state, garmin_id) VALUES(2, 26, 'female', 'E01-02', NULL, 'no information', 'no information', 'T002', '1970-01-01', false, 0, NULL);
INSERT INTO patient (id, age, gender, EHR_id, alexa_user_id, medical_history, medication, participant_id, last_read_at, reviewed, state, garmin_id) VALUES(3, 27, 'male', 'E01-03', NULL, 'no information', 'no information', 'T003', '1970-01-01', false, 0, NULL);
INSERT INTO patient (id, age, gender, EHR_id, alexa_user_id, medical_history, medication, participant_id, last_read_at, reviewed, state, garmin_id) VALUES(4, 28, 'female', 'E01-04', NULL, 'no information', 'no information', 'T004', '1970-01-01', false, 0, NULL);
INSERT INTO patient (id, age, gender, EHR_id, alexa_user_id, medical_history, medication, participant_id, last_read_at, reviewed, state, garmin_id) VALUES(5, 29, 'male', 'E01-05', NULL, 'no information', 'no information', 'T005', '1970-01-01', false, 0, NULL);"""
            for statement in sql.strip().split(";"):
                if statement.strip():
                    connection.execute(text(statement))
            connection.execute(text("COMMIT;"))
        db.session.commit()
        ids = {
            # "Name1": "ID_1",
            # "Name2": "ID_2",
            # Add additional mappings as needed
        }
        i = 1
        for key in ids:
            patient = Patient(
                age=25,
                gender="male",
                EHR_id=f"TEST-{key}",
                alexa_user_id=ids[key],
                medical_history="no information",
                medication="no information",
                reviewed=False,
                state=0,
                last_read_at=datetime(1970, 1, 1),
                participant_id=f"TEST-{key}",
            )
            db.session.add(patient)
            i += 1
        db.session.commit()
        print("Patients generated.")


@app.cli.command("create-user")
@click.option("--username", required=True, type=str, help="Username for the new user")
@click.option("--password", required=True, type=str, help="Password for the new user")
@click.option("--email", required=True, type=str, help="Email for the new user")
@click.option("--name", required=True, type=str, help="Real name for the new user")
def create_user(username, password, email, name):
    with app.app_context():
        print(f"Creating user with username {username}")

        # Check if the username or email already exists
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
def reset_password(username, password):
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
def assign_patient(user_id, patient_id):
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


@app.cli.command("create-patient")
@click.option("--patient-id", required=True, type=int)
@click.option("--participant-id", required=True, type=str)
@click.option("--EHR-id", required=True, type=str)
@click.option("--alexa-note-id", type=int)
@click.option("--garmin-id", type=str)
def create_patient(patient_id, participant_id, ehr_id, alexa_note_id, garmin_id):
    with app.app_context():
        print(f"Creating patient with id {patient_id}")
        alexa_user_id = ""
        if alexa_note_id:
            note = AlexaIDNote.query.filter_by(id=alexa_note_id).first()
            alexa_user_id = note.alexa_user_id
        patient = Patient(
            id=patient_id,
            age=0,
            gender="male",
            EHR_id=ehr_id,
            alexa_user_id=alexa_user_id,
            medical_history="no information",
            medication="no information",
            participant_id=participant_id,
            last_read_at=datetime(1970, 1, 1),
            reviewed=False,
            state=0,
            garmin_id= garmin_id
        )
        db.session.add(patient)
        db.session.commit()
        create_report_for_patient(patient)
        db.session.commit()


@app.cli.command("remove-conversation-summaries")
def remove_conversation_summaries():
    with app.app_context():
        patient_ids = [6, 7, 8, 10, 11, 12, 13, 14, 15]
        for pid in patient_ids:
            reports = Report.query.filter_by(patient_id=pid).all()
            for report in reports:
                summaries = ReportSummary.query.filter_by(report_id=report.id).all()
                for summary in summaries:
                    db.session.delete(summary)
                conversations = ConversationLog.query.filter_by(
                    report_id=report.id
                ).all()
                for conversation in conversations:
                    db.session.delete(conversation)
                notes = ReportNote.query.filter_by(report_id=report.id).all()
                for note in notes:
                    db.session.delete(note)
        db.session.commit()

    report_ids = [151, 152, 158, 153, 154, 155, 156, 157]
    with app.app_context():
        reports = Report.query.filter(Report.id.not_in(report_ids)).all()
        for report in reports:
            summaries = ReportSummary.query.filter_by(report_id=report.id).all()
            for summary in summaries:
                db.session.delete(summary)
            conversations = ConversationLog.query.filter_by(report_id=report.id).all()
            for conversation in conversations:
                db.session.delete(conversation)
            notes = ReportNote.query.filter_by(report_id=report.id).all()
            for note in notes:
                db.session.delete(note)
        db.session.commit()
