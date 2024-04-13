from flask import current_app, jsonify

from .db import Patient


# get patients, return all patients
@current_app.route("/patients", methods=["GET"])
def get_patients():
    patients = Patient.query.all()
    return jsonify(patients)
