from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from . import config  # noqa

db = SQLAlchemy()
cors = CORS()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = config.db_url
migrate = Migrate(app, db, render_as_batch=True)

cors.init_app(app)
db.init_app(app)
migrate.init_app(app)

with app.app_context():
    from . import apis  # noqa
    from . import db
