import json
from dataclasses import asdict
from datetime import datetime, timedelta
from functools import wraps
from threading import Thread

from flask import abort, current_app, jsonify, request

from .app import app
from .config import VALID_API_KEYS, symptom_descriptions
from .db import ConversationLog, Patient, Report, ReportNote, ReportSummary, db
from .openai import conversation, key_questions, summary


# a decorator to valid the 'authentication' header for an api key
def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            abort(401)  # Unauthorized

        api_key = auth_header.split(" ")[1]
        if api_key not in VALID_API_KEYS:
            abort(401)  # Unauthorized

        return f(*args, **kwargs)

    return decorated_function


# get patients, return all patients
@current_app.route("/patients", methods=["GET"])
@api_key_required
def get_patients():
    # sort by patient state
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
        if patient["state"] is None:
            patient["state"] = 0
            patient["read"] = True
    patients = sorted(
        patients,
        key=lambda x: -1 if x["reviewed"] else (x["state"] if x["state"] else 0),
        reverse=True,
    )
    return jsonify(patients)


@current_app.route("/patients/<int:id>", methods=["PATCH"])
@api_key_required
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
@api_key_required
def get_patient(id):
    # also get reports
    patient = db.get(Patient, id)
    patient.last_read_at = datetime.utcnow()
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
    # time.sleep(1)
    return jsonify(patient)


@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["GET"])
@api_key_required
def get_patient_reports(id, report_id):
    reports = Report.query.filter_by(patient_id=id, id=report_id).all()
    conversation_logs = ConversationLog.query.filter_by(report_id=report_id).all()
    reports = asdict(reports[0])
    reports["conversation_logs"] = conversation_logs
    summary = ReportSummary.query.filter_by(report_id=report_id).all()
    notes = ReportNote.query.filter_by(report_id=report_id).all()
    reports["summary"] = summary
    reports["notes"] = notes
    # time.sleep(1)
    return jsonify(reports)


# update report
@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["PATCH"])
@api_key_required
def update_report(id, report_id):
    patient = Patient.query.get(id)
    data = request.get_json()
    report = Report.query.filter_by(id=report_id).first()
    for key in data:
        setattr(report, key, data[key])
    db.session.add(report)
    # if report is latest
    if (
        report.id
        == Report.query.filter_by(patient_id=id)
        .order_by(Report.created_at.desc())
        .first()
        .id
    ):
        print("is latest")
        patient.state = max(
            [
                symptom_descriptions[symptom]["max_scale"]
                if getattr(report, f"{symptom}_state") == 2
                else getattr(report, f"{symptom}_state")
                for symptom in symptom_descriptions.keys()
            ]
        )
        db.session.add(patient)
    db.session.commit()
    return jsonify({"message": "Report updated."})


# delete note
@current_app.route(
    "/patients/<int:id>/report/<int:report_id>/note/<int:note_id>", methods=["DELETE"]
)
@api_key_required
def delete_report_note(id, report_id, note_id):
    note = ReportNote.query.filter_by(id=note_id).first()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"message": "Note deleted."})


# create note
@current_app.route("/patients/<int:id>/report/<int:report_id>/note", methods=["POST"])
@api_key_required
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
    # get last 4am, if pass 4am then today, otherwise yesterday
    today = datetime.now().replace(hour=4, minute=0, second=0, microsecond=0)
    if datetime.now() < today:
        today -= timedelta(days=1)
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
@api_key_required
def create_conversation_log(alexa_user_id):
    # get patient with alexa_user_id
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        return jsonify({"message": "Patient not found."}), 404
    report = get_or_create_report(patient.id)
    data = request.get_json()["content"]
    log = ConversationLog(
        patient_id=patient.id,
        report_id=report.id,
        role="user",
        content=data,
        created_at=datetime.utcnow(),
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
        chain_of_thoughts = """breathing: not discussed
fever: not discussed
stools: not discussed
pain: not discussed
drainage: not discussed
activity: not discussed
conscious: not discussed
constipation: not discussed
diarrhea: not discussed
eating: not discussed
swelling: not discussed
mood: not discussed
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


def session_end_hook(alexa_user_id):
    with app.app_context():
        patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
        print(patient)
        report = get_or_create_report(patient.id)
        print(report)
        messages = ConversationLog.query.filter_by(report_id=report.id).all()
        messages = [asdict(message) for message in messages]
        messages = [
            {
                "id": message["id"],
                "content": message["content"],
                "role": message["role"],
            }
            for message in messages
        ]
        print(messages)
        try:
            response = key_questions(json.dumps(messages))
            print(response)
            response = json.loads(response)
        except Exception:
            response = {}
        print(response)
        for key in response:
            setattr(report, f"{key}_state", response[key]["state"])
            setattr(report, f"{key}_logs", json.dumps(response[key]["logs"]))
            if "scale" in response[key]:
                if hasattr(report, f"{key}_scale"):
                    setattr(report, f"{key}_scale", response[key]["scale"])

        db.session.add(report)
        summaries = summary(json.dumps(messages), json.dumps(response))
        try:
            summaries = json.loads(summaries)
            # firstly delete all old summaries
            ReportSummary.query.filter_by(report_id=report.id).delete()
            for summaryi in summaries:
                report_summary = ReportSummary(
                    report_id=report.id, highlight_keywords="", **summaryi
                )
                db.session.add(report_summary)
            db.session.commit()
        except Exception as e:
            print(e)
        patient.state = max(
            [
                symptom_descriptions[symptom]["max_scale"]
                if getattr(report, f"{symptom}_state") == 2
                else getattr(report, f"{symptom}_state")
                for symptom in symptom_descriptions.keys()
            ]
        )
        db.session.add(patient)
        db.session.commit()
        print("session end hook done")


# summarize key questions
@current_app.route("/alexa_user/<alexa_user_id>/session_end", methods=["POST"])
@api_key_required
def session_end(alexa_user_id):
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        return jsonify({"message": "Patient not found."}), 404
    Thread(target=session_end_hook, args=(alexa_user_id,)).start()

    return jsonify({"message": "success"})


# get today last message
@current_app.route("/alexa_user/<alexa_user_id>/last_message", methods=["GET"])
@api_key_required
def get_last_message(alexa_user_id):
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        return jsonify({"message": "Patient not found."}), 404
    report = get_or_create_report(patient.id)
    messages = ConversationLog.query.filter_by(report_id=report.id).all()
    if len(messages) == 0:
        return jsonify({"message": "No messages."})
    messages = [asdict(message) for message in messages]
    messages = [i for i in messages if i["role"] == "assistant"]
    return jsonify({"message": "success", "last_message": messages[-1]})
