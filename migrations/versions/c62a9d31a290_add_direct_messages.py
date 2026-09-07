"""add direct messages

Revision ID: c62a9d31a290
Revises: 8e9ac58ce13b
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "c62a9d31a290"
down_revision = "8e9ac58ce13b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "direct_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_direct_message_sender_id", "direct_message", ["sender_id"])
    op.create_index("ix_direct_message_recipient_id", "direct_message", ["recipient_id"])
    op.create_index("ix_direct_message_created_at", "direct_message", ["created_at"])


def downgrade():
    op.drop_index("ix_direct_message_created_at", table_name="direct_message")
    op.drop_index("ix_direct_message_recipient_id", table_name="direct_message")
    op.drop_index("ix_direct_message_sender_id", table_name="direct_message")
    op.drop_table("direct_message")
