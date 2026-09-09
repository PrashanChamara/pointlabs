"""add attendance records

Revision ID: e8b3d1f6a024
Revises: d6a1e4c8f702
"""
from alembic import op
import sqlalchemy as sa

revision = "e8b3d1f6a024"
down_revision = "d6a1e4c8f702"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("attendance_record", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False), sa.Column("work_date", sa.Date(), nullable=False), sa.Column("checked_in_at", sa.DateTime(), nullable=False), sa.Column("checked_out_at", sa.DateTime()), sa.Column("check_in_note", sa.String(500)), sa.Column("check_out_note", sa.String(500)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id", "work_date", name="uq_attendance_user_work_date"))
    op.create_index("ix_attendance_record_user_id", "attendance_record", ["user_id"])
    op.create_index("ix_attendance_record_work_date", "attendance_record", ["work_date"])


def downgrade():
    op.drop_index("ix_attendance_record_work_date", table_name="attendance_record"); op.drop_index("ix_attendance_record_user_id", table_name="attendance_record"); op.drop_table("attendance_record")
