import json
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from flask_migrate import Migrate
from ask_sdk_core.serialize import DefaultSerializer
from ask_sdk_core.skill import CustomSkill
from ask_sdk_model import RequestEnvelope

from . import config  # noqa
from .db import db

# cors allow everyting


app = Flask(__name__)
cors = CORS()
app.config["SQLALCHEMY_DATABASE_URI"] = config.db_url
migrate = Migrate(app, db, render_as_batch=True)

cors.init_app(app)
db.init_app(app)
migrate.init_app(app)

with app.app_context():
    from . import apis  # noqa
    from . import cli  # noqa
    from . import db as db_module  # noqa

try:
    from . import alexa as alexa_module  # noqa
except Exception:
    alexa_module = None

serializer = DefaultSerializer()


@app.route("/invoke_skill", methods=["POST"])
def invoke_skill():
    if not alexa_module or not getattr(alexa_module, "skill_builder", None):
        return jsonify({"error": "Alexa module not available"}), 500
    raw_body = request.get_data(as_text=True)
    try:
        g.alexa_raw_request = request.get_json(silent=True) or json.loads(raw_body)
    except Exception:
        g.alexa_raw_request = None
    try:
        envelope = serializer.deserialize(raw_body, RequestEnvelope)
        skill = CustomSkill(
            skill_configuration=alexa_module.skill_builder.skill_configuration
        )
        response = skill.invoke(envelope, None)
        return jsonify(serializer.serialize(response))
    except Exception as exc:
        app.logger.exception("Alexa invoke_skill failed: %s", exc)
        return jsonify({"error": "Alexa invoke error"}), 500
