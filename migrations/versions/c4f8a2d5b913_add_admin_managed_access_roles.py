"""add administrator-managed access roles

Revision ID: c4f8a2d5b913
Revises: b9e5c2a67d42
"""
from datetime import datetime
from alembic import op
import sqlalchemy as sa

revision = "c4f8a2d5b913"
down_revision = "b9e5c2a67d42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("access_role",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("grants_hr_access", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_manage_configuration", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(400)),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_access_role_is_active", "access_role", ["is_active"])
    roles = sa.table("access_role", sa.column("name", sa.String), sa.column("is_active", sa.Boolean), sa.column("grants_hr_access", sa.Boolean), sa.column("can_manage_configuration", sa.Boolean), sa.column("description", sa.String))
    op.bulk_insert(roles, [
        {"name": "Employee", "is_active": True, "grants_hr_access": False, "can_manage_configuration": False, "description": "Standard self-service employee access."},
        {"name": "HR Operations", "is_active": True, "grants_hr_access": True, "can_manage_configuration": True, "description": "HR operations and configuration access."},
    ])
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("access_role_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_user_access_role", "access_role", ["access_role_id"], ["id"])
    op.create_index("ix_user_access_role_id", "user", ["access_role_id"])
    with op.batch_alter_table("approval_workflow_step") as batch:
        batch.add_column(sa.Column("access_role_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_workflow_step_access_role", "access_role", ["access_role_id"], ["id"])
    # Preserve existing accounts: map historic fixed values to their editable role records.
    op.execute("UPDATE user SET access_role_id = (SELECT id FROM access_role WHERE name = 'HR Operations') WHERE role IN ('admin', 'hr')")
    op.execute("UPDATE user SET access_role_id = (SELECT id FROM access_role WHERE name = 'Employee') WHERE access_role_id IS NULL")


def downgrade():
    with op.batch_alter_table("approval_workflow_step") as batch:
        batch.drop_constraint("fk_workflow_step_access_role", type_="foreignkey")
        batch.drop_column("access_role_id")
    op.drop_index("ix_user_access_role_id", table_name="user")
    with op.batch_alter_table("user") as batch:
        batch.drop_constraint("fk_user_access_role", type_="foreignkey")
        batch.drop_column("access_role_id")
    op.drop_index("ix_access_role_is_active", table_name="access_role")
    op.drop_table("access_role")
