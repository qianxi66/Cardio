# import datetime
import json
import random
from datetime import datetime, timedelta

from .app import app
from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, db


def initialize_reports():
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            for i in range(10):
                # random state, read false, empty logs
                symptom_kwargs = [
                    {
                        f"{symptom}_state": random.randint(0, 4),
                        f"{symptom}_read": False,
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


@app.cli.command("generate-reports")
def generate_reports():
    initialize_reports()
    generate_conversation_logs()
    update_reports()
