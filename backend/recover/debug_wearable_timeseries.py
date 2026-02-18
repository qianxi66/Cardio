"""
Debug script for wearable timeseries null values.
Run from backend: python -m recover.debug_wearable_timeseries

Checks MongoDB collections (garmin_hr, garmin_respiration, garmin_ibi) for participant
test002 and reports:
- Document field names (especially time and value fields)
- Time unit (seconds vs milliseconds)
- Doc count per 5-min bin to explain nulls
"""

import datetime
import json
import os
import sys

from pymongo import MongoClient

# Load config without importing recover (avoids ask_sdk etc)
def _get_mongo_uri():
    explicit = os.getenv("RECOVER_MONGODB_URL")
    if explicit:
        return explicit
    config_path = os.getenv(
        "RECOVER_MONGODB_CONFIG_PATH",
        "/home/ubuntu/wearable/ubiwell-study-backend-core/config/study_config.json",
    )
    try:
        with open(config_path) as f:
            cfg = json.load(f).get("database", {})
        from urllib.parse import quote_plus
        u = quote_plus(cfg.get("username", ""))
        p = quote_plus(cfg.get("password", ""))
        h = cfg.get("host", "127.0.0.1")
        pt = str(cfg.get("port", "27017"))
        auth = quote_plus(cfg.get("auth_source", "admin"))
        return f"mongodb://{u}:{p}@{h}:{pt}/?authSource={auth}"
    except Exception:
        return "mongodb://127.0.0.1:27017"

mongodb_url = _get_mongo_uri()

PARTICIPANT_ID = "test002"
DB_NAME = "study_db"
BIN_SECONDS = 5 * 60


def _participant_filter(pid):
    return {"$or": [{"uid": pid}, {"participant_id": pid}]}


def main():
    print("=" * 60)
    print(f"Debug: Wearable Timeseries for participant '{PARTICIPANT_ID}'")
    print("=" * 60)

    client = MongoClient(mongodb_url)
    db = client[DB_NAME]

    now_utc = datetime.datetime.utcnow()
    start_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    start_ts = int(start_utc.timestamp())
    end_ts = int(now_utc.timestamp())

    print(f"\nWindow: {start_utc} -> {now_utc}")
    print(f"Timestamps (seconds): {start_ts} -> {end_ts}")

    collections = [
        ("garmin_hr", "heart_rate", "heart_rate"),
        ("garmin_respiration", "respiration", "respiration"),
        ("garmin_ibi", "processed_at", "bbi"),
    ]

    for coll_name, time_hint, value_hint in collections:
        print("\n" + "-" * 50)
        print(f"Collection: {coll_name}")
        print("-" * 50)

        coll = db[coll_name]
        sample = coll.find_one(_participant_filter(PARTICIPANT_ID))
        if not sample:
            print("  No document found for this participant.")
            continue

        print(f"  Sample keys: {list(sample.keys())}")

        time_fields = ["timestamp", "startTimeInSeconds", "processed_at", "startTime"]
        time_field = None
        time_val = None
        for f in time_fields:
            if f in sample:
                time_field = f
                time_val = sample.get(f)
                break
        if not time_field:
            print("  WARNING: No known time field (timestamp, startTimeInSeconds, processed_at).")
            print(f"  Available: {[k for k in sample if 'time' in k.lower() or 'ts' in k.lower()]}")
        else:
            print(f"  Time field: '{time_field}' = {time_val}")
            is_millis = time_val and time_val > 1e12
            print(f"  Likely unit: {'milliseconds' if is_millis else 'seconds'}")

        value_fields = [value_hint, "value", "heart_rate", "respiration"]
        value_field = None
        for f in value_fields:
            if f in sample:
                value_field = f
                print(f"  Value field: '{value_field}' = {sample.get(f)}")
                break
        if not value_field:
            print("  WARNING: No known value field.")
            print(f"  Numeric-like keys: {[k for k, v in sample.items() if isinstance(v, (int, float))]}")

        count = coll.count_documents({
            **_participant_filter(PARTICIPANT_ID),
            time_field or "timestamp": {"$gte": start_ts, "$lte": end_ts},
        })
        print(f"  Total docs in 24h window: {count}")

        if count == 0:
            latest = coll.find_one(_participant_filter(PARTICIPANT_ID), sort=[(time_field or "timestamp", -1)])
            if latest:
                tv = latest.get(time_field or "timestamp")
                ts = tv / 1000 if tv and tv > 1e12 else (tv or 0)
                print(f"  Latest doc time: {datetime.datetime.utcfromtimestamp(ts)} (ts={tv})")

        docs_in_bins = {}
        cursor = coll.find(
            {
                **_participant_filter(PARTICIPANT_ID),
                (time_field or "timestamp"): {"$gte": start_ts, "$lte": end_ts},
            },
            {time_field or "timestamp": 1},
        )
        for doc in cursor:
            ts = doc.get(time_field or "timestamp")
            if ts is None:
                continue
            if ts > 1e12:
                ts = ts / 1000
            offset = int(ts - start_ts)
            bin_offset = offset - (offset % BIN_SECONDS)
            docs_in_bins[bin_offset] = docs_in_bins.get(bin_offset, 0) + 1

        num_bins = max(1, (end_ts - start_ts) // BIN_SECONDS)
        bins_with_data = len(docs_in_bins)
        bins_without = num_bins - bins_with_data
        print(f"  5-min bins: total={num_bins}, with_data={bins_with_data}, empty={bins_without}")
        if bins_without > 0:
            print(f"  -> {bins_without} nulls expected in API output")

    client.close()
    print("\n" + "=" * 60)
    print("If many bins are empty, nulls are expected (device not worn / no samples in that 5-min window).")
    print("If time or value fields differ from 'timestamp'/'heart_rate' etc, aggregation may need adjustment.")
    print("=" * 60)


if __name__ == "__main__":
    main()
