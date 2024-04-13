from flask import Flask
from flask_alembic import Alembic
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from . import config  # noqa

alembic = Alembic()
db = SQLAlchemy()
cors = CORS()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = config.db_url

cors.init_app(app)
db.init_app(app)
alembic.init_app(app)

with app.app_context():
    from . import (
        apis,  # noqa
        db,
    )
