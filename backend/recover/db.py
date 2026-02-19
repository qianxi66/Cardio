from __future__ import annotations

import types
import typing as t
import sqlite3
from datetime import datetime

from sqlalchemy import ForeignKey, Column, Table, Float, Boolean, Date, Integer, String, event
from sqlalchemy.engine import Engine
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.table import _Table

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.collections import InstrumentedList
from typing import List, Optional # Import Optional
from .symptoms import symptom_descriptions

db = SQLAlchemy()
# from .symptoms import symptom_descriptions # This is no longer needed if Report model is removed

_O = t.TypeVar("_O", bound=object)  # Based on sqlalchemy.orm._typing.py


def as_dict(self, _visited=None):
    if _visited is None:
        _visited = set()
    obj_id = getattr(self, "id", None)
    visit_key = (self.__class__, obj_id) if obj_id is not None else (self.__class__, id(self))
    if visit_key in _visited:
        if obj_id is not None:
            return {"id": obj_id}
        return {}
    _visited.add(visit_key)
    fields = {
        field: getattr(self, field)
        for field in [c.name for c in self.__table__.columns]
        if field != "password" # Exclude password from being dumped
    }
    # Handle relationships defined in __relationship_keys__
    for field in getattr(self, '__relationship_keys__', []): # Safely get __relationship_keys__
        attr = getattr(self, field)
        if isinstance(attr, InstrumentedList): # If it's a list of related objects
            fields[field] = [item.as_dict(_visited) for item in attr]
        elif attr is not None: # If it's a single related object and not None
            fields[field] = attr.as_dict(_visited)
        else: # If it's None
            fields[field] = None
    return fields


db.Model.as_dict = as_dict
# Initialize __relationship_keys__ for all models
db.Model.__relationship_keys__ = []


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=30000;")
    cursor.close()


class NotFound(Exception):
    def __init__(self, table_name, ident: t.Any) -> None:
        self.table_name = table_name
        self.ident = ident

    def __str__(self) -> str:
        return f"{self.table_name}({self.ident}) not found"


# Many-to-many relationship table between User and Patient
user_patient_table = Table(
    "user_patient_table",
    db.Model.metadata,
    Column("patient_id", ForeignKey("patient.id")),
    Column("user_id", ForeignKey("user.id")),
)


class User(db.Model):
    __tablename__ = "user" # Explicitly define table name
    __relationship_keys__ = ["patients", "tokens", "report_notes"] # Added tokens and report_notes for completeness
    id: Mapped[int] = mapped_column(primary_key=True)
    patients: Mapped[List["Patient"]] = relationship(
        secondary=user_patient_table, back_populates="users"
    )
    username: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(db.String(255), nullable=False)
    email: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.String(100))

    # Relationships for Token and ReportNote (if needed to access from User)
    tokens: Mapped[List["Token"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    report_notes: Mapped[List["ReportNote"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Token(db.Model):
    __tablename__ = "token" # Explicitly define table name
    __relationship_keys__ = ["user"]
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    userid: Mapped[int] = mapped_column(db.ForeignKey("user.id"), nullable=False)
    rememberme: Mapped[bool] = mapped_column(db.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    user: Mapped["User"] = relationship(back_populates="tokens") # Add relationship to User


class Patient(db.Model):
    __tablename__ = "patient" # Explicitly define table name
    __relationship_keys__ = ["users", "hospitalizations", "summaries", "risks", "conversation_logs", "report_notes"] # Added other relationships
    id: Mapped[int] = mapped_column(primary_key=True)
    users: Mapped[List["User"]] = relationship(
        secondary=user_patient_table, back_populates="patients"
    )
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(db.Integer)
    gender: Mapped[Optional[str]] = mapped_column(db.String(10)) # e.g., 'Male', 'Female', 'Other'
    EHR_id: Mapped[Optional[str]] = mapped_column(db.String(50))
    alexa_user_id: Mapped[Optional[str]] = mapped_column(db.String(50), unique=True)
    participant_id: Mapped[Optional[str]] = mapped_column(db.String(20), unique=True)
    garmin_id: Mapped[Optional[str]] = mapped_column(db.String(50), unique=True)
    
    # Cancer related fields (as strings, consider lookup tables for better integrity)
    cancer_type: Mapped[Optional[str]] = mapped_column(db.String(100))
    cancer_stage: Mapped[Optional[str]] = mapped_column(db.String(100))
    treatment_type: Mapped[Optional[str]] = mapped_column(db.String(100))

    last_read_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime) # Last time patient data was read/synced
    
    # Relationships for Hospitalization, Summary, Risk, ConversationLog
    hospitalizations: Mapped[List["Hospitalization"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    summaries: Mapped[List["Summary"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    risks: Mapped[List["Risk"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    conversation_logs: Mapped[List["ConversationLog"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    report_notes: Mapped[List["ReportNote"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Hospitalization(db.Model):
    __tablename__ = "hospitalization" # Explicitly define table name
    __relationship_keys__ = ["patient"]
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="hospitalizations") # Relationship back to Patient

    date: Mapped[datetime] = mapped_column(db.DateTime, nullable=False) # Admission date/time
    event: Mapped[str] = mapped_column(db.String(500), nullable=False) # Description of the event/reason



class Summary(db.Model):
    __tablename__ = "summary"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="summaries")

    # Vital signs summary (float for more precision)
    heart_rate_min: Mapped[Optional[float]] = mapped_column(Float)
    heart_rate_max: Mapped[Optional[float]] = mapped_column(Float)
    heart_rate_average: Mapped[Optional[float]] = mapped_column(Float)
    
    spo2_min: Mapped[Optional[float]] = mapped_column(Float)
    spo2_max: Mapped[Optional[float]] = mapped_column(Float)
    spo2_average: Mapped[Optional[float]] = mapped_column(Float)
    
    respiration_min: Mapped[Optional[float]] = mapped_column(Float)
    respiration_max: Mapped[Optional[float]] = mapped_column(Float)
    respiration_average: Mapped[Optional[float]] = mapped_column(Float)
    
    hrv_min: Mapped[Optional[float]] = mapped_column(Float)
    hrv_max: Mapped[Optional[float]] = mapped_column(Float)
    hrv_average: Mapped[Optional[float]] = mapped_column(Float)

    date: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)

for symptom_name in symptom_descriptions:
    setattr(Summary, f"{symptom_name}_state", mapped_column(Integer, nullable=True))
    
    setattr(Summary, f"{symptom_name}_logs", mapped_column(String, nullable=True))
    
    if symptom_descriptions[symptom_name].get("likert", False):
        setattr(Summary, f"{symptom_name}_scale", mapped_column(Integer, nullable=True))


class Risk(db.Model):
    __tablename__ = "risk" # Explicitly define table name
    __relationship_keys__ = ["patient"]
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="risks")

    risk_score: Mapped[float] = mapped_column(Float, nullable=False) # Floating point for risk score
    
    # Importance scores (float for more precision)
    important_of_chest: Mapped[Optional[float]] = mapped_column(Float)
    important_of_heart: Mapped[Optional[float]] = mapped_column(Float)
    important_of_respiration: Mapped[Optional[float]] = mapped_column(Float)
    important_of_hrv: Mapped[Optional[float]] = mapped_column(Float)

    date: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow) # When this risk assessment was generated


class ConversationLog(db.Model):
    __tablename__ = "conversation_log" # Explicitly define table name
    __relationship_keys__ = ["patient"]
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="conversation_logs")

    role: Mapped[str] = mapped_column(db.String(50), nullable=False) # e.g., 'user', 'assistant', 'system'
    content: Mapped[str] = mapped_column(db.Text, nullable=False)
    chain_of_thoughts: Mapped[Optional[str]] = mapped_column(db.Text) # Can be null

    # New symptom fields based on conversation analysis
    symptoms_chest: Mapped[Optional[str]] = mapped_column(db.Text) # e.g., "tightness, pain, discomfort"
    symptoms_other: Mapped[Optional[str]] = mapped_column(db.Text) # e.g., "fatigue, dizziness"

    date: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow) # Changed from created_at to date as per request


class ReportNote(db.Model):
    __tablename__ = "report_note" # Explicitly define table name
    __relationship_keys__ = ["user"]
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="report_notes")
    patient_id: Mapped[int] = mapped_column(db.Integer, ForeignKey("patient.id"))
    patient: Mapped["Patient"] = relationship(back_populates="report_notes")

    content: Mapped[str] = mapped_column(db.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, onupdate=datetime.utcnow)


class AlexaIDNote(db.Model):
    __tablename__ = "alexa_id_note" # Explicitly define table name
    id: Mapped[int] = mapped_column(primary_key=True)
    alexa_user_id: Mapped[str] = mapped_column(db.Text, nullable=False, unique=True) # Assuming unique
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, onupdate=datetime.utcnow)


# --- Helper function for db.get ---
def get(
    self: SQLAlchemy,
    entity: type[_O] | _Table,
    ident: t.Any,
    *,
    description: str | None = None,
) -> _O:
    # if entity is a type of model
    if isinstance(entity, type) and issubclass(entity, self.Model):
        value = self.session.get(entity, ident)
        if value is None:
            raise NotFound(entity.__name__, ident)
        return value

    else: # Fallback for non-model entities (e.g., Table objects directly)
        value = self.session.execute(
            entity.select().where(entity.primary_key.columns[0] == ident)
        ).first()

        if value is None:
            raise NotFound(entity.fullname, ident)
        return value


# Apply the get method to the db instance
db.get = types.MethodType(get, db)
