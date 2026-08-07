from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None
from sqlalchemy.exc import OperationalError

from .app import app
from .config import mongodb_client_kwargs, mongodb_url
from .db import Patient, Summary, Note, db
from .symptoms import symptom_descriptions


EASTERN_TZ = ZoneInfo("America/New_York")
BIN_SECONDS = 5 * 60
STATE_BIN_SECONDS = 15 * 60


def _create_mongo_client():
    if MongoClient is None:
        print("[cardio_summary_sync] pymongo is not installed; skip wearable sync/backfill")
        return None
    try:
        return MongoClient(mongodb_url, **mongodb_client_kwargs)
    except Exception as exc:
        print(f"[cardio_summary_sync] cannot create Mongo client: {exc}")
        return None


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


def _get_daily_summary(patient_id: int, day_start_sql: datetime):
    day_end_sql = day_start_sql + timedelta(days=1)
    return (
        Summary.query.filter_by(patient_id=patient_id)
        .filter(Summary.date >= day_start_sql, Summary.date < day_end_sql)
        .first()
    )


def _create_daily_summary(patient_id: int, day_start_sql: datetime):
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


def _fetch_spo2_values(db2, participant_id: str, start_ts: int, end_ts: int):
    """Fetch SpO2 values from multiple possible Garmin collections/fields."""
    spo2_candidates = [
        ("garmin_spo2", "spo2"),
        ("garmin_spo2", "oxygen_saturation"),
        ("garmin_pulse_ox", "spo2"),
        ("garmin_pulse_ox", "oxygen_saturation"),
        ("garmin_hr", "spo2"),
        ("garmin_hr", "oxygen_saturation"),
        ("garmin_respiration", "spo2"),
        ("garmin_respiration", "oxygen_saturation"),
        ("garmin_stress", "spo2"),
        ("garmin_stress", "oxygen_saturation"),
    ]
    out: list[float] = []
    for collection_name, value_field in spo2_candidates:
        try:
            cursor = db2[collection_name].find(
                {
                    **_participant_filter(participant_id),
                    "timestamp": {"$gte": start_ts, "$lte": end_ts},
                    value_field: {"$type": "number", "$gt": 50, "$lte": 100},
                },
                {value_field: 1},
            )
            for doc in cursor:
                value = doc.get(value_field)
                if isinstance(value, (int, float)) and math.isfinite(value) and 50 < value <= 100:
                    out.append(float(value))
        except Exception:
            continue
    return out


def _is_alert(metric: str, value: float | None) -> bool:
    """Return True if the value exceeds alert thresholds (matches chart logic)."""
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    if metric == "heart_rate":
        return value > 120 or value < 60
    if metric == "respiration":
        return value > 24 or value < 8
    if metric == "spo2":
        return value < 94
    if metric == "hrv":
        return value < 15
    return False


def _wearable_state(metric: str, stats: dict) -> int:
    """Compute wearable dot state: 0=no data, 1=green(normal), 3=red(alert)."""
    if stats["min"] is None:
        return 0
    # Check if any extreme value triggers an alert
    for key in ("min", "max", "avg"):
        if _is_alert(metric, stats[key]):
            return 3
    return 1


def _scan_alert_state(metric: str, value_map: dict[int, float | None]) -> int:
    """Compute state from binned values: 0=no data, 1=green, 3=red."""
    values = [
        value
        for value in value_map.values()
        if isinstance(value, (int, float)) and math.isfinite(value)
    ]
    if not values:
        return 0
    for value in values:
        if _is_alert(metric, value):
            return 3
    return 1


def _merge_spo2_bins(db2, participant_id: str, start_ts: int, end_ts: int, bin_seconds: int):
    spo2_candidates = [
        ("garmin_spo2", "spo2"),
        ("garmin_spo2", "oxygen_saturation"),
        ("garmin_pulse_ox", "spo2"),
        ("garmin_pulse_ox", "oxygen_saturation"),
        ("garmin_hr", "spo2"),
        ("garmin_hr", "oxygen_saturation"),
        ("garmin_respiration", "spo2"),
        ("garmin_respiration", "oxygen_saturation"),
        ("garmin_stress", "spo2"),
        ("garmin_stress", "oxygen_saturation"),
    ]
    spo2_map: dict[int, float] = {}
    from .apis import _aggregate_avg_by_bin

    for collection_name, value_field in spo2_candidates:
        try:
            cur_map = _aggregate_avg_by_bin(
                db2,
                participant_id,
                collection_name,
                start_ts,
                end_ts,
                bin_seconds,
                value_field,
                min_value=0,
            )
        except Exception:
            continue
        for bucket, value in cur_map.items():
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            if value < 50 or value > 100:
                continue
            if bucket not in spo2_map:
                spo2_map[bucket] = float(value)
    return spo2_map


def _sync_once():
    from .apis import _aggregate_avg_by_bin, _aggregate_rmssd_by_bin

    day_start_sql, start_ts, end_ts = _day_window_eastern_now()
    client = _create_mongo_client()
    if client is None:
        return
    db2 = client["study_db"]
    try:
        patients = Patient.query.filter(Patient.participant_id.isnot(None)).all()
        created = 0
        updated = 0
        skipped_no_data = 0
        skipped_db_error = 0
        for patient in patients:
            participant_id = (patient.participant_id or "").strip()
            if not participant_id:
                continue

            hr_values = _fetch_numeric_values(
                db2, participant_id, "garmin_hr", "heart_rate", start_ts, end_ts
            )
            resp_values = _fetch_numeric_values(
                db2, participant_id, "garmin_respiration", "respiration", start_ts, end_ts
            )
            hrv_values = _fetch_hrv_rmssd_bins(db2, participant_id, start_ts, end_ts)
            spo2_values = _fetch_spo2_values(db2, participant_id, start_ts, end_ts)

            hr = _safe_stats(hr_values)
            resp = _safe_stats(resp_values)
            hrv = _safe_stats(hrv_values)
            spo2 = _safe_stats(spo2_values)

            # Dot states follow the same 15-minute bin rule used by chart logic.
            hr_map = _aggregate_avg_by_bin(
                db2,
                participant_id,
                "garmin_hr",
                start_ts,
                end_ts,
                STATE_BIN_SECONDS,
                "heart_rate",
                min_value=0,
            )
            resp_map = _aggregate_avg_by_bin(
                db2,
                participant_id,
                "garmin_respiration",
                start_ts,
                end_ts,
                STATE_BIN_SECONDS,
                "respiration",
                min_value=0,
            )
            hrv_map = _aggregate_rmssd_by_bin(
                db2,
                participant_id,
                start_ts,
                end_ts,
                STATE_BIN_SECONDS,
                time_field="timestamp",
                value_field="bbi",
            )
            spo2_map = _merge_spo2_bins(
                db2,
                participant_id,
                start_ts,
                end_ts,
                STATE_BIN_SECONDS,
            )

            has_wearable_data = any(
                [
                    hr["min"] is not None,
                    resp["min"] is not None,
                    hrv["min"] is not None,
                    spo2["min"] is not None,
                ]
            )
            if not has_wearable_data:
                skipped_no_data += 1
                continue

            summary = _get_daily_summary(patient.id, day_start_sql)
            is_new = summary is None
            if is_new:
                summary = _create_daily_summary(patient.id, day_start_sql)

            summary.heart_rate_min = _round_metric("heart_rate_min", hr["min"])
            summary.heart_rate_max = _round_metric("heart_rate_max", hr["max"])
            summary.heart_rate_average = _round_metric("heart_rate_average", hr["avg"])

            summary.respiration_min = _round_metric("respiration_min", resp["min"])
            summary.respiration_max = _round_metric("respiration_max", resp["max"])
            summary.respiration_average = _round_metric("respiration_average", resp["avg"])

            summary.hrv_min = _round_metric("hrv_min", hrv["min"])
            summary.hrv_max = _round_metric("hrv_max", hrv["max"])
            summary.hrv_average = _round_metric("hrv_average", hrv["avg"])

            summary.spo2_min = _round_metric("spo2_min", spo2["min"])
            summary.spo2_max = _round_metric("spo2_max", spo2["max"])
            summary.spo2_average = _round_metric("spo2_average", spo2["avg"])

            # Update wearable dot states from 15-minute bins.
            summary.heart_rate_state = _scan_alert_state("heart_rate", hr_map)
            summary.respiration_state = _scan_alert_state("respiration", resp_map)
            summary.spo2_state = _scan_alert_state("spo2", spo2_map)
            summary.hrv_state = _scan_alert_state("hrv", hrv_map)

            try:
                db.session.commit()
                if is_new:
                    created += 1
                else:
                    updated += 1
            except OperationalError:
                db.session.rollback()
                skipped_db_error += 1
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
            f"[cardio_summary_sync] created={created} updated={updated} "
            f"(skipped_no_data={skipped_no_data}, skipped_db_error={skipped_db_error}) "
            f"for ET day {day_start_sql.date()} "
            f"(start_ts={start_ts}, end_ts={end_ts})"
        )
    finally:
        client.close()


def main():
    with app.app_context():
        _sync_once()


def backfill_wearable_states():
    """Scan ALL existing summaries and update wearable dot states from MongoDB.

    Uses the same aggregation pipeline approach as the timeseries chart API
    for efficient server-side aggregation (15-min bins).
    """
    from .apis import (
        _aggregate_avg_by_bin,
        _aggregate_rmssd_by_bin,
        _participant_filter,
    )

    BIN_BACKFILL = 15 * 60  # 15-min bins, same as chart

    client = _create_mongo_client()
    if client is None:
        return
    db2 = client["study_db"]
    try:
        patients = Patient.query.filter(Patient.participant_id.isnot(None)).all()
        total_updated = 0
        total_red = 0
        for patient in patients:
            participant_id = (patient.participant_id or "").strip()
            if not participant_id:
                continue
            summaries = Summary.query.filter_by(patient_id=patient.id).all()
            for summary in summaries:
                summary_date = summary.date
                if summary_date is None:
                    continue
                # Build day window in Eastern time (same as timeseries API)
                if summary_date.tzinfo is None:
                    day_start_et = summary_date.replace(
                        hour=0, minute=0, second=0, microsecond=0,
                        tzinfo=EASTERN_TZ,
                    )
                else:
                    day_start_et = summary_date.astimezone(EASTERN_TZ).replace(
                        hour=0, minute=0, second=0, microsecond=0,
                    )
                day_end_et = day_start_et + timedelta(days=1)
                start_ts = int(day_start_et.timestamp())
                end_ts = int(day_end_et.timestamp())

                # --- Heart Rate ---
                hr_map = _aggregate_avg_by_bin(
                    db2, participant_id, "garmin_hr",
                    start_ts, end_ts, BIN_BACKFILL, "heart_rate", min_value=0,
                )
                # --- Respiration ---
                resp_map = _aggregate_avg_by_bin(
                    db2, participant_id, "garmin_respiration",
                    start_ts, end_ts, BIN_BACKFILL, "respiration", min_value=0,
                )
                # --- HRV ---
                hrv_map = _aggregate_rmssd_by_bin(
                    db2, participant_id,
                    start_ts, end_ts, BIN_BACKFILL,
                    time_field="timestamp", value_field="bbi",
                )
                # --- SpO2 (multi-source, same as chart) ---
                spo2_candidates = [
                    ("garmin_spo2", "spo2"),
                    ("garmin_spo2", "oxygen_saturation"),
                    ("garmin_pulse_ox", "spo2"),
                    ("garmin_pulse_ox", "oxygen_saturation"),
                    ("garmin_hr", "spo2"),
                    ("garmin_hr", "oxygen_saturation"),
                    ("garmin_respiration", "spo2"),
                    ("garmin_respiration", "oxygen_saturation"),
                    ("garmin_stress", "spo2"),
                    ("garmin_stress", "oxygen_saturation"),
                ]
                spo2_map: dict = {}
                for coll, field in spo2_candidates:
                    try:
                        cur = _aggregate_avg_by_bin(
                            db2, participant_id, coll,
                            start_ts, end_ts, BIN_BACKFILL, field, min_value=0,
                        )
                    except Exception:
                        continue
                    for bucket, value in cur.items():
                        if not isinstance(value, (int, float)) or not math.isfinite(value):
                            continue
                        if value < 50 or value > 100:
                            continue
                        if bucket not in spo2_map:
                            spo2_map[bucket] = value

                # Scan binned values for alerts
                def _scan_alert(metric: str, value_map: dict) -> int:
                    """0=no data, 1=green, 3=red."""
                    vals = [v for v in value_map.values()
                            if v is not None and isinstance(v, (int, float)) and math.isfinite(v)]
                    if not vals:
                        return 0
                    for v in vals:
                        if _is_alert(metric, v):
                            return 3
                    return 1

                summary.heart_rate_state = _scan_alert("heart_rate", hr_map)
                summary.respiration_state = _scan_alert("respiration", resp_map)
                summary.hrv_state = _scan_alert("hrv", hrv_map)
                summary.spo2_state = _scan_alert("spo2", spo2_map)

                if summary.heart_rate_state == 3 or summary.respiration_state == 3 \
                        or summary.hrv_state == 3 or summary.spo2_state == 3:
                    total_red += 1
                total_updated += 1

            try:
                db.session.commit()
            except OperationalError:
                db.session.rollback()

            print(
                f"[backfill] patient {patient.id} ({participant_id}): "
                f"{len(summaries)} summaries"
            )

        print(f"[backfill] done. scanned={total_updated}, red_days={total_red}")
    finally:
        client.close()


def run_backfill():
    with app.app_context():
        backfill_wearable_states()


if __name__ == "__main__":
    main()
