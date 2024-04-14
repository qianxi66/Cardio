import time
from dataclasses import asdict

from flask import current_app, jsonify

from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, db


# get patients, return all patients
@current_app.route("/patients", methods=["GET"])
def get_patients():
    # patients = Patient.query.all()
    # return jsonify(patients)
    # get all patints
    # join the latest report
    # query the maximum of all the states and return the patient
    patients = Patient.query.all()
    patients = [asdict(patient) for patient in patients]
    for patient in patients:
        latest_report = (
            Report.query.filter_by(patient_id=patient["id"])
            .order_by(Report.created_at.desc())
            .first()
        )
        patient["state"] = max(
            [
                getattr(latest_report, f"{symptom}_state")
                for symptom in symptom_descriptions.keys()
            ]
        )
    time.sleep(10)
    return jsonify(patients)


@current_app.route("/patients/<int:id>", methods=["GET"])
def get_patient(id):
    # also get reports
    patient = db.get(Patient, id)
    reports = Report.query.filter_by(patient_id=id).all()
    patient = asdict(patient)
    patient["reports"] = reports
    time.sleep(10)
    return jsonify(patient)


@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["GET"])
def get_patient_reports(id, report_id):
    reports = Report.query.filter_by(patient_id=id, id=report_id).all()
    conversation_logs = ConversationLog.query.filter_by(report_id=report_id).all()
    reports = asdict(reports[0])
    reports["conversation_logs"] = conversation_logs
    return jsonify(reports)
