import types
import typing as t
from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.table import _Table

from .app import db

_O = t.TypeVar("_O", bound=object)  # Based on sqlalchemy.orm._typing.py


class NotFound(Exception):
    def __init__(self, table_name, ident: t.Any) -> None:
        self.table_name = table_name
        self.ident = ident

    def __str__(self) -> str:
        return f"{self.table_name}({self.ident}) not found"


@dataclass
class Patient(db.Model):
    id: int
    age: int
    gender: str
    EHR_id: str
    alexa_user_id: str
    medical_history: str
    medication: str
    participant_id: str

    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    EHR_id = db.Column(db.String(50))
    alexa_user_id = db.Column(db.String(50), nullable=True)
    medical_history = db.Column(db.Text)
    medication = db.Column(db.Text)
    participant_id = db.Column(db.String(20))


@dataclass
class User(db.Model):
    id: int
    username: str
    password: str
    email: str
    name: str

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(255))
    email = db.Column(db.String(100))
    name = db.Column(db.String(100))


@dataclass
class Report(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    patient_id: int = db.Column(db.Integer, db.ForeignKey("patient.id"))
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    read: bool = db.Column(db.Boolean, default=False)

    pain_state: int = db.Column(db.Integer)
    pain_logs: str = db.Column(db.String)

    breathing_state: int = db.Column(db.Integer)
    breathing_logs: str = db.Column(db.String)

    fever_state: int = db.Column(db.Integer)
    fever_logs: str = db.Column(db.String)

    stools_state: int = db.Column(db.Integer)
    stools_logs: str = db.Column(db.String)

    drainage_state: int = db.Column(db.Integer)
    drainage_logs: str = db.Column(db.String)

    activity_state: int = db.Column(db.Integer)
    activity_logs: str = db.Column(db.String)

    conscious_state: int = db.Column(db.Integer)
    conscious_logs: str = db.Column(db.String)

    constipation_state: int = db.Column(db.Integer)
    constipation_logs: str = db.Column(db.String)

    diarrhea_state: int = db.Column(db.Integer)
    diarrhea_logs: str = db.Column(db.String)

    eating_state: int = db.Column(db.Integer)
    eating_logs: str = db.Column(db.String)

    swelling_state: int = db.Column(db.Integer)
    swelling_logs: str = db.Column(db.String)

    mood_state: int = db.Column(db.Integer)
    mood_logs: str = db.Column(db.String)


@dataclass
class ReportNote(db.Model):
    id: int
    report_id: int
    user_id: int
    content: str
    created_at: datetime
    updated_at: datetime

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


@dataclass
class ReportSummary(db.Model):
    id: int
    report_id: int
    category: str
    content: str
    conversation_log_ids: str
    highlight_keywords: str

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"))
    category = db.Column(db.String(50))
    content = db.Column(db.Text)
    conversation_log_ids = db.Column(db.String)
    highlight_keywords = db.Column(db.String)


@dataclass
class ConversationLog(db.Model):
    id: int
    patient_id: int
    report_id: int
    role: str
    content: str
    created_at: datetime

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"))
    role = db.Column(db.String(50))
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def get(
    self: SQLAlchemy,
    entity: type[_O] | _Table,
    ident: t.Any,
    *,
    description: str | None = None,
) -> _O:
    print(entity)
    # if entity is a type of model
    if isinstance(entity, type) and issubclass(entity, self.Model):
        value = self.session.get(entity, ident)
        if value is None:
            raise NotFound(entity.__name__, ident)
        return value

    else:
        value = self.session.execute(
            entity.select().where(entity.primary_key.columns[0] == ident)
        ).first()

        if value is None:
            raise NotFound(entity.fullname, ident)
        return value


current_app.extensions["sqlalchemy"].get = types.MethodType(get, db)
