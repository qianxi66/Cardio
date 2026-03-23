from __future__ import annotations

import types
import typing as t
import sqlite3
from datetime import datetime

from sqlalchemy import ForeignKey, Column, Index, Table, Float, Boolean, Date, Integer, String, Text, event
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
    __relationship_keys__ = ["patients", "tokens"]
    id: Mapped[int] = mapped_column(primary_key=True)
    patients: Mapped[List["Patient"]] = relationship(
        secondary=user_patient_table, back_populates="users"
    )
    username: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(db.String(255), nullable=False)
    email: Mapped[str] = mapped_column(db.String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(db.String(100))

    # Relationships
    tokens: Mapped[List["Token"]] = relationship(back_populates="user", cascade="all, delete-orphan")


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
    __relationship_keys__ = ["users", "admission_histories", "summaries", "risks", "conversation_logs", "medications", "notes", "preadmission_medications", "io_metrics", "medication_execution_metrics"]
    id: Mapped[int] = mapped_column(primary_key=True)
    users: Mapped[List["User"]] = relationship(
        secondary=user_patient_table, back_populates="patients"
    )
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(db.Integer)
    gender: Mapped[Optional[str]] = mapped_column(db.String(10)) # e.g., 'Male', 'Female', 'Other'
    EHR_id: Mapped[Optional[str]] = mapped_column(db.String(50))
    email: Mapped[Optional[str]] = mapped_column(db.String(255), unique=True)
    alexa_user_id: Mapped[Optional[str]] = mapped_column(db.String(50), unique=True)
    participant_id: Mapped[Optional[str]] = mapped_column(db.String(20), unique=True)
    garmin_id: Mapped[Optional[str]] = mapped_column(db.String(50), unique=True)
    
    # Cancer related fields
    cancer_type: Mapped[Optional[str]] = mapped_column(db.String(100))
    cancer_stage: Mapped[Optional[str]] = mapped_column(db.String(100))       # used as diagnosis date label in UI
    treatment_type: Mapped[Optional[str]] = mapped_column(db.String(100))     # used as allergy history label in UI
    treatment_plan: Mapped[Optional[str]] = mapped_column(db.Text)
    treatment_cycle: Mapped[Optional[str]] = mapped_column(db.String(100))
    next_appointment_date: Mapped[Optional[datetime]] = mapped_column(db.DateTime)

    last_read_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime) # Last time patient data was read/synced
    
    # Relationships
    admission_histories: Mapped[List["AdmissionHistory"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    summaries: Mapped[List["Summary"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    risks: Mapped[List["Risk"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    conversation_logs: Mapped[List["ConversationLog"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    medications: Mapped[List["Medication"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    notes: Mapped[List["Note"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    preadmission_medications: Mapped[List["PreadmissionMedication"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    io_metrics: Mapped[List["IOMetric"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    medication_execution_metrics: Mapped[List["MedicationExecutionMetric"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class AdmissionHistory(db.Model):
    """Patient hospital admission / discharge records."""
    __tablename__ = "admission_history"
    __relationship_keys__ = ["patient"]
    __table_args__ = (
        Index("ix_admission_history_patient_date", "patient_id", "admission_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="admission_histories")

    admission_date: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    discharge_date: Mapped[Optional[datetime]] = mapped_column(db.DateTime)  # null = still admitted
    diagnosis: Mapped[Optional[str]] = mapped_column(db.Text)   # primary diagnosis text
    symptoms: Mapped[Optional[str]] = mapped_column(db.Text)    # symptom description at admission
    notes: Mapped[Optional[str]] = mapped_column(db.Text)       # free-form clinical notes

    # --- new fields (v2) ---
    careunit_id: Mapped[Optional[str]] = mapped_column(db.String(20))          # source care-unit ID  e.g. "1", "54"
    careunit_name: Mapped[Optional[str]] = mapped_column(db.String(100))       # e.g. "CCU", "MICU"
    destination_unit_id: Mapped[Optional[str]] = mapped_column(db.String(20))   # transfer-out unit ID
    destination_unit_name: Mapped[Optional[str]] = mapped_column(db.String(100))# e.g. "FA2", "CC7"
    discharge_status: Mapped[Optional[str]] = mapped_column(db.String(50))     # Home/Rehab/SNF/Expired/No Disch Status/Other
    admission_type: Mapped[Optional[str]] = mapped_column(db.String(30))       # emergency/elective/urgent
    readmission_flag: Mapped[Optional[bool]] = mapped_column(db.Boolean, default=False)
    los_minutes: Mapped[Optional[int]] = mapped_column(db.Integer)             # length-of-stay in minutes

    # back-refs from child tables
    preadmission_medications: Mapped[List["PreadmissionMedication"]] = relationship(back_populates="admission_history", cascade="all, delete-orphan")
    io_metrics: Mapped[List["IOMetric"]] = relationship(back_populates="admission_history", cascade="all, delete-orphan")
    medication_execution_metrics: Mapped[List["MedicationExecutionMetric"]] = relationship(back_populates="admission_history", cascade="all, delete-orphan")



class Summary(db.Model):
    __tablename__ = "summary"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="summaries")

    date: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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


class Medication(db.Model):
    """Medications prescribed or taken by a patient."""
    __tablename__ = "medication"
    __relationship_keys__ = ["patient"]
    __table_args__ = (
        Index("ix_medication_patient_start", "patient_id", "start_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="medications")

    drug_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    dosage: Mapped[Optional[str]] = mapped_column(db.String(255))  # e.g. "10mg twice daily"
    start_date: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(db.DateTime)  # null = ongoing
    recorded_by_user_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("user.id"))  # who entered it
    notes: Mapped[Optional[str]] = mapped_column(db.Text)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)

    # --- new fields (v2) ---
    route: Mapped[Optional[str]] = mapped_column(db.String(50))          # PO / IV / SC / IM / PR / INH
    frequency: Mapped[Optional[str]] = mapped_column(db.String(50))      # QD / BID / TID / Q4-6H:PRN
    schedule_hours: Mapped[Optional[str]] = mapped_column(db.String(100)) # e.g. "10", "08,20"
    dose_count: Mapped[Optional[int]] = mapped_column(db.Integer)         # number of doses in order
    is_current_medication: Mapped[Optional[bool]] = mapped_column(db.Boolean, default=False)
    order_source: Mapped[Optional[str]] = mapped_column(db.String(50))   # inpatient_order / outpatient_list / imported


class Note(db.Model):
    """Clinical or AI-generated notes attached to a patient.
    creator_type = 'user'  → user_id is set, shown in doctor UI
    creator_type = 'ai'    → user_id is null, shown as AI summary
    """
    __tablename__ = "note"
    __relationship_keys__ = ["patient"]
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="notes")

    user_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("user.id"))  # null if AI
    creator_type: Mapped[str] = mapped_column(db.String(10), nullable=False)  # 'user' | 'ai'
    content: Mapped[str] = mapped_column(db.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)


class PreadmissionMedication(db.Model):
    """Baseline medications patient was taking before hospital admission."""
    __tablename__ = "preadmission_medication"
    __relationship_keys__ = ["patient"]
    __table_args__ = (
        Index("ix_preadm_med_patient", "patient_id"),
        Index("ix_preadm_med_admission", "admission_history_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="preadmission_medications")
    admission_history_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("admission_history.id"))
    admission_history: Mapped[Optional["AdmissionHistory"]] = relationship(back_populates="preadmission_medications")

    drug_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    dosage: Mapped[Optional[str]] = mapped_column(db.String(255))
    frequency: Mapped[Optional[str]] = mapped_column(db.String(100))
    started_before_admission_date: Mapped[Optional[datetime]] = mapped_column(db.DateTime)
    active_at_admission: Mapped[Optional[bool]] = mapped_column(db.Boolean, default=True)
    source_text: Mapped[Optional[str]] = mapped_column(db.Text)       # free-form original text
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)


class IOMetric(db.Model):
    """Summary-level I/O (intake/output) metrics per patient per day."""
    __tablename__ = "io_metric"
    __relationship_keys__ = ["patient"]
    __table_args__ = (
        Index("ix_io_metric_patient_date", "patient_id", "metric_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="io_metrics")
    admission_history_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("admission_history.id"))
    admission_history: Mapped[Optional["AdmissionHistory"]] = relationship(back_populates="io_metrics")

    metric_date: Mapped[Optional[datetime]] = mapped_column(Date)          # date of measurement
    io_event_count: Mapped[int] = mapped_column(db.Integer, default=0)     # total I/O events
    io_total_volume_ml: Mapped[float] = mapped_column(Float, default=0.0)  # total volume in mL
    io_total_volume_measurement_count: Mapped[int] = mapped_column(db.Integer, default=0)  # <= event_count
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)


class MedicationExecutionMetric(db.Model):
    """Summary-level medication administration execution metrics."""
    __tablename__ = "medication_execution_metric"
    __relationship_keys__ = ["patient"]
    __table_args__ = (
        Index("ix_med_exec_patient_date", "patient_id", "metric_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(db.ForeignKey("patient.id"), nullable=False)
    patient: Mapped["Patient"] = relationship(back_populates="medication_execution_metrics")
    admission_history_id: Mapped[Optional[int]] = mapped_column(db.ForeignKey("admission_history.id"))
    admission_history: Mapped[Optional["AdmissionHistory"]] = relationship(back_populates="medication_execution_metrics")

    metric_date: Mapped[Optional[datetime]] = mapped_column(Date)
    ad_event_count: Mapped[int] = mapped_column(db.Integer, default=0)     # administered
    me_event_count: Mapped[int] = mapped_column(db.Integer, default=0)     # medication events
    so_event_count: Mapped[int] = mapped_column(db.Integer, default=0)     # standing orders
    med_admin_execution_event_count: Mapped[int] = mapped_column(db.Integer, default=0)  # = ad + me + so
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)


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
