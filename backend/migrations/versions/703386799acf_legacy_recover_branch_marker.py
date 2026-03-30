"""legacy recover branch marker

Revision ID: 703386799acf
Revises: 8a7d1b2c4e9f
Create Date: 2026-03-28 16:10:00.000000

This no-op revision bridges legacy databases that were stamped with
703386799acf from an alternate migration directory.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "703386799acf"
down_revision = "8a7d1b2c4e9f"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy bridge revision: intentionally no schema operation.
    pass


def downgrade():
    # Legacy bridge revision: intentionally no schema operation.
    pass
