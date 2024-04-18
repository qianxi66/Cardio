import json
import time
from dataclasses import asdict
from datetime import datetime

import pytz
from flask import current_app, jsonify, request

from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, ReportNote, ReportSummary, db
from .openai import conversation


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
            if patient["last_read_at"]:
                patient["read"] = patient["last_read_at"] >= latest_report.created_at
            else:
                patient["read"] = False
        else:
            patient["state"] = 0
    return jsonify(patients)


@current_app.route("/patients/<int:id>", methods=["PATCH"])
def update_patient(id):
    data = request.get_json()
    print(data)
    patient = db.get(Patient, id)
    for key in data:
        setattr(patient, key, data[key])
    db.session.add(patient)
    db.session.commit()
    # time.sleep(10)
    return jsonify({"message": "Patient state updated."})


@current_app.route("/patients/<int:id>", methods=["GET"])
def get_patient(id):
    # also get reports
    patient = db.get(Patient, id)
    patient.last_read_at = datetime.now()
    db.session.add(patient)
    db.session.commit()
    reports = (
        Report.query.filter_by(patient_id=id).order_by(Report.created_at.desc()).all()
    )
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


# helper function; get today's report (created_at >= today's begin) or create a new report for a user
def get_or_create_report(patient_id):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    # to utc
    today = today.astimezone(pytz.utc)
    report = (
        Report.query.filter_by(patient_id=patient_id)
        .filter(Report.created_at >= today)
        .first()
    )
    if report is None:
        symptom_kwargs = [
            {
                f"{symptom}_state": 0,
                f"{symptom}_logs": "[]",
            }
            for symptom in symptom_descriptions.keys()
        ]
        symptom_kwargs = {k: v for d in symptom_kwargs for k, v in d.items()}
        report = Report(patient_id=patient_id, **symptom_kwargs)
        patient = Patient.query.get(patient_id)
        patient.reviewed = False
        db.session.add(patient)
        db.session.add(report)
        db.session.commit()
    return report


# conversation
@current_app.route("/alexa_user/<alexa_user_id>/conversation", methods=["POST"])
def create_conversation_log(alexa_user_id):
    # get patient with alexa_user_id
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    report = get_or_create_report(patient.id)
    data = request.get_json()["content"]
    log = ConversationLog(
        patient_id=patient.id,
        report_id=report.id,
        role="user",
        content=data,
        created_at=datetime.now(),
    )
    db.session.add(log)
    db.session.commit()
    # get all conversation logs for this report
    conversation_logs = ConversationLog.query.filter_by(report_id=report.id).all()
    conversation_logs = [asdict(log) for log in conversation_logs]
    conversation_logs = [
        {
            "content": log["content"]
            if log["role"] == "user"
            else log["chain_of_thoughts"] + "==============\n" + log["content"],
            "role": log["role"],
        }
        for log in conversation_logs
    ]
    print(conversation_logs)
    assistant_message = conversation(conversation_logs)
    print(assistant_message)
    try:
        chain_of_thoughts = assistant_message.split("==============")[0]
        assistant_message = assistant_message.split("==============")[1].strip(" \n")
    except IndexError:
        chain_of_thoughts = """breathing: false
fever: false
stools: false
pain: false
drainage: false
activity: false
conscious: false
constipation: false
diarrhea: false
eating: false
swelling: false
mood: false
"""
        pass
    log = ConversationLog(
        patient_id=patient.id,
        report_id=report.id,
        role="assistant",
        content=assistant_message,
        chain_of_thoughts=chain_of_thoughts,
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(log)
