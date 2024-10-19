"""empty message

Revision ID: f3ec2b3c18cc
Revises: f5fd7435f282
Create Date: 2024-10-18 23:27:32.799278

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f3ec2b3c18cc"
down_revision = "f5fd7435f282"
branch_labels = None
depends_on = None


def upgrade():
    # update conversation_log and report_note, set updated_at and created_at to now
    # no such function now in sqlite
    # op.execute("UPDATE conversation_log SET created_at = CURRENT_TIMESTAMP")
    op.execute(
        "UPDATE report_note SET updated_at = CURRENT_TIMESTAMP, created_at = CURRENT_TIMESTAMP"
    )
    op.execute(
        "UPDATE report_summary SET updated_at = CURRENT_TIMESTAMP, created_at = CURRENT_TIMESTAMP"
    )


def downgrade():
    pass
