import json
from dataclasses import asdict
from datetime import datetime, timedelta
from functools import wraps
import secrets
import string
from threading import Thread
import bcrypt
from flask import abort, current_app, jsonify, request, g

from .app import app
from .config import symptom_descriptions
from .db import (
    ConversationLog,
    Patient,
    Report,
    ReportNote,
    ReportSummary,
    User,
    db,
    Token,
)
from .openai_utils import conversation, key_questions, summary


def generate_random_string(length=32):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def verify_password(input_password, stored_hashed_password):
    input_password_encoded = input_password.encode("utf-8")
    stored_hashed_password_encoded = stored_hashed_password.encode("utf-8")

    return bcrypt.checkpw(input_password_encoded, stored_hashed_password_encoded)


# api for user to login


@current_app.route("/login", methods=["POST"])
def login():
    auth = request.json
    if not auth or not auth.get("username") or not auth.get("password"):
        return jsonify({"message": "Could not verify"}), 401

    username = auth.get("username")
    password = auth.get("password")
    rememberme = auth.get("rememberme")

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"message": "WRONG USERNAME"}), 401

    if user and verify_password(password, user.password):
        token_string = generate_random_string()
        token = Token(token=token_string, userid=user.id, rememberme=rememberme)
        db.session.add(token)
        db.session.commit()

        return jsonify(
            {
                "token": token,
            }
        )

    return jsonify({"message": "WRONG PASSWORD"}), 401


TOKEN_EXPIRATION_HOURS = 24
REMEMBERME_EXPIRATION_HOURS = 72


# a decorator to valid the 'authentication' header for an api key
def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            abort(401)  # Unauthorized

        # get Token
        token_string = auth_header.split(" ")[1]

        # dearch token in db
        token = Token.query.filter_by(token=token_string).first()

        if not token:
            abort(401)
        # token expired
        if not token.rememberme and datetime.utcnow() - token.created_at > timedelta(
            hours=TOKEN_EXPIRATION_HOURS
        ):
            abort(401)
        # rememberme expired
        if token.rememberme and datetime.utcnow() - token.created_at > timedelta(
            hours=REMEMBERME_EXPIRATION_HOURS
        ):
            abort(401)

        # get user
        user = User.query.filter_by(id=token.userid).first()
        if user:
            g.current_user = user
        else:
            g.current_user = None
            abort(401)

        return f(*args, **kwargs)

    return decorated_function


# get patients, return all patients
@current_app.route("/patients", methods=["GET"])
@api_key_required
def get_patients():
    userid = g.current_user.id

    # select patients by userid
    patients = Patient.query.filter_by(user_id=userid).all()

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


@current_app.route("/patients", methods=["POST"])
@api_key_required
def create_patient():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400

    # Ensure necessary fields are provided; modify as per your data model
    required_fields = ["EHRid", "age", "doctor", "gender"]
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"message": f"Missing fields: {', '.join(missing_fields)}"}), 400

    # search userid by username
    user = User.query.filter_by(username=data["doctor"]).first()

    # Create a new Patient instance
    patient = Patient(
        EHR_id=data.get("EHR_id"),
        age=data.get("age"),
        gender=data.get("gender"),
        medical_history=data.get("medicalhistory", ""),
        medication=data.get("medication", ""),
        user_id=user.id,  # Associate the patient with the current user
        last_read_at=datetime.utcnow(),
    )

    db.session.add(patient)
    db.session.commit()

    return jsonify(
        {"message": "Patient created successfully", "patient": asdict(patient)}
    ), 201


@current_app.route("/patients/<int:id>", methods=["PATCH"])
@api_key_required
def update_patient(id):
    data = request.get_json()
    print(data)
    userid = g.current_user.id
    patient = db.get(Patient, id)
    if patient.user_id != userid:
        return jsonify({"message": "permission denied"}), 401
    else:
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
    userid = g.current_user.id
    patient = db.get(Patient, id)
    if patient.user_id != userid:
        return jsonify({"message": "permission denied"}), 401
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
    print("session_end_hook")
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
        print(summaries)
        try:
            summaries = json.loads(summaries)["result"]
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
    print(patient)
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
        # create a new assistant message
        msg = "Hello, this is the RECOVER research study chatbot assistant developed by Northeastern University Human-centered AI lab. Are you ready to start today's questions?"
        message = ConversationLog(
            patient_id=patient.id,
            report_id=report.id,
            role="assistant",
            chain_of_thoughts="",
            content=msg,
        )
        db.session.add(message)
        db.session.commit()
        return jsonify({"message": "success", "last_message": asdict(message)})
    messages = [asdict(message) for message in messages]
    messages = [i for i in messages if i["role"] == "assistant"]
    return jsonify({"message": "success", "last_message": messages[-1]})
