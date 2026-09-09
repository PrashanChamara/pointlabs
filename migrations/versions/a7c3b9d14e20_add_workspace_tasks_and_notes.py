"""add workspace tasks and notes

Revision ID: a7c3b9d14e20
Revises: f1d40edf6835
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c3b9d14e20"
down_revision = "f1d40edf6835"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_task_user_id", "workspace_task", ["user_id"])
    op.create_index("ix_workspace_task_due_at", "workspace_task", ["due_at"])
    op.create_table(
        "workspace_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(length=600), nullable=False),
        sa.Column("color", sa.String(length=24), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_note_user_id", "workspace_note", ["user_id"])
    op.create_index("ix_workspace_note_is_global", "workspace_note", ["is_global"])


def downgrade():
    op.drop_index("ix_workspace_note_is_global", table_name="workspace_note")
    op.drop_index("ix_workspace_note_user_id", table_name="workspace_note")
    op.drop_table("workspace_note")
    op.drop_index("ix_workspace_task_due_at", table_name="workspace_task")
    op.drop_index("ix_workspace_task_user_id", table_name="workspace_task")
    op.drop_table("workspace_task")
