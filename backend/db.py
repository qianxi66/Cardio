import typing as t
from dataclasses import dataclass
from datetime import datetime

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
    id: int
    patient_id: int
    created_at: datetime
    updated_at: datetime
    pain: int
    breathing: int
    fever: int
    stools: int
    drainage: int
    activity: int
    consciousness: int
    constipation: int
    diarrhea: int
    eating: int
    swelling: int
    mood: int

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    pain = db.Column(db.Integer)
    breathing = db.Column(db.Integer)
    fever = db.Column(db.Integer)
    stools = db.Column(db.Integer)
    drainage = db.Column(db.Integer)
    activity = db.Column(db.Integer)
    consciousness = db.Column(db.Integer)
    constipation = db.Column(db.Integer)
    diarrhea = db.Column(db.Integer)
    eating = db.Column(db.Integer)
    swelling = db.Column(db.Integer)
    mood = db.Column(db.Integer)


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
