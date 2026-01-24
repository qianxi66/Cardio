from datetime import datetime, timedelta

from .app import app
from .db import Patient, Report, db
from .symptoms import symptom_descriptions


def _day_start_utc(now: datetime) -> datetime:
    day_start = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if now < day_start:
        day_start -= timedelta(days=1)
    return day_start


def ensure_daily_reports() -> int:
    created = 0
    now = datetime.utcnow()
    day_start = _day_start_utc(now)
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            existing = (
                Report.query.filter_by(patient_id=patient.id)
                .filter(Report.created_at >= day_start)
                .first()
            )
            if existing:
                continue
            symptom_kwargs = [
                {f"{symptom}_state": 0, f"{symptom}_logs": "[]"}
                for symptom in symptom_descriptions.keys()
            ]
            symptom_kwargs = {k: v for d in symptom_kwargs for k, v in d.items()}
            report = Report(patient_id=patient.id, **symptom_kwargs)
            patient.reviewed = False
            db.session.add(patient)
            db.session.add(report)
            created += 1
        db.session.commit()
    return created


def main() -> None:
    created = ensure_daily_reports()
    print(f"daily_reports_created={created}")


if __name__ == "__main__":
    main()
