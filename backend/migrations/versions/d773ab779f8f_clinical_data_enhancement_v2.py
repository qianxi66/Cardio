"""clinical_data_enhancement_v2

Add new columns to AdmissionHistory and Medication.
Create new tables: PreadmissionMedication, IOMetric, MedicationExecutionMetric.

Revision ID: d773ab779f8f
Revises: 3f006f336d43
Create Date: 2026-03-05 15:43:37.908931

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd773ab779f8f'
down_revision = '3f006f336d43'
branch_labels = None
depends_on = None


def upgrade():
    # --- A. New columns on admission_history ---
    with op.batch_alter_table('admission_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('careunit_id', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('careunit_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('destination_unit_id', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('destination_unit_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('discharge_status', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('admission_type', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('readmission_flag', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('los_minutes', sa.Integer(), nullable=True))
        batch_op.create_index('ix_admission_history_patient_date', ['patient_id', 'admission_date'])

    # --- B. New columns on medication ---
    with op.batch_alter_table('medication', schema=None) as batch_op:
        batch_op.add_column(sa.Column('route', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('frequency', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('schedule_hours', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('dose_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_current_medication', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('order_source', sa.String(length=50), nullable=True))
        batch_op.create_index('ix_medication_patient_start', ['patient_id', 'start_date'])

    # --- C. New table: preadmission_medication ---
    op.create_table('preadmission_medication',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('admission_history_id', sa.Integer(), nullable=True),
        sa.Column('drug_name', sa.String(length=255), nullable=False),
        sa.Column('dosage', sa.String(length=255), nullable=True),
        sa.Column('frequency', sa.String(length=100), nullable=True),
        sa.Column('started_before_admission_date', sa.DateTime(), nullable=True),
        sa.Column('active_at_admission', sa.Boolean(), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admission_history_id'], ['admission_history.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_preadm_med_patient', 'preadmission_medication', ['patient_id'])
    op.create_index('ix_preadm_med_admission', 'preadmission_medication', ['admission_history_id'])

    # --- D. New table: io_metric ---
    op.create_table('io_metric',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('admission_history_id', sa.Integer(), nullable=True),
        sa.Column('metric_date', sa.Date(), nullable=True),
        sa.Column('io_event_count', sa.Integer(), nullable=True),
        sa.Column('io_total_volume_ml', sa.Float(), nullable=True),
        sa.Column('io_total_volume_measurement_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admission_history_id'], ['admission_history.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_io_metric_patient_date', 'io_metric', ['patient_id', 'metric_date'])

    # --- E. New table: medication_execution_metric ---
    op.create_table('medication_execution_metric',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('admission_history_id', sa.Integer(), nullable=True),
        sa.Column('metric_date', sa.Date(), nullable=True),
        sa.Column('ad_event_count', sa.Integer(), nullable=True),
        sa.Column('me_event_count', sa.Integer(), nullable=True),
        sa.Column('so_event_count', sa.Integer(), nullable=True),
        sa.Column('med_admin_execution_event_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admission_history_id'], ['admission_history.id'], ),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_med_exec_patient_date', 'medication_execution_metric', ['patient_id', 'metric_date'])


def downgrade():
    # --- Drop new tables ---
    op.drop_index('ix_med_exec_patient_date', table_name='medication_execution_metric')
    op.drop_table('medication_execution_metric')

    op.drop_index('ix_io_metric_patient_date', table_name='io_metric')
    op.drop_table('io_metric')

    op.drop_index('ix_preadm_med_admission', table_name='preadmission_medication')
    op.drop_index('ix_preadm_med_patient', table_name='preadmission_medication')
    op.drop_table('preadmission_medication')

    # --- Drop new columns from medication ---
    with op.batch_alter_table('medication', schema=None) as batch_op:
        batch_op.drop_index('ix_medication_patient_start')
        batch_op.drop_column('order_source')
        batch_op.drop_column('is_current_medication')
        batch_op.drop_column('dose_count')
        batch_op.drop_column('schedule_hours')
        batch_op.drop_column('frequency')
        batch_op.drop_column('route')

    # --- Drop new columns from admission_history ---
    with op.batch_alter_table('admission_history', schema=None) as batch_op:
        batch_op.drop_index('ix_admission_history_patient_date')
        batch_op.drop_column('los_minutes')
        batch_op.drop_column('readmission_flag')
        batch_op.drop_column('admission_type')
        batch_op.drop_column('discharge_status')
        batch_op.drop_column('destination_unit_name')
        batch_op.drop_column('destination_unit_id')
        batch_op.drop_column('careunit_name')
        batch_op.drop_column('careunit_id')
