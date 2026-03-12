"""add likert scale columns to summary

Revision ID: 8c6d0b91a2ef
Revises: d5edfdf9001a
Create Date: 2026-03-10 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision = "8c6d0b91a2ef"
down_revision = "d5edfdf9001a"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    existing = {c["name"] for c in inspector.get_columns("summary")}

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
