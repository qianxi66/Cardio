"""add email to patient

Revision ID: 8a7d1b2c4e9f
Revises: 3302c235ed43
Create Date: 2026-03-10 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8a7d1b2c4e9f"
down_revision = "3302c235ed43"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("patient", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint("uq_patient_email", ["email"])


def downgrade():
    with op.batch_alter_table("patient", schema=None) as batch_op:
        batch_op.drop_constraint("uq_patient_email", type_="unique")
        batch_op.drop_column("email")
