# import datetime
import json
import random
from datetime import datetime, timedelta

from sqlalchemy import text

from .app import app
from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, ReportNote, ReportSummary, db


def initialize_reports():
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            for i in range(10):
                # random state, read false, empty logs
                symptom_kwargs = [
                    {
                        f"{symptom}_state": 0,
                        f"{symptom}_logs": "",
                    }
                    for symptom in symptom_descriptions.keys()
                ]
                symptom_kwargs_ = dict(
                    [(k, v) for d in symptom_kwargs for k, v in d.items()]
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
                    [(k, v) for d in symptom_kwargs for k, v in d.items()] + likerts
                )
                report = Report(
                    patient_id=patient.id,
                    **symptom_kwargs,
                )
                db.session.add(report)
            # update created_at
            reports = Report.query.filter_by(patient_id=patient.id).all()
            for i, report in enumerate(reports):
                report.created_at = datetime.utcnow() - timedelta(days=(i+1))
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
                # find random logs
                random_logs = random.sample(log_ids, 3)
                setattr(report, symptom + "_logs", json.dumps(random_logs))
            db.session.add(report)
        db.session.commit()


def generate_summaries():
    with app.app_context():
        report = Report.query.all()
        for r in report:
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
                db.session.add(summary)
        db.session.commit()


def generate_notes():
    with app.app_context():
        report = Report.query.all()
        for r in report:
            for i in range(3):
                note = ReportNote(
                    report_id=r.id,
                    user_id=0,
                    content=random.choice(
                        [
                            "should check in with patient tomorrow",
                            "shouldn't be a problem",
                            "keep watch",
                        ]
                    ),
                )
                db.session.add(note)
        db.session.commit()


@app.cli.command("generate-reports")
def generate_reports():
    initialize_reports()
    generate_conversation_logs()
    update_reports()


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
            sql = """INSERT INTO patient VALUES(1, 25, 'male', 'E01-01', NULL, 'no information', 'no information', 'T001 Alex', '1970-01-01', false, 0);
INSERT INTO patient VALUES(2, 26, 'female', 'E01-02', NULL, 'no information', 'no information', 'T002 Bella', '1970-01-01', false, 0);
INSERT INTO patient VALUES(3, 27, 'male', 'E01-03', NULL, 'no information', 'no information', 'T003 Charlie', '1970-01-01', false, 0);
INSERT INTO patient VALUES(4, 28, 'female', 'E01-04', NULL, 'no information', 'no information', 'T004 Dana', '1970-01-01', false, 0);
INSERT INTO patient VALUES(5, 29, 'male', 'E01-05', NULL, 'no information', 'no information', 'T005 Ethan', '1970-01-01', false, 0);
INSERT INTO patient VALUES(6, 30, 'female', 'E01-06', NULL, 'no information', 'no information', 'T006 Fiona', '1970-01-01', false, 0);
INSERT INTO patient VALUES(7, 31, 'male', 'E01-07', NULL, 'no information', 'no information', 'T007 George', '1970-01-01', false, 0);
INSERT INTO patient VALUES(8, 32, 'female', 'E01-08', NULL, 'no information', 'no information', 'T008 Hannah', '1970-01-01', false, 0);
INSERT INTO patient VALUES(9, 33, 'male', 'E01-09', NULL, 'no information', 'no information', 'T009 Ian', '1970-01-01', false, 0);
INSERT INTO patient VALUES(10, 34, 'female', 'E01-10', NULL, 'no information', 'no information', 'T010 Jenna', '1970-01-01', false, 0);
INSERT INTO patient VALUES(11, 35, 'male', 'E01-11', NULL, 'no information', 'no information', 'T011 Kyle', '1970-01-01', false, 0);
INSERT INTO patient VALUES(12, 36, 'female', 'E01-12', NULL, 'no information', 'no information', 'T012 Lily', '1970-01-01', false, 0);
INSERT INTO patient VALUES(13, 37, 'male', 'E01-13', NULL, 'no information', 'no information', 'T013 Max', '1970-01-01', false, 0);
INSERT INTO patient VALUES(14, 38, 'female', 'E01-14', NULL, 'no information', 'no information', 'T014 Nora', '1970-01-01', false, 0);
INSERT INTO patient VALUES(15, 39, 'male', 'E01-15', NULL, 'no information', 'no information', 'T015 Oliver', '1970-01-01', false, 0);
"""
            for statement in sql.split(";"):
                connection.execute(text(statement))
            connection.execute(text("COMMIT;"))
        db.session.commit()
        print("Patients generated.")
