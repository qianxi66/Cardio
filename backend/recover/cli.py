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
                        f"{symptom}_state": random.randint(0, 3),
                        f"{symptom}_logs": "",
                    }
                    for symptom in symptom_descriptions.keys()
                ]
                symptom_kwargs = dict(
                    (k, v) for d in symptom_kwargs for k, v in d.items()
                )
                report = Report(
                    patient_id=patient.id,
                    **symptom_kwargs,
                )
                db.session.add(report)
            # update created_at
            reports = Report.query.filter_by(patient_id=patient.id).all()
            for i, report in enumerate(reports):
                report.created_at = datetime.utcnow() - timedelta(days=i)
                db.session.add(report)

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
            sql = """INSERT INTO patient VALUES(1,25,'male','E01-01',NULL,'no information','no information','T001');
    INSERT INTO patient VALUES(2,26,'female','E01-02',NULL,'no information','no information','T002');
    INSERT INTO patient VALUES(3,27,'male','E01-03',NULL,'no information','no information','T003');
    INSERT INTO patient VALUES(4,28,'female','E01-04',NULL,'no information','no information','T004');
    INSERT INTO patient VALUES(5,29,'male','E01-05',NULL,'no information','no information','T005');
    INSERT INTO patient VALUES(6,30,'female','E01-06',NULL,'no information','no information','T006');
    INSERT INTO patient VALUES(7,31,'male','E01-07',NULL,'no information','no information','T007');
    INSERT INTO patient VALUES(8,32,'female','E01-08',NULL,'no information','no information','T008');
    INSERT INTO patient VALUES(9,33,'male','E01-09',NULL,'no information','no information','T009');
    INSERT INTO patient VALUES(10,34,'female','E01-10',NULL,'no information','no information','T010');
    INSERT INTO patient VALUES(11,35,'male','E01-11',NULL,'no information','no information','T011');
    INSERT INTO patient VALUES(12,36,'female','E01-12',NULL,'no information','no information','T012');
    INSERT INTO patient VALUES(13,37,'male','E01-13',NULL,'no information','no information','T013');
    INSERT INTO patient VALUES(14,38,'female','E01-14',NULL,'no information','no information','T014');
    INSERT INTO patient VALUES(15,39,'male','E01-15',NULL,'no information','no information','T015');"""
            for statement in sql.split(";"):
                connection.execute(text(statement))
            connection.execute(text("COMMIT;"))
        db.session.commit()
        print("Patients generated.")
