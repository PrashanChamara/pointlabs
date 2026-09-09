"""add credential expiry reminder delivery records

Revision ID: f1d7b5c9a308
Revises: e8b3d1f6a024
"""
from alembic import op
import sqlalchemy as sa

revision = "f1d7b5c9a308"
down_revision = "e8b3d1f6a024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("compliance_reminder", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False), sa.Column("document_kind", sa.String(80), nullable=False), sa.Column("expiry_date", sa.Date(), nullable=False), sa.Column("threshold_days", sa.Integer(), nullable=False), sa.Column("sent_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("user_id", "document_kind", "expiry_date", "threshold_days", name="uq_compliance_reminder_delivery"))
    op.create_index("ix_compliance_reminder_user_id", "compliance_reminder", ["user_id"])


def downgrade():
    op.drop_index("ix_compliance_reminder_user_id", table_name="compliance_reminder"); op.drop_table("compliance_reminder")
