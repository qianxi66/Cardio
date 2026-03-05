from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from pymongo import MongoClient
from sqlalchemy.exc import OperationalError

from .app import app
from .config import mongodb_client_kwargs, mongodb_url
from .db import Patient, Summary, Note, db
from .symptoms import symptom_descriptions


EASTERN_TZ = ZoneInfo("America/New_York")
BIN_SECONDS = 5 * 60


def _participant_filter(participant_id: str):
    return {"$or": [{"uid": participant_id}, {"participant_id": participant_id}]}


def _round_metric(field_name: str, value: float | None) -> float | None:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if field_name.startswith("heart_rate_"):
        return float(int(round(value)))
    return round(float(value), 1)


def _safe_stats(values: Iterable[float]):
    clean = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    if not clean:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": min(clean),
        "max": max(clean),
        "avg": (sum(clean) / len(clean)),
    }


def _day_window_eastern_now():
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(EASTERN_TZ)
    day_start_et = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    # Mongo timestamps are UTC epoch seconds.
    start_ts = int(day_start_et.timestamp())
    end_ts = int(now_et.timestamp())
    # Keep SQL datetime naive, but aligned to ET day boundary.
    day_start_sql = day_start_et.replace(tzinfo=None)
    return day_start_sql, start_ts, end_ts


def _get_or_create_daily_summary(patient_id: int, day_start_sql: datetime):
    day_end_sql = day_start_sql + timedelta(days=1)
    summary = (
        Summary.query.filter_by(patient_id=patient_id)
        .filter(Summary.date >= day_start_sql, Summary.date < day_end_sql)
        .first()
    )
    if summary is None:
        summary = Summary(patient_id=patient_id, date=day_start_sql)
        for symptom in symptom_descriptions:
            setattr(summary, f"{symptom}_state", 0)
            setattr(summary, f"{symptom}_logs", "[]")
        db.session.add(summary)
    return summary


def _fetch_numeric_values(db2, participant_id: str, collection_name: str, value_field: str, start_ts: int, end_ts: int):
    cursor = db2[collection_name].find(
        {
            **_participant_filter(participant_id),
            "timestamp": {"$gte": start_ts, "$lte": end_ts},
        },
        {value_field: 1},
    )
    out: list[float] = []
    for doc in cursor:
        value = doc.get(value_field)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        if value <= 0:
            continue
        out.append(float(value))
    return out


def _bucket_offset_expr(start_ts: int, interval_seconds: int, field: str):
    diff_expr = {"$subtract": [f"${field}", start_ts]}
    return {"$subtract": [diff_expr, {"$mod": [diff_expr, interval_seconds]}]}


def _fetch_hrv_rmssd_bins(db2, participant_id: str, start_ts: int, end_ts: int):
    pipeline = [
        {"$match": {**_participant_filter(participant_id)}},
        {
            "$addFields": {
                "_ts_primary": {
                    "$convert": {
                        "input": "$timestamp",
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
                        "input": "$bbi",
                        "to": "double",
                        "onError": None,
                        "onNull": None,
                    }
                },
                "_val_fallback": {
                    "$convert": {
                        "input": "$value",
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
                "_id": _bucket_offset_expr(start_ts, BIN_SECONDS, field="_ts"),
                "values": {"$push": "$_val"},
            }
        },
    ]
    rows = db2["garmin_ibi"].aggregate(pipeline)
    rmssd_values: list[float] = []
    for row in rows:
        values = row.get("values") or []
        clean = [v for v in values if isinstance(v, (int, float)) and v > 0 and math.isfinite(v)]
        if len(clean) < 2:
            continue
        squared_diffs = []
        for i in range(len(clean) - 1):
            diff = clean[i + 1] - clean[i]
            squared_diffs.append(diff ** 2)
        if not squared_diffs:
            continue
        rmssd = math.sqrt(sum(squared_diffs) / len(squared_diffs))
        if math.isfinite(rmssd):
            rmssd_values.append(float(rmssd))
    return rmssd_values


def _sync_once():
    day_start_sql, start_ts, end_ts = _day_window_eastern_now()
    client = MongoClient(mongodb_url, **mongodb_client_kwargs)
    db2 = client["study_db"]
    try:
        patients = Patient.query.filter(Patient.participant_id.isnot(None)).all()
        updated = 0
        skipped = 0
        for patient in patients:
            participant_id = (patient.participant_id or "").strip()
            if not participant_id:
                continue

            summary = _get_or_create_daily_summary(patient.id, day_start_sql)

            hr_values = _fetch_numeric_values(
                db2, participant_id, "garmin_hr", "heart_rate", start_ts, end_ts
            )
            resp_values = _fetch_numeric_values(
                db2, participant_id, "garmin_respiration", "respiration", start_ts, end_ts
            )
            hrv_values = _fetch_hrv_rmssd_bins(db2, participant_id, start_ts, end_ts)

            hr = _safe_stats(hr_values)
            resp = _safe_stats(resp_values)
            hrv = _safe_stats(hrv_values)

            summary.heart_rate_min = _round_metric("heart_rate_min", hr["min"])
            summary.heart_rate_max = _round_metric("heart_rate_max", hr["max"])
            summary.heart_rate_average = _round_metric("heart_rate_average", hr["avg"])

            summary.respiration_min = _round_metric("respiration_min", resp["min"])
            summary.respiration_max = _round_metric("respiration_max", resp["max"])
            summary.respiration_average = _round_metric("respiration_average", resp["avg"])

            summary.hrv_min = _round_metric("hrv_min", hrv["min"])
            summary.hrv_max = _round_metric("hrv_max", hrv["max"])
            summary.hrv_average = _round_metric("hrv_average", hrv["avg"])

            try:
                db.session.commit()
                updated += 1
            except OperationalError:
                db.session.rollback()
                skipped += 1
                continue

            # Generate AI summary note for today if one doesn't exist yet.
            # Importing here (inside the app context) avoids circular imports.
            day_end_sql = day_start_sql + timedelta(days=1)
            has_note = (
                Note.query.filter_by(patient_id=patient.id, creator_type="ai")
                .filter(
                    Note.created_at >= day_start_sql,
                    Note.created_at < day_end_sql,
                )
                .first()
                is not None
            )
            if not has_note:
                try:
                    from .apis import _generate_ai_note_for_patient
                    _generate_ai_note_for_patient(patient.id, day_start_sql)
                except Exception as exc:
                    print(f"[cardio_summary_sync] AI note failed for patient {patient.id}: {exc}")

        print(
            f"[cardio_summary_sync] synced {updated} patients (skipped={skipped}) "
            f"for ET day {day_start_sql.date()} "
            f"(start_ts={start_ts}, end_ts={end_ts})"
        )
    finally:
        client.close()


def main():
    with app.app_context():
        _sync_once()


if __name__ == "__main__":
    main()
