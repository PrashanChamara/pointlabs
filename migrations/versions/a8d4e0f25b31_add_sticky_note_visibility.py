"""add sticky note visibility

Revision ID: a8d4e0f25b31
Revises: a7c3b9d14e20
"""
from alembic import op
import sqlalchemy as sa

revision = "a8d4e0f25b31"
down_revision = "a7c3b9d14e20"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("workspace_note") as batch_op:
        batch_op.add_column(sa.Column("show_everywhere", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index("ix_workspace_note_show_everywhere", ["show_everywhere"], unique=False)

def downgrade():
    with op.batch_alter_table("workspace_note") as batch_op:
        batch_op.drop_index("ix_workspace_note_show_everywhere")
        batch_op.drop_column("show_everywhere")
