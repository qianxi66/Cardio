from __future__ import annotations

import types
import typing as t
from datetime import datetime

from sqlalchemy import ForeignKey
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.table import _Table

from sqlalchemy.orm import Mapped
from typing import List
from sqlalchemy import Column
from sqlalchemy import Table
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import InstrumentedList
from .app import db
from .symptoms import symptom_descriptions

_O = t.TypeVar("_O", bound=object)  # Based on sqlalchemy.orm._typing.py


# db.Model.as_dict = lambda self: {
#     field: getattr(self, field)
#     for field in [c.name for c in self.__table__.columns]
#     + [self.__mapper__.relationships.keys()]
# }
def as_dict(self):
    fields = {
        field: getattr(self, field)
        for field in [c.name for c in self.__table__.columns]
        if field != "password"
    }
    for field in self.__relationship_keys__:
        attr = getattr(self, field)
        # if is InstrumentedList
        if isinstance(attr, InstrumentedList):
            fields[field] = [item.as_dict() for item in attr]
        else:
            fields[field] = attr.as_dict()
    return fields


db.Model.as_dict = as_dict
db.Model.__relationship_keys__ = []


class NotFound(Exception):
    def __init__(self, table_name, ident: t.Any) -> None:
        self.table_name = table_name
        self.ident = ident

    def __str__(self) -> str:
        return f"{self.table_name}({self.ident}) not found"


user_patient_table = Table(
    "user_patient_table",
    db.Model.metadata,
    Column("patient_id", ForeignKey("patient.id")),
    Column("user_id", ForeignKey("user.id")),
)


class Patient(db.Model):
    __relationship_keys__ = ["users"]
    id: Mapped[int] = mapped_column(primary_key=True)
    users: Mapped[List[User]] = relationship(
        secondary=user_patient_table, back_populates="patients"
    )
    age: int
    gender: str
    EHR_id: str
    alexa_user_id: str
    medical_history: str
    medication: str
    participant_id: str
    last_read_at: datetime
    reviewed: bool
    state: int

    id = db.Column(db.Integer, primary_key=True)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    EHR_id = db.Column(db.String(50))
    alexa_user_id = db.Column(db.String(50), nullable=True)
    medical_history = db.Column(db.Text)
    medication = db.Column(db.Text)
    participant_id = db.Column(db.String(20))
    last_read_at = db.Column(db.DateTime)
    reviewed = db.Column(db.Boolean, default=False)
    state = db.Column(db.Integer, default=0)


class ReportNote(db.Model):
    __relationship_keys__ = ["user"]
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, ForeignKey("user.id"))
    user: Mapped["User"] = relationship()
    report_id: Mapped[int] = mapped_column(db.Integer, ForeignKey("report.id"))
    content: Mapped[str] = mapped_column(db.Text)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime, onupdate=datetime.utcnow)


class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    patients: Mapped[List[Patient]] = relationship(secondary=user_patient_table)
    username: Mapped[str] = mapped_column(db.String(50))
    password: Mapped[str] = mapped_column(db.String(255))
    email: Mapped[str] = mapped_column(db.String(100))
    name: Mapped[str] = mapped_column(db.String(100))


class Token(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(db.String(255))
    userid: Mapped[int] = mapped_column(db.ForeignKey("user.id"), nullable=False)
    rememberme: Mapped[bool] = mapped_column(db.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(db.DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    # user: Mapped["User"] = relationship()


class Report(db.Model):
    id: int = db.Column(db.Integer, primary_key=True)
    patient_id: int = db.Column(db.Integer, db.ForeignKey("patient.id"))
    created_at: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at: datetime = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    read: bool = db.Column(db.Boolean, default=False)


for symptom_name in symptom_descriptions:
    setattr(Report, symptom_name + "_state", db.Column(db.Integer))
    setattr(Report, symptom_name + "_logs", db.Column(db.String))
    if symptom_descriptions[symptom_name]["likert"]:
        setattr(Report, symptom_name + "_scale", db.Column(db.Integer))


class AlexaIDNote(db.Model):
    id: int
    alexa_user_id: str
    created_at: datetime
    updated_at: datetime

    id = db.Column(db.Integer, primary_key=True)
    alexa_user_id = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


class ReportSummary(db.Model):
    id: int
    report_id: int
    category: str
    content: str
    conversation_log_ids: str
    highlight_keywords: str
    created_at: datetime
    updated_at: datetime

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"))
    category = db.Column(db.String(50))
    content = db.Column(db.Text)
    conversation_log_ids = db.Column(db.String)
    highlight_keywords = db.Column(db.String)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


class ConversationLog(db.Model):
    id: int
    patient_id: int
    report_id: int
    role: str
    content: str
    chain_of_thoughts: str
    created_at: datetime

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))
    report_id = db.Column(db.Integer, db.ForeignKey("report.id"))
    role = db.Column(db.String(50))
    content = db.Column(db.Text)
    chain_of_thoughts = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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

    else:
        value = self.session.execute(
            entity.select().where(entity.primary_key.columns[0] == ident)
        ).first()

        if value is None:
            raise NotFound(entity.fullname, ident)
        return value


current_app.extensions["sqlalchemy"].get = types.MethodType(get, db)
