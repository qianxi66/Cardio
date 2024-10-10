import json
from dataclasses import asdict
from datetime import datetime, timedelta
from functools import wraps
import random
import secrets
import string
from threading import Thread
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
import bcrypt
from flask import abort, current_app, jsonify, logging, request, g
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


@current_app.route("/get_user_info", methods=["GET"])
def get_user_info():
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"message": "Token is missing"}), 401

        token = token.split(" ")[1]
        token_record = Token.query.filter_by(token=token).first()

        if not token_record:
            return jsonify({"message": "Invalid token"}), 401

        user = User.query.get(token_record.userid)
        if not user:
            return jsonify({"message": "User not found"}), 404

        return jsonify({"user_id": user.id, "username": user.username})

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


def patient_to_dict(patient):
    return {
        "id": patient.id,
        "age": patient.age,
        "gender": patient.gender,
        "EHR_id": patient.EHR_id,
        "alexa_user_id": patient.alexa_user_id,
        "medical_history": patient.medical_history,
        "medication": patient.medication,
        "participant_id": patient.participant_id,
        "last_read_at": patient.last_read_at,
        "reviewed": patient.reviewed,
        "state": patient.state,
    }


@current_app.route("/patients", methods=["GET"])
@api_key_required
def get_patients():
    try:
        patients = g.current_user.patients

        patients_dict = [patient_to_dict(patient) for patient in patients]

        for patient in patients_dict:
            latest_report = (
                Report.query.filter_by(patient_id=patient["id"])
                .order_by(Report.created_at.desc())
                .first()
            )
            if latest_report:
                if patient["last_read_at"]:
                    patient["read"] = (
                        patient["last_read_at"] >= latest_report.created_at
                    )
                else:
                    patient["read"] = False
            else:
                patient["state"] = 0
            if patient["state"] is None:
                patient["state"] = 0
                patient["read"] = True

        patients_dict = sorted(
            patients_dict,
            key=lambda x: -1 if x["reviewed"] else (x["state"] if x["state"] else 0),
            reverse=True,
        )

        return jsonify(patients_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/users", methods=["GET"])
@api_key_required
def get_users():
    try:
        # Assuming you have access to the database session
        session: Session = db.session
        users = session.query(User).all()

        # Convert User objects to dictionary format
        users_dict = [user_to_dict(user) for user in users]

        return jsonify(users_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


def user_to_dict(user):
    """Helper function to convert User object to dictionary"""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.name,
        # Add more fields as needed
    }


def generate_report_for_patient(patient):
    for i in range(10):
        # random state, read false, empty logs
        symptom_kwargs = [
            {
                f"{symptom}_state": 0,
                f"{symptom}_logs": "[]",
            }
            for symptom in symptom_descriptions.keys()
        ]
        symptom_kwargs_ = dict([(k, v) for d in symptom_kwargs for k, v in d.items()])

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

        # Debug output
        print(f"Iteration {i}: symptom_kwargs_ = {symptom_kwargs_}")
        print(f"Iteration {i}: likerts = {likerts}")

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

    # Debug output for reports
    print(f"Reports for patient {patient.id} before updating created_at:")
    for report in reports:
        print(report)

    for i, report in enumerate(reports):
        report.created_at = datetime.utcnow() - timedelta(days=(i + 1))
        db.session.add(report)

    # Debug output for updated reports
    print(f"Reports for patient {patient.id} after updating created_at:")
    for report in reports:
        print(report)

    patient.state = max(
        [
            symptom_descriptions[symptom]["max_scale"]
            if getattr(reports[0], f"{symptom}_state") == 2
            else getattr(reports[0], f"{symptom}_state")
            for symptom in symptom_descriptions.keys()
        ]
    )

    # Debug output for patient state
    print(f"Patient {patient.id} state updated to: {patient.state}")

    db.session.add(patient)
    db.session.commit()

    # Final debug output
    print(f"Reports and patient {patient.id} state committed to the database.")


@current_app.route("/patients", methods=["POST"])
@api_key_required
def create_patient():
    try:
        data = request.get_json()
        print("Received data:", data)
        if not data:
            return jsonify({"message": "No input data provided"}), 400

        required_fields = ["user"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            print("Missing fields:", missing_fields)
            return jsonify(
                {"message": f"Missing fields: {', '.join(missing_fields)}"}
            ), 400
        print("a")

        user_ids = data.get("user")
        users = User.query.filter(User.id.in_(user_ids)).all()

        if not users:
            return jsonify({"message": "No valid users found"}), 400

        patient = Patient(
            EHR_id=data.get("EHR_id"),
            age=data.get("age"),
            gender=data.get("gender"),
            participant_id=data.get("participant_id"),
            medical_history=data.get("medical_history", ""),
            medication=data.get("medication", ""),
            last_read_at=datetime.utcnow(),
            reviewed=False,
            state=0,
        )
        print("-----------")
        print(patient.participant_id)

        db.session.add(patient)
        db.session.flush()

        patient.users.extend(users)

        db.session.commit()

        print("Patient data before saving:", patient_to_dict(patient))
        print("c")

        generate_report_for_patient(patient)

        print("Patient data before saving:", patient_to_dict(patient))

        return jsonify(
            {
                "message": "Patient created successfully",
                "patient": patient_to_dict(patient),
            }
        ), 201
    except Exception:
        # logging.error("An error occurred: %s", e, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients/<int:id>", methods=["PATCH"])
@api_key_required
def update_patient(id):
    data = request.get_json()
    print(data)
    # userid = g.current_user.id
    patient = db.get(Patient, id)
    # todo :check permission?
    for key in data:
        setattr(patient, key, data[key])
    db.session.add(patient)
    db.session.commit()
    # time.sleep(10)
    return jsonify({"message": "Patient state updated."})


@current_app.route("/patients/<int:id>", methods=["GET"])
@api_key_required
def get_patient(id):
    try:
        userid = g.current_user.id
        patient = db.get(Patient, id)

        if not any(user.id == userid for user in patient.users):
            return jsonify({"message": "permission denied"}), 401

        patient.last_read_at = datetime.utcnow()
        db.session.add(patient)
        db.session.commit()

        reports = (
            Report.query.filter_by(patient_id=id)
            .order_by(Report.created_at.desc())
            .all()
        )

        patient_dict = patient_to_dict(patient)
        reports_dict = [asdict(report) for report in reports]

        for r in reports_dict:
            for symptom in symptom_descriptions.keys():
                r[f"{symptom}_logs"] = json.loads(r[f"{symptom}_logs"])

        patient_dict["users"] = [
            {"id": user.id, "name": user.name} for user in patient.users
        ]  # add userid and user name
        patient_dict["reports"] = reports_dict

        return jsonify(patient_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


def report_note_to_dict(note: ReportNote) -> dict:
    return {
        "id": note.id,
        "user_id": note.user_id,
        "report_id": note.report_id,
        "content": note.content,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        "user": {
            "id": note.user.id,
            "username": note.user.username,
            "name": note.user.name,
        }
        if note.user
        else None,  # ensure user not none.
    }


def report_to_dict(report: Report) -> dict:
    return {
        "id": report.id,
        "patient_id": report.patient_id,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
        "read": report.read,
        "pain_state": report.pain_state,
        "pain_logs": report.pain_logs,
        "breathing_state": report.breathing_state,
        "breathing_logs": report.breathing_logs,
        "fever_state": report.fever_state,
        "fever_logs": report.fever_logs,
        "stools_state": report.stools_state,
        "stools_logs": report.stools_logs,
        "drainage_state": report.drainage_state,
        "drainage_logs": report.drainage_logs,
        "activity_state": report.activity_state,
        "activity_logs": report.activity_logs,
        "conscious_state": report.conscious_state,
        "conscious_logs": report.conscious_logs,
        "constipation_state": report.constipation_state,
        "constipation_logs": report.constipation_logs,
        "diarrhea_state": report.diarrhea_state,
        "diarrhea_logs": report.diarrhea_logs,
        "eating_state": report.eating_state,
        "eating_logs": report.eating_logs,
        "swelling_state": report.swelling_state,
        "swelling_logs": report.swelling_logs,
        "mood_state": report.mood_state,
        "mood_logs": report.mood_logs,
        "misc_state": report.misc_state,
        "misc_logs": report.misc_logs,
        "breathing_scale": report.breathing_scale,
        "pain_scale": report.pain_scale,
        "conscious_scale": report.conscious_scale,
        "constipation_scale": report.constipation_scale,
        "eating_scale": report.eating_scale,
    }


def report_summary_to_dict(summary: ReportSummary) -> dict:
    return {
        "id": summary.id,
        "report_id": summary.report_id,
        "category": summary.category,
        "content": summary.content,
        "conversation_log_ids": summary.conversation_log_ids,
        "highlight_keywords": summary.highlight_keywords,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
        "updated_at": summary.updated_at.isoformat() if summary.updated_at else None,
    }


def conversation_log_to_dict(log: ConversationLog) -> dict:
    return {
        "id": log.id,
        "patient_id": log.patient_id,
        "report_id": log.report_id,
        "role": log.role,
        "content": log.content,
        "chain_of_thoughts": log.chain_of_thoughts,
        "created_at": log.created_at.isoformat(),
    }


@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["GET"])
@api_key_required
def get_patient_reports(id, report_id):
    report = Report.query.filter_by(patient_id=id, id=report_id).first()

    if report is None:
        return jsonify({"error": "Report not found"}), 404

    report_dict = report_to_dict(report)

    conversation_logs = ConversationLog.query.filter_by(report_id=report_id).all()
    report_dict["conversation_logs"] = [
        conversation_log_to_dict(log) for log in conversation_logs
    ]

    summaries = ReportSummary.query.filter_by(report_id=report_id).all()
    print(summaries)
    report_dict["summary"] = [report_summary_to_dict(s) for s in summaries]

    notes = (
        ReportNote.query.options(joinedload(ReportNote.user))
        .filter_by(report_id=report_id)
        .all()
    )
    report_dict["notes"] = [report_note_to_dict(note) for note in notes]

    return jsonify(report_dict)


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
