import json
import math
from datetime import datetime, timedelta
from functools import wraps
import random
import secrets
import string
from threading import Thread
import time
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
import bcrypt
from flask import abort, current_app, jsonify, request, g
from .app import app
from .db import (
    AlexaIDNote,
    ConversationLog,
    Hospitalization,
    Patient,
    ReportNote,
    Risk,
    Summary,
    User,
    db,
    Token,
)
from .config import (
    VALID_API_KEYS,
    mongodb_url,
    mongodb_client_kwargs,
    GREETINGS,
)
from .openai_utils import conversation, key_questions
from .symptoms import symptom_descriptions
from pymongo import MongoClient
import logging
from sqlalchemy.exc import OperationalError

# Cache for wearable data
wearable_data_cache = {}  # Format: {alexa_user_id: {'timestamp': datetime, 'data': {...}}}
CACHE_EXPIRY_MINUTES = 60  # Cache expires after 60 minutes

MONGO_BACKOFF_SECONDS = 30
_mongo_unavailable_until = 0.0


def _get_mongo_client():
    global _mongo_unavailable_until
    now = time.time()
    if now < _mongo_unavailable_until:
        return None
    client = None
    try:
        client = MongoClient(mongodb_url, **mongodb_client_kwargs)
        client.admin.command("ping")
        return client
    except Exception:
        _mongo_unavailable_until = now + MONGO_BACKOFF_SECONDS
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        return None


def _utc_midnight_window(days=1):
    now_utc = datetime.utcnow()
    start_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    if days > 1:
        start_utc = start_utc - timedelta(days=days - 1)
    return start_utc, now_utc


def _build_labels(start_dt, end_dt, bin_seconds, label_style):
    labels = []
    cursor = start_dt
    while cursor <= end_dt:
        if label_style == "time":
            labels.append(cursor.strftime("%-H:%M"))
        else:
            labels.append(cursor.strftime("%m/%d %H:%M"))
        cursor += timedelta(seconds=bin_seconds)
    return labels


def _participant_filter(participant_id):
    return {"$or": [{"uid": participant_id}, {"participant_id": participant_id}]}


def _average_metric(db2, participant_id, collection, start_ts, end_ts, value_field):
    values = []
    cursor = db2[collection].find(
        {
            **_participant_filter(participant_id),
            "timestamp": {"$gte": start_ts, "$lte": end_ts},
        },
        {value_field: 1},
    )
    for doc in cursor:
        value = doc.get(value_field)
        if not isinstance(value, (int, float)):
            continue
        if not math.isfinite(value):
            continue
        values.append(value)
    if not values:
        return None
    return sum(values) / len(values)


def _rmssd_ibi(db2, participant_id, start_ts, end_ts):
    ibi_values = []
    cursor = db2["garmin_ibi"].find(
        {
            **_participant_filter(participant_id),
            "timestamp": {"$gte": start_ts, "$lte": end_ts},
        },
        {"value": 1},
    )
    for doc in cursor:
        value = doc.get("value")
        if value is None or value <= 0:
            continue
        if not isinstance(value, (int, float)):
            continue
        if not math.isfinite(value):
            continue
        ibi_values.append(value)
    if len(ibi_values) < 2:
        return None
    squared_diffs = []
    for i in range(len(ibi_values) - 1):
        diff = ibi_values[i + 1] - ibi_values[i]
        squared_diffs.append(diff ** 2)
    if not squared_diffs:
        return None
    mean_squared_diff = sum(squared_diffs) / len(squared_diffs)
    return math.sqrt(mean_squared_diff)


def _bucket_offset_expr(start_ts, interval_seconds, field="timestamp"):
    diff_expr = {"$subtract": [f"${field}", start_ts]}
    return {"$subtract": [diff_expr, {"$mod": [diff_expr, interval_seconds]}]}


def _aggregate_avg_by_bin(
    db2,
    participant_id,
    collection_name,
    start_ts,
    end_ts,
    interval_seconds,
    value_field,
    *,
    min_value=0,
):
    pipeline = [
        {"$match": {**_participant_filter(participant_id)}},
        {
            "$addFields": {
                "_ts": {
                    "$convert": {
                        "input": "$timestamp",
                        "to": "long",
                        "onError": None,
                        "onNull": None,
                    }
                },
                "_val": {
                    "$convert": {
                        "input": f"${value_field}",
                        "to": "double",
                        "onError": None,
                        "onNull": None,
                    }
                },
            }
        },
        {
            "$match": {
                "_ts": {"$gte": start_ts, "$lte": end_ts},
                "_val": {"$gt": min_value},
            }
        },
        {
            "$group": {
                "_id": _bucket_offset_expr(start_ts, interval_seconds, field="_ts"),
                "avg_value": {"$avg": "$_val"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    results = db2[collection_name].aggregate(pipeline)
    out = {}
    for row in results:
        value = row.get("avg_value")
        if not isinstance(value, (int, float)):
            continue
        if not math.isfinite(value):
            continue
        if value <= min_value:
            continue
        out[int(row["_id"])] = value
    return out


def _aggregate_rmssd_by_bin(
    db2,
    participant_id,
    start_ts,
    end_ts,
    interval_seconds,
    *,
    time_field="timestamp",
    value_field="value",
):
    pipeline = [
        {"$match": {**_participant_filter(participant_id)}},
        {
            "$addFields": {
                "_ts_primary": {
                    "$convert": {
                        "input": f"${time_field}",
                        "to": "long",
                        "onError": None,
                        "onNull": None,
                    }
                },
                "_ts_fallback": {
                    "$convert": {
                        "input": "$processed_at",
                        "to": "long",
                        "onError": None,
                        "onNull": None,
                    }
                },
                "_val_primary": {
                    "$convert": {
                        "input": f"${value_field}",
                        "to": "double",
                        "onError": None,
                        "onNull": None,
                    }
                },
                "_val_fallback": {
                    "$convert": {
                        "input": "$bbi",
                        "to": "double",
                        "onError": None,
                        "onNull": None,
                    }
                },
            }
        },
        {
            "$addFields": {
                "_ts": {"$ifNull": ["$_ts_primary", "$_ts_fallback"]},
                "_val": {"$ifNull": ["$_val_primary", "$_val_fallback"]},
            }
        },
        {
            "$match": {
                "_ts": {"$gte": start_ts, "$lte": end_ts},
                "_val": {"$gt": 0},
            }
        },
        {
            "$group": {
                "_id": _bucket_offset_expr(start_ts, interval_seconds, field="_ts"),
                "values": {"$push": "$_val"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    results = db2["garmin_ibi"].aggregate(pipeline)
    out = {}
    for row in results:
        values = row.get("values") or []
        clean = [v for v in values if isinstance(v, (int, float)) and v > 0 and math.isfinite(v)]
        if len(clean) < 2:
            out[int(row["_id"])] = None
            continue
        squared_diffs = []
        for i in range(len(clean) - 1):
            diff = clean[i + 1] - clean[i]
            squared_diffs.append(diff ** 2)
        if not squared_diffs:
            out[int(row["_id"])] = None
            continue
        out[int(row["_id"])] = math.sqrt(sum(squared_diffs) / len(squared_diffs))
    return out

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
        now = datetime.utcnow()
        # Token expired
        if not token.rememberme and now - token.updated_at > timedelta(
            hours=TOKEN_EXPIRATION_HOURS
        ):
            abort(401)
        # Remember me expired
        if token.rememberme and now - token.updated_at > timedelta(
            hours=REMEMBERME_EXPIRATION_HOURS
        ):
            abort(401)
        # Avoid writing on every request to reduce SQLite lock contention.
        if now - token.updated_at > timedelta(minutes=10):
            token.updated_at = now
            db.session.add(token)
            try:
                db.session.commit()
            except OperationalError:
                db.session.rollback()
                current_app.logger.warning(
                    "Skipping token updated_at write due to DB lock"
                )
        # Get user
        user = User.query.filter_by(id=token.userid).first()
        if user:
            g.current_user = user
        else:
            g.current_user = None
            abort(401)

        return f(*args, **kwargs)

    return decorated_function


def _columns_dict(model_obj):
    return {c.name: getattr(model_obj, c.name) for c in model_obj.__table__.columns}


def _user_dict(user):
    data = _columns_dict(user)
    data.pop("password", None)
    return data


def _get_patient_for_user(patient_id, user_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return None, (jsonify({"message": "Patient not found"}), 404)
    if not any(user.id == user_id for user in patient.users):
        return None, (jsonify({"message": "Permission denied"}), 401)
    return patient, None


def _parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.utcfromtimestamp(value)
        except Exception:
            return None
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


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
        patients_dict = [_columns_dict(patient) for patient in patients]
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

        users_dict = [_user_dict(user) for user in users]

        return jsonify(users_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients", methods=["POST"])
@login_required
def create_patient():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"message": "No input data provided"}), 400
        required_fields = ["user", "name"]
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
            name=data.get("name"),
            age=data.get("age"),
            gender=data.get("gender"),
            EHR_id=data.get("EHR_id") or data.get("ehr_id"),
            alexa_user_id=data.get("alexa_user_id"),
            participant_id=data.get("participant_id"),
            garmin_id=data.get("garmin_id"),
            cancer_type=data.get("cancer_type"),
            cancer_stage=data.get("cancer_stage"),
            treatment_type=data.get("treatment_type"),
            last_read_at=datetime.utcnow(),
        )

        db.session.add(patient)
        db.session.flush()

        patient.users.extend(users)

        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Patient created successfully",
                    "patient": _columns_dict(patient),
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
        if "ehr_id" in data and "EHR_id" not in data:
            data["EHR_id"] = data["ehr_id"]
            data.pop("ehr_id", None)

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
    client = _get_mongo_client()
    if client is None:
        return {"mean": None, "max": None, "min": None}
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
    client = _get_mongo_client()
    if client is None:
        return None
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
    client = _get_mongo_client()
    if client is None:
        return False
    try:
        db2 = client[db_name]
        if id_field == "uid":
            query = {
                **_participant_filter(participant_id),
                "timestamp": {"$gte": start_ts, "$lte": end_ts},
            }
        else:
            query = {
                id_field: participant_id,
                "timestamp": {"$gte": start_ts, "$lte": end_ts},
            }
        doc = db2[collection_name].find(query, {"_id": 1}).limit(1)
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
    client = _get_mongo_client()
    if client is None:
        return None
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
    client = _get_mongo_client()
    if client is None:
        return None
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
    client = _get_mongo_client()
    if client is None:
        return []
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
        patient, error = _get_patient_for_user(id, g.current_user.id)
        if error:
            return error

        patient.last_read_at = datetime.utcnow()
        db.session.add(patient)
        db.session.commit()

        patient_dict = _columns_dict(patient)
        patient_dict["users"] = [_user_dict(user) for user in patient.users]
        patient_dict["hospitalizations"] = [
            _columns_dict(item) for item in patient.hospitalizations
        ]
        patient_dict["summaries"] = [_columns_dict(item) for item in patient.summaries]
        patient_dict["risks"] = [_columns_dict(item) for item in patient.risks]
        patient_dict["conversation_logs"] = [
            _columns_dict(item) for item in patient.conversation_logs
        ]
        patient_dict["report_notes"] = [
            {
                **_columns_dict(note),
                "user": _user_dict(note.user) if note.user else None,
            }
            for note in patient.report_notes
        ]

        return jsonify(patient_dict)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients/<int:id>/wearable/timeseries", methods=["GET"])
@login_required
def get_patient_wearable_timeseries(id):
    try:
        start_time = time.time()
        patient, error = _get_patient_for_user(id, g.current_user.id)
        if error:
            return error

        range_param = request.args.get("range", "24h").strip().lower()
        if range_param == "7d":
            bin_seconds = 3 * 3600
            start_dt, now_dt = _utc_midnight_window(days=7)
            label_style = "date"
        else:
            bin_seconds = 5 * 60   #aggregated by 5 minutes
            start_dt, now_dt = _utc_midnight_window()
            label_style = "time"
        start_ts = int(start_dt.timestamp())
        end_ts = int(now_dt.timestamp())
        labels = _build_labels(start_dt, now_dt, bin_seconds, label_style)

        series = {
            "heart_rate": [],
            "respiration": [],
            "heart_rate_variability": [],
        }

        participant_id = patient.participant_id
        def finalize(payload):
            payload["elapsed_ms"] = int((time.time() - start_time) * 1000)
            return jsonify(payload)

        if not participant_id:
            series["heart_rate"] = [None] * len(labels)
            series["respiration"] = [None] * len(labels)
            series["heart_rate_variability"] = [None] * len(labels)
            return finalize(
                {
                    "times": labels,
                    "series": series,
                    "window": {"start_ts": start_ts, "end_ts": end_ts, "timezone": "UTC"},
                    "range": range_param,
                }
            )

        client = _get_mongo_client()
        if client is None:
            series["heart_rate"] = [None] * len(labels)
            series["respiration"] = [None] * len(labels)
            series["heart_rate_variability"] = [None] * len(labels)
            return finalize(
                {
                    "times": labels,
                    "series": series,
                    "window": {"start_ts": start_ts, "end_ts": end_ts, "timezone": "UTC"},
                    "range": range_param,
                }
            )

        try:
            db2 = client["study_db"]
            has_hr = _mongo_has_any(
                participant_id,
                "garmin_hr",
                start_ts,
                end_ts,
                db_name="study_db",
                id_field="uid",
            )
            has_resp = _mongo_has_any(
                participant_id,
                "garmin_respiration",
                start_ts,
                end_ts,
                db_name="study_db",
                id_field="uid",
            )
            has_ibi = _mongo_has_any(
                participant_id,
                "garmin_ibi",
                start_ts,
                end_ts,
                db_name="study_db",
                id_field="uid",
            )
            if not (has_hr or has_resp or has_ibi):
                series["heart_rate"] = [None] * len(labels)
                series["respiration"] = [None] * len(labels)
                series["heart_rate_variability"] = [None] * len(labels)
                return finalize(
                    {
                        "times": labels,
                        "series": series,
                        "window": {
                            "start_ts": start_ts,
                            "end_ts": end_ts,
                            "timezone": "UTC",
                        },
                        "range": range_param,
                    }
                )

            hr_map = _aggregate_avg_by_bin(
                db2,
                participant_id,
                "garmin_hr",
                start_ts,
                end_ts,
                bin_seconds,
                "heart_rate",
                min_value=0,
            )
            resp_map = _aggregate_avg_by_bin(
                db2,
                participant_id,
                "garmin_respiration",
                start_ts,
                end_ts,
                bin_seconds,
                "respiration",
                min_value=0,
            )
            hrv_map = _aggregate_rmssd_by_bin(
                db2,
                participant_id,
                start_ts,
                end_ts,
                bin_seconds,
                time_field="timestamp",
                value_field="bbi",
            )
            for i in range(len(labels)):
                bin_start = start_ts + i * bin_seconds
                if end_ts <= bin_start:
                    series["heart_rate"].append(None)
                    series["respiration"].append(None)
                    series["heart_rate_variability"].append(None)
                    continue
                series["heart_rate"].append(hr_map.get(i * bin_seconds))
                series["respiration"].append(resp_map.get(i * bin_seconds))
                series["heart_rate_variability"].append(hrv_map.get(i * bin_seconds))
        finally:
            client.close()

        return finalize(
            {
                "times": labels,
                "series": series,
                "window": {"start_ts": start_ts, "end_ts": end_ts, "timezone": "UTC"},
                "range": range_param,
            }
        )
    except Exception as e:
        logging.error(f"Failed to fetch wearable timeseries: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@current_app.route("/patients/<int:id>/hospitalizations", methods=["GET"])
@login_required
def get_hospitalizations(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    items = Hospitalization.query.filter_by(patient_id=patient.id).order_by(
        Hospitalization.date.desc()
    ).all()
    return jsonify([_columns_dict(item) for item in items])


@current_app.route("/patients/<int:id>/hospitalizations", methods=["POST"])
@login_required
def create_hospitalization(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    data = request.get_json() or {}
    event = data.get("event")
    if not event:
        return jsonify({"message": "Missing fields: event"}), 400
    date_value = _parse_datetime(data.get("date")) or datetime.utcnow()
    hospitalization = Hospitalization(
        patient_id=patient.id,
        date=date_value,
        event=event,
    )
    db.session.add(hospitalization)
    db.session.commit()
    return jsonify(_columns_dict(hospitalization)), 201


@current_app.route("/patients/<int:id>/summaries", methods=["GET"])
@login_required
def get_summaries(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    items = Summary.query.filter_by(patient_id=patient.id).order_by(
        Summary.date.desc()
    ).all()
    return jsonify([_columns_dict(item) for item in items])


@current_app.route("/patients/<int:id>/summaries", methods=["POST"])
@login_required
def create_summary(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    data = request.get_json() or {}
    date_value = _parse_datetime(data.get("date"))
    summary = Summary(
        patient_id=patient.id,
        heart_rate_min=data.get("heart_rate_min"),
        heart_rate_max=data.get("heart_rate_max"),
        heart_rate_average=data.get("heart_rate_average"),
        spo2_min=data.get("spo2_min"),
        spo2_max=data.get("spo2_max"),
        spo2_average=data.get("spo2_average"),
        respiration_min=data.get("respiration_min"),
        respiration_max=data.get("respiration_max"),
        respiration_average=data.get("respiration_average"),
        hrv_min=data.get("hrv_min"),
        hrv_max=data.get("hrv_max"),
        hrv_average=data.get("hrv_average"),
        short_of_breath=data.get("short_of_breath"),
        chest_discomfort=data.get("chest_discomfort"),
        fatigue=data.get("fatigue"),
        palpitation=data.get("palpitation"),
        swelling=data.get("swelling"),
        syncope=data.get("syncope"),
        date=date_value or datetime.utcnow(),
    )
    db.session.add(summary)
    db.session.commit()
    return jsonify(_columns_dict(summary)), 201


@current_app.route("/patients/<int:id>/risks", methods=["GET"])
@login_required
def get_risks(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    items = Risk.query.filter_by(patient_id=patient.id).order_by(
        Risk.date.desc()
    ).all()
    return jsonify([_columns_dict(item) for item in items])


@current_app.route("/patients/<int:id>/risks", methods=["POST"])
@login_required
def create_risk(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    data = request.get_json() or {}
    if data.get("risk_score") is None:
        return jsonify({"message": "Missing fields: risk_score"}), 400
    date_value = _parse_datetime(data.get("date"))
    risk = Risk(
        patient_id=patient.id,
        risk_score=data.get("risk_score"),
        important_of_chest=data.get("important_of_chest"),
        important_of_heart=data.get("important_of_heart"),
        important_of_respiration=data.get("important_of_respiration"),
        important_of_hrv=data.get("important_of_hrv"),
        date=date_value or datetime.utcnow(),
    )
    db.session.add(risk)
    db.session.commit()
    return jsonify(_columns_dict(risk)), 201


@current_app.route("/patients/<int:id>/conversation_logs", methods=["GET"])
@login_required
def get_conversation_logs(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    items = ConversationLog.query.filter_by(patient_id=patient.id).order_by(
        ConversationLog.date.desc()
    ).all()
    return jsonify([_columns_dict(item) for item in items])


@current_app.route("/patients/<int:id>/conversation_logs", methods=["POST"])
@login_required
def create_conversation_log_for_patient(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    data = request.get_json() or {}
    role = data.get("role")
    content = data.get("content")
    if not role or not content:
        return jsonify({"message": "Missing fields: role, content"}), 400
    date_value = _parse_datetime(data.get("date"))
    log = ConversationLog(
        patient_id=patient.id,
        role=role,
        content=content,
        chain_of_thoughts=data.get("chain_of_thoughts"),
        symptoms_chest=data.get("symptoms_chest"),
        symptoms_other=data.get("symptoms_other"),
        date=date_value or datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(_columns_dict(log)), 201


@current_app.route("/patients/<int:id>/notes", methods=["GET"])
@login_required
def get_patient_notes(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    notes = ReportNote.query.options(joinedload(ReportNote.user)).filter_by(
        patient_id=patient.id
    ).order_by(ReportNote.created_at.desc()).all()
    return jsonify(
        [
            {
                **_columns_dict(note),
                "user": _user_dict(note.user) if note.user else None,
            }
            for note in notes
        ]
    )


@current_app.route("/patients/<int:id>/notes", methods=["POST"])
@login_required
def create_patient_note(id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    data = request.get_json() or {}
    content = data.get("content")
    if not content:
        return jsonify({"message": "Missing fields: content"}), 400
    note = ReportNote(
        patient_id=patient.id,
        user_id=g.current_user.id,
        content=content,
        created_at=datetime.utcnow(),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(_columns_dict(note)), 201


@current_app.route("/patients/<int:id>/notes/<int:note_id>", methods=["DELETE"])
@login_required
def delete_patient_note(id, note_id):
    patient, error = _get_patient_for_user(id, g.current_user.id)
    if error:
        return error
    note = ReportNote.query.filter_by(id=note_id, patient_id=patient.id).first()
    if not note:
        return jsonify({"message": "Note not found"}), 404
    db.session.delete(note)
    db.session.commit()
    return jsonify({"message": "Note deleted."})


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
    
    data = request.get_json() or {}
    content = data.get("content")
    if not content:
        return jsonify({"message": "Missing fields: content"}), 400
    log = ConversationLog(
        patient_id=patient.id,
        role="user",
        content=content,
        date=datetime.utcnow(),
    )
    
    db.session.add(log)
    db.session.commit()
    
    conversation_logs = (
        ConversationLog.query.filter_by(patient_id=patient.id)
        .order_by(ConversationLog.date.asc())
        .all()
    )
    conversation_logs = [_columns_dict(log) for log in conversation_logs]
    conversation_logs = [
        {
            "content": log["content"]
            if log["role"] == "user"
            else (log.get("chain_of_thoughts") or "") + "==============\n" + log["content"],
            "role": log["role"],
        }
        for log in conversation_logs
    ]
    assistant_message = conversation(conversation_logs, wearable_data, None)
    try:
        chain_of_thoughts, assistant_message = assistant_message.split(
            "==============", 1
        )
        assistant_message = assistant_message.strip()
    except ValueError:
        chain_of_thoughts = ""
    log = ConversationLog(
        patient_id=patient.id,
        role="assistant",
        content=assistant_message,
        chain_of_thoughts=chain_of_thoughts,
        date=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(_columns_dict(log))


def _date_midnight(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_or_create_summary(patient_id, target_date):
    day_start = _date_midnight(target_date)
    day_end = day_start + timedelta(days=1)
    summary = (
        Summary.query.filter_by(patient_id=patient_id)
        .filter(Summary.date >= day_start, Summary.date < day_end)
        .first()
    )
    if summary is None:
        summary = Summary(patient_id=patient_id, date=day_start)
        for symptom in symptom_descriptions:
            setattr(summary, f"{symptom}_state", 0)
            setattr(summary, f"{symptom}_logs", "[]")
        db.session.add(summary)
        db.session.commit()
    return summary


def process_patient_summary(patient_id, target_date):
    """
    Process conversation logs for a patient on target_date: run key_questions
    and write symptom state/logs to Summary.
    """
    with app.app_context():
        day_start = _date_midnight(target_date)
        day_end = day_start + timedelta(days=1)
        logs = (
            ConversationLog.query.filter_by(patient_id=patient_id)
            .filter(ConversationLog.date >= day_start, ConversationLog.date < day_end)
            .order_by(ConversationLog.date.asc())
            .all()
        )
        if not logs:
            return
        messages = [
            {"id": log.id, "content": log.content, "role": log.role}
            for log in logs
        ]
        try:
            response = key_questions(json.dumps(messages))
            response = json.loads(response)
        except Exception as e:
            logging.warning("key_questions failed: %s", e)
            return
        summary = get_or_create_summary(patient_id, target_date)
        for key in response:
            if key not in symptom_descriptions:
                continue
            setattr(summary, f"{key}_state", response[key].get("state", 0))
            setattr(summary, f"{key}_logs", json.dumps(response[key].get("logs", [])))
            if "scale" in response[key] and hasattr(summary, f"{key}_scale"):
                setattr(summary, f"{key}_scale", response[key]["scale"])
        db.session.add(summary)
        db.session.commit()
        logging.info("process_patient_summary done for patient_id=%s date=%s", patient_id, target_date)


def session_end_hook(alexa_user_id):
    with app.app_context():
        patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
        if patient is None:
            return
        process_patient_summary(patient.id, datetime.utcnow())


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
    messages = (
        ConversationLog.query.filter_by(patient_id=patient.id)
        .order_by(ConversationLog.date.asc())
        .all()
    )
    if len(messages) == 0:
        msg = (
            "Hello, thanks for checking in for our study. "
            "How are you managing your caregiving and taking care of yourself today? "
        )
        message = ConversationLog(
            patient_id=patient.id,
            role="assistant",
            chain_of_thoughts="",
            content=msg,
            date=datetime.utcnow(),
        )
        db.session.add(message)
        db.session.commit()
        return jsonify({"message": "success", "last_message": _columns_dict(message)})
    messages = [_columns_dict(message) for message in messages]
    messages = [i for i in messages if i["role"] == "assistant"]
    if "CONVERSATION_END" in messages[-1]["content"]:
        msg = random.choice(GREETINGS)
        message = ConversationLog(
            patient_id=patient.id,
            role="assistant",
            chain_of_thoughts="",
            content=msg,
            date=datetime.utcnow(),
        )
        db.session.add(message)
        db.session.commit()
        return jsonify({"message": "success", "last_message": _columns_dict(message)})
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
