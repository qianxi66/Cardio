import json
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
from .symptoms import symptom_descriptions
from .db import (
    AlexaIDNote,
    ConversationLog,
    Patient,
    Report,
    ReportNote,
    ReportSummary,
    User,
    db,
    Token,
)
from .config import VALID_API_KEYS
from .openai_utils import conversation, key_questions, summary


def generate_random_string(length=32):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def verify_password(input_password, stored_hashed_password):
    input_password_encoded = input_password.encode("utf-8")
    stored_hashed_password_encoded = stored_hashed_password.encode("utf-8")

    return bcrypt.checkpw(input_password_encoded, stored_hashed_password_encoded)


# API for user to login
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

        return jsonify({"token": token.as_dict()})

    return jsonify({"message": "WRONG PASSWORD"}), 401


TOKEN_EXPIRATION_HOURS = 2
REMEMBERME_EXPIRATION_HOURS = 48


def api_key_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            abort(401)  # Unauthorized

        # Get token
        token_string = auth_header.split(" ")[1]
        if token_string not in VALID_API_KEYS:
            abort(401)
        return f(*args, **kwargs)

    return decorated_function


# Decorator to validate the 'Authorization' header for an API key
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            abort(401)  # Unauthorized

        # Get token
        token_string = auth_header.split(" ")[1]

        # Search token in db
        token = Token.query.filter_by(token=token_string).first()

        if not token:
            abort(401)
        # Token expired
        if not token.rememberme and datetime.utcnow() - token.updated_at > timedelta(
            hours=TOKEN_EXPIRATION_HOURS
        ):
            abort(401)
        # Remember me expired
        if token.rememberme and datetime.utcnow() - token.updated_at > timedelta(
            hours=REMEMBERME_EXPIRATION_HOURS
        ):
            abort(401)
        token.updated_at = datetime.utcnow()
        db.session.add(token)
        db.session.commit()
        # Get user
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


@current_app.route("/patients", methods=["GET"])
@login_required
def get_patients():
    try:
        patients = g.current_user.patients

        patients_dict = [patient.as_dict() for patient in patients]

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
                patient["read"] = True
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
@login_required
def get_users():
    try:
        session: Session = db.session
        users = session.query(User).all()

        users_dict = [
            {k: v for k, v in user.as_dict().items() if k != "password"}
            for user in users
        ]

        return jsonify(users_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


def generate_report_for_patient(patient):
    i = 1
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
            random.randint(1, 10) if symptom_kwargs_[f"{symptom}_state"] == 2 else 0,
        )
        for symptom, description in symptom_descriptions.items()
        if description["likert"]
    ]

    symptom_kwargs = dict(
        [(k, v) for d in symptom_kwargs for k, v in d.items()] + likerts
    )
    report = Report(
        patient_id=patient.id,
        **symptom_kwargs,
    )
    db.session.add(report)

    reports = Report.query.filter_by(patient_id=patient.id).all()

    for i, report in enumerate(reports):
        report.created_at = datetime.utcnow() - timedelta(days=(i + 1))
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


@current_app.route("/patients", methods=["POST"])
@login_required
def create_patient():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "No input data provided"}), 400

        required_fields = ["user"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify(
                {"message": f"Missing fields: {', '.join(missing_fields)}"}
            ), 400

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

        db.session.add(patient)
        db.session.flush()

        patient.users.extend(users)

        db.session.commit()

        generate_report_for_patient(patient)

        return (
            jsonify(
                {
                    "message": "Patient created successfully",
                    "patient": patient.as_dict(),
                }
            ),
            201,
        )
    except Exception:
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients/<int:id>", methods=["PATCH"])
@login_required
def update_patient(id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "No input data provided"}), 400

        patient = Patient.query.get(id)
        if not patient:
            return jsonify({"message": "Patient not found"}), 404

        if "user" in data:
            new_user_ids = set(data.get("user", []))
            current_user_ids = {user.id for user in patient.users}

            users_to_add = new_user_ids - current_user_ids
            users_to_remove = current_user_ids - new_user_ids

            if users_to_add:
                users_to_add_objs = User.query.filter(User.id.in_(users_to_add)).all()
                patient.users.extend(users_to_add_objs)

            if users_to_remove:
                users_to_remove_objs = User.query.filter(
                    User.id.in_(users_to_remove)
                ).all()
                for user in users_to_remove_objs:
                    patient.users.remove(user)

        for key in data:
            if key != "user":
                setattr(patient, key, data[key])

        db.session.commit()

        return (
            jsonify({"patient_id": id, "message": "Patient updated successfully."}),
            200,
        )

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients/<int:id>", methods=["GET"])
@login_required
def get_patient(id):
    try:
        userid = g.current_user.id
        patient = db.get(Patient, id)

        if not any(user.id == userid for user in patient.users):
            return jsonify({"message": "Permission denied"}), 401

        patient.last_read_at = datetime.utcnow()
        db.session.add(patient)
        db.session.commit()

        reports = (
            Report.query.filter_by(patient_id=id)
            .order_by(Report.created_at.desc())
            .all()
        )

        patient_dict = patient.as_dict()
        reports_dict = [report.as_dict() for report in reports]

        for r in reports_dict:
            for symptom in symptom_descriptions.keys():
                raw_data = r.get(f"{symptom}_logs", "")
                if raw_data:
                    try:
                        r[f"{symptom}_logs"] = json.loads(raw_data)
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decoding failed for {symptom}_logs: {e}")
                        r[f"{symptom}_logs"] = []
                else:
                    r[f"{symptom}_logs"] = []

        patient_dict["users"] = [
            {k: v for k, v in user.as_dict().items() if k != "password"}
            for user in patient.users
        ]
        patient_dict["reports"] = reports_dict

        return jsonify(patient_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["GET"])
@login_required
def get_patient_reports(id, report_id):
    report = Report.query.filter_by(patient_id=id, id=report_id).first()

    if report is None:
        return jsonify({"error": "Report not found"}), 404

    report_dict = report.as_dict()

    conversation_logs = ConversationLog.query.filter_by(report_id=report_id).all()
    report_dict["conversation_logs"] = [log.as_dict() for log in conversation_logs]

    summaries = ReportSummary.query.filter_by(report_id=report_id).all()
    report_dict["summary"] = [s.as_dict() for s in summaries]

    notes = (
        ReportNote.query.options(joinedload(ReportNote.user))
        .filter_by(report_id=report_id)
        .all()
    )
    report_dict["notes"] = [note.as_dict() for note in notes]

    return jsonify(report_dict)


@current_app.route("/patients/<int:id>/report/<int:report_id>", methods=["PATCH"])
@login_required
def update_report(id, report_id):
    patient = Patient.query.get(id)
    data = request.get_json()
    report = Report.query.get(report_id)
    for key in data:
        setattr(report, key, data[key])
    db.session.add(report)
    # If report is latest
    latest_report = (
        Report.query.filter_by(patient_id=id).order_by(Report.created_at.desc()).first()
    )
    if report.id == latest_report.id:
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


@current_app.route(
    "/patients/<int:id>/report/<int:report_id>/note/<int:note_id>",
    methods=["DELETE"],
)
@login_required
def delete_report_note(id, report_id, note_id):
    note = ReportNote.query.filter_by(id=note_id).first()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"message": "Note deleted."})


@current_app.route("/patients/<int:id>/report/<int:report_id>/note", methods=["POST"])
@login_required
def create_report_note(id, report_id):
    data = request.get_json()
    note = ReportNote(
        report_id=report_id,
        user_id=g.current_user.id,
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


@current_app.route("/alexa_user/<alexa_user_id>/conversation", methods=["POST"])
@api_key_required
def create_conversation_log(alexa_user_id):
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
    conversation_logs = ConversationLog.query.filter_by(report_id=report.id).all()
    conversation_logs = [log.as_dict() for log in conversation_logs]
    conversation_logs = [
        {
            "content": log["content"]
            if log["role"] == "user"
            else log["chain_of_thoughts"] + "==============\n" + log["content"],
            "role": log["role"],
        }
        for log in conversation_logs
    ]
    assistant_message = conversation(conversation_logs)
    try:
        chain_of_thoughts, assistant_message = assistant_message.split(
            "==============", 1
        )
        assistant_message = assistant_message.strip()
    except ValueError:
        chain_of_thoughts = """physical: not discussed
stress: not discussed
emotion: not discussed
selfcare: not discussed
communication: not discussed
processing: not discussed
"""
    session_end = "CONVERSATION_END" in assistant_message
    log = ConversationLog(
        patient_id=patient.id,
        report_id=report.id,
        role="assistant",
        content=assistant_message.replace("CONVERSATION_END", ""),
        chain_of_thoughts=chain_of_thoughts,
    )
    db.session.add(log)
    db.session.commit()
    log.content += "CONVERSATION_END" if session_end else ""
    return jsonify(log.as_dict())


def session_end_hook(alexa_user_id):
    with app.app_context():
        patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
        report = get_or_create_report(patient.id)
        messages = ConversationLog.query.filter_by(report_id=report.id).all()
        messages = [message.as_dict() for message in messages]
        messages = [
            {
                "id": message["id"],
                "content": message["content"],
                "role": message["role"],
            }
            for message in messages
        ]
        try:
            response = key_questions(json.dumps(messages))
            response = json.loads(response)
        except Exception:
            response = {}
        for key in response:
            setattr(report, f"{key}_state", response[key]["state"])
            setattr(report, f"{key}_logs", json.dumps(response[key]["logs"]))
            if "scale" in response[key]:
                if hasattr(report, f"{key}_scale"):
                    setattr(report, f"{key}_scale", response[key]["scale"])
                    if response[key]["scale"] == 0:
                        pass
                    elif 1 <= response[key]["scale"] <= 3:
                        setattr(report, f"{key}_state", 2)
                    elif 4 <= response[key]["scale"] <= 6:
                        setattr(report, f"{key}_state", 3)
                    elif 7 <= response[key]["scale"] <= 10:
                        setattr(report, f"{key}_state", 4)

        db.session.add(report)
        summaries = summary(json.dumps(messages), json.dumps(response))
        try:
            summaries = json.loads(summaries)["result"]
            ReportSummary.query.filter_by(report_id=report.id).delete()
            for summaryi in summaries:
                report_summary = ReportSummary(
                    report_id=report.id, highlight_keywords="", **summaryi
                )
                db.session.add(report_summary)
            db.session.commit()
        except Exception as e:
            logging.error(f"An error occurred while summarizing: {e}")
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


@current_app.route("/alexa_user/<alexa_user_id>/session_end", methods=["POST"])
@api_key_required
def session_end(alexa_user_id):
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        return jsonify({"message": "Patient not found."}), 404
    Thread(target=session_end_hook, args=(alexa_user_id,)).start()

    return jsonify({"message": "success"})


@current_app.route("/alexa_user/<alexa_user_id>/last_message", methods=["GET"])
@api_key_required
def get_last_message(alexa_user_id):
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        return jsonify({"message": "Patient not found."}), 404
    report = get_or_create_report(patient.id)
    messages = ConversationLog.query.filter_by(report_id=report.id).all()
    if len(messages) == 0:
        msg = (
            "Hello, thanks for checking in for our study."
            "How are you feeling today? "
        )
        message = ConversationLog(
            patient_id=patient.id,
            report_id=report.id,
            role="assistant",
            chain_of_thoughts="",
            content=msg,
        )
        db.session.add(message)
        db.session.commit()
        return jsonify({"message": "success", "last_message": message.as_dict()})
    messages = [message.as_dict() for message in messages]
    messages = [i for i in messages if i["role"] == "assistant"]
    return jsonify({"message": "success", "last_message": messages[-1]})


@current_app.route("/alexa_user/<alexa_user_id>/create_note", methods=["POST"])
@api_key_required
def create_note(alexa_user_id):
    note = AlexaIDNote(
        alexa_user_id=alexa_user_id,
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"message": "success", "note": note.as_dict()})
