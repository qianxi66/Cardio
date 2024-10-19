"""empty message

Revision ID: f5fd7435f282
Revises: a41aaf6ffc45
Create Date: 2024-10-18 23:20:31.871748

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f5fd7435f282"
down_revision = "a41aaf6ffc45"
branch_labels = None
depends_on = None


def upgrade():
    # create user

    # user = User(
    #     username="default",
    #     password="unhashed_password_impossible_to_login",
    #     email="admin@example.com",
    #     name="Default User",
    # )
    # db.session.add(user)
    # db.session.commit()
    # raw sql
    op.execute(
        "INSERT INTO user (username, password, email, name) VALUES ('default', 'unhashed_password_impossible_to_login', 'admin@example.com', 'Default User')"
    )
    # for all patients, insert user_patient_table
    op.execute(
        "INSERT INTO user_patient_table (patient_id, user_id) SELECT id, 1 FROM patient"
    )
    # for all report notes, set user_id to 1
    op.execute("UPDATE report_note SET user_id = 1 WHERE report_id IS NOT NULL")

    pass


def downgrade():
    pass
