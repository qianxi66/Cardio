import json
import time
from dataclasses import asdict

from flask import current_app, jsonify, request

from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, ReportNote, ReportSummary, db


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
        if latest_report:
            patient["state"] = max(
                [
                    getattr(latest_report, f"{symptom}_state")
                    for symptom in symptom_descriptions.keys()
                ]
            )
        else:
            patient["state"] = 0
    time.sleep(1)
    return jsonify(patients)


@current_app.route("/patients/<int:id>", methods=["GET"])
def get_patient(id):
    # also get reports
    patient = db.get(Patient, id)
    reports = Report.query.filter_by(patient_id=id).all()
    patient = asdict(patient)
    reports = [asdict(report) for report in reports]
    for r in reports:
        for symptom in symptom_descriptions.keys():
            r[f"{symptom}_logs"] = json.loads(r[f"{symptom}_logs"])
    patient["reports"] = reports
    time.sleep(1)
    return jsonify(patient)


@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["GET"])
def get_patient_reports(id, report_id):
    reports = Report.query.filter_by(patient_id=id, id=report_id).all()
    conversation_logs = ConversationLog.query.filter_by(report_id=report_id).all()
    reports = asdict(reports[0])
    reports["conversation_logs"] = conversation_logs
    summary = ReportSummary.query.filter_by(report_id=report_id).all()
    notes = ReportNote.query.filter_by(report_id=report_id).all()
    reports["summary"] = summary
    reports["notes"] = notes
    time.sleep(1)
    return jsonify(reports)


# delete note
@current_app.route(
    "/patients/<int:id>/report/<int:report_id>/note/<int:note_id>", methods=["DELETE"]
)
def delete_report_note(id, report_id, note_id):
    note = ReportNote.query.filter_by(id=note_id).first()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"message": "Note deleted."})


# create note
@current_app.route("/patients/<int:id>/report/<int:report_id>/note", methods=["POST"])
def create_report_note(id, report_id):
    data = request.get_json()
    note = ReportNote(
        report_id=report_id,
        user_id=data["user_id"],
        content=data["content"],
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"message": "Note created."})
