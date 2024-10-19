"""empty message

Revision ID: a41aaf6ffc45
Revises: 51efa9131487
Create Date: 2024-10-18 22:47:49.988968

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from recover.symptoms import symptom_descriptions


# revision identifiers, used by Alembic.
revision = "a41aaf6ffc45"
down_revision = "51efa9131487"
branch_labels = None
depends_on = None


def upgrade():
    # Import the symptom descriptions

    # Dynamically define columns based on the symptom descriptions
    report_columns = []

    for symptom_name, symptom_info in symptom_descriptions.items():
        state_column_name = f"{symptom_name}_state"
        report_columns.append(column(state_column_name, sa.Integer))

        if symptom_info.get("likert", False):
            scale_column_name = f"{symptom_name}_scale"
            report_columns.append(column(scale_column_name, sa.Integer))

    # Define the 'report' table with the dynamically created columns
    report = table("report", *report_columns)

    # Now perform the updates
    for symptom_name, symptom_info in symptom_descriptions.items():
        state_column_name = f"{symptom_name}_state"
        state_column = sa.column(state_column_name)
        # Update NULL state values to zero
        op.execute(
            report.update().where(state_column.is_(None)).values({state_column_name: 0})
        )

        # If the symptom uses a scale (likert), update NULL scale values to zero
        if symptom_info.get("likert", False):
            scale_column_name = f"{symptom_name}_scale"
            scale_column = sa.column(scale_column_name)
            op.execute(
                report.update()
                .where(scale_column.is_(None))
                .values({scale_column_name: 0})
            )


def downgrade():
    # No action needed for downgrade
    pass
