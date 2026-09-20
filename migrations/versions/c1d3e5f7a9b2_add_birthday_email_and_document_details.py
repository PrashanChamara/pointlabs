"""add birthday email settings and employee document details

Revision ID: c1d3e5f7a9b2
Revises: ac19c777da37
Create Date: 2026-09-20 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c1d3e5f7a9b2"
down_revision = "ac19c777da37"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("employee_document", schema=None) as batch_op:
        batch_op.add_column(sa.Column("details", sa.String(length=500), nullable=True))

    op.create_table(
        "birthday_email_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("attachment_filename", sa.String(length=255), nullable=True),
        sa.Column("attachment_stored_path", sa.String(length=255), nullable=True),
        sa.Column("attachment_mime_type", sa.String(length=120), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("birthday_email_settings")
    with op.batch_alter_table("employee_document", schema=None) as batch_op:
        batch_op.drop_column("details")
