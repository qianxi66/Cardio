"""add fatigue and likert scale columns

Revision ID: 2ec53f3f4d7a
Revises: d773ab779f8f
Create Date: 2026-03-11 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


revision = "2ec53f3f4d7a"
down_revision = "d773ab779f8f"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    existing = {c["name"] for c in inspector.get_columns("summary")}
    if "fatigue_state" not in existing:
        op.add_column("summary", sa.Column("fatigue_state", sa.Integer(), nullable=True))
    if "fatigue_logs" not in existing:
        op.add_column("summary", sa.Column("fatigue_logs", sa.String(), nullable=True))
    if "short_of_breath_scale" not in existing:
        op.add_column("summary", sa.Column("short_of_breath_scale", sa.Integer(), nullable=True))
    if "chest_discomfort_scale" not in existing:
        op.add_column("summary", sa.Column("chest_discomfort_scale", sa.Integer(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    existing = {c["name"] for c in inspector.get_columns("summary")}
    if "chest_discomfort_scale" in existing:
        op.drop_column("summary", "chest_discomfort_scale")
    if "short_of_breath_scale" in existing:
        op.drop_column("summary", "short_of_breath_scale")
    if "fatigue_logs" in existing:
        op.drop_column("summary", "fatigue_logs")
    if "fatigue_state" in existing:
        op.drop_column("summary", "fatigue_state")
