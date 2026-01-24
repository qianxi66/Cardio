import json
import math
from datetime import datetime, timedelta
from functools import wraps
import random
import secrets
import string
from threading import Thread
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
import bcrypt
from flask import abort, current_app, jsonify, request, g
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
from .config import (
    VALID_API_KEYS, mongodb_url, GREETINGS
)
from .openai_utils import conversation, key_questions, summary
from pymongo import MongoClient
import logging

# Cache for wearable data
wearable_data_cache = {}  # Format: {alexa_user_id: {'timestamp': datetime, 'data': {...}}}
CACHE_EXPIRY_MINUTES = 60  # Cache expires after 60 minutes

def get_cached_wearable_data(alexa_user_id):
    """Get wearable data from cache if it exists and is not expired"""
    if alexa_user_id in wearable_data_cache:
        cache_entry = wearable_data_cache[alexa_user_id]
        cache_age = datetime.utcnow() - cache_entry['timestamp']
        if cache_age.total_seconds() < CACHE_EXPIRY_MINUTES * 60:
            return cache_entry['data']
    return None

def set_cached_wearable_data(alexa_user_id, data):
    """Store wearable data in cache"""
    wearable_data_cache[alexa_user_id] = {
        'timestamp': datetime.utcnow(),
        'data': data
    }

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
            garmin_id=data.get("garmin_id"),
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



def _mongo_wearable_stats(
    participant_id,
    collection_name,
    start_ts,
    end_ts,
    *,
    db_name,
    id_field,
    value_field,
    min_value=None,
):
    if not participant_id:
        return {"mean": None, "max": None, "min": None}
    client = MongoClient(mongodb_url)
    try:
        db2 = client[db_name]
        cursor = db2[collection_name].find(
            {
                id_field: participant_id,
                "timestamp": {"$gte": start_ts, "$lte": end_ts},
            },
            {value_field: 1},
        )
        values = []
        for doc in cursor:
            value = doc.get(value_field)
            if not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value):
                continue
            if min_value is not None and value < min_value:
                continue
            values.append(value)
        if not values:
            return {"mean": None, "max": None, "min": None}
        return {
            "mean": sum(values) / len(values),
            "max": max(values),
            "min": min(values),
        }
    finally:
        client.close()


def _mongo_latest_value(
    participant_id,
    collection_name,
    start_ts,
    end_ts,
    *,
    db_name,
    id_field,
    value_field,
    min_value=None,
):
    if not participant_id:
        return None
    client = MongoClient(mongodb_url)
    try:
        db2 = client[db_name]
        doc = (
            db2[collection_name]
            .find(
                {
                    id_field: participant_id,
                    "timestamp": {"$gte": start_ts, "$lte": end_ts},
                },
                {value_field: 1},
            )
            .sort("timestamp", -1)
            .limit(1)
        )
        doc = next(doc, None)
        if not doc:
            return None
        value = doc.get(value_field)
        if not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
        if min_value is not None and value < min_value:
            return None
        return value
    finally:
        client.close()


def _mongo_has_any(
    participant_id,
    collection_name,
    start_ts,
    end_ts,
    *,
    db_name,
    id_field,
):
    if not participant_id:
        return False
    client = MongoClient(mongodb_url)
    try:
        db2 = client[db_name]
        doc = (
            db2[collection_name]
            .find(
                {
                    id_field: participant_id,
                    "timestamp": {"$gte": start_ts, "$lte": end_ts},
                },
                {"_id": 1},
            )
            .limit(1)
        )
        return next(doc, None) is not None
    finally:
        client.close()


def _steps_max_since_reset(
    participant_id,
    start_ts,
    end_ts,
    *,
    db_name,
    id_field,
    value_field,
    min_value=0,
    reset_lookback_hours=36,
):
    if not participant_id:
        return None
    client = MongoClient(mongodb_url)
    try:
        db2 = client[db_name]
        lookback_start = max(0, int(start_ts - reset_lookback_hours * 3600))
        cursor = db2["garmin_steps"].find(
            {
                id_field: participant_id,
                "timestamp": {"$gte": lookback_start, "$lte": end_ts},
            },
            {value_field: 1, "timestamp": 1},
        ).sort("timestamp", 1)
        rows = []
        for doc in cursor:
            ts = doc.get("timestamp")
            value = doc.get(value_field)
            if not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value):
                continue
            if value < min_value:
                continue
            if not isinstance(ts, (int, float)):
                continue
            rows.append((int(ts), value))
        if not rows:
            return None
        reset_ts = None
        prev_val = None
        for ts, val in rows:
            if prev_val is not None and val < prev_val:
                reset_ts = ts
            prev_val = val
        window_start = max(start_ts, reset_ts) if reset_ts else start_ts
        day_values = [val for ts, val in rows if window_start <= ts <= end_ts]
        if not day_values:
            return None
        return max(day_values)
    finally:
        client.close()


def _steps_total_for_window(
    participant_id,
    start_ts,
    end_ts,
    *,
    db_name,
    id_field,
    value_field,
    min_value=0,
):
    if not participant_id:
        return None
    client = MongoClient(mongodb_url)
    try:
        db2 = client[db_name]
        cursor = db2["garmin_steps"].find(
            {
                id_field: participant_id,
                "timestamp": {"$gte": start_ts, "$lte": end_ts},
            },
            {value_field: 1, "timestamp": 1},
        ).sort("timestamp", 1)
        values = []
        for doc in cursor:
            value = doc.get(value_field)
            if not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value):
                continue
            if value < min_value:
                continue
            values.append(value)
        if not values:
            return None
        decreases = 0
        prev_val = None
        for val in values:
            if prev_val is not None and val < prev_val:
                decreases += 1
            prev_val = val
        max_val = max(values)
        if decreases <= 2:
            return max_val
        total = sum(values)
        return total if total > 0 else max_val
    finally:
        client.close()


def _step_resets(
    participant_id,
    start_ts,
    end_ts,
    *,
    db_name,
    id_field,
    value_field,
    min_value=0,
):
    if not participant_id:
        return []
    client = MongoClient(mongodb_url)
    try:
        db2 = client[db_name]
        cursor = db2["garmin_steps"].find(
            {
                id_field: participant_id,
                "timestamp": {"$gte": start_ts, "$lte": end_ts},
            },
            {value_field: 1, "timestamp": 1},
        ).sort("timestamp", 1)
        prev_val = None
        resets = []
        for doc in cursor:
            ts = doc.get("timestamp")
            value = doc.get(value_field)
            if not isinstance(value, (int, float)):
                continue
            if not math.isfinite(value):
                continue
            if value < min_value:
                continue
            if not isinstance(ts, (int, float)):
                continue
            ts = int(ts)
            if prev_val is not None and value < prev_val:
                resets.append(ts)
            prev_val = value
        return resets
    finally:
        client.close()


def _day_window_from_steps_reset(
    participant_id,
    report_date,
    *,
    db_name,
    id_field,
    value_field,
    min_value=0,
    reset_lookback_hours=36,
    reset_lookahead_hours=36,
):
    if not participant_id:
        return None
    anchor_ts = int(report_date.timestamp())
    lookback_start = max(0, int(anchor_ts - reset_lookback_hours * 3600))
    lookahead_end = int(anchor_ts + reset_lookahead_hours * 3600)
    resets = _step_resets(
        participant_id,
        lookback_start,
        lookahead_end,
        db_name=db_name,
        id_field=id_field,
        value_field=value_field,
        min_value=min_value,
    )
    if not resets:
        return None
    start_reset = None
    next_reset = None
    for ts in resets:
        if ts <= anchor_ts:
            start_reset = ts
        else:
            next_reset = ts
            break
    if start_reset is None:
        if next_reset is None:
            return None
        start_reset = next_reset - 24 * 3600
        end_reset = next_reset
    else:
        end_reset = None
        for ts in resets:
            if ts > start_reset:
                end_reset = ts
                break
        if end_reset is None:
            end_reset = start_reset + 24 * 3600
    return start_reset, end_reset - 1
@current_app.route("/patients/<int:id>", methods=["GET"])
@login_required
def get_patient(id):
    try:
        userid = g.current_user.id
        patient = db.get(Patient, id)

        if not any(user.id == userid for user in patient.users):
            return jsonify({"message": "Permission denied"}), 401

        # Ensure today's report exists so the dashboard shows current day.
        get_or_create_report(patient.id)

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

            # Start of the day
            start_of_day = r["created_at"].replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_of_day = r["created_at"].replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            if patient.participant_id:
                try:
                    report_day_start_ts = int(start_of_day.timestamp())
                    report_day_end_ts = int(end_of_day.timestamp())
                    has_steps_for_report_day = _mongo_has_any(
                        patient.participant_id,
                        "garmin_steps",
                        report_day_start_ts,
                        report_day_end_ts,
                        db_name="study_db",
                        id_field="uid",
                    )
                    has_hr_for_report_day = _mongo_has_any(
                        patient.participant_id,
                        "garmin_hr",
                        report_day_start_ts,
                        report_day_end_ts,
                        db_name="study_db",
                        id_field="uid",
                    )
                    has_stress_for_report_day = _mongo_has_any(
                        patient.participant_id,
                        "garmin_stress",
                        report_day_start_ts,
                        report_day_end_ts,
                        db_name="study_db",
                        id_field="uid",
                    )
                    start_ts = report_day_start_ts
                    end_ts = report_day_end_ts
                    if has_steps_for_report_day:
                        day_window = _day_window_from_steps_reset(
                            patient.participant_id,
                            r["created_at"],
                            db_name="study_db",
                            id_field="uid",
                            value_field="total_steps",
                            min_value=0,
                        )
                        if day_window:
                            start_ts, end_ts = day_window
                    stress_stats = {"mean": None, "max": None, "min": None}
                    hr_stats = {"max": None, "min": None}
                    steps_stats = {"mean": None, "max": None, "min": None}
                    steps_latest = None
                    steps_total = None
                    if has_stress_for_report_day:
                        stress_stats = _mongo_wearable_stats(
                            patient.participant_id,
                            "garmin_stress",
                            start_ts,
                            end_ts,
                            db_name="study_db",
                            id_field="uid",
                            value_field="heart_rate",
                            min_value=0,
                        )
                    if has_hr_for_report_day:
                        hr_stats = _mongo_wearable_stats(
                            patient.participant_id,
                            "garmin_hr",
                            start_ts,
                            end_ts,
                            db_name="study_db",
                            id_field="uid",
                            value_field="heart_rate",
                            min_value=1,
                        )
                    if has_steps_for_report_day:
                        steps_stats = _mongo_wearable_stats(
                            patient.participant_id,
                            "garmin_steps",
                            start_ts,
                            end_ts,
                            db_name="study_db",
                            id_field="uid",
                            value_field="total_steps",
                            min_value=0,
                        )
                        steps_latest = _mongo_latest_value(
                            patient.participant_id,
                            "garmin_steps",
                            start_ts,
                            end_ts,
                            db_name="study_db",
                            id_field="uid",
                            value_field="total_steps",
                            min_value=0,
                        )
                        steps_total = _steps_total_for_window(
                            patient.participant_id,
                            start_ts,
                            end_ts,
                            db_name="study_db",
                            id_field="uid",
                            value_field="total_steps",
                            min_value=0,
                        )
                    current_app.logger.info(
                        "steps window pid=%s report_id=%s report_at=%s report_day_start=%s report_day_end=%s start_ts=%s end_ts=%s has_steps_day=%s has_hr_day=%s has_stress_day=%s steps_total=%s steps_latest=%s steps_max=%s steps_mean=%s",
                        patient.participant_id,
                        r.get("id"),
                        r.get("created_at"),
                        report_day_start_ts,
                        report_day_end_ts,
                        start_ts,
                        end_ts,
                        has_steps_for_report_day,
                        has_hr_for_report_day,
                        has_stress_for_report_day,
                        steps_total,
                        steps_latest,
                        steps_stats["max"],
                        steps_stats["mean"],
                    )

                    r["stress"] = {
                        "avg_stress": (
                            stress_stats["mean"] if has_stress_for_report_day else None
                        )
                    }
                    r["heart_rate"] = {
                        "max_hr": hr_stats["max"] if has_hr_for_report_day else None,
                        "min_hr": hr_stats["min"] if has_hr_for_report_day else None,
                    }
                    steps_value = None
                    if has_steps_for_report_day:
                        steps_value = (
                            steps_total
                            if steps_total is not None
                            else (
                                steps_latest
                                if steps_latest is not None
                                else steps_stats["max"]
                            )
                        )
                    r["steps"] = {"total_steps": steps_value}
                except Exception as e:
                    logging.error(f"Failed to fetch data from MongoDB: {e}")
                    r["heart_rate"] = {"max_hr": None, "min_hr": None}
                    r["steps"] = {"total_steps": None}
                    r["stress"] = {"avg_stress": None}
            else:
                r["heart_rate"] = {"max_hr": None, "min_hr": None}
                r["steps"] = {"total_steps": None}
                r["stress"] = {"avg_stress": None}
            
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


def fetch_day_sensor_data(participant_id, start, end):
    stress_stats = _mongo_wearable_stats(
        participant_id,
        "garmin_stress",
        start,
        end,
        db_name="study_db",
        id_field="uid",
        value_field="heart_rate",
        min_value=0,
    )
    steps_stats = _mongo_wearable_stats(
        participant_id,
        "garmin_steps",
        start,
        end,
        db_name="study_db",
        id_field="uid",
        value_field="total_steps",
        min_value=0,
    )
    steps_total = _steps_total_for_window(
        participant_id,
        start,
        end,
        db_name="study_db",
        id_field="uid",
        value_field="total_steps",
        min_value=0,
    )
    data = {}
    data["avg_stress"] = stress_stats["mean"]
    data["max_stress"] = stress_stats["max"]
    data["avg_steps"] = steps_stats["mean"]
    data["max_steps"] = steps_total if steps_total is not None else steps_stats["max"]
    return data

def get_week_boundaries(date):
    """Get the start and end of the week (Monday-Sunday) containing the given date."""
    # Get the current weekday (0 is Monday, 6 is Sunday)
    weekday = date.weekday()
    # Calculate the date of Monday (start of week)
    week_start = date - timedelta(days=weekday)
    # Calculate the date of Sunday (end of week)
    week_end = week_start + timedelta(days=7)
    return week_start, week_end

@current_app.route("/alexa_user/<alexa_user_id>/conversation", methods=["POST"])
@api_key_required
def create_conversation_log(alexa_user_id):
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        return jsonify({"message": "Patient not found."}), 404
    report = get_or_create_report(patient.id)
    
    # Get wearable data for today, yesterday and weeks
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    
    # Get current and last week's boundaries
    this_week_start, this_week_end = get_week_boundaries(today)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start  # Last week ends where this week starts
    
    # Initialize wearable data structure
    wearable_data = {
        "today": {},
        "yesterday": {},
        "this_week": {},  # Current week's data
        "last_week": {}   # Last week's data
    }
    
    if patient.participant_id:
        # Try to get data from cache first
        cached_data = get_cached_wearable_data(patient.alexa_user_id)
        if cached_data is not None:
            wearable_data = cached_data
            print("Using cached wearable data")
            print(wearable_data)
        else:
            try:
                # Get data for today and yesterday
                today_data = fetch_day_sensor_data(
                    patient.participant_id,
                    int(today.timestamp()),
                    int((today + timedelta(days=1)).timestamp() - 1),
                )

                yesterday_data = fetch_day_sensor_data(
                    patient.participant_id,
                    int(yesterday.timestamp()),
                    int(today.timestamp() - 1),
                )

                # Get this week's data (Monday-Sunday)
                this_week_data = fetch_day_sensor_data(
                    patient.participant_id,
                    int(this_week_start.timestamp()),
                    int(this_week_end.timestamp() - 1),
                )

                # Get last week's data (Monday-Sunday)
                last_week_data = fetch_day_sensor_data(
                    patient.participant_id,
                    int(last_week_start.timestamp()),
                    int(last_week_end.timestamp() - 1),
                )

                # Update wearable_data with the results
                if today_data:
                    wearable_data["today"].update(today_data)
                if yesterday_data:
                    wearable_data["yesterday"].update(yesterday_data)
                if this_week_data:
                    wearable_data["this_week"].update(this_week_data)
                    wearable_data["this_week"]["week_start"] = this_week_start.strftime("%Y-%m-%d")
                    wearable_data["this_week"]["week_end"] = this_week_end.strftime("%Y-%m-%d")
                if last_week_data:
                    wearable_data["last_week"].update(last_week_data)
                    wearable_data["last_week"]["week_start"] = last_week_start.strftime("%Y-%m-%d")
                    wearable_data["last_week"]["week_end"] = last_week_end.strftime("%Y-%m-%d")
                
                # Store the fetched data in cache
                set_cached_wearable_data(patient.alexa_user_id, wearable_data)
                print("Wearable data fetched and cached")
                current_app.logger.info(f"Wearable data fetched and cached for {patient.alexa_user_id} from {today} to {yesterday}")
                current_app.logger.info(f"Wearable data in conversation: {wearable_data}")
                
            except Exception as e:
                current_app.logger.error(f"Failed to fetch wearable data: {e}")
                wearable_data = None
                print("Failed to fetch wearable data")
    else:
        wearable_data = None
        print("No participant id")
    
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
    # TODO: get the most recent N reports of the current patient, 
    # Get the summary of the N reports, and use it as the context of the conversation
    recent_reports = Report.query.filter_by(patient_id=patient.id).order_by(Report.created_at.desc()).limit(10).all()
    recent_reports_summaries = ReportSummary.query.filter(ReportSummary.report_id.in_([r.id for r in recent_reports])).all()
    recent_reports_summaries = [recent_reports_summary.as_dict() for recent_reports_summary in recent_reports_summaries]
    recent_reports_summaries =[
        {
            "content": r["content"],
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        }
        for r in recent_reports_summaries
    ]
    
    assistant_message = conversation(conversation_logs, wearable_data, recent_reports_summaries)
    try:
        chain_of_thoughts, assistant_message = assistant_message.split(
            "==============", 1
        )
        assistant_message = assistant_message.strip()
    except ValueError:
        chain_of_thoughts = """physical: not discussed
stress: not discussed
mood: not discussed
misc: not discussed
"""
    log = ConversationLog(
        patient_id=patient.id,
        report_id=report.id,
        role="assistant",
        content=assistant_message,
        chain_of_thoughts=chain_of_thoughts,
    )
    db.session.add(log)
    db.session.commit()
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
            "Hello, thanks for checking in for our study. "
            "How are you managing your caregiving and taking care of yourself today? "
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
    if "CONVERSATION_END" in messages[-1]["content"]:
        msg = random.choice(GREETINGS)
        symptom_kwargs = [
            {
                f"{symptom}_state": 0,
                f"{symptom}_logs": "[]",
            }
            for symptom in symptom_descriptions.keys()
        ]
        symptom_kwargs = {k: v for d in symptom_kwargs for k, v in d.items()}
        report = Report(patient_id=patient.id, **symptom_kwargs)
        patient = Patient.query.get(patient.id)
        patient.reviewed = False
        db.session.add(patient)
        db.session.add(report)
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
    else:
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
