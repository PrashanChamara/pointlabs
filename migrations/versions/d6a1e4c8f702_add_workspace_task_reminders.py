"""add idempotent workspace task reminders

Revision ID: d6a1e4c8f702
Revises: c4f8a2d5b913
"""
from alembic import op
import sqlalchemy as sa

revision = "d6a1e4c8f702"
down_revision = "c4f8a2d5b913"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("workspace_task") as batch:
        batch.add_column(sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_workspace_task_reminder_sent_at", ["reminder_sent_at"], unique=False)


def downgrade():
    with op.batch_alter_table("workspace_task") as batch:
        batch.drop_index("ix_workspace_task_reminder_sent_at")
        batch.drop_column("reminder_sent_at")
