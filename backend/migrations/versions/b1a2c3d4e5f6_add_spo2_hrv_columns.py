"""add spo2/hrv summary columns and ensure patient.email exists

Revision ID: b1a2c3d4e5f6
Revises: 8a7d1b2c4e9f, 703386799acf
Create Date: 2026-03-28 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


# revision identifiers, used by Alembic.
revision = "b1a2c3d4e5f6"
down_revision = ("8a7d1b2c4e9f", "703386799acf")
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)

    # Some databases were on an alternate migration chain that never added patient.email.
    patient_columns = {c["name"] for c in inspector.get_columns("patient")}
    if "email" not in patient_columns:
        with op.batch_alter_table("patient", schema=None) as batch_op:
            batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))

    existing = {c["name"] for c in inspector.get_columns("summary")}

    new_columns = [
        "spo2_state",
        "spo2_logs",
        "hrv_state",
        "hrv_logs",
        "spo2_min",
        "spo2_max",
        "spo2_average",
    ]
    for col_name in new_columns:
        if col_name not in existing:
            if col_name.endswith("_logs"):
                op.add_column("summary", sa.Column(col_name, sa.String(), nullable=True))
            elif col_name.endswith("_state"):
                op.add_column("summary", sa.Column(col_name, sa.Integer(), nullable=True))
            else:
                op.add_column("summary", sa.Column(col_name, sa.Float(), nullable=True))


def downgrade():
    for col_name in [
        "spo2_state",
        "spo2_logs",
        "hrv_state",
        "hrv_logs",
        "spo2_min",
        "spo2_max",
        "spo2_average",
    ]:
        op.drop_column("summary", col_name)
