"""add attendance change requests

Revision ID: f4b6d8e0a2c4
Revises: c1d3e5f7a9b2
Create Date: 2026-09-20 23:20:00.000000
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "f4b6d8e0a2c4"
down_revision = "c1d3e5f7a9b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "attendance_change_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("other_request_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("requested_check_in_time", sa.Time(), nullable=True),
        sa.Column("requested_check_out_time", sa.Time(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_comment", sa.String(length=500), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["other_request_id"], ["other_request.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("other_request_id"),
    )
    op.create_index("ix_attendance_change_request_user_id", "attendance_change_request", ["user_id"])
    op.create_index("ix_attendance_change_request_attendance_date", "attendance_change_request", ["attendance_date"])
    op.create_index("ix_attendance_change_request_status", "attendance_change_request", ["status"])

    # The catalogue is administrator-managed after creation.  Insert this new
    # built-in service only once; existing organisations keep their own types.
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM request_type WHERE name = :name"),
        {"name": "Change Attendance"},
    ).scalar()
    if not exists:
        bind.execute(
            sa.text(
                "INSERT INTO request_type (name, description, is_active, created_at) "
                "VALUES (:name, :description, :is_active, :created_at)"
            ),
            {
                "name": "Change Attendance",
                "description": "Request a reviewed correction to an official check-in or check-out record.",
                "is_active": True,
                "created_at": datetime.utcnow(),
            },
        )


def downgrade():
    # Keep the service-catalogue row: it may already be referenced by a real
    # HR request, and removing reference data during a downgrade would be unsafe.
    op.drop_index("ix_attendance_change_request_status", table_name="attendance_change_request")
    op.drop_index("ix_attendance_change_request_attendance_date", table_name="attendance_change_request")
    op.drop_index("ix_attendance_change_request_user_id", table_name="attendance_change_request")
    op.drop_table("attendance_change_request")
