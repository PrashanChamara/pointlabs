"""add employee profile photo metadata

Revision ID: b7e4f2a9d301
Revises: 0c8d3e7f5a21
Create Date: 2026-09-17
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e4f2a9d301"
down_revision = "0c8d3e7f5a21"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("employee_profile") as batch_op:
        batch_op.add_column(sa.Column("profile_photo_stored_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("profile_photo_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("profile_photo_mime_type", sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table("employee_profile") as batch_op:
        batch_op.drop_column("profile_photo_mime_type")
        batch_op.drop_column("profile_photo_filename")
        batch_op.drop_column("profile_photo_stored_path")
