"""Add simple designation-based approval cases.

Revision ID: 0c8d3e7f5a21
Revises: f1d7b5c9a308
Create Date: 2026-09-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0c8d3e7f5a21"
down_revision = "f1d7b5c9a308"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("designation") as batch_op:
        batch_op.add_column(sa.Column("is_admin_designation", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "designation_approval_case",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("current_designation_id", sa.Integer(), nullable=True),
        sa.Column("awaiting_response_from_id", sa.Integer(), nullable=True),
        sa.Column("return_to_approver_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["requester_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["current_designation_id"], ["designation.id"]),
        sa.ForeignKeyConstraint(["awaiting_response_from_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["return_to_approver_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_type", "subject_id", name="uq_designation_approval_subject"),
    )
    op.create_index("ix_designation_approval_case_subject_type", "designation_approval_case", ["subject_type"])
    op.create_index("ix_designation_approval_case_subject_id", "designation_approval_case", ["subject_id"])
    op.create_index("ix_designation_approval_case_requester_id", "designation_approval_case", ["requester_id"])
    op.create_index("ix_designation_approval_case_status", "designation_approval_case", ["status"])

    op.create_table(
        "designation_approval_assignment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=False),
        sa.Column("designation_id", sa.Integer(), nullable=True),
        sa.Column("assigned_by_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("acted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["designation_approval_case.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["designation_id"], ["designation.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_designation_approval_assignment_case_id", "designation_approval_assignment", ["case_id"])
    op.create_index("ix_designation_approval_assignment_assignee_id", "designation_approval_assignment", ["assignee_id"])
    op.create_index("ix_designation_approval_assignment_status", "designation_approval_assignment", ["status"])

    op.create_table(
        "designation_approval_action",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("from_designation_id", sa.Integer(), nullable=True),
        sa.Column("to_designation_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["designation_approval_case.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["from_designation_id"], ["designation.id"]),
        sa.ForeignKeyConstraint(["to_designation_id"], ["designation.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_designation_approval_action_case_id", "designation_approval_action", ["case_id"])
    op.create_index("ix_designation_approval_action_action", "designation_approval_action", ["action"])


def downgrade():
    op.drop_table("designation_approval_action")
    op.drop_table("designation_approval_assignment")
    op.drop_table("designation_approval_case")
    with op.batch_alter_table("designation") as batch_op:
        batch_op.drop_column("is_admin_designation")
