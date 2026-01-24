from datetime import datetime
from pymongo import MongoClient, DESCENDING

from .config import mongodb_url


METRICS = {
    "heart_rate": {
        "collection": "garmin_hr",
        "max_value": 160,
        "thresholds": [60, 100, 120],
        "scale": True,
    },
    "respiration": {
        "collection": "garmin_respiration",
        "max_value": 30,
        "thresholds": [12, 20, 24],
        "scale": True,
    },
    "stress": {
        "collection": "garmin_stress",
        "max_value": 100,
        "thresholds": [25, 50, 75],
        "scale": True,
    },
    "steps": {
        "collection": "garmin_steps",
        "max_value": 12000,
        "thresholds": [3000, 7000, 10000],
        "scale": False,
    },
    "energy": {
        "collection": "garmin_energy",
        "max_value": 120,
        "thresholds": [25, 50, 75],
        "scale": True,
    },
    "ibi": {
        "collection": "garmin_ibi",
        "max_value": 1200,
        "thresholds": [600, 900, 1100],
        "scale": True,
    },
}


def _state_from_value(value, thresholds):
    if value is None:
        return None
    if value <= thresholds[0]:
        return 1
    if value <= thresholds[1]:
        return 2
    if value <= thresholds[2]:
        return 3
    return 4


def _scale_from_value(value, max_value):
    if value is None or max_value <= 0:
        return 0
    return int(max(0, min(100, (value / max_value) * 100)))


def _latest_value(db, collection_name, patient_id, participant_id=None):
    query = {"patient_id": patient_id}
    doc = db[collection_name].find(query).sort("timestamp", DESCENDING).limit(1)
    result = next(doc, None)
    if result is None and participant_id:
        result = (
            db[collection_name]
            .find({"participant_id": participant_id})
            .sort("timestamp", DESCENDING)
            .limit(1)
        )
        result = next(result, None)
    if result is None:
        return None
    return result.get("value")


def metrics_for_participant(patient_id, participant_id=None, db_name=None):
    client = MongoClient(mongodb_url)
    db = client[db_name or "study_db"]
    metrics = {}
    try:
        for key, meta in METRICS.items():
            value = _latest_value(db, meta["collection"], patient_id, participant_id)
            state = _state_from_value(value, meta["thresholds"])
            scale = _scale_from_value(value, meta["max_value"]) if meta["scale"] else 0
            metrics[key] = {
                "value": value,
                "state": state,
                "scale": scale,
                "updated_at": datetime.utcnow(),
            }
    finally:
        client.close()
    return metrics
